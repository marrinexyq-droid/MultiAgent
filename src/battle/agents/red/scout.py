import json
from ..base import AgentBase
from ...battle_types import AgentState, Action, ActionType, Position, Role


class RedScout(AgentBase):
    def __init__(self, state: AgentState):
        super().__init__(state)
        self._last_comm_turn = 0

    def _rule_action(self, obs: dict) -> Action:
        enemies = obs.get("visible_enemies", [])
        self_pos = self.state.pos
        turn = obs.get("turn", 0)

        if not enemies and self.state.skill_cooldown_remaining == 0 and turn % 4 == 0:
            return Action(self.state.agent_id, ActionType.SKILL, skill_id="focus_recon")

        if enemies and (turn - self._last_comm_turn >= 3):
            nearest = min(enemies, key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y))
            self._last_comm_turn = turn
            report = {
                "type": "enemy_spot",
                "target_id": nearest["agent_id"],
                "pos": nearest["pos"],
                "hp": nearest["hp"],
            }
            return Action(self.state.agent_id, ActionType.COMMUNICATE, message=json.dumps(report))

        if enemies:
            return Action(self.state.agent_id, ActionType.SCOUT)

        if self.state.rally_target:
            return self._move_toward(self.state.rally_target, obs)

        if self.state.team.value == "red":
            directions = [(self.state.move_speed, 0), (0, self.state.move_speed), (0, -self.state.move_speed), (-self.state.move_speed, 0)]
        else:
            directions = [(-self.state.move_speed, 0), (0, -self.state.move_speed), (0, self.state.move_speed), (self.state.move_speed, 0)]
        best_dir = None
        best_score = -999
        for dx, dy in directions:
            nx, ny = self_pos.x + dx, self_pos.y + dy
            if 0 <= nx < obs.get("grid_size", 8) and 0 <= ny < obs.get("grid_size", 8):
                score = (nx + ny) * 2 + (8 - nx) if self.state.team.value == "red" else ((7 - nx) + (7 - ny)) * 2 + nx
                if score > best_score:
                    best_score = score
                    best_dir = Position(nx, ny)
        if best_dir:
            return Action(self.state.agent_id, ActionType.MOVE, target=best_dir)

        return Action(self.state.agent_id, ActionType.SCOUT)
