import json

from .base import AgentBase
from ..battle_types import Action, ActionType, Position, Role
from ..grid_rules import distance as grid_distance


class GenericRoleAgent(AgentBase):
    def _opportunity_score(self, enemies: list[dict], allies: list[dict]) -> int:
        if not enemies:
            return 0
        nearest = min(enemy["distance"] for enemy in enemies)
        exposed = sum(1 for enemy in enemies if enemy.get("distance", 99) <= self.state.vision_range or enemy.get("hp", 999) < 80)
        allied_support = sum(1 for ally in allies if ally.get("distance", 99) <= 2)
        score = 45 + exposed * 12 + allied_support * 8 - nearest * 6 + (self.state.risk_preference - 50) // 4
        return max(0, min(100, score))

    def _prefer_task_execution(self, memory: dict) -> dict | None:
        tasks = list(memory.get("tasks", {}).values()) if isinstance(memory, dict) else []
        candidates = [task for task in tasks if task.get("assignee") == self.state.agent_id and task.get("status") in {"pending", "in_progress", "blocked"}]
        if not candidates:
            return None
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        return min(candidates, key=lambda task: (priority_rank.get(task.get("priority", "medium"), 3), task.get("updated_turn", 0)))

    def _task_target(self, task: dict) -> Position | None:
        target_pos = task.get("target_position") or task.get("target_pos")
        if isinstance(target_pos, dict) and "x" in target_pos and "y" in target_pos:
            return Position(target_pos["x"], target_pos["y"])
        return None

    def _build_prompt(self, obs: dict, shared_memory: dict) -> str:
        prompt = super()._build_prompt(obs, shared_memory)
        role_notes = {
            Role.COORDINATOR: "Prioritize team tasking, reassign nearby allies, and avoid direct frontline exposure.",
            Role.SCOUT: "Prioritize forward scouting, high-value target revelation, and avoiding direct fights.",
            Role.ATTACKER: "Prioritize exposed or marked targets, push with support, and deliver concentrated fire.",
            Role.DEFENDER: "Prioritize control zones, protect valuable teammates, and stabilize pressure points.",
            Role.SUPPORT: "Prioritize repairing damaged allies and restoring resources to critical teammates.",
            Role.JAMMER: "Prioritize disrupting enemy information flow and high-value coordination units.",
            Role.CONTROLLER: "Prioritize locking key lanes and slowing enemy movement through control zones.",
            Role.ASSAULTER: "Prioritize backline penetration, high-value targets, and fast disengage windows.",
        }
        return f"{prompt}\nSpecific role doctrine: {role_notes.get(self.state.role, 'Support the team objective.')}"

    def _rule_action(self, obs: dict) -> Action:
        enemies = obs.get("visible_enemies", [])
        allies = obs.get("visible_allies", [])
        memory = obs.get("shared_memory", {})
        self_pos = self.state.pos
        opportunity = self._opportunity_score(enemies, allies)
        active_task = self._prefer_task_execution(memory)
        if active_task and self.state.task_priority >= 60:
            target = self._task_target(active_task)
            if target and grid_distance(self.state.pos, target, obs.get("grid_type", "square")) > 0 and self.state.coordination_preference >= 50:
                return self._move_toward(target, obs)

        if self.state.role == Role.COORDINATOR:
            if self.state.skill_cooldown_remaining == 0 and allies and (opportunity >= self.state.skill_trigger_threshold or self.state.coordination_preference >= 75):
                target = self._priority_zone(obs)
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="coordination_pulse", skill_target=target)
            if enemies and self.state.ammo > 0 and any(enemy["distance"] <= self.state.attack_range for enemy in enemies):
                nearest = min(enemies, key=lambda enemy: enemy["distance"])
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])
            return self._move_toward(self._priority_zone(obs), obs)

        if self.state.role == Role.SCOUT:
            if self.state.skill_cooldown_remaining == 0 and (opportunity >= self.state.skill_trigger_threshold or self.state.mobility_bias >= 70):
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="scan_reveal", skill_target=self._priority_zone(obs))
            if enemies:
                farthest = max(enemies, key=lambda enemy: enemy["distance"])
                if farthest["distance"] <= self.state.attack_range and self.state.ammo > 0:
                    return Action(self.state.agent_id, ActionType.ATTACK, target_id=farthest["agent_id"])
                return self._move_toward(Position(farthest["pos"]["x"], farthest["pos"]["y"]), obs)
            return Action(self.state.agent_id, ActionType.SCOUT)

        if self.state.role == Role.ATTACKER:
            target_id = self._marked_target(enemies, memory)
            if target_id and self.state.skill_cooldown_remaining == 0 and self.state.ammo > 0 and opportunity >= self.state.skill_trigger_threshold:
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="focused_burst", target_id=target_id)
            if target_id:
                return self._engage_target(enemies, target_id, obs)
            return super()._rule_action(obs)

        if self.state.role == Role.DEFENDER:
            threatened = self._enemy_near_control(obs)
            if threatened and self.state.skill_cooldown_remaining == 0 and self.state.hold_bias >= self.state.skill_trigger_threshold:
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="guard_hold", skill_target=self._nearest_control(obs))
            if enemies and self.state.ammo > 0 and any(enemy["distance"] <= self.state.attack_range for enemy in enemies):
                nearest = min(enemies, key=lambda enemy: enemy["distance"])
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])
            return self._move_toward(self._nearest_control(obs), obs)

        if self.state.role == Role.SUPPORT:
            critical_ally = self._critical_ally(allies)
            if critical_ally and self.state.skill_cooldown_remaining == 0 and (critical_ally.get("hp", 100) <= max(20, self.state.skill_trigger_threshold)):
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="repair_supply", target_id=critical_ally["agent_id"])
            if critical_ally:
                return self._move_toward(Position(critical_ally["pos"]["x"], critical_ally["pos"]["y"]), obs)
            return self._move_toward(self._priority_zone(obs), obs)

        if self.state.role == Role.JAMMER:
            target = self._high_value_enemy(enemies)
            if target and self.state.skill_cooldown_remaining == 0 and opportunity >= self.state.skill_trigger_threshold:
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="link_jam", target_id=target["agent_id"])
            if target:
                return self._move_toward(Position(target["pos"]["x"], target["pos"]["y"]), obs)
            return self._move_toward(self._priority_zone(obs), obs)

        if self.state.role == Role.CONTROLLER:
            if self.state.skill_cooldown_remaining == 0 and (self.state.hold_bias >= 55 or opportunity >= self.state.skill_trigger_threshold):
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="zone_lock", skill_target=self._nearest_control(obs))
            if enemies and self.state.ammo > 0 and any(enemy["distance"] <= self.state.attack_range for enemy in enemies):
                nearest = min(enemies, key=lambda enemy: enemy["distance"])
                return Action(self.state.agent_id, ActionType.ATTACK, target_id=nearest["agent_id"])
            return self._move_toward(self._nearest_control(obs), obs)

        if self.state.role == Role.ASSAULTER:
            target = self._high_value_enemy(enemies)
            if target and self.state.skill_cooldown_remaining == 0 and opportunity >= self.state.skill_trigger_threshold:
                return Action(self.state.agent_id, ActionType.SKILL, skill_id="breach_dash", target_id=target["agent_id"])
            if target:
                return self._engage_target(enemies, target["agent_id"], obs)
            return self._move_toward(self._priority_zone(obs), obs)

        return super()._rule_action(obs)

    def _engage_target(self, enemies: list[dict], target_id: str, obs: dict) -> Action:
        target = next((enemy for enemy in enemies if enemy["agent_id"] == target_id), None)
        if not target:
            return super()._rule_action(obs)
        if target["distance"] <= self.state.attack_range and self.state.ammo > 0:
            return Action(self.state.agent_id, ActionType.ATTACK, target_id=target_id)
        return self._move_toward(Position(target["pos"]["x"], target["pos"]["y"]), obs)

    def _marked_target(self, enemies: list[dict], memory: dict) -> str | None:
        beliefs = memory.get("beliefs", {}) if isinstance(memory, dict) else {}
        if self.state.target_preference == "frontline":
            frontline = min(enemies, key=lambda enemy: enemy["distance"]) if enemies else None
            return frontline["agent_id"] if frontline else None
        if self.state.target_preference == "backline":
            target = self._high_value_enemy(enemies)
            return target["agent_id"] if target else None
        for enemy in enemies:
            if enemy["agent_id"] in beliefs:
                return enemy["agent_id"]
        return enemies[0]["agent_id"] if enemies else None

    def _critical_ally(self, allies: list[dict]) -> dict | None:
        low_hp = [ally for ally in allies if ally.get("hp", 999) <= 55]
        return min(low_hp, key=lambda ally: ally["hp"]) if low_hp else None

    def _high_value_enemy(self, enemies: list[dict]) -> dict | None:
        if not enemies:
            return None
        role_priority = {
            "coordinator": 0,
            "support": 1,
            "jammer": 2,
            "controller": 3,
            "scout": 4,
            "attacker": 5,
            "assaulter": 6,
            "defender": 7,
        }
        return min(enemies, key=lambda enemy: (role_priority.get(enemy["role"], 99), enemy["distance"]))

    def _zones(self, obs: dict, key: str) -> list[dict]:
        scenario = obs.get("scenario", {})
        return scenario.get(key, []) if isinstance(scenario, dict) else []

    def _zone_center(self, zone: dict) -> Position:
        return Position(zone["x"] + max(0, zone["width"] // 2), zone["y"] + max(0, zone["height"] // 2))

    def _nearest_control(self, obs: dict) -> Position:
        controls = self._zones(obs, "control_zones")
        if controls:
            return min((self._zone_center(zone) for zone in controls), key=lambda pos: grid_distance(self.state.pos, pos, obs.get("grid_type", "square")))
        return self._priority_zone(obs)

    def _priority_zone(self, obs: dict) -> Position:
        if self.state.hold_bias >= 70:
            controls = self._zones(obs, "control_zones")
            if controls:
                return self._zone_center(controls[0])
        if self.state.team.value == "red":
            zones = self._zones(obs, "blue_spawn_zones") or self._zones(obs, "control_zones")
        else:
            zones = self._zones(obs, "red_spawn_zones") or self._zones(obs, "control_zones")
        if zones:
            zone = zones[-1] if self.state.mobility_bias >= 70 and len(zones) > 1 else zones[0]
            return self._zone_center(zone)
        return Position(obs.get("width", 8) // 2, obs.get("height", 8) // 2)

    def _enemy_near_control(self, obs: dict) -> bool:
        controls = self._zones(obs, "control_zones")
        if not controls:
            return False
        centers = [self._zone_center(zone) for zone in controls]
        for enemy in obs.get("visible_enemies", []):
            pos = Position(enemy["pos"]["x"], enemy["pos"]["y"])
            if any(grid_distance(pos, center, obs.get("grid_type", "square")) <= 2 for center in centers):
                return True
        return False

    def choose_action(self, obs: dict, shared_memory: dict) -> Action:
        obs = dict(obs)
        obs["shared_memory"] = shared_memory
        return super().choose_action(obs, shared_memory)
