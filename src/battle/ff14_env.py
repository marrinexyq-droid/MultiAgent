from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .battle_types import Action, ActionType, Position, Skill, Team, TacticalEvent
from .ff14_roster import FF14_JOBS, Ff14Job, fantasy_scenario_config
from .ff14_skills import SKILLS
from .grid_rules import distance as grid_distance, neighbors as hex_neighbors


@dataclass
class Ff14Unit:
    agent_id: str
    team: Team
    job_key: str
    job: Ff14Job
    pos: Position
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    alive: bool = True
    buffs: dict[str, int] = field(default_factory=dict)
    skill_cooldowns: dict[str, int] = field(default_factory=dict)
    remaining_mp: int = 0
    movement_points: int = 6
    has_acted: bool = False
    combo_step: int = 0
    combo_skill_id: str = ""
    last_skill_turn: int = 0
    resources: dict[str, int] = field(default_factory=dict)
    total_damage_dealt: int = 0
    total_damage_taken: int = 0
    total_healing_done: int = 0

    @property
    def attack_power(self) -> int:
        return self.job.attack_power

    @property
    def vision_range(self) -> int:
        return self.job.vision_range

    @property
    def attack_range(self) -> int:
        return self.job.attack_range

    def has_buff(self, buff: str) -> bool:
        return self.buffs.get(buff, 0) > 0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "team": self.team.value,
            "job_key": self.job_key,
            "role_label": self.job.label,
            "icon": self.job.icon,
            "alive": self.alive,
            "pos": {"x": self.pos.x, "y": self.pos.y},
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "attack_power": self.attack_power,
            "vision_range": self.vision_range,
            "attack_range": self.attack_range,
            "movement_points": self.movement_points,
            "remaining_mp": self.remaining_mp,
            "buffs": dict(self.buffs),
            "group": self.job.group,
            "combo_step": self.combo_step,
            "resources": dict(self.resources),
            "total_damage_dealt": self.total_damage_dealt,
            "total_damage_taken": self.total_damage_taken,
            "total_healing_done": self.total_healing_done,
        }


