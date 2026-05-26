import uuid

from .battle_types import Message, Position, Role, Team
from .stats import BattleStats


class SharedMemoryPool:
    def __init__(self, team: Team, battle_stats: BattleStats | None = None):
        self.team = team
        self.battle_stats = battle_stats
        self.observations: list[dict] = []
        self.beliefs: dict[str, dict] = {}
        self.risk_zones: dict[str, dict] = {}
        self.tasks: dict[str, dict] = {}
        self.summaries: list[dict] = []
        self.latest_summary: dict = {}
        self.processed_msg_ids: set[str] = set()
        self.decay_rate = 0.85
        self.min_store_confidence = 0.1
        self.max_observations = 80
        self.current_turn = 0

        # Backward-compatible legacy views used by the existing runner, UI, and agents.
        self.enemy_tracks: dict[str, list[dict]] = {}
        self.team_tasks: dict[str, dict] = {}

    def _source_weight(self, sender_role: Role, obs_type: str) -> float:
        weights = {
            Role.COORDINATOR: {
                "enemy_spot": 0.95,
                "enemy_lost": 0.9,
                "risk_zone": 1.0,
                "task_assign": 1.0,
            },
            Role.SCOUT: {
                "enemy_spot": 1.15,
                "enemy_lost": 1.0,
                "risk_zone": 1.05,
                "task_assign": 0.9,
            },
            Role.ATTACKER: {
                "enemy_spot": 1.05,
                "enemy_lost": 0.9,
                "risk_zone": 0.95,
                "task_assign": 0.9,
            },
            Role.DEFENDER: {
                "enemy_spot": 1.0,
                "enemy_lost": 0.95,
                "risk_zone": 1.1,
                "task_assign": 0.9,
            },
            Role.SUPPORT: {
                "enemy_spot": 0.85,
                "enemy_lost": 0.85,
                "risk_zone": 0.9,
                "task_assign": 0.95,
            },
            Role.JAMMER: {
                "enemy_spot": 1.0,
                "enemy_lost": 0.95,
                "risk_zone": 1.05,
                "task_assign": 0.9,
            },
            Role.CONTROLLER: {
                "enemy_spot": 0.95,
                "enemy_lost": 0.9,
                "risk_zone": 1.15,
                "task_assign": 0.9,
            },
            Role.ASSAULTER: {
                "enemy_spot": 0.95,
                "enemy_lost": 0.9,
                "risk_zone": 0.9,
                "task_assign": 0.85,
            },
        }
        return weights.get(sender_role, {}).get(obs_type, 1.0)

    def _normalize_confidence(self, msg: Message, obs_type: str) -> float:
        weighted = float(msg.confidence) * self._source_weight(msg.sender_role, obs_type)
        return max(self.min_store_confidence, min(1.0, weighted))

    def _record_observation(self, msg: Message) -> dict:
        content = msg.content
        obs_type = content.get("type", "unknown")
        pos = content.get("pos")
        record = {
            "obs_id": msg.msg_id,
            "source_agent_id": msg.sender_id,
            "source_role": msg.sender_role.value,
            "timestamp": msg.timestamp,
            "obs_type": obs_type,
            "target_id": content.get("target_id"),
            "position": pos,
            "pos": pos,
            "hp_estimate": content.get("hp"),
            "hp": content.get("hp"),
            "confidence": self._normalize_confidence(msg, obs_type),
            "raw_payload": content,
        }
        self.observations.append(record)
        self.observations = self.observations[-self.max_observations :]
        return record

    def _compute_trend(self, previous_pos: dict | None, current_pos: dict | None) -> str:
        if not previous_pos or not current_pos:
            return "uncertain"
        if previous_pos == current_pos:
            return "static"
        if self.team == Team.RED:
            return "approaching" if current_pos.get("x", 0) < previous_pos.get("x", 0) else "retreating"
        return "approaching" if current_pos.get("x", 0) > previous_pos.get("x", 0) else "retreating"

    def _threat_level(self, hp_estimate: int | None, confidence: float, source_count: int) -> str:
        if confidence >= 0.7 and source_count >= 2:
            return "high"
        if (hp_estimate or 0) >= 90 or confidence >= 0.5:
            return "medium"
        return "low"

    def _update_enemy_belief(self, obs: dict):
        target_id = obs.get("target_id")
        if not target_id:
            return

        previous = self.beliefs.get(target_id, {})
        sources = list(previous.get("sources", []))
        if obs["source_agent_id"] not in sources:
            sources.append(obs["source_agent_id"])

        previous_pos = previous.get("last_known_position")
        current_pos = obs.get("position")
        conflict_penalty = 0.0
        if previous_pos and current_pos and previous_pos != current_pos:
            conflict_penalty = 0.08

        confidence = max(self.min_store_confidence, min(1.0, obs["confidence"] + (0.08 if len(sources) >= 2 else 0.0) - conflict_penalty))
        belief = {
            "target_id": target_id,
            "last_known_position": current_pos or previous_pos,
            "last_seen_turn": obs["timestamp"],
            "hp_estimate": obs.get("hp_estimate") if obs.get("hp_estimate") is not None else previous.get("hp_estimate"),
            "confidence_score": confidence,
            "source_count": len(sources),
            "verified": len(sources) >= 2 and conflict_penalty == 0.0 and confidence >= 0.55,
            "threat_level": self._threat_level(obs.get("hp_estimate"), confidence, len(sources)),
            "trend": self._compute_trend(previous_pos, current_pos),
            "last_reporter": obs["source_agent_id"],
            "last_reporter_role": obs["source_role"],
            "evidence_ids": (previous.get("evidence_ids", []) + [obs["obs_id"]])[-5:],
            "sources": sources,
            "timestamp": obs["timestamp"],
        }
        self.beliefs[target_id] = belief

    def _write_risk_zone(self, msg: Message, obs: dict):
        x = msg.content.get("x", 0)
        y = msg.content.get("y", 0)
        zone_key = f"{x},{y}"
        previous = self.risk_zones.get(zone_key)
        confidence = obs["confidence"]
        if previous:
            confidence = min(1.0, max(confidence, previous["confidence"]) + 0.05)
        self.risk_zones[zone_key] = {
            "zone_key": zone_key,
            "reporter": msg.sender_id,
            "source_role": msg.sender_role.value,
            "timestamp": msg.timestamp,
            "confidence": confidence,
            "reason": msg.content.get("reason", ""),
        }

    def _write_task(self, msg: Message, obs: dict):
        content = msg.content
        task_id = content.get("task_id", str(uuid.uuid4())[:8])
        existing = self.tasks.get(task_id, {})
        status = content.get("status", existing.get("status", "pending"))
        task = {
            "task_id": task_id,
            "assigner": msg.sender_id,
            "assignee": content.get("assignee", existing.get("assignee")),
            "task_type": content.get("task_type", existing.get("task_type", "maneuver")),
            "task": content.get("task", existing.get("task", "")),
            "target_id": content.get("target_id", existing.get("target_id")),
            "target_position": content.get("target_pos", existing.get("target_position")),
            "priority": content.get("priority", existing.get("priority", "medium")),
            "status": status,
            "created_turn": existing.get("created_turn", msg.timestamp),
            "updated_turn": msg.timestamp,
            "deadline_turn": content.get("deadline_turn", existing.get("deadline_turn", msg.timestamp + 6)),
            "result": content.get("result", existing.get("result")),
            "failure_reason": content.get("failure_reason", existing.get("failure_reason")),
            "confidence": obs["confidence"] if status not in {"completed", "cancelled"} else min(1.0, obs["confidence"] + 0.05),
            "source_role": msg.sender_role.value,
        }
        self.tasks[task_id] = task
        if self.battle_stats and msg.content.get("type") == "task_assign":
            self.battle_stats.record_task_assignment(
                msg.sender_id,
                task_id=task_id,
                assignee_id=task.get("assignee"),
                target_id=task.get("target_id"),
                target_pos=task.get("target_position"),
                turn=msg.timestamp,
            )

    def _prune_tasks(self):
        for task_id in list(self.tasks.keys()):
            task = self.tasks[task_id]
            if task["status"] not in {"completed", "cancelled", "expired"} and task.get("deadline_turn", 0) < self.current_turn:
                task["status"] = "expired"
                task["failure_reason"] = task.get("failure_reason") or "deadline_passed"
            if task["confidence"] < self.min_store_confidence:
                del self.tasks[task_id]

    def _memory_health(self, top_confidence: float, active_tasks: int, observation_count: int) -> str:
        if observation_count >= 6 and top_confidence >= 0.6:
            return "fresh"
        if active_tasks > 0 or top_confidence >= 0.35:
            return "degrading"
        return "stale"

    def update_summary(self):
        belief_list = sorted(self.beliefs.values(), key=lambda item: item["confidence_score"], reverse=True)
        active_tasks = [task for task in self.tasks.values() if task["status"] in {"pending", "in_progress", "blocked"}]
        risk_list = sorted(self.risk_zones.values(), key=lambda item: item["confidence"], reverse=True)
        primary = belief_list[0] if belief_list else None

        if active_tasks:
            recommended_focus = active_tasks[0].get("task") or active_tasks[0].get("task_type") or "推进任务执行"
        elif primary:
            recommended_focus = f"跟踪 {primary['target_id']}"
        else:
            recommended_focus = "维持侦察并收集新情报"

        summary = {
            "turn": self.current_turn,
            "team": self.team.value,
            "primary_threat": primary["target_id"] if primary else None,
            "secondary_threats": [belief["target_id"] for belief in belief_list[1:3]],
            "high_risk_zones": [risk["zone_key"] for risk in risk_list[:3] if risk["confidence"] >= 0.35],
            "active_tasks": len(active_tasks),
            "active_task_ids": [task["task_id"] for task in active_tasks[:4]],
            "unverified_targets": len([belief for belief in belief_list if not belief["verified"]]),
            "recommended_focus": recommended_focus,
            "memory_health": self._memory_health(primary["confidence_score"] if primary else 0.0, len(active_tasks), len(self.observations)),
            "belief_count": len(belief_list),
            "observation_count": len(self.observations),
            "risk_zone_count": len(risk_list),
        }
        self.latest_summary = summary
        self.summaries.append(summary)
        self.summaries = self.summaries[-20:]

    def _sync_legacy_views(self):
        filtered_tracks: dict[str, list[dict]] = {}
        for target_id in self.beliefs.keys():
            related = [
                obs for obs in self.observations
                if obs.get("target_id") == target_id and obs.get("obs_type") == "enemy_spot"
            ]
            related.sort(key=lambda item: item["timestamp"], reverse=True)
            reports = [
                {
                    "reporter": obs["source_agent_id"],
                    "pos": obs.get("position"),
                    "hp": obs.get("hp_estimate"),
                    "timestamp": obs["timestamp"],
                    "confidence": obs["confidence"],
                }
                for obs in related[:5]
            ]
            if reports:
                filtered_tracks[target_id] = reports
            else:
                belief = self.beliefs[target_id]
                filtered_tracks[target_id] = [
                    {
                        "reporter": belief.get("last_reporter"),
                        "pos": belief.get("last_known_position"),
                        "hp": belief.get("hp_estimate"),
                        "timestamp": belief.get("timestamp"),
                        "confidence": belief.get("confidence_score", 0.0),
                    }
                ]
        self.enemy_tracks = filtered_tracks

        self.team_tasks = {
            task_id: {
                "assigner": task["assigner"],
                "assignee": task.get("assignee"),
                "task": task.get("task"),
                "target_id": task.get("target_id"),
                "target_pos": task.get("target_position"),
                "timestamp": task.get("updated_turn"),
                "confidence": task.get("confidence", 0.0),
                "status": task.get("status"),
                "priority": task.get("priority"),
            }
            for task_id, task in self.tasks.items()
            if task.get("status") not in {"completed", "cancelled", "expired"}
        }

    def write(self, msg: Message) -> bool:
        if msg.msg_id in self.processed_msg_ids:
            return False
        self.processed_msg_ids.add(msg.msg_id)
        self.current_turn = max(self.current_turn, msg.timestamp)

        obs = self._record_observation(msg)
        msg_type = msg.content.get("type", "")
        if self.battle_stats and msg.sender_id in self.battle_stats.agent_records:
            self.battle_stats.record_report(
                msg.sender_id,
                obs["confidence"],
                report_id=msg.msg_id,
                report_type=msg_type,
                target_id=obs.get("target_id"),
                target_pos=obs.get("position"),
                turn=msg.timestamp,
            )

        if msg_type == "enemy_spot":
            self._update_enemy_belief(obs)
        elif msg_type == "enemy_lost":
            target_id = msg.content.get("target_id")
            if target_id in self.beliefs:
                self.beliefs[target_id]["confidence_score"] *= 0.8
                self.beliefs[target_id]["trend"] = "uncertain"
                self.beliefs[target_id]["timestamp"] = msg.timestamp
        elif msg_type == "risk_zone":
            self._write_risk_zone(msg, obs)
        elif msg_type in {"task_assign", "task_update"}:
            self._write_task(msg, obs)

        self._prune_tasks()
        self._sync_legacy_views()
        self.update_summary()
        return True

    def update_task_progress(self, agents: dict[str, object], turn: int):
        updated = False
        for task in self.tasks.values():
            if task["status"] in {"completed", "cancelled", "expired"}:
                continue
            assignee = task.get("assignee")
            target_pos = task.get("target_position")
            target_id = task.get("target_id")
            agent = agents.get(assignee) if assignee else None
            if agent is None or not getattr(agent, "alive", True):
                if task["status"] == "pending":
                    task["status"] = "blocked"
                    task["updated_turn"] = turn
                    updated = True
                continue

            if task["status"] == "pending":
                task["status"] = "in_progress"
                task["updated_turn"] = turn
                updated = True
                if self.battle_stats:
                    self.battle_stats.record_task_in_progress(task["task_id"])

            reached_position = False
            if target_pos:
                reached_position = agent.pos.x == target_pos["x"] and agent.pos.y == target_pos["y"]
            reached_target = False
            if target_id and target_id in self.beliefs:
                belief = self.beliefs[target_id]
                belief_pos = belief.get("last_known_position")
                if belief_pos:
                    reached_target = agent.pos.distance_to(Position(belief_pos["x"], belief_pos["y"])) <= 1
            if reached_position or reached_target:
                task["status"] = "completed"
                task["updated_turn"] = turn
                task["result"] = "objective_reached"
                task["confidence"] = min(1.0, task["confidence"] + 0.1)
                updated = True
                if self.battle_stats:
                    self.battle_stats.record_task_completion(assignee, task_id=task["task_id"])

        if updated:
            self._sync_legacy_views()
            self.update_summary()

    def _infer_role(self, agent_id: str) -> Role | None:
        agent_id = agent_id.lower()
        if any(token in agent_id for token in ("commander", "coordinator")):
            return Role.COORDINATOR
        if any(token in agent_id for token in ("scout", "probe")):
            return Role.SCOUT
        if any(token in agent_id for token in ("attacker", "striker")):
            return Role.ATTACKER
        if any(token in agent_id for token in ("defender", "guard")):
            return Role.DEFENDER
        if "support" in agent_id:
            return Role.SUPPORT
        if "jammer" in agent_id:
            return Role.JAMMER
        if any(token in agent_id for token in ("controller", "suppressor")):
            return Role.CONTROLLER
        if any(token in agent_id for token in ("assaulter", "infiltrator")):
            return Role.ASSAULTER
        return None

    def read_observations(self, limit: int = 6, min_confidence: float = 0.3) -> list[dict]:
        items = [obs for obs in self.observations if obs["confidence"] >= min_confidence]
        items.sort(key=lambda item: item["timestamp"], reverse=True)
        return items[:limit]

    def read_beliefs(self, min_confidence: float = 0.3) -> dict[str, dict]:
        beliefs = {
            target_id: {
                key: value
                for key, value in belief.items()
                if key not in {"sources", "evidence_ids"}
            }
            for target_id, belief in self.beliefs.items()
            if belief["confidence_score"] >= min_confidence
        }
        return dict(sorted(beliefs.items(), key=lambda item: item[1]["confidence_score"], reverse=True))

    def read_tasks(self, status_filter: set[str] | None = None, min_confidence: float = 0.3) -> dict[str, dict]:
        status_filter = status_filter or {"pending", "in_progress", "blocked", "completed", "expired", "cancelled"}
        tasks = {
            task_id: task
            for task_id, task in self.tasks.items()
            if task["status"] in status_filter and task["confidence"] >= min_confidence
        }
        return dict(sorted(tasks.items(), key=lambda item: item[1]["updated_turn"], reverse=True))

    def read_summary(self) -> dict:
        return self.latest_summary.copy() if self.latest_summary else {
            "turn": self.current_turn,
            "team": self.team.value,
            "primary_threat": None,
            "secondary_threats": [],
            "high_risk_zones": [],
            "active_tasks": 0,
            "active_task_ids": [],
            "unverified_targets": 0,
            "recommended_focus": "维持侦察并收集新情报",
            "memory_health": "stale",
            "belief_count": 0,
            "observation_count": 0,
            "risk_zone_count": 0,
        }

    def read_for_agent(self, agent_id: str, role: Role | None = None, min_confidence: float = 0.3) -> dict:
        role = role or self._infer_role(agent_id)
        summary = self.read_summary()
        beliefs = self.read_beliefs(min_confidence)
        observations = self.read_observations(limit=8 if role == Role.COORDINATOR else 5, min_confidence=min_confidence)
        tasks = self.read_tasks(min_confidence=min_confidence)

        if role == Role.SCOUT:
            beliefs = dict(sorted(beliefs.items(), key=lambda item: (item[1]["verified"], -item[1]["confidence_score"]))[:4])
        elif role == Role.ATTACKER:
            relevant_tasks = {
                task_id: task for task_id, task in tasks.items()
                if task.get("assignee") in {None, agent_id} or task.get("target_id")
            }
            tasks = dict(list(relevant_tasks.items())[:4])
            beliefs = dict(list(beliefs.items())[:3])
        elif role == Role.DEFENDER:
            risk_keys = set(summary.get("high_risk_zones", []))
            if risk_keys:
                filtered_risks = {key: value for key, value in self.risk_zones.items() if key in risk_keys and value["confidence"] >= min_confidence}
            else:
                filtered_risks = {key: value for key, value in self.risk_zones.items() if value["confidence"] >= min_confidence}
        elif role == Role.SUPPORT:
            tasks = {
                task_id: task for task_id, task in tasks.items()
                if task.get("assignee") in {None, agent_id} or task.get("priority") == "high"
            }
            filtered_risks = {key: value for key, value in self.risk_zones.items() if value["confidence"] >= min_confidence}
        elif role == Role.JAMMER:
            beliefs = dict(list(beliefs.items())[:4])
            filtered_risks = {key: value for key, value in self.risk_zones.items() if value["confidence"] >= min_confidence}
        elif role == Role.CONTROLLER:
            risk_keys = set(summary.get("high_risk_zones", []))
            filtered_risks = {
                key: value for key, value in self.risk_zones.items()
                if value["confidence"] >= min_confidence and (not risk_keys or key in risk_keys)
            }
        elif role == Role.ASSAULTER:
            beliefs = dict(list(beliefs.items())[:3])
            tasks = {
                task_id: task for task_id, task in tasks.items()
                if task.get("target_id") or task.get("priority") == "high"
            }
            filtered_risks = {key: value for key, value in self.risk_zones.items() if value["confidence"] >= min_confidence}
        else:
            filtered_risks = {key: value for key, value in self.risk_zones.items() if value["confidence"] >= min_confidence}

        if role not in {Role.DEFENDER, Role.CONTROLLER}:
            filtered_risks = {key: value for key, value in self.risk_zones.items() if value["confidence"] >= min_confidence}

        return {
            "enemy_tracks": {
                target_id: reports
                for target_id, reports in self.enemy_tracks.items()
                if reports and reports[0]["confidence"] >= min_confidence
            },
            "risk_zones": filtered_risks,
            "team_tasks": {
                task_id: task for task_id, task in self.team_tasks.items() if task["confidence"] >= min_confidence
            },
            "observations": observations,
            "beliefs": beliefs,
            "tasks": tasks,
            "summary": summary,
        }

    def read(self, agent_id: str, min_confidence: float = 0.3) -> dict:
        return self.read_for_agent(agent_id, min_confidence=min_confidence)

    def decay(self):
        self.current_turn += 1

        for obs in self.observations:
            obs["confidence"] *= self.decay_rate
        self.observations = [obs for obs in self.observations if obs["confidence"] >= self.min_store_confidence]

        for target_id in list(self.beliefs.keys()):
            self.beliefs[target_id]["confidence_score"] *= self.decay_rate
            if self.beliefs[target_id]["confidence_score"] < self.min_store_confidence:
                del self.beliefs[target_id]

        for zone_key in list(self.risk_zones.keys()):
            self.risk_zones[zone_key]["confidence"] *= self.decay_rate
            if self.risk_zones[zone_key]["confidence"] < self.min_store_confidence:
                del self.risk_zones[zone_key]

        for task_id in list(self.tasks.keys()):
            task = self.tasks[task_id]
            if task["status"] not in {"completed", "cancelled", "expired"}:
                task["confidence"] *= self.decay_rate
                if task["status"] == "pending":
                    task["status"] = "in_progress"
            if task["confidence"] < self.min_store_confidence:
                del self.tasks[task_id]

        self._prune_tasks()
        self._sync_legacy_views()
        self.update_summary()

    def create_message(self, sender_id: str, sender_role: Role, content: dict, timestamp: int) -> Message:
        return Message(
            msg_id=str(uuid.uuid4())[:8],
            sender_id=sender_id,
            sender_role=sender_role,
            content=content,
            timestamp=timestamp,
            confidence=1.0,
        )
