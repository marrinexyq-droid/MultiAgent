import json
import random
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..battle_types import Action, ActionType, Position
from ..config import config
from ..ff14_skills import SKILLS, COMBOS

GROUP_STRATEGY = {
    "mt": "你是MT(主坦克)。职责: 拉住敌人仇恨,保护队友。优先使用防御技能和仇恨技能。",
    "st": "你是ST(副坦克)。职责: 辅助MT,吸引多余敌人。使用减伤和范围攻击。",
    "dps": "你是DPS(输出)。职责: 最大化伤害输出。优先攻击低血量敌人,使用爆发技能。",
    "healer": "你是Healer(治疗)。职责: 保持团队血量。优先治疗低血量队友,适时使用护盾。",
}


class Ff14Agent:
    def __init__(self, unit):
        self.unit = unit
        self.client = self._build_client()
        self.turn_count = 0

    def _build_client(self) -> Any:
        if not config.api_key or OpenAI is None:
            return None
        return OpenAI(api_key=config.api_key, base_url=config.api_base_url)

    def choose_action(self, obs: dict) -> Action:
        self.turn_count = obs.get("turn", 0)
        try:
            return self._rule_action(obs)
        except Exception:
            return Action(self.unit.agent_id, ActionType.HOLD)

    def _llm_action(self, obs: dict) -> Action:
        prompt = self._build_prompt(obs)
        try:
            import httpx
            http_client = httpx.Client(timeout=8)
            client = OpenAI(api_key=config.api_key, base_url=config.api_base_url, http_client=http_client)
            resp = client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": "你是一个魔幻战斗AI。只输出JSON,不要其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=200,
            )
            text = resp.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            if data.get("action") == "skill":
                sid = data.get("skill_id", "")
                tid = data.get("target_id", "")
                return Action(self.unit.agent_id, ActionType.SKILL, skill_id=sid, target_id=tid)
            if data.get("action") == "move":
                t = data.get("target", {})
                return Action(self.unit.agent_id, ActionType.MOVE, target=Position(t.get("x", 0), t.get("y", 0)))
            return Action(self.unit.agent_id, ActionType.HOLD)
        except Exception:
            return self._rule_action(obs)

    def _build_prompt(self, obs: dict) -> str:
        me = obs.get("self", {})
        job_name = me.get("role_label", "未知")
        group = me.get("group", "dps")
        strategy = GROUP_STRATEGY.get(group, "")
        skills_text = "\n".join(
            f"  - {s['name']}(ID:{s['id']}): {s['description']}" for s in me.get("available_skills", [])
        ) or "  无可用技能（全部冷却中）"
        allies_text = "\n".join(
            f"  {a['agent_id']} {a['role_label']} HP {a['hp']}/{a['max_hp']} @({a['pos']['x']},{a['pos']['y']})"
            for a in obs.get("allies", [])
        ) or "  无"
        enemies_text = "\n".join(
            f"  {e['agent_id']} {e['role_label']} HP {e['hp']}/{e['max_hp']} @({e['pos']['x']},{e['pos']['y']})"
            for e in obs.get("enemies", [])
        ) or "  无"

        return f"""你是{job_name}({group})。
{strategy}

你的属性:
  HP {me.get('hp',0)}/{me.get('max_hp',0)}
  MP {me.get('mp',0)}
  位置 ({me.get('pos',{}).get('x',0)},{me.get('pos',{}).get('y',0)})
  Buffs: {', '.join(me.get('buffs',{}).keys()) or '无'}

可用技能:
{skills_text}

友方:
{allies_text}

敌方:
{enemies_text}

请选择行动,以JSON格式返回:
攻击敌人: {{"action":"skill","skill_id":"dk_1","target_id":"blue_warrior_1"}}
治疗队友: {{"action":"skill","skill_id":"whm_1","target_id":"red_dragoon_1"}}
防御: {{"action":"skill","skill_id":"dk_2"}}
移动: {{"action":"move","target":{{"x":4,"y":5}}}}
待命: {{"action":"hold"}}"""

    def _nearest_enemy(self, me: dict, enemies: list) -> dict | None:
        if not enemies:
            return None
        return min(enemies, key=lambda e: grid_dist(Position(me["pos"]["x"], me["pos"]["y"]), Position(e["pos"]["x"], e["pos"]["y"])))

    def _move_toward(self, me: dict, target: dict) -> Position | None:
        mx, my = me["pos"]["x"], me["pos"]["y"]
        tx, ty = target["pos"]["x"], target["pos"]["y"]
        dx = tx - mx
        dy = ty - my
        nx = mx + (1 if dx > 0 else -1 if dx < 0 else 0)
        ny = my + (1 if dy > 0 else -1 if dy < 0 else 0)
        if (nx, ny) != (mx, my) and 0 <= nx <= 11 and 0 <= ny <= 9:
            return Position(nx, ny)
        return None

    def _move_away(self, me: dict, target: dict) -> Position | None:
        mx, my = me["pos"]["x"], me["pos"]["y"]
        tx, ty = target["pos"]["x"], target["pos"]["y"]
        dx = mx - tx
        dy = my - ty
        nx = mx + (1 if dx > 0 else -1 if dx < 0 else 0)
        ny = my + (1 if dy > 0 else -1 if dy < 0 else 0)
        if (nx, ny) != (mx, my) and 0 <= nx <= 11 and 0 <= ny <= 9:
            return Position(nx, ny)
        return None

    def _retreat_pos(self, me: dict, enemies: list) -> Position | None:
        near = self._nearest_enemy(me, enemies)
        if not near:
            return None
        return self._move_away(me, near)

    def _needs_reposition(self, me: dict, enemies: list, group: str) -> bool:
        """Only return True if significantly out of position (don't waste turns on tiny adjustments)"""
        if not enemies:
            return False
        near = self._nearest_enemy(me, enemies)
        if not near:
            return False
        dist = grid_dist(Position(me["pos"]["x"], me["pos"]["y"]), Position(near["pos"]["x"], near["pos"]["y"]))
        if group in ("mt", "st"):
            return dist > 3  # If enemy is far, move closer
        is_melee = self.unit.job_key in ("dragoon", "monk")
        desired = 2 if is_melee else 4
        if group == "dps":
            return dist > desired + 2 or (dist < desired - 2 and not is_melee)
        if group == "healer":
            return dist < 2 or dist > 6
        return False

    def _do_reposition(self, me: dict, enemies: list, group: str) -> Action | None:
        near = self._nearest_enemy(me, enemies)
        if not near:
            return None
        dist = grid_dist(Position(me["pos"]["x"], me["pos"]["y"]), Position(near["pos"]["x"], near["pos"]["y"]))
        if group in ("mt", "st"):
            pos = self._move_toward(me, near)
            if pos: return Action(self.unit.agent_id, ActionType.MOVE, target=pos)
        is_melee = self.unit.job_key in ("dragoon", "monk")
        if is_melee:
            pos = self._move_toward(me, near)
            if pos: return Action(self.unit.agent_id, ActionType.MOVE, target=pos)
        if dist < 2:
            pos = self._move_away(me, near)
            if pos: return Action(self.unit.agent_id, ActionType.MOVE, target=pos)
        if group == "healer" and dist > 5:
            pos = self._move_toward(me, near)
            if pos: return Action(self.unit.agent_id, ActionType.MOVE, target=pos)
        return None

    def _rule_action(self, obs: dict) -> Action:
        me = obs.get("self", {})
        enemies = obs.get("enemies", [])
        allies = obs.get("allies", [])
        skills = me.get("available_skills", [])
        group = me.get("group", "dps")
        hp_pct = me.get("hp", 1) / max(1, me.get("max_hp", 1))

        if not enemies:
            return Action(self.unit.agent_id, ActionType.HOLD)

        # 站位维护 - 只在明显偏离位置时移动
        if self._needs_reposition(me, enemies, group):
            pos_action = self._do_reposition(me, enemies, group)
            if pos_action:
                return pos_action

        # 低血量后撤
        if hp_pct < 0.3 and group in ("dps", "healer"):
            retreat = self._retreat_pos(me, enemies)
            if retreat:
                return Action(self.unit.agent_id, ActionType.MOVE, target=retreat)

        if group == "healer":
            # 治疗自己如果 HP 太低
            if hp_pct < 0.4:
                heal_self = [s for s in skills if SKILLS.get(s["id"]) and SKILLS[s["id"]].heal_power > 0]
                if heal_self:
                    return Action(self.unit.agent_id, ActionType.SKILL, skill_id=heal_self[0]["id"], target_id=me["agent_id"])
            hurt = [a for a in allies if a["hp"] < a["max_hp"] * 0.7]
            if hurt:
                target = min(hurt, key=lambda a: a["hp"] / a["max_hp"])
                heal_skills = [s for s in skills if SKILLS.get(s["id"]) and SKILLS[s["id"]].heal_power > 0]
                if heal_skills:
                    return Action(self.unit.agent_id, ActionType.SKILL, skill_id=heal_skills[0]["id"], target_id=target["agent_id"])
                shield_skills = [s for s in skills if SKILLS.get(s["id"]) and SKILLS[s["id"]].buff_type in ("shield", "party_shield")]
                if shield_skills:
                    return Action(self.unit.agent_id, ActionType.SKILL, skill_id=shield_skills[0]["id"], target_id=target["agent_id"])

        if group in ("mt", "st"):
            if hp_pct < 0.4:
                def_skills = [s for s in skills if SKILLS.get(s["id"]) and SKILLS[s["id"]].buff_type == "defense_up"]
                if def_skills:
                    return Action(self.unit.agent_id, ActionType.SKILL, skill_id=def_skills[0]["id"])
            nearest = self._nearest_enemy(me, enemies)
            if nearest:
                combo = COMBOS.get(self.unit.job_key, [])
                combo_skill = combo[self.unit.combo_step] if self.unit.combo_step < len(combo) else None
                if combo_skill and self.unit.skill_cooldowns.get(combo_skill, 0) == 0:
                    return Action(self.unit.agent_id, ActionType.SKILL, skill_id=combo_skill, target_id=nearest["agent_id"])
                atk_skills = [s for s in skills if SKILLS.get(s["id"]) and SKILLS[s["id"]].base_damage > 0]
                if atk_skills:
                    return Action(self.unit.agent_id, ActionType.SKILL, skill_id=atk_skills[0]["id"], target_id=nearest["agent_id"])

        # DPS: 智能选目标，优先杀治疗 > 低血 > 近
        if group == "dps":
            close_allies = [a for a in allies if grid_dist(Position(me["pos"]["x"], me["pos"]["y"]), Position(a["pos"]["x"], a["pos"]["y"])) <= 1]
            if close_allies:
                retreat = self._retreat_pos(me, enemies)
                if retreat:
                    return Action(self.unit.agent_id, ActionType.MOVE, target=retreat)

            def target_score(e: dict) -> int:
                s = 0
                if e.get("group") == "healer": s += 30
                hp_p = e["hp"] / max(1, e["max_hp"])
                if hp_p < 0.3: s += 25
                elif hp_p < 0.5: s += 15
                dist = grid_dist(Position(me["pos"]["x"], me["pos"]["y"]), Position(e["pos"]["x"], e["pos"]["y"]))
                if dist <= 2: s += 10
                elif dist <= 4: s += 5
                return s
            target = max(enemies, key=target_score)
        elif group in ("mt", "st"):
            target = self._nearest_enemy(me, enemies)
        else:
            target = min(enemies, key=lambda e: e["hp"])

        if target:
            # Prefer combo skill if available
            combo = COMBOS.get(self.unit.job_key, [])
            combo_skill = combo[self.unit.combo_step] if self.unit.combo_step < len(combo) else None
            if combo_skill and self.unit.skill_cooldowns.get(combo_skill, 0) == 0:
                skill_id = combo_skill
            else:
                atk = [s for s in skills if SKILLS.get(s["id"]) and SKILLS[s["id"]].base_damage > 0]
                skill_id = atk[0]["id"] if atk else None
            if skill_id:
                return Action(self.unit.agent_id, ActionType.SKILL, skill_id=skill_id, target_id=target["agent_id"])
        return Action(self.unit.agent_id, ActionType.HOLD)