class FantasyEnv:
    def __init__(self, scenario=None):
        sc = scenario or fantasy_scenario_config()
        self.scenario = sc
        self.width = sc.width
        self.height = sc.height
        self.grid_type = "hex"
        self.units: dict[str, Ff14Unit] = {}
        self.turn = 0
        self.max_turns = 80
        self.events: list[str] = []
        self.structured_events: list[TacticalEvent] = []
        self.danger_zones: list[dict] = []
        self.team_lb: dict[str, int] = {"red": 0, "blue": 0}

    def reset(self, red_jobs: list[tuple[str, Position]], blue_jobs: list[tuple[str, Position]]):
        self.units.clear()
        self.turn = 0
        self.events.clear()
        self.structured_events.clear()
        self.danger_zones.clear()
        self.team_lb = {"red": 0, "blue": 0}
        for idx, (job_key, pos) in enumerate(red_jobs, 1):
            job = FF14_JOBS[job_key]
            unit = Ff14Unit(
                agent_id=f"red_{job_key}_{idx}",
                team=Team.RED,
                job_key=job_key,
                job=job,
                pos=pos,
                hp=job.hp,
                max_hp=job.hp,
                mp=100,
                max_mp=100,
                movement_points=job.movement_points,
                remaining_mp=job.movement_points,
            )
            self.units[unit.agent_id] = unit
        for idx, (job_key, pos) in enumerate(blue_jobs, 1):
            job = FF14_JOBS[job_key]
            unit = Ff14Unit(
                agent_id=f"blue_{job_key}_{idx}",
                team=Team.BLUE,
                job_key=job_key,
                job=job,
                pos=pos,
                hp=job.hp,
                max_hp=job.hp,
                mp=100,
                max_mp=100,
                movement_points=job.movement_points,
                remaining_mp=job.movement_points,
            )
            self.units[unit.agent_id] = unit
        self._emit("RESULT", "战斗开始！红蓝双方进入战场", markers=["START"])

    def step(self, actions: list[Action]):
        self.turn += 1
        self.events.clear()
        self.structured_events.clear()
        for unit in self.units.values():
            if unit.alive:
                unit.remaining_mp = unit.movement_points
                unit.has_acted = False
                self._tick_buffs(unit)
                self._tick_cooldowns(unit)
        valid = [a for a in actions if self._valid(a)]
        moves = [a for a in valid if a.action_type == ActionType.MOVE]
        skills = [a for a in valid if a.action_type == ActionType.SKILL]
        for m in moves:
            self._exec_move(m)
        for s in skills:
            self._exec_skill(s)
        # LB gauge: +3 per turn base, +1 per 200 damage taken per unit
        for team_key in ("red", "blue"):
            team_units = [u for u in self.units.values() if u.team.value == team_key]
            for u in team_units:
                if u.alive:
                    self.team_lb[team_key] += 3
            for ev in self.structured_events:
                meta = ev.metadata or {}
                if meta.get("damage") and ev.target_id and ev.target_id in [t.agent_id for t in team_units]:
                    self.team_lb[team_key] += max(1, meta["damage"] // 200)
            self.team_lb[team_key] = min(100, self.team_lb[team_key])
            if self.team_lb[team_key] >= 100:
                self._emit("LB", f"{team_key.upper()} 极限技准备就绪!", markers=["LB"])
        return self._check_done()

    def _valid(self, action: Action) -> bool:
        unit = self.units.get(action.agent_id)
        if not unit or not unit.alive:
            return False
        if action.action_type == ActionType.MOVE:
            if not action.target or not self._in_bounds(action.target):
                return False
            if action.target == unit.pos:
                return True
            cost = 2
            if unit.remaining_mp < cost:
                return False
            for other in self.units.values():
                if other.alive and other.agent_id != unit.agent_id and other.pos == action.target:
                    return False
            return True
        if action.action_type == ActionType.SKILL:
            if not action.skill_id:
                return False
            if unit.skill_cooldowns.get(action.skill_id, 0) > 0:
                return False
            skill = SKILLS.get(action.skill_id)
            if not skill:
                return False
            if skill.target_type == "enemy" and not action.target_id:
                return False
            if skill.target_type == "ally" and not action.target_id:
                return False
            if skill.target_type == "aoe" and not action.target_id and not action.skill_target:
                return False
            return True
        return True

    def _exec_move(self, action: Action):
        unit = self.units[action.agent_id]
        old = unit.pos
        unit.pos = action.target
        unit.remaining_mp -= 2
        self._emit("MOVE", f"{unit.agent_id} ({old.x},{old.y})→({action.target.x},{action.target.y})",
                   actor_id=unit.agent_id, team=unit.team.value, target_position=action.target)

    def _effect_type(self, skill) -> str:
        if skill.heal_power > 0 and skill.base_damage == 0:
            return "heal" if skill.target_type in ("ally", "party") else "attack"
        if skill.buff_type in ("shield", "party_shield"):
            return "shield"
        if skill.buff_type == "defense_up":
            return "defense"
        if skill.buff_type == "damage_up":
            return "buff"
        if skill.buff_type in ("regen",):
            return "regen"
        if skill.target_type == "aoe":
            return "aoe"
        if skill.base_damage >= 40:
            return "big_attack"
        if skill.cooldown >= 5:
            return "ultimate"
        return "attack"

    def _exec_skill(self, action: Action):
        unit = self.units[action.agent_id]
        skill = SKILLS[action.skill_id]
        unit.skill_cooldowns[action.skill_id] = skill.cooldown + 1
        unit.has_acted = True
        effect = self._effect_type(skill)

        # Combo tracking
        from .ff14_skills import COMBOS
        combo_list = COMBOS.get(unit.job_key, [])
        if combo_list:
            if unit.combo_step < len(combo_list) and combo_list[unit.combo_step] == action.skill_id:
                unit.combo_step += 1
                if unit.combo_step >= len(combo_list):
                    unit.combo_step = 0
            else:
                unit.combo_step = 1 if combo_list[0] == action.skill_id else 0
        else:
            unit.combo_step = 0

        # Class resource tracking
        if unit.job_key == "dark_knight" and action.skill_id == "dk_1":
            unit.resources["dark_blood"] = unit.resources.get("dark_blood", 0) + 10
        if unit.job_key == "dark_knight" and action.skill_id == "dk_4" and unit.resources.get("dark_blood", 0) >= 30:
            unit.resources["dark_blood"] -= 30
        if unit.job_key == "monk" and action.skill_id in ("mnk_1", "mnk_2"):
            unit.resources["chakra"] = unit.resources.get("chakra", 0) + 5
        if unit.job_key == "black_mage" and action.skill_id == "blm_1":
            unit.resources["fire_stance"] = min(3, unit.resources.get("fire_stance", 0) + 1)
        if unit.job_key == "black_mage" and action.skill_id == "blm_2":
            unit.resources["fire_stance"] = 0

        if skill.target_type == "self":
            self._apply_buff(unit, skill)
            self._emit("SKILL", f"{unit.agent_id} 使用 {skill.name}",
                       actor_id=unit.agent_id, team=unit.team.value, markers=["SKILL"],
                       metadata={"effect": effect, "skill_name": skill.name})
            return
        if skill.target_type == "enemy" and action.target_id:
            target = self.units.get(action.target_id)
            if target and target.alive:
                dmg = self._calc_damage(unit, skill, target)
                target.hp = max(0, target.hp - dmg)
                unit.total_damage_dealt += dmg
                target.total_damage_taken += dmg
                if skill.heal_power > 0:
                    unit.hp = min(unit.max_hp, unit.hp + skill.heal_power)
                    unit.total_healing_done += skill.heal_power
                self._emit("ATTACK", f"{unit.agent_id} → {action.target_id} {skill.name} 伤害{dmg}",
                           actor_id=unit.agent_id, team=unit.team.value, target_id=action.target_id,
                           target_position=target.pos, markers=["ATTACK"],
                           metadata={"effect": effect, "damage": dmg, "skill_name": skill.name})
                if not target.alive or target.hp <= 0:
                    target.alive = False
                    self._emit("RESULT", f"{action.target_id} 已被击败!", markers=["DOWN"],
                               target_position=target.pos)
        if skill.target_type == "ally" and action.target_id:
            target = self.units.get(action.target_id)
            if target and target.alive:
                heal = skill.heal_power + (unit.job.heal_power or 0)
                target.hp = min(target.max_hp, target.hp + heal)
                unit.total_healing_done += heal
                if skill.buff_type:
                    self._apply_buff(target, skill)
                self._emit("SKILL", f"{unit.agent_id} 对 {action.target_id} 使用 {skill.name} 恢复{heal}HP",
                           actor_id=unit.agent_id, team=unit.team.value, target_id=action.target_id,
                           target_position=target.pos, markers=["SUPPORT"],
                           metadata={"effect": effect, "heal": heal, "skill_name": skill.name})
        if skill.target_type == "party":
            for u in self.units.values():
                if u.team == unit.team and u.alive:
                    if skill.heal_power > 0:
                        u.hp = min(u.max_hp, u.hp + skill.heal_power)
                        unit.total_healing_done += skill.heal_power
                    if skill.buff_type:
                        self._apply_buff(u, skill)
            self._emit("SKILL", f"{unit.agent_id} 使用 {skill.name} 作用于全队",
                       actor_id=unit.agent_id, team=unit.team.value, markers=["SKILL"],
                       metadata={"effect": effect, "skill_name": skill.name})
        if skill.target_type == "aoe":
            center = action.skill_target or (self.units[action.target_id].pos if action.target_id else unit.pos)
            # Emit danger zone warning
            dz_key = f"{center.x},{center.y}"
            if dz_key not in [f"{d['center']['x']},{d['center']['y']}" for d in self.danger_zones]:
                self.danger_zones.append({
                    "center": {"x": center.x, "y": center.y},
                    "radius": skill.aoe_radius,
                    "skill_name": skill.name,
                    "source_team": unit.team.value,
                })
            self._emit("DANGER", f"⚠ {skill.name} 即将降临 ({center.x},{center.y})",
                       actor_id=unit.agent_id, team=unit.team.value, target_position=center,
                       markers=["DANGER"], metadata={"effect": "aoe_pending", "skill_name": skill.name, "radius": skill.aoe_radius})
            for u in self.units.values():
                if u.alive and u.team != unit.team and grid_distance(center, u.pos, "hex") <= skill.aoe_radius:
                    dmg = self._calc_damage(unit, skill, u)
                    u.hp = max(0, u.hp - dmg)
                    unit.total_damage_dealt += dmg
                    u.total_damage_taken += dmg
                    if not u.alive or u.hp <= 0:
                        u.alive = False
                        self._emit("RESULT", f"{u.agent_id} 已被击败!", markers=["DOWN"],
                                   target_position=u.pos)
            self._emit("ATTACK", f"{unit.agent_id} 使用 {skill.name} 范围攻击",
                       actor_id=unit.agent_id, team=unit.team.value, target_position=center,
                       markers=["ATTACK"], metadata={"effect": "aoe", "skill_name": skill.name})

    def _apply_buff(self, target: Ff14Unit, skill: Skill):
        if skill.buff_duration > 0 and skill.buff_type:
            target.buffs[skill.buff_type] = max(target.buffs.get(skill.buff_type, 0), skill.buff_duration + 1)

    def _calc_damage(self, attacker: Ff14Unit, skill: Skill, target: Ff14Unit) -> int:
        base = skill.base_damage + attacker.attack_power
        # Combo bonus: step 3+ = 1.3x, completed cycle = 1.5x
        from .ff14_skills import COMBOS
        cl = COMBOS.get(attacker.job_key, [])
        if cl and len(cl) > 2 and attacker.combo_step >= min(3, len(cl)):
            base = int(base * 1.3)
        if attacker.has_buff("damage_up"):
            base = int(base * 1.3)
        # Class resource bonus
        if attacker.job_key == "black_mage":
            fire_stance = attacker.resources.get("fire_stance", 0)
            if fire_stance >= 3:
                base = int(base * 1.5)
            elif fire_stance >= 2:
                base = int(base * 1.25)
        if attacker.job_key == "monk" and skill.skill_id == "mnk_3" and attacker.resources.get("chakra", 0) >= 10:
            base = int(base * 1.5)
            attacker.resources["chakra"] -= 10
        if attacker.has_buff("crit_up") and random.random() < 0.3:
            base = int(base * 1.5)
        if target.has_buff("vulnerability"):
            base = int(base * 1.2)
        if target.has_buff("defense_up"):
            base = int(base * 0.6)
        if target.has_buff("shield"):
            base = int(base * 0.5)
            target.buffs["shield"] = target.buffs.get("shield", 0) - 1
        return max(1, base + random.randint(-3, 3))

    def _tick_buffs(self, unit: Ff14Unit):
        expired = [k for k, v in unit.buffs.items() if v <= 1]
        for k in expired:
            del unit.buffs[k]
        for k in list(unit.buffs.keys()):
            if k not in expired:
                unit.buffs[k] -= 1

    def _tick_cooldowns(self, unit: Ff14Unit):
        expired = [k for k, v in unit.skill_cooldowns.items() if v <= 1]
        for k in expired:
            del unit.skill_cooldowns[k]
        for k in list(unit.skill_cooldowns.keys()):
            if k not in expired:
                unit.skill_cooldowns[k] -= 1

    def _check_done(self) -> bool:
        red_alive = sum(1 for u in self.units.values() if u.team == Team.RED and u.alive)
        blue_alive = sum(1 for u in self.units.values() if u.team == Team.BLUE and u.alive)
        if red_alive == 0:
            self._emit("RESULT", "蓝队获胜!", team=Team.BLUE.value, markers=["RESULT"])
            return True
        if blue_alive == 0:
            self._emit("RESULT", "红队获胜!", team=Team.RED.value, markers=["RESULT"])
            return True
        if self.turn >= self.max_turns:
            self._emit("RESULT", "平局: 达到最大回合数", markers=["RESULT"])
            return True
        return False

    def _in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def _emit(self, etype: str, summary: str, *, actor_id=None, team=None, target_id=None, target_position=None, markers=None, metadata=None):
        self.events.append(summary)
        self.structured_events.append(TacticalEvent(
            turn=self.turn, type=etype, actor_id=actor_id, team=team,
            target_id=target_id,
            target_position={"x": target_position.x, "y": target_position.y} if isinstance(target_position, Position) else target_position,
            summary=summary, markers=markers or [etype], metadata=metadata or {},
        ))
