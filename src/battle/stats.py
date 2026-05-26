from dataclasses import dataclass, field

from .battle_types import Role, Team


@dataclass
class AgentCombatRecord:
    agent_id: str
    team: Team
    role: Role
    damage_dealt: int = 0
    damage_taken: int = 0
    kills: int = 0
    assists: int = 0
    enemy_spotted: int = 0
    first_spots: int = 0
    high_confidence_reports: int = 0
    tasks_assigned: int = 0
    tasks_completed: int = 0
    control_turns: int = 0
    skill_uses: int = 0
    communication_count: int = 0
    turns_alive: int = 0
    blocked_moves: int = 0
    coordination_contributions: int = 0
    used_reports: int = 0
    decisive_reports: int = 0
    used_task_assignments: int = 0
    holds_under_pressure: int = 0
    targeted_strikes: int = 0
    commendations: list[str] = field(default_factory=list)


class BattleStats:
    def __init__(self):
        self.agent_records: dict[str, AgentCombatRecord] = {}
        self.damage_by_target: dict[str, dict[str, int]] = {}
        self.intel_records: dict[str, dict] = {}
        self.task_records: dict[str, dict] = {}
        self.team_first_spot_turn: dict[Team, int | None] = {Team.RED: None, Team.BLUE: None}
        self.team_control_turns: dict[Team, int] = {Team.RED: 0, Team.BLUE: 0}
        self.team_reports: dict[Team, int] = {Team.RED: 0, Team.BLUE: 0}
        self.team_high_confidence_reports: dict[Team, int] = {Team.RED: 0, Team.BLUE: 0}
        self.team_task_assignments: dict[Team, int] = {Team.RED: 0, Team.BLUE: 0}
        self.team_task_completions: dict[Team, int] = {Team.RED: 0, Team.BLUE: 0}
        self.team_skill_uses: dict[Team, int] = {Team.RED: 0, Team.BLUE: 0}
        self.control_history: list[dict[str, str]] = []
        self.last_control_signature: tuple | None = None
        self.consecutive_control_stable_turns = 0
        self.consecutive_no_damage_turns = 0
        self.consecutive_no_elimination_turns = 0
        self.consecutive_no_progress_turns = 0
        self.last_turn_had_damage = False
        self.last_turn_had_elimination = False
        self.last_turn_had_control_change = False
        self.last_turn_had_task_progress = False

    def register_agent(self, agent) -> None:
        self.agent_records[agent.agent_id] = AgentCombatRecord(
            agent_id=agent.agent_id,
            team=agent.team,
            role=agent.role,
        )

    def _match_target(self, intel: dict, target_id: str | None, target_pos: dict | None) -> bool:
        if target_id and intel.get("target_id") == target_id:
            return True
        intel_pos = intel.get("target_pos")
        if target_pos and intel_pos:
            return intel_pos.get("x") == target_pos.get("x") and intel_pos.get("y") == target_pos.get("y")
        return False

    def _mark_reports(self, team: Team, target_id: str | None = None, target_pos: dict | None = None, decisive: bool = False, turn: int | None = None) -> int:
        matched = 0
        ranked = sorted(
            self.intel_records.values(),
            key=lambda item: (item.get("used", False), -item.get("turn", 0)),
        )
        for intel in ranked:
            if intel.get("team") != team:
                continue
            if turn is not None and abs(turn - intel.get("turn", turn)) > 3:
                continue
            if not self._match_target(intel, target_id, target_pos):
                continue
            sender_id = intel.get("sender_id")
            record = self.agent_records.get(sender_id)
            if not record:
                continue
            if not intel.get("used"):
                intel["used"] = True
                record.used_reports += 1
                matched += 1
            if decisive and not intel.get("decisive"):
                intel["decisive"] = True
                record.decisive_reports += 1
            if matched >= 2:
                break
        return matched

    def record_damage(self, attacker_id: str, target_id: str, damage: int, turn: int | None = None) -> None:
        if attacker_id in self.agent_records:
            self.agent_records[attacker_id].damage_dealt += damage
        if target_id in self.agent_records:
            self.agent_records[target_id].damage_taken += damage
        self.damage_by_target.setdefault(target_id, {})
        self.damage_by_target[target_id][attacker_id] = self.damage_by_target[target_id].get(attacker_id, 0) + damage
        attacker = self.agent_records.get(attacker_id)
        if attacker:
            used_matches = self._mark_reports(attacker.team, target_id=target_id, decisive=False, turn=turn)
            active_targets = {
                task.get("target_id")
                for task in self.task_records.values()
                if task.get("team") == attacker.team and task.get("status") in {"pending", "in_progress", "completed"}
            }
            if target_id in active_targets or used_matches > 0:
                attacker.targeted_strikes += 1
        self.last_turn_had_damage = True
        self.last_turn_had_task_progress = True

    def record_kill(self, attacker_id: str, target_id: str) -> None:
        if attacker_id in self.agent_records:
            self.agent_records[attacker_id].kills += 1
            attacker = self.agent_records[attacker_id]
            self._mark_reports(attacker.team, target_id=target_id, decisive=True)
        for contributor_id, amount in self.damage_by_target.get(target_id, {}).items():
            if contributor_id != attacker_id and amount > 0 and contributor_id in self.agent_records:
                self.agent_records[contributor_id].assists += 1
        self.last_turn_had_elimination = True
        self.last_turn_had_task_progress = True

    def record_skill_use(self, agent_id: str) -> None:
        record = self.agent_records.get(agent_id)
        if not record:
            return
        record.skill_uses += 1
        self.team_skill_uses[record.team] += 1
        self.last_turn_had_task_progress = True

    def record_scout_spot(self, agent_id: str, target_ids: list[str], turn: int) -> None:
        record = self.agent_records.get(agent_id)
        if not record:
            return
        unique_targets = len(set(target_ids))
        record.enemy_spotted += unique_targets
        if unique_targets and self.team_first_spot_turn[record.team] is None:
            self.team_first_spot_turn[record.team] = turn
            record.first_spots += unique_targets
        if unique_targets:
            self.last_turn_had_task_progress = True

    def record_report(
        self,
        sender_id: str,
        confidence: float,
        report_id: str | None = None,
        report_type: str = "enemy_spot",
        target_id: str | None = None,
        target_pos: dict | None = None,
        turn: int | None = None,
    ) -> None:
        record = self.agent_records.get(sender_id)
        if not record:
            return
        record.communication_count += 1
        self.team_reports[record.team] += 1
        if confidence >= 0.7:
            record.high_confidence_reports += 1
            self.team_high_confidence_reports[record.team] += 1
        if report_id:
            self.intel_records[report_id] = {
                "report_id": report_id,
                "sender_id": sender_id,
                "team": record.team,
                "turn": turn or 0,
                "confidence": confidence,
                "report_type": report_type,
                "target_id": target_id,
                "target_pos": target_pos,
                "used": False,
                "decisive": False,
            }
        self.last_turn_had_task_progress = True

    def record_task_assignment(
        self,
        assigner_id: str,
        task_id: str | None = None,
        assignee_id: str | None = None,
        target_id: str | None = None,
        target_pos: dict | None = None,
        turn: int | None = None,
    ) -> None:
        record = self.agent_records.get(assigner_id)
        if not record:
            return
        record.tasks_assigned += 1
        self.team_task_assignments[record.team] += 1
        if task_id:
            self.task_records[task_id] = {
                "task_id": task_id,
                "assigner_id": assigner_id,
                "assignee_id": assignee_id,
                "team": record.team,
                "target_id": target_id,
                "target_pos": target_pos,
                "turn": turn or 0,
                "status": "pending",
                "used": False,
            }
            self._mark_reports(record.team, target_id=target_id, target_pos=target_pos, decisive=False, turn=turn)
        self.last_turn_had_task_progress = True

    def record_task_in_progress(self, task_id: str | None) -> None:
        if not task_id:
            return
        task = self.task_records.get(task_id)
        if not task:
            return
        task["status"] = "in_progress"
        if task["used"]:
            return
        task["used"] = True
        assigner_id = task.get("assigner_id")
        if assigner_id in self.agent_records:
            self.agent_records[assigner_id].used_task_assignments += 1
            self.agent_records[assigner_id].coordination_contributions += 1
        self.last_turn_had_task_progress = True

    def record_task_completion(self, assignee_id: str | None, task_id: str | None = None) -> None:
        if assignee_id and assignee_id in self.agent_records:
            record = self.agent_records[assignee_id]
            record.tasks_completed += 1
            record.coordination_contributions += 1
            self.team_task_completions[record.team] += 1
            self.last_turn_had_task_progress = True
        if task_id and task_id in self.task_records:
            task = self.task_records[task_id]
            task["status"] = "completed"
            if not task.get("used"):
                self.record_task_in_progress(task_id)
            self._mark_reports(task["team"], target_id=task.get("target_id"), target_pos=task.get("target_pos"), decisive=True)
            assigner_id = task.get("assigner_id")
            if assigner_id in self.agent_records:
                self.agent_records[assigner_id].coordination_contributions += 1
            self.last_turn_had_task_progress = True

    def record_task_support(self, agent_id: str) -> None:
        record = self.agent_records.get(agent_id)
        if not record:
            return
        record.coordination_contributions += 1
        self.last_turn_had_task_progress = True

    def record_blocked_move(self, agent_id: str) -> None:
        if agent_id in self.agent_records:
            self.agent_records[agent_id].blocked_moves += 1

    def record_turn_presence(self, agents: dict, control_points: list) -> None:
        occupancy: dict[str, str] = {}
        for agent in agents.values():
            if agent.alive and agent.agent_id in self.agent_records:
                self.agent_records[agent.agent_id].turns_alive += 1
        for index, point in enumerate(control_points):
            controller = "none"
            for agent in agents.values():
                if agent.alive and agent.pos == point:
                    controller = agent.team.value
                    if agent.agent_id in self.agent_records:
                        self.agent_records[agent.agent_id].control_turns += 1
                        if agent.role == Role.DEFENDER:
                            enemy_nearby = any(
                                other.alive
                                and other.team != agent.team
                                and agent.pos.distance_to(other.pos) <= 2
                                for other in agents.values()
                            )
                            if enemy_nearby:
                                self.agent_records[agent.agent_id].holds_under_pressure += 1
                    self.team_control_turns[agent.team] += 1
                    break
            occupancy[f"cp_{index}"] = controller
        self.control_history.append(occupancy)
        signature = tuple(sorted(occupancy.items()))
        self.last_turn_had_control_change = signature != self.last_control_signature
        if self.last_turn_had_control_change:
            self.consecutive_control_stable_turns = 0
        else:
            self.consecutive_control_stable_turns += 1
        self.last_control_signature = signature

    def finalize_turn(self) -> None:
        if self.last_turn_had_damage:
            self.consecutive_no_damage_turns = 0
        else:
            self.consecutive_no_damage_turns += 1

        if self.last_turn_had_elimination:
            self.consecutive_no_elimination_turns = 0
        else:
            self.consecutive_no_elimination_turns += 1

        if self.last_turn_had_damage or self.last_turn_had_elimination or self.last_turn_had_control_change or self.last_turn_had_task_progress:
            self.consecutive_no_progress_turns = 0
        else:
            self.consecutive_no_progress_turns += 1

        self.last_turn_had_damage = False
        self.last_turn_had_elimination = False
        self.last_turn_had_control_change = False
        self.last_turn_had_task_progress = False

    def should_adjudicate_stalemate(self) -> bool:
        return (
            self.consecutive_no_damage_turns >= 6
            and self.consecutive_no_elimination_turns >= 6
            and self.consecutive_control_stable_turns >= 6
            and self.consecutive_no_progress_turns >= 6
        )
