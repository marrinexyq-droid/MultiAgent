import json

from ..base import AgentBase
from ...battle_types import AgentState, Action, ActionType, Position, Role


class RedCommander(AgentBase):
    def __init__(self, state: AgentState):
        super().__init__(state)
        self._last_comm_turn = 0
        self._target_pos = None

    def _rule_action(self, obs: dict) -> Action:
        enemies = obs.get("visible_enemies", [])
        allies = obs.get("visible_allies", [])
        self_pos = self.state.pos
        turn = obs.get("turn", 0)

        if enemies and self.state.ammo > 0:
            nearest = min(enemies, key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y))
            dist = abs(nearest["pos"]["x"] - self_pos.x) + abs(nearest["pos"]["y"] - self_pos.y)
            if dist <= self.state.attack_range:
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])
            self._target_pos = nearest["pos"]

        if allies and self.state.skill_cooldown_remaining == 0 and turn % 5 == 0:
            if enemies:
                nearest_enemy = min(
                    enemies,
                    key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y),
                )
                skill_target = Position(nearest_enemy["pos"]["x"], nearest_enemy["pos"]["y"])
            else:
                skill_target = self._enemy_zone(obs)[0]
            return Action(self.state.agent_id, ActionType.SKILL, skill_id="rally_order", skill_target=skill_target)

        if enemies and (turn - self._last_comm_turn >= 4):
            self._last_comm_turn = turn
            assignee_id = self._pick_attacker_id(allies)
            nearest = min(
                enemies,
                key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y),
            )
            msg = json.dumps(
                {
                    "type": "task_assign",
                    "assignee": assignee_id,
                    "task": "engage",
                    "target_id": nearest["agent_id"],
                    "target_pos": {
                        "x": nearest["pos"]["x"],
                        "y": nearest["pos"]["y"],
                    },
                },
                ensure_ascii=False,
            )
            return Action(self.state.agent_id, ActionType.COMMUNICATE, message=msg)

        if self._target_pos:
            tp = self._target_pos
            if isinstance(tp, dict):
                tx, ty = tp.get("x", 0), tp.get("y", 0)
            else:
                tx, ty = tp.x, tp.y
            
            # Move in one axis at a time (prioritize larger distance)
            dx = tx - self_pos.x
            dy = ty - self_pos.y
            if abs(dx) >= abs(dy):
                new_x = self_pos.x + (1 if dx > 0 else -1 if dx < 0 else 0)
                return self._move_toward(Position(new_x, self_pos.y), obs)
            else:
                new_y = self_pos.y + (1 if dy > 0 else -1 if dy < 0 else 0)
                return self._move_toward(Position(self_pos.x, new_y), obs)

        enemy_base_candidates = self._enemy_zone(obs)
        base_target = min(
            enemy_base_candidates,
            key=lambda pos: abs(pos.x - self_pos.x) + abs(pos.y - self_pos.y),
        )

        return self._move_toward(base_target, obs)

    def _enemy_zone(self, obs: dict) -> list[Position]:
        grid_size = obs.get("grid_size", 8)
        if self.state.team.value == "red":
            return [Position(grid_size - 2, grid_size - 3), Position(grid_size - 2, grid_size - 2)]
        return [Position(1, 1), Position(1, 2)]

    def _pick_attacker_id(self, allies: list[dict]) -> str:
        attacker = next((ally for ally in allies if ally["role"] == Role.ATTACKER.value), None)
        return attacker["agent_id"] if attacker else self.state.agent_id