def grid_dist(a: Position, b: Position) -> int:
    aq = a.x - (a.y - (a.y & 1)) // 2
    bq = b.x - (b.y - (b.y & 1)) // 2
    return int((abs(aq - bq) + abs(aq + a.y - bq - b.y) + abs(a.y - b.y)) / 2)


def build_obs(unit, env) -> dict:
    enemies = []
    allies = []
    for u in env.units.values():
        if not u.alive:
            continue
        entry = {
            "agent_id": u.agent_id, "role_label": u.job.label, "group": u.job.group,
            "hp": u.hp, "max_hp": u.max_hp, "mp": u.mp,
            "pos": {"x": u.pos.x, "y": u.pos.y},
        }
        if u.team != unit.team:
            enemies.append(entry)
        elif u.agent_id != unit.agent_id:
            allies.append(entry)

    available = []
    for sid in unit.job.skill_ids:
        if unit.skill_cooldowns.get(sid, 0) == 0:
            skill = SKILLS.get(sid)
            if skill:
                available.append({
                    "id": sid, "name": skill.name,
                    "description": skill.description,
                    "type": skill.target_type,
                    "damage": skill.base_damage,
                    "heal": skill.heal_power,
                })

    return {
        "turn": env.turn,
        "self": {
            "agent_id": unit.agent_id, "role_label": unit.job.label,
            "group": unit.job.group, "hp": unit.hp, "max_hp": unit.max_hp,
            "mp": unit.mp, "pos": {"x": unit.pos.x, "y": unit.pos.y},
            "buffs": dict(unit.buffs),
            "available_skills": available,
        },
        "allies": allies,
        "enemies": enemies,
    }
