from ..base import AgentBase
from ...battle_types import AgentState, Action, ActionType, Position, Role, Team


class BlueDefender(AgentBase):
    def __init__(self, state: AgentState):
        super().__init__(state)
        self._target_pos = None

    def _rule_action(self, obs: dict) -> Action:
        enemies = obs.get("visible_enemies", [])
        self_pos = self.state.pos

        if enemies and self.state.skill_cooldown_remaining == 0 and self.state.hp < self.state.max_hp:
            return Action(self.state.agent_id, ActionType.SKILL, skill_id="fortify")

        if enemies and self.state.ammo > 0:
            nearest = min(enemies, key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y))
            dist = abs(nearest["pos"]["x"] - self_pos.x) + abs(nearest["pos"]["y"] - self_pos.y)
            if dist <= self.state.attack_range:
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])
            self._target_pos = nearest["pos"]

        if enemies:
            nearest = min(enemies, key=lambda e: abs(e["pos"]["x"] - self_pos.x) + abs(e["pos"]["y"] - self_pos.y))
            self._target_pos = nearest["pos"]

        if self._target_pos:
            tp = self._target_pos
            if isinstance(tp, dict):
                tx, ty = tp.get("x", 0), tp.get("y", 0)
            else:
                tx, ty = tp.x, tp.y
            dx = tx - self_pos.x
            dy = ty - self_pos.y
            if abs(dx) >= abs(dy):
                new_x = self_pos.x + (1 if dx > 0 else -1 if dx < 0 else 0)
                if new_x != self_pos.x:
                    return self._move_toward(Position(new_x, self_pos.y), obs)
            else:
                new_y = self_pos.y + (1 if dy > 0 else -1 if dy < 0 else 0)
                if new_y != self_pos.y:
                    return self._move_toward(Position(self_pos.x, new_y), obs)

        if self._target_pos:
            return self._move_toward(self._target_pos)
        
        return self._patrol_toward_base(obs)

    def _patrol_toward_base(self, obs: dict) -> Action:
        # Patrol toward the control zone at (6,5)-(6,6)
        self_pos = self.state.pos
        if self.state.team.value == "blue":
            base_x, base_y = obs.get("grid_size", 8) - 2, obs.get("grid_size", 8) - 3
        else:
            base_x, base_y = 1, 1
        dx = base_x - self_pos.x
        dy = base_y - self_pos.y
        
        if abs(dx) >= abs(dy) and dx != 0:
            new_x = self_pos.x + (1 if dx > 0 else -1)
            return self._move_toward(Position(new_x, self_pos.y), obs)
        elif dy != 0:
            new_y = self_pos.y + (1 if dy > 0 else -1)
            return self._move_toward(Position(self_pos.x, new_y), obs)
        
        return Action(self.state.agent_id, ActionType.HOLD)

    def _move_toward(self, target, obs: dict | None = None) -> Action:
        self_pos = self.state.pos
        if isinstance(target, dict):
            tx, ty = target.get("x", 0), target.get("y", 0)
        else:
            tx, ty = target.x, target.y
        dx = tx - self_pos.x
        dy = ty - self_pos.y
        step = max(1, self.state.move_speed)
        if abs(dx) >= abs(dy):
            move = min(step, abs(dx))
            new_x = self_pos.x + move * (1 if dx > 0 else -1 if dx < 0 else 0)
            if new_x != self_pos.x:
                return Action(self.state.agent_id, ActionType.MOVE, target=Position(new_x, self_pos.y))
        else:
            move = min(step, abs(dy))
            new_y = self_pos.y + move * (1 if dy > 0 else -1 if dy < 0 else 0)
            if new_y != self_pos.y:
                return Action(self.state.agent_id, ActionType.MOVE, target=Position(self_pos.x, new_y))
        return Action(self.state.agent_id, ActionType.HOLD)
