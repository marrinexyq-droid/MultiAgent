import random
from typing import Optional

from .battle_types import Action, ActionType, AgentState, Position, RectZone, Role, ScenarioConfig, TacticalEvent, Team, TerrainCell, TerrainType
from .grid_rules import distance as grid_distance, has_line_of_sight
from .roster import default_scenario_config
from .stats import BattleStats
from .terrain import cost_for as terrain_cost, cover_for as terrain_cover, concealment_for as terrain_concealment, terrain_label


class BattlefieldEnv:
    def __init__(self, grid_size: int = 8, scenario_config: ScenarioConfig | None = None):
        scenario = scenario_config or default_scenario_config(grid_size, grid_size)
        self.scenario = scenario
        self.width = scenario.width
        self.height = scenario.height
        self.grid_type = getattr(scenario, "grid_type", "square")
        self.grid_size = max(self.width, self.height)
        self.agents: dict[str, AgentState] = {}
        self.turn = 0
        self.max_turns = 50
        self.events: list[str] = []
        self.structured_events: list[TacticalEvent] = []
        self.stats = BattleStats()
        self.active_effects: list[dict] = []
        self.terrain_grid = scenario.terrain_grid

    @staticmethod
    def _resolve_ttype(cell: object) -> TerrainType:
        if isinstance(cell, TerrainCell):
            return cell.type
        if isinstance(cell, TerrainType):
            return cell
        return TerrainType.OPEN

    def _terrain_at(self, x: int, y: int) -> TerrainType:
        if self.terrain_grid and 0 <= y < len(self.terrain_grid) and 0 <= x < len(self.terrain_grid[y]):
            return self._resolve_ttype(self.terrain_grid[y][x])
        return TerrainType.OPEN

    def _mp_cost(self, x: int, y: int, role_key: str | None = None) -> int:
        return terrain_cost(self._terrain_at(x, y), role_key)

    def _terrain_label(self, x: int, y: int) -> str:
        return terrain_label(self._terrain_at(x, y))

    def reset(self, red_agents: list[AgentState], blue_agents: list[AgentState]) -> dict:
        self.agents.clear()
        self.turn = 0
        self.events.clear()
        self.structured_events.clear()
        self.active_effects = []
        self.stats = BattleStats()

        for agent in red_agents + blue_agents:
            agent.remaining_mp = agent.movement_points or agent.move_speed * 3
            self.agents[agent.agent_id] = agent
            self.stats.register_agent(agent)

        self._emit_event(
            "RESULT",
            f"对抗演练开始! 红队: {len(red_agents)} 单位, 蓝队: {len(blue_agents)} 单位",
            markers=["START"],
        )
        return self._get_all_observations()

    def step(self, actions: list[Action]) -> tuple[dict, bool]:
        self.turn += 1
        self.events.clear()
        self.structured_events.clear()
        self._expire_area_effects()
        for agent in self.agents.values():
            if agent.alive:
                agent.remaining_mp = agent.movement_points or agent.move_speed * 3

        valid_actions = [action for action in actions if self._is_valid_action(action)]
        grouped = {
            ActionType.SCOUT: [action for action in valid_actions if action.action_type == ActionType.SCOUT],
            ActionType.SKILL: [action for action in valid_actions if action.action_type == ActionType.SKILL],
            ActionType.MOVE: [action for action in valid_actions if action.action_type == ActionType.MOVE],
            ActionType.ATTACK: [action for action in valid_actions if action.action_type == ActionType.ATTACK],
            ActionType.COMMUNICATE: [action for action in valid_actions if action.action_type == ActionType.COMMUNICATE],
        }

        for action in grouped[ActionType.SCOUT]:
            self._execute_scout(action)
        for action in grouped[ActionType.SKILL]:
            self._execute_skill(action)
        for action in self._resolve_move_actions(grouped[ActionType.MOVE]):
            self._execute_move(action)
        for action in grouped[ActionType.ATTACK]:
            self._execute_attack(action)
        for action in grouped[ActionType.COMMUNICATE]:
            self._emit_event("TASK", f"[协同通信] {action.agent_id}: {action.message}", actor_id=action.agent_id, team=self.agents[action.agent_id].team.value, markers=["TASK"])

        self._tick_effects()
        self.stats.record_turn_presence(self.agents, self._control_points())
        self.stats.finalize_turn()
        done = self._check_termination()
        return self._get_all_observations(), done

    def get_observation(self, agent_id: str) -> dict:
        agent = self.agents.get(agent_id)
        if not agent or not agent.alive:
            return {}

        visible_enemies = []
        visible_allies = []
        effective_vision = max(1, agent.vision_range - (1 if agent.jammed_turns_remaining > 0 else 0))

        for other_id, other in self.agents.items():
            if other_id == agent_id or not other.alive:
                continue
            if other.stealth_turns_remaining > 0 and other.team != agent.team and grid_distance(agent.pos, other.pos, self.grid_type) > 1:
                continue
            if other.team != agent.team and not has_line_of_sight(agent.pos, other.pos, self.terrain_grid):
                continue
            if other.team != agent.team:
                conceal = terrain_concealment(self._terrain_at(other.pos.x, other.pos.y))
                conceal_penalty = round(conceal * effective_vision)
                if conceal_penalty > 0 and grid_distance(agent.pos, other.pos, self.grid_type) > max(1, effective_vision - conceal_penalty):
                    continue
            dist = grid_distance(agent.pos, other.pos, self.grid_type)
            if dist <= effective_vision or other.exposed_turns_remaining > 0:
                info = {
                    "agent_id": other_id,
                    "team": other.team.value,
                    "role": other.role.value,
                    "pos": {"x": other.pos.x, "y": other.pos.y},
                    "hp": other.hp,
                    "distance": dist,
                }
                if other.team == agent.team:
                    visible_allies.append(info)
                else:
                    visible_enemies.append(info)

        return {
            "self": {
                "agent_id": agent.agent_id,
                "role": agent.role.value,
                "pos": {"x": agent.pos.x, "y": agent.pos.y},
                "hp": agent.hp,
                "ammo": agent.ammo,
                "move_speed": agent.move_speed,
                "skill_name": agent.skill_name,
                "skill_description": agent.skill_description,
                "skill_cooldown": agent.skill_cooldown,
                "skill_cooldown_remaining": agent.skill_cooldown_remaining,
                "rally_target": {"x": agent.rally_target.x, "y": agent.rally_target.y} if agent.rally_target else None,
                "rally_turns_remaining": agent.rally_turns_remaining,
                "exposed_turns_remaining": agent.exposed_turns_remaining,
                "jammed_turns_remaining": agent.jammed_turns_remaining,
                "control_zone_turns_remaining": agent.control_zone_turns_remaining,
                "stealth_turns_remaining": agent.stealth_turns_remaining,
            },
            "visible_enemies": visible_enemies,
            "visible_allies": visible_allies,
            "turn": self.turn,
            "width": self.width,
            "height": self.height,
            "grid_size": self.grid_size,
            "grid_type": self.grid_type,
            "scenario": self.scenario.to_dict(),
            "effects": list(self.active_effects),
            "terrain_at_pos": self._terrain_label(agent.pos.x, agent.pos.y),
            "terrain_cover": terrain_cover(self._terrain_at(agent.pos.x, agent.pos.y)),
        }

    def _emit_event(
        self,
        event_type: str,
        summary: str,
        *,
        actor_id: str | None = None,
        team: str | None = None,
        target_id: str | None = None,
        target_position: Position | dict | None = None,
        markers: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.events.append(summary)
        if isinstance(target_position, Position):
            target_position = {"x": target_position.x, "y": target_position.y}
        self.structured_events.append(
            TacticalEvent(
                turn=self.turn,
                type=event_type,
                actor_id=actor_id,
                team=team,
                target_id=target_id,
                target_position=target_position,
                summary=summary,
                markers=markers or [],
                metadata=metadata or {},
            )
        )

    def _is_valid_action(self, action: Action) -> bool:
        agent = self.agents.get(action.agent_id)
        if not agent or not agent.alive:
            return False

        if action.action_type == ActionType.MOVE:
            if not action.target:
                return False
            if not self._in_bounds(action.target):
                return False
            if action.target == agent.pos:
                return True
            cost = self._mp_cost(action.target.x, action.target.y, agent.role.value)
            if cost > agent.remaining_mp:
                return False
            if self.grid_type != "hex" and action.target.x != agent.pos.x and action.target.y != agent.pos.y:
                return False
            for other in self.agents.values():
                if other.alive and other.agent_id != agent.agent_id and other.pos == action.target:
                    return False
            return True

        if action.action_type == ActionType.ATTACK:
            if not action.target_id:
                return False
            target = self.agents.get(action.target_id)
            if not target or not target.alive:
                return False
            return grid_distance(agent.pos, target.pos, self.grid_type) <= agent.attack_range and agent.ammo > 0

        if action.action_type == ActionType.SKILL:
            if agent.skill_cooldown_remaining > 0:
                return False
            if agent.role in {Role.ATTACKER, Role.JAMMER, Role.ASSAULTER}:
                return bool(action.target_id and self.agents.get(action.target_id) and self.agents[action.target_id].alive)
            if agent.role == Role.SUPPORT:
                return bool(action.target_id and self.agents.get(action.target_id) and self.agents[action.target_id].alive)
            return True

        if action.action_type == ActionType.COMMUNICATE:
            return action.message is not None

        return True

    def _resolve_move_actions(self, move_actions: list[Action]) -> list[Action]:
        resolved: list[Action] = []
        occupied = {agent_id: Position(agent.pos.x, agent.pos.y) for agent_id, agent in self.agents.items() if agent.alive}
        reserved_targets: set[Position] = set()
        for action in move_actions:
            agent = self.agents[action.agent_id]
            target = action.target
            if target is None or target == agent.pos:
                continue
            cost = self._mp_cost(target.x, target.y, agent.role.value)
            if cost > agent.remaining_mp:
                self.events.append(f"[移动力不足] {action.agent_id} 移动力({agent.remaining_mp})不足以进入 {self._terrain_label(target.x, target.y)}(成本{cost})")
                self.structured_events.append(
                    TacticalEvent(
                        turn=self.turn,
                        type="BLOCK",
                        actor_id=action.agent_id,
                        team=agent.team.value,
                        target_position={"x": target.x, "y": target.y},
                        summary=f"{action.agent_id} 移动力不足，无法进入{self._terrain_label(target.x, target.y)}(需要{cost}MP，剩余{agent.remaining_mp}MP)",
                        markers=["BLOCK"],
                        metadata={"reason": "insufficient_mp", "terrain": self._terrain_label(target.x, target.y), "cost": cost, "remaining": agent.remaining_mp},
                    )
                )
                self.stats.record_blocked_move(action.agent_id)
                continue
            occupied_without_self = {pos for agent_id, pos in occupied.items() if agent_id != action.agent_id}
            if target in occupied_without_self or target in reserved_targets:
                self.events.append(f"[位置阻塞] {action.agent_id} 无法转移到 ({target.x},{target.y})，目标位置已被占用")
                self.structured_events.append(
                    TacticalEvent(
                        turn=self.turn,
                        type="BLOCK",
                        actor_id=action.agent_id,
                        team=agent.team.value,
                        target_position={"x": target.x, "y": target.y},
                        summary=f"{action.agent_id} 进入受阻，目标位置已被占用。",
                        markers=["BLOCK"],
                        metadata={"reason": "occupied"},
                    )
                )
                self.stats.record_blocked_move(action.agent_id)
                continue
            if self._is_controlled_by_enemy(agent, target):
                self._emit_event(
                    "BLOCK",
                    f"[控制限制] {action.agent_id} 尝试进入 ({target.x},{target.y}) 时受到封锁压制",
                    actor_id=action.agent_id,
                    team=agent.team.value,
                    target_position=target,
                    markers=["BLOCK"],
                    metadata={"reason": "enemy_control"},
                )
                self.stats.record_blocked_move(action.agent_id)
                continue
            occupied[action.agent_id] = Position(target.x, target.y)
            reserved_targets.add(target)
            resolved.append(action)
        return resolved

    def _execute_move(self, action: Action):
        agent = self.agents[action.agent_id]
        old_pos = agent.pos
        cost = self._mp_cost(action.target.x, action.target.y, agent.role.value)
        agent.remaining_mp = max(0, agent.remaining_mp - cost)
        agent.pos = action.target
        terrain_name = self._terrain_label(action.target.x, action.target.y)
        self._emit_event(
            "MOVE",
            f"[移动] {action.agent_id} ({old_pos.x},{old_pos.y})→({action.target.x},{action.target.y}) {terrain_name} 消耗{cost}MP 剩余{agent.remaining_mp}MP",
            actor_id=action.agent_id,
            team=agent.team.value,
            target_position=action.target,
            metadata={"from": {"x": old_pos.x, "y": old_pos.y}, "to": {"x": action.target.x, "y": action.target.y}, "terrain": terrain_name, "mp_cost": cost, "remaining_mp": agent.remaining_mp},
        )

    def _execute_attack(self, action: Action):
        attacker = self.agents[action.agent_id]
        target = self.agents[action.target_id]
        bonus = 0
        if target.exposed_turns_remaining > 0:
            bonus += 6
        if attacker.role == Role.ATTACKER and target.exposed_turns_remaining > 0:
            bonus += 8
        if attacker.role == Role.ASSAULTER and target.role in {Role.COORDINATOR, Role.SUPPORT, Role.JAMMER}:
            bonus += 10
        damage = self._roll_damage(attacker, bonus=bonus)
        raw_damage = damage
        cover = terrain_cover(self._terrain_at(target.pos.x, target.pos.y))
        applied_damage = self._apply_damage(target, damage)
        attacker.ammo = max(0, attacker.ammo - 1)
        self.stats.record_damage(attacker.agent_id, target.agent_id, applied_damage, turn=self.turn)
        markers = ["ATTACK"]
        if target.exposed_turns_remaining > 0:
            markers.append("FOCUS")
        terrain_cover_str = f" 🛡️{self._terrain_label(target.pos.x, target.pos.y)}掩护-{round(cover*100)}%" if cover > 0 else ""
        self._emit_event(
            "ATTACK",
            f"[对抗] {action.agent_id}→{action.target_id} 原始{raw_damage}{terrain_cover_str} 实际{applied_damage} 目标HP={target.hp}",
            actor_id=action.agent_id,
            team=attacker.team.value,
            target_id=action.target_id,
            target_position=target.pos,
            markers=markers,
            metadata={"damage": applied_damage, "raw_damage": raw_damage, "terrain_cover": cover, "terrain": self._terrain_label(target.pos.x, target.pos.y)},
        )
        if target.hp <= 0:
            target.alive = False
            self.stats.record_kill(attacker.agent_id, target.agent_id)
            self._emit_event("RESULT", f"[失效] {action.target_id} 已退出对抗!", actor_id=action.agent_id, team=attacker.team.value, target_id=action.target_id, target_position=target.pos, markers=["RESULT", "DOWN"])

    def _execute_skill(self, action: Action):
        agent = self.agents[action.agent_id]

        if agent.role == Role.COORDINATOR:
            assignees = []
            for other in self.agents.values():
                if other.team == agent.team and other.alive and other.agent_id != agent.agent_id and grid_distance(agent.pos, other.pos, self.grid_type) <= 2:
                    other.rally_target = action.skill_target or self._priority_zone(agent.team)
                    other.rally_turns_remaining = 2
                    assignees.append(other.agent_id)
            agent.effect_radius = 2
            agent.effect_turns_remaining = 1
            self.active_effects.append(
                {
                    "type": "coordination_field",
                    "team": agent.team.value,
                    "center": {"x": agent.pos.x, "y": agent.pos.y},
                    "radius": 2,
                    "turns_remaining": 1,
                    "source_id": agent.agent_id,
                    "affected_ids": assignees,
                    "skill_name": agent.skill_name,
                    "impact_summary": "提升附近友军任务响应与集火协同",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self._emit_event(
                "TASK",
                f"[技能] {agent.agent_id} 使用 {agent.skill_name}，强化周边友军协同",
                actor_id=agent.agent_id,
                team=agent.team.value,
                target_position=action.skill_target or self._priority_zone(agent.team),
                markers=["TASK"],
                metadata={
                    "effect": "coordination_pulse",
                    "assignees": assignees,
                    "task": "协同广播",
                    "impact_summary": "提升附近友军任务响应与集火协同",
                },
            )

        elif agent.role == Role.SCOUT:
            spotted = []
            for other in self.agents.values():
                if other.team != agent.team and other.alive and grid_distance(agent.pos, other.pos, self.grid_type) <= agent.vision_range + 2:
                    other.exposed_turns_remaining = max(other.exposed_turns_remaining, 2)
                    spotted.append(
                        {
                            "agent_id": other.agent_id,
                            "role": other.role.value,
                            "pos": {"x": other.pos.x, "y": other.pos.y},
                        }
                    )
            agent.effect_radius = agent.vision_range + 2
            agent.effect_turns_remaining = 1
            self.active_effects.append(
                {
                    "type": "scan_field",
                    "team": agent.team.value,
                    "center": {"x": agent.pos.x, "y": agent.pos.y},
                    "radius": agent.vision_range + 2,
                    "turns_remaining": 1,
                    "source_id": agent.agent_id,
                    "affected_ids": [item["agent_id"] for item in spotted],
                    "skill_name": agent.skill_name,
                    "impact_summary": "揭示目标并提升队友锁定概率",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            if spotted:
                self.stats.record_scout_spot(agent.agent_id, [item["agent_id"] for item in spotted], self.turn)
            self._emit_event(
                "SPOT",
                f"[技能] {agent.agent_id} 使用 {agent.skill_name}，揭示目标: {[item['agent_id'] for item in spotted] or '无'}",
                actor_id=agent.agent_id,
                team=agent.team.value,
                markers=["SPOT"],
                metadata={
                    "targets": spotted,
                    "impact_summary": "揭示目标并提升队友锁定概率",
                },
            )

        elif agent.role == Role.ATTACKER and action.target_id:
            target = self.agents[action.target_id]
            damage = self._roll_damage(agent, bonus=14 + (6 if target.exposed_turns_remaining > 0 else 0))
            applied_damage = self._apply_damage(target, damage, attacker_pos=agent.pos)
            agent.ammo = max(0, agent.ammo - 1)
            self.active_effects.append(
                {
                    "type": "focused_burst",
                    "team": agent.team.value,
                    "center": {"x": target.pos.x, "y": target.pos.y},
                    "radius": 0,
                    "turns_remaining": 1,
                    "source_id": agent.agent_id,
                    "target_id": target.agent_id,
                    "skill_name": agent.skill_name,
                    "impact_summary": "对暴露目标造成更高打击",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self.stats.record_damage(agent.agent_id, target.agent_id, applied_damage, turn=self.turn)
            self._emit_event("ATTACK", f"[技能] {agent.agent_id} 使用 {agent.skill_name} -> {action.target_id}, 影响值={applied_damage}, 目标状态值={target.hp}", actor_id=agent.agent_id, team=agent.team.value, target_id=action.target_id, target_position=target.pos, markers=["ATTACK", "FOCUS"], metadata={"damage": applied_damage, "effect": "focused_burst"})
            if target.hp <= 0:
                target.alive = False
                self.stats.record_kill(agent.agent_id, target.agent_id)
                self._emit_event("RESULT", f"[失效] {action.target_id} 已退出对抗!", actor_id=agent.agent_id, team=agent.team.value, target_id=action.target_id, target_position=target.pos, markers=["RESULT", "DOWN"])

        elif agent.role == Role.DEFENDER:
            agent.defense_bonus = 0.45
            agent.defense_bonus_turns = 1
            agent.effect_radius = 1
            agent.effect_turns_remaining = 1
            self.active_effects.append(
                {
                    "type": "guard_field",
                    "team": agent.team.value,
                    "center": {"x": agent.pos.x, "y": agent.pos.y},
                    "radius": 1,
                    "turns_remaining": 1,
                    "source_id": agent.agent_id,
                    "affected_ids": [agent.agent_id],
                    "skill_name": agent.skill_name,
                    "impact_summary": "稳固本地防线并降低受击损耗",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self._emit_event("SKILL", f"[技能] {agent.agent_id} 使用 {agent.skill_name}，稳固本地防线", actor_id=agent.agent_id, team=agent.team.value, target_position=agent.pos, markers=["GUARD"], metadata={"effect": "guard_hold"})

        elif agent.role == Role.SUPPORT and action.target_id:
            target = self.agents[action.target_id]
            repaired = min(target.max_hp - target.hp, 18)
            reammo = min(target.max_ammo - target.ammo, 2)
            target.hp += repaired
            target.ammo += reammo
            self.active_effects.append(
                {
                    "type": "support_link",
                    "team": agent.team.value,
                    "center": {"x": target.pos.x, "y": target.pos.y},
                    "radius": 0,
                    "turns_remaining": 1,
                    "source_id": agent.agent_id,
                    "target_id": target.agent_id,
                    "skill_name": agent.skill_name,
                    "impact_summary": "恢复 HP 与资源，维持持续作战能力",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self.stats.record_task_support(agent.agent_id)
            self._emit_event("SKILL", f"[技能] {agent.agent_id} 使用 {agent.skill_name}，恢复 {action.target_id} 状态 {repaired} / 资源 {reammo}", actor_id=agent.agent_id, team=agent.team.value, target_id=action.target_id, target_position=target.pos, markers=["SUPPORT"], metadata={"repair": repaired, "reammo": reammo})

        elif agent.role == Role.JAMMER and action.target_id:
            target = self.agents[action.target_id]
            target.jammed_turns_remaining = max(target.jammed_turns_remaining, 2)
            self.active_effects.append(
                {
                    "type": "jam_zone",
                    "team": agent.team.value,
                    "center": {"x": target.pos.x, "y": target.pos.y},
                    "radius": 1,
                    "turns_remaining": 2,
                    "source_id": agent.agent_id,
                    "target_id": target.agent_id,
                    "skill_name": agent.skill_name,
                    "impact_summary": "降低置信度并制造信息失真",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self.stats.record_task_support(agent.agent_id)
            self._emit_event("JAM", f"[技能] {agent.agent_id} 使用 {agent.skill_name}，干扰 {action.target_id} 的信息链路", actor_id=agent.agent_id, team=agent.team.value, target_id=action.target_id, target_position=target.pos, markers=["JAM"], metadata={"effect": "link_jam"})

        elif agent.role == Role.CONTROLLER:
            center = action.skill_target or self._nearest_control_zone_center(agent.team)
            self.active_effects.append(
                {
                    "type": "control_zone",
                    "team": agent.team.value,
                    "center": {"x": center.x, "y": center.y},
                    "radius": 1,
                    "turns_remaining": 2,
                    "source_id": agent.agent_id,
                    "skill_name": agent.skill_name,
                    "impact_summary": "限制路径与推进，形成封锁区域",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self._emit_event("BLOCK", f"[技能] {agent.agent_id} 使用 {agent.skill_name}，封锁 ({center.x},{center.y}) 周边区域", actor_id=agent.agent_id, team=agent.team.value, target_position=center, markers=["BLOCK"], metadata={"effect": "zone_lock"})

        elif agent.role == Role.ASSAULTER and action.target_id:
            target = self.agents[action.target_id]
            if grid_distance(agent.pos, target.pos, self.grid_type) > 1:
                agent.pos = Position(target.pos.x, max(0, target.pos.y - 1))
            damage = self._roll_damage(agent, bonus=10)
            applied_damage = self._apply_damage(target, damage, attacker_pos=agent.pos)
            agent.stealth_turns_remaining = 1
            agent.ammo = max(0, agent.ammo - 1)
            self.active_effects.append(
                {
                    "type": "engage_trace",
                    "team": agent.team.value,
                    "center": {"x": target.pos.x, "y": target.pos.y},
                    "radius": 1,
                    "turns_remaining": 1,
                    "source_id": agent.agent_id,
                    "target_id": target.agent_id,
                    "skill_name": agent.skill_name,
                    "impact_summary": "高机动切入后排并制造关键接敌",
                }
            )
            self.stats.record_skill_use(agent.agent_id)
            self.stats.record_damage(agent.agent_id, target.agent_id, applied_damage, turn=self.turn)
            self._emit_event("ENGAGE", f"[技能] {agent.agent_id} 使用 {agent.skill_name}，突入打击 {action.target_id}，影响值={applied_damage}", actor_id=agent.agent_id, team=agent.team.value, target_id=action.target_id, target_position=target.pos, markers=["ENGAGE"], metadata={"damage": applied_damage})
            if target.hp <= 0:
                target.alive = False
                self.stats.record_kill(agent.agent_id, target.agent_id)
                self._emit_event("RESULT", f"[失效] {action.target_id} 已退出对抗!", actor_id=agent.agent_id, team=agent.team.value, target_id=action.target_id, target_position=target.pos, markers=["RESULT", "DOWN"])

        agent.skill_cooldown_remaining = agent.skill_cooldown + 1

    def _execute_scout(self, action: Action):
        agent = self.agents[action.agent_id]
        spotted = []
        for other_id, other in self.agents.items():
            if other.team != agent.team and other.alive and grid_distance(agent.pos, other.pos, self.grid_type) <= agent.vision_range and has_line_of_sight(agent.pos, other.pos, self.terrain_grid):
                spotted.append({"agent_id": other_id, "role": other.role.value, "pos": {"x": other.pos.x, "y": other.pos.y}, "hp": other.hp})
        if spotted:
            for item in spotted:
                self.agents[item["agent_id"]].exposed_turns_remaining = max(self.agents[item["agent_id"]].exposed_turns_remaining, 1)
            self.stats.record_scout_spot(action.agent_id, [item["agent_id"] for item in spotted], self.turn)
            self._emit_event(
                "SPOT",
                f"[侦测] {action.agent_id} 发现目标: {[item['agent_id'] for item in spotted]}",
                actor_id=action.agent_id,
                team=agent.team.value,
                markers=["SPOT"],
                metadata={"targets": spotted, "impact_summary": "发现高价值目标并刷新态势"},
            )

    def _roll_damage(self, attacker: AgentState, bonus: int = 0) -> int:
        return max(1, attacker.attack_power + bonus + random.randint(-4, 4))

    def _apply_damage(self, target: AgentState, damage: int, attacker_pos: Position | None = None) -> int:
        mitigated = damage
        terrain_cover_bonus = terrain_cover(self._terrain_at(target.pos.x, target.pos.y))
        if terrain_cover_bonus > 0:
            mitigated = max(1, round(mitigated * (1 - terrain_cover_bonus)))
        if target.defense_bonus_turns > 0 and target.defense_bonus > 0:
            mitigated = max(1, round(mitigated * (1 - target.defense_bonus)))
        target.hp = max(0, target.hp - mitigated)
        return mitigated

    def _tick_effects(self):
        for agent in self.agents.values():
            if agent.skill_cooldown_remaining > 0:
                agent.skill_cooldown_remaining -= 1
            if agent.defense_bonus_turns > 0:
                agent.defense_bonus_turns -= 1
                if agent.defense_bonus_turns == 0:
                    agent.defense_bonus = 0.0
            if agent.effect_turns_remaining > 0:
                agent.effect_turns_remaining -= 1
                if agent.effect_turns_remaining == 0:
                    agent.effect_radius = 0
            if agent.rally_turns_remaining > 0:
                agent.rally_turns_remaining -= 1
                if agent.rally_turns_remaining == 0:
                    agent.rally_target = None
            if agent.exposed_turns_remaining > 0:
                agent.exposed_turns_remaining -= 1
            if agent.jammed_turns_remaining > 0:
                agent.jammed_turns_remaining -= 1
            if agent.control_zone_turns_remaining > 0:
                agent.control_zone_turns_remaining -= 1
            if agent.stealth_turns_remaining > 0:
                agent.stealth_turns_remaining -= 1

    def _expire_area_effects(self):
        active = []
        for effect in self.active_effects:
            if effect["turns_remaining"] > 0:
                effect["turns_remaining"] -= 1
                if effect["turns_remaining"] > 0:
                    active.append(effect)
        self.active_effects = active

    def _check_termination(self) -> bool:
        red_alive = sum(1 for agent in self.agents.values() if agent.team == Team.RED and agent.alive)
        blue_alive = sum(1 for agent in self.agents.values() if agent.team == Team.BLUE and agent.alive)
        if red_alive == 0:
            self._emit_event("RESULT", "[结果] 蓝队获胜! 红队全部失效。", team=Team.BLUE.value, markers=["RESULT"])
            return True
        if blue_alive == 0:
            self._emit_event("RESULT", "[结果] 红队获胜! 蓝队全部失效。", team=Team.RED.value, markers=["RESULT"])
            return True
        if self.turn >= self.max_turns:
            self._emit_event("RESULT", f"[结果] 达到最大回合数 ({self.max_turns})，进入结果评估。", markers=["RESULT"])
            return True
        if self.stats.should_adjudicate_stalemate():
            self._emit_event("RESULT", "[结果] 对抗进入僵局，提前进入裁决评估。", markers=["RESULT", "STALEMATE"])
            return True
        return False

    def _in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def _control_points(self) -> list[Position]:
        points: list[Position] = []
        for zone in self.scenario.control_zones:
            for x in range(zone.x, zone.x + zone.width):
                for y in range(zone.y, zone.y + zone.height):
                    points.append(Position(x, y))
        return points

    def _priority_zone(self, team: Team) -> Position:
        zones = self.scenario.blue_spawn_zones if team == Team.RED else self.scenario.red_spawn_zones
        if not zones:
            zones = self.scenario.control_zones
        zone = zones[0]
        return Position(zone.x + max(0, zone.width // 2), zone.y + max(0, zone.height // 2))

    def _nearest_control_zone_center(self, team: Team) -> Position:
        if not self.scenario.control_zones:
            return self._priority_zone(team)
        zone = self.scenario.control_zones[0]
        return Position(zone.x + max(0, zone.width // 2), zone.y + max(0, zone.height // 2))

    def _is_controlled_by_enemy(self, agent: AgentState, target: Position) -> bool:
        for effect in self.active_effects:
            if effect.get("type") != "control_zone" or effect.get("team") == agent.team.value:
                continue
            center = Position(effect["center"]["x"], effect["center"]["y"])
            if grid_distance(center, target, self.grid_type) <= effect.get("radius", 1):
                return True
        return False

    def compute_team_visibility(self, team: Team) -> list[list[bool]]:
        visible = [[False] * self.width for _ in range(self.height)]
        for agent in self.agents.values():
            if agent.team != team or not agent.alive:
                continue
            visible[agent.pos.y][agent.pos.x] = True
            effective_vision = max(1, agent.vision_range - (1 if agent.jammed_turns_remaining > 0 else 0))
            from .terrain import concealment_for
            for y in range(self.height):
                for x in range(self.width):
                    pos = Position(x, y)
                    dist = grid_distance(agent.pos, pos, self.grid_type)
                    if dist == 0:
                        continue
                    if dist > effective_vision:
                        continue
                    from .grid_rules import has_line_of_sight
                    if not has_line_of_sight(agent.pos, pos, self.terrain_grid):
                        continue
                    conceal = concealment_for(self._terrain_at(x, y))
                    conceal_penalty = round(conceal * effective_vision)
                    if conceal_penalty > 0 and dist > max(1, effective_vision - conceal_penalty):
                        continue
                    visible[y][x] = True
        return visible

    def _get_all_observations(self) -> dict:
        return {agent_id: self.get_observation(agent_id) for agent_id in self.agents}

    def render(self) -> str:
        role_names_cn = {
            Role.COORDINATOR.value: "协",
            Role.SCOUT.value: "侦",
            Role.ATTACKER.value: "攻",
            Role.DEFENDER.value: "守",
            Role.SUPPORT.value: "援",
            Role.JAMMER.value: "扰",
            Role.CONTROLLER.value: "控",
            Role.ASSAULTER.value: "突",
        }
        terrain_chars = {
            TerrainType.OPEN: ".",
            TerrainType.ROAD: "=",
            TerrainType.FOREST: "f",
            TerrainType.URBAN: "H",
            TerrainType.WATER: "~",
            TerrainType.ROUGH: "^",
            TerrainType.MARSH: "m",
            TerrainType.MOUNTAIN: "M",
        }
        grid = [["·" for _ in range(self.width)] for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                grid[y][x] = terrain_chars.get(self._terrain_at(x, y), ".")
        for agent in self.agents.values():
            if agent.alive:
                grid[agent.pos.y][agent.pos.x] = role_names_cn.get(agent.role.value, "?")
        lines = [f"=== 第 {self.turn} 回合 / 对抗态势 ==="]
        for row in grid:
            lines.append(" ".join(row))
        lines.append("")
        lines.extend(f"  {event}" for event in self.events)
        return "\n".join(lines)
