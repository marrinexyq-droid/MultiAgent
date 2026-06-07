import json
import random
import time
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on local environment
    OpenAI = None

from ..battle_types import Action, ActionType, Position, AgentState, Role
from ..config import config
from ..grid_rules import distance as grid_distance, neighbors as grid_neighbors, step_toward
from ..llm_actions import parse_llm_action_response


_shared_llm_client: Any | None = None


class AgentBase:
    def __init__(self, state: AgentState):
        self.state = state
        self.client = self._build_client()
        self.turn_count = 0
        self._prev_action = None
        self._prev_target = None
        self._recent_positions: list[Position] = [Position(state.pos.x, state.pos.y)]
        self.last_llm_trace: dict[str, Any] | None = None

    def _build_client(self) -> Any:
        if not config.api_key or OpenAI is None:
            return None
        global _shared_llm_client
        if _shared_llm_client is None:
            _shared_llm_client = OpenAI(api_key=config.api_key, base_url=config.api_base_url, timeout=8)
        return _shared_llm_client

    def choose_action(self, obs: dict, shared_memory: dict) -> Action:
        self.turn_count = obs.get("turn", 0)
        self._sync_state_from_obs(obs)

        if self.client:
            action = self._llm_action(obs, shared_memory)
        else:
            action = self._rule_action(obs)
        return self._finalize_action(action, obs)

    def _sync_state_from_obs(self, obs: dict):
        if not obs.get("self"):
            return

        self_state = obs["self"]
        if "pos" in self_state:
            current_pos = Position(self_state["pos"]["x"], self_state["pos"]["y"])
            if self._recent_positions[-1] != current_pos:
                self._recent_positions.append(current_pos)
                self._recent_positions = self._recent_positions[-4:]
            self.state.pos = current_pos
        if "hp" in self_state:
            self.state.hp = self_state["hp"]
        if "ammo" in self_state:
            self.state.ammo = self_state["ammo"]
        if "move_speed" in self_state:
            self.state.move_speed = self_state["move_speed"]
        if "skill_name" in self_state:
            self.state.skill_name = self_state["skill_name"]
        if "skill_description" in self_state:
            self.state.skill_description = self_state["skill_description"]
        if "skill_cooldown" in self_state:
            self.state.skill_cooldown = self_state["skill_cooldown"]
        if "skill_cooldown_remaining" in self_state:
            self.state.skill_cooldown_remaining = self_state["skill_cooldown_remaining"]
        rally_target = self_state.get("rally_target")
        self.state.rally_target = Position(rally_target["x"], rally_target["y"]) if rally_target else None
        self.state.rally_turns_remaining = self_state.get("rally_turns_remaining", 0)

    def _finalize_action(self, action: Action, obs: dict) -> Action:
        if action.action_type == ActionType.MOVE:
            action = self._avoid_oscillation(action, obs)
        self._prev_action = action.action_type
        self._prev_target = action.target
        return action

    def _avoid_oscillation(self, action: Action, obs: dict) -> Action:
        if action.target is None or len(self._recent_positions) < 2:
            return action

        current_pos = self._recent_positions[-1]
        recent_history = self._recent_positions[:-1][-3:]
        recent_coords = {(pos.x, pos.y) for pos in recent_history}
        if (action.target.x, action.target.y) not in recent_coords:
            return action

        blocked = {
            (ally["pos"]["x"], ally["pos"]["y"])
            for ally in obs.get("visible_allies", [])
        }
        blocked.update(
            (enemy["pos"]["x"], enemy["pos"]["y"])
            for enemy in obs.get("visible_enemies", [])
        )

        nearest_enemy = None
        enemies = obs.get("visible_enemies", [])
        if enemies:
            nearest_enemy = min(
                enemies,
                key=lambda e: grid_distance(current_pos, Position(e["pos"]["x"], e["pos"]["y"]), obs.get("grid_type", "square")),
            )

        alternatives: list[Position] = []
        width = obs.get("width", obs.get("grid_size", 8))
        height = obs.get("height", obs.get("grid_size", 8))
        grid_type = obs.get("grid_type", "square")
        for candidate in grid_neighbors(current_pos, grid_type):
            nx, ny = candidate.x, candidate.y
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in recent_coords:
                continue
            if (nx, ny) in blocked:
                continue
            alternatives.append(candidate)

        if not alternatives:
            for candidate in grid_neighbors(current_pos, grid_type):
                nx, ny = candidate.x, candidate.y
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if (nx, ny) in blocked or (nx, ny) == (action.target.x, action.target.y):
                    continue
                alternatives.append(candidate)

        if not alternatives:
            return Action(self.state.agent_id, ActionType.HOLD)

        if nearest_enemy:
            best = min(
                alternatives,
                key=lambda pos: grid_distance(pos, Position(nearest_enemy["pos"]["x"], nearest_enemy["pos"]["y"]), grid_type),
            )
            return Action(self.state.agent_id, ActionType.MOVE, target=best)

        return Action(self.state.agent_id, ActionType.MOVE, target=alternatives[0])

    def _build_prompt(self, obs: dict, shared_memory: dict) -> str:
        self_info = obs.get("self", {})
        enemies = obs.get("visible_enemies", [])
        allies = obs.get("visible_allies", [])
        
        # Include shared memory if available
        mem_info = ""
        if shared_memory and shared_memory.get("summary"):
            summary = shared_memory["summary"]
            mem_info += (
                f"\nTeam memory summary: primary_threat={summary.get('primary_threat')}, "
                f"active_tasks={summary.get('active_tasks')}, focus={summary.get('recommended_focus')}, "
                f"health={summary.get('memory_health')}\n"
            )
        if shared_memory and shared_memory.get("beliefs"):
            beliefs = []
            for tid, belief in list(shared_memory["beliefs"].items())[:3]:
                pos = belief.get("last_known_position")
                if pos:
                    beliefs.append(
                        {
                            "target": tid,
                            "pos": pos,
                            "confidence": round(float(belief.get("confidence_score", 0.0)), 2),
                            "trend": belief.get("trend"),
                        }
                    )
            if beliefs:
                mem_info += f"Fused threat beliefs: {json.dumps(beliefs)}\n"
        if shared_memory and shared_memory.get("enemy_tracks"):
            tracks = []
            for tid, reports in shared_memory["enemy_tracks"].items():
                if reports:
                    r = reports[0]
                    if r.get("pos"):
                        tracks.append({"target": tid, "pos": r["pos"]})
            if tracks:
                mem_info = f"\nKnown enemy positions from team: {json.dumps(tracks[:3])}\n"

        role_priority = {
            Role.COORDINATOR: "coordinate team movement, assign tasks, and maintain initiative",
            Role.SCOUT: "observe the field, collect intelligence, and reveal opponent positions",
            Role.ATTACKER: "advance on pressure points, engage nearby opponents, and capitalize on openings",
            Role.DEFENDER: "protect control zones, contain threats, and stabilize the line",
            Role.SUPPORT: "restore critical teammates and sustain the formation",
            Role.JAMMER: "disrupt enemy sensing and reduce coordination quality",
            Role.CONTROLLER: "lock important lanes and shape movement space",
            Role.ASSAULTER: "cut into vulnerable backline targets and create breakthroughs",
        }

        role_specific_instruction = {
            Role.COORDINATOR: "Act like a field coordinator: synthesize information and guide the next team action.",
            Role.SCOUT: "Act like a reconnaissance unit: scout first, then share fresh information with teammates.",
            Role.ATTACKER: "Act like an execution unit: move toward the control zone and engage opponents when adjacent.",
            Role.DEFENDER: "Act like a holding unit: patrol the control zone, watch for movement, and respond quickly.",
            Role.SUPPORT: "Act like a sustain unit: keep key allies alive and avoid direct exposure.",
            Role.JAMMER: "Act like an electronic warfare unit: create confusion and attack the enemy information chain.",
            Role.CONTROLLER: "Act like an area denial unit: shape where the enemy can safely move.",
            Role.ASSAULTER: "Act like a breach unit: pick moments to cut into high-value backline targets.",
        }

        prompt = (
            f"You are a {self.state.role.value} unit (ID: {self.state.agent_id}) in a {obs.get('width', obs.get('grid_size', 8))}x{obs.get('height', obs.get('grid_size', 8))} confrontation simulation.\n\n"
            f"Your status: position=({self_info.get('pos',{}).get('x',0)},{self_info.get('pos',{}).get('y',0)}), "
            f"Health={self_info.get('hp',0)}, Resources={self_info.get('ammo',0)}, "
            f"MoveSpeed={self_info.get('move_speed',1)}, Skill={self_info.get('skill_name','none')}, "
            f"Cooldown={self_info.get('skill_cooldown_remaining',0)}\n"
            f"{mem_info}"
            f"Visible opponents nearby: {json.dumps(enemies) if enemies else 'None'}\n"
            f"Visible teammates nearby: {json.dumps(allies) if allies else 'None'}\n"
            f"Current turn: {obs.get('turn', 0)}\n\n"
            f"IMPORTANT: You must take a practical action every turn. Communication is secondary.\n"
            f"Do NOT bounce between the same two positions repeatedly.\n\n"
            f"Available actions (choose one):\n"
            f"- move: move to an adjacent position or two cells in a straight line if your move speed allows.\n"
            f"- hold: remain in the current position.\n"
            f"- attack: engage an adjacent opponent unit (distance=1).\n"
            f"- scout: observe the surroundings when no target is confirmed.\n"
            f"- skill: use your role skill when cooldown is 0.\n"
            f"- communicate: share fresh information with the team.\n\n"
            f"Your role: {role_priority.get(self.state.role, 'survive and fight')}\n"
            f"{role_specific_instruction.get(self.state.role, '')}\n\n"
            f"If opponents are visible, ATTACK or MOVE toward them.\n"
            f"If no opponents are visible, MOVE toward the nearest priority zone or control zone and preserve role discipline.\n\n"
            f'Respond with ONLY a JSON object:\n'
            f'{{"action_type": "move|hold|attack|scout|skill|communicate", "target": {{"x": 1, "y": 1}}, "target_id": "enemy_id", "skill_id": "skill_name", "skill_target": {{"x": 1, "y": 1}}, "message": "text"}}\n\n'
            f'Example: {{"action_type": "move", "target": {{"x": 3, "y": 2}}}}'
        )
        return prompt

    def _llm_action(self, obs: dict, shared_memory: dict) -> Action:
        started_at = time.perf_counter()
        trace = {
            "agent_id": self.state.agent_id,
            "ok": False,
            "fallback_reason": None,
            "latency_ms": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "raw_completion": None,
            "llm_error": None,
            "json_mode_requested": True,
        }
        try:
            prompt = self._build_prompt(obs, shared_memory)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a battle simulation action planner. "
                        "Return exactly one valid minified JSON object and no prose, markdown, or code fence."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            request_payload = {
                "model": config.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 512,
            }
            try:
                response = self.client.chat.completions.create(
                    **request_payload,
                    response_format={"type": "json_object"},
                )
            except Exception as json_mode_error:
                error_text = str(json_mode_error)
                if not any(keyword in error_text.lower() for keyword in ("response_format", "json_object", "json mode")):
                    raise
                trace["json_mode_requested"] = False
                trace["llm_error"] = error_text[:500]
                response = self.client.chat.completions.create(**request_payload)
            content = response.choices[0].message.content.strip()
            trace["raw_completion"] = content[:1200]
            usage = getattr(response, "usage", None)
            if usage is not None:
                trace["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
                trace["completion_tokens"] = getattr(usage, "completion_tokens", None)
                trace["total_tokens"] = getattr(usage, "total_tokens", None)
            valid_targets = {
                item["agent_id"]
                for item in obs.get("visible_enemies", []) + obs.get("visible_allies", [])
                if item.get("agent_id")
            }
            parsed = parse_llm_action_response(
                content,
                agent_id=self.state.agent_id,
                width=obs.get("width", obs.get("grid_size", 8)),
                height=obs.get("height", obs.get("grid_size", 8)),
                valid_target_ids=valid_targets,
            )
            trace["ok"] = parsed.ok
            trace["fallback_reason"] = parsed.fallback_reason
            return parsed.action if parsed.ok else self._rule_action(obs)
        except Exception as exc:
            trace["fallback_reason"] = "llm_call_failed"
            trace["llm_error"] = str(exc)[:500]
            return self._rule_action(obs)
        finally:
            trace["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            self.last_llm_trace = trace

    def _rule_action(self, obs: dict) -> Action:
        enemies = obs.get("visible_enemies", [])
        self_pos = self.state.pos

        if self.state.rally_target:
            return self._move_toward(Position(self.state.rally_target.x, self.state.rally_target.y), obs)

        if enemies and self.state.ammo > 0:
            nearest = min(enemies, key=lambda e: grid_distance(self_pos, Position(e["pos"]["x"], e["pos"]["y"]), obs.get("grid_type", "square")))
            dist = grid_distance(self_pos, Position(nearest["pos"]["x"], nearest["pos"]["y"]), obs.get("grid_type", "square"))
            if dist <= self.state.attack_range:
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])

        if enemies:
            nearest = min(enemies, key=lambda e: grid_distance(self_pos, Position(e["pos"]["x"], e["pos"]["y"]), obs.get("grid_type", "square")))
            target = step_toward(
                self_pos,
                Position(nearest["pos"]["x"], nearest["pos"]["y"]),
                obs.get("width", obs.get("grid_size", 8)),
                obs.get("height", obs.get("grid_size", 8)),
                obs.get("grid_type", "square"),
                steps=max(1, self.state.move_speed),
            )
            if target != self_pos:
                return Action(self.state.agent_id, ActionType.MOVE, target=target)

        if self.state.role == Role.SCOUT:
            return Action(self.state.agent_id, ActionType.SCOUT)

        return self._advance_to_control_zone(obs)

    def _advance_to_control_zone(self, obs: dict) -> Action:
        self_pos = self.state.pos
        scenario = obs.get("scenario", {})
        if self.state.team.value == "red":
            zones = scenario.get("blue_spawn_zones") or scenario.get("control_zones") or []
        else:
            zones = scenario.get("red_spawn_zones") or scenario.get("control_zones") or []
        if zones:
            zone = zones[0]
            target = Position(zone["x"] + max(0, zone["width"] // 2), zone["y"] + max(0, zone["height"] // 2))
        else:
            target = Position(obs.get("width", obs.get("grid_size", 8)) // 2, obs.get("height", obs.get("grid_size", 8)) // 2)
        return self._move_toward(target, obs)

    def _move_toward(self, target: Position, obs: dict) -> Action:
        self_pos = self.state.pos
        step = max(1, self.state.move_speed)
        if obs.get("grid_type") == "hex":
            next_pos = step_toward(
                self_pos,
                target,
                obs.get("width", obs.get("grid_size", 8)),
                obs.get("height", obs.get("grid_size", 8)),
                "hex",
                steps=step,
            )
            if next_pos != self_pos:
                return Action(self.state.agent_id, ActionType.MOVE, target=next_pos)
            return Action(self.state.agent_id, ActionType.HOLD)
        dx = target.x - self_pos.x
        dy = target.y - self_pos.y
        if abs(dx) >= abs(dy) and dx != 0:
            move = min(step, abs(dx))
            return Action(
                self.state.agent_id,
                ActionType.MOVE,
                target=Position(self_pos.x + move * (1 if dx > 0 else -1), self_pos.y),
            )
        if dy != 0:
            move = min(step, abs(dy))
            return Action(
                self.state.agent_id,
                ActionType.MOVE,
                target=Position(self_pos.x, self_pos.y + move * (1 if dy > 0 else -1)),
            )
        return Action(self.state.agent_id, ActionType.HOLD)
