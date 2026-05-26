from ..base import AgentBase
from ...battle_types import AgentState, Action, ActionType, Position, Role


class RedAttacker(AgentBase):
    def __init__(self, state: AgentState):
        super().__init__(state)
        self._target_pos = None

    def choose_action(self, obs: dict, shared_memory: dict) -> Action:
        self.turn_count = obs.get("turn", 0)
        self._sync_state_from_obs(obs)

        for task in shared_memory.get("tasks", shared_memory.get("team_tasks", {})).values():
            if task.get("assignee") == self.state.agent_id and task.get("target_pos"):
                self._target_pos = task["target_pos"]
            elif task.get("assignee") == self.state.agent_id and task.get("target_position"):
                self._target_pos = task["target_position"]

        if shared_memory.get("beliefs"):
            for belief in shared_memory["beliefs"].values():
                if belief.get("last_known_position"):
                    self._target_pos = belief["last_known_position"]
                    break

        if shared_memory.get("enemy_tracks"):
            for target_id, reports in shared_memory["enemy_tracks"].items():
                if reports:
                    latest = reports[0]
                    if latest.get("pos"):
                        self._target_pos = latest["pos"]

        if self.client:
            action = self._llm_action(obs, shared_memory)
        else:
            action = self._rule_action(obs)
        return self._finalize_action(action, obs)

    def _rule_action(self, obs: dict) -> Action:
        enemies = obs.get("visible_enemies", [])
        self_pos = self.state.pos

        if enemies and self.state.ammo > 0:
            nearest = min(enemies, key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y))
            dist = abs(nearest["pos"]["x"] - self_pos.x) + abs(nearest["pos"]["y"] - self_pos.y)
            if dist <= self.state.attack_range and self.state.skill_cooldown_remaining == 0:
                return Action(self.state.agent_id, ActionType.SKILL, target_id=nearest["agent_id"], skill_id="power_strike")
            if dist <= self.state.attack_range:
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])

        if enemies:
            nearest = min(enemies, key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y))
            self._target_pos = nearest["pos"]

        if self._target_pos:
            tp = self._target_pos
            if isinstance(tp, dict):
                tx, ty = tp.get("x", 0), tp.get("y", 0)
            else:
                tx, ty = tp.x, tp.y
            
            # Move in one axis at a time
            dx = tx - self_pos.x
            dy = ty - self_pos.y
            if abs(dx) >= abs(dy):
                new_x = self_pos.x + (1 if dx > 0 else -1 if dx < 0 else 0)
                return self._move_toward(Position(new_x, self_pos.y), obs)
            else:
                new_y = self_pos.y + (1 if dy > 0 else -1 if dy < 0 else 0)
                return self._move_toward(Position(self_pos.x, new_y), obs)

        if self.state.rally_target:
            return self._move_toward(self.state.rally_target, obs)

        if self.state.team.value == "red":
            default_target = Position(obs.get("grid_size", 8) - 2, obs.get("grid_size", 8) - 3)
        else:
            default_target = Position(1, 2)
        return self._move_toward(default_target, obs)
