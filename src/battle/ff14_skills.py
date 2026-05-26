from .battle_types import Skill

COMBOS: dict[str, list[str]] = {
    "dark_knight": ["dk_1", "dk_3", "dk_1", "dk_4"],
    "warrior":     ["wr_1", "wr_4", "wr_2"],
    "dragoon":     ["drg_1", "drg_2", "drg_1", "drg_4"],
    "monk":        ["mnk_1", "mnk_2", "mnk_3"],
    "black_mage":  ["blm_1", "blm_1", "blm_1", "blm_4"],
    "bard":        ["brd_1", "brd_2", "brd_1", "brd_4"],
}

SKILLS: dict[str, Skill] = {
    # ── 暗黑骑士 (Dark Knight) ──
    "dk_1": Skill("dk_1", "暗黑波动", "范围暗属性攻击，附加仇恨", target_type="aoe", base_damage=250, aoe_radius=1, cooldown=2),
    "dk_2": Skill("dk_2", "深恶痛绝", "大幅减少自身受到的伤害", target_type="self", buff_duration=2, buff_type="defense_up", cooldown=4),
    "dk_3": Skill("dk_3", "吸血深渊", "攻击敌人并恢复HP", target_type="enemy", base_damage=350, heal_power=200, cooldown=3),
    "dk_4": Skill("dk_4", "暗黑布道", "为全体友方提供减伤", target_type="party", buff_duration=2, buff_type="party_defense", cooldown=5),
    "dk_5": Skill("dk_5", "死寂", "免疫控制效果", target_type="self", buff_duration=1, buff_type="cc_immune", cooldown=6),

    # ── 战士 (Warrior) ──
    "wr_1": Skill("wr_1", "战嚎", "嘲讽目标，强制攻击自己", target_type="enemy", base_damage=150, cooldown=2),
    "wr_2": Skill("wr_2", "原初之魂", "高伤害攻击，附加吸血", target_type="enemy", base_damage=500, heal_power=150, cooldown=3),
    "wr_3": Skill("wr_3", "复仇", "受到攻击时反击伤害", target_type="self", buff_duration=2, buff_type="thorns", cooldown=4),
    "wr_4": Skill("wr_4", "暴风斩", "范围物理攻击", target_type="aoe", base_damage=300, aoe_radius=1, cooldown=2),
    "wr_5": Skill("wr_5", "死斗", "锁定HP不低于1", target_type="self", buff_duration=1, buff_type="undying", cooldown=7),

    # ── 龙骑士 (Dragoon) ──
    "drg_1": Skill("drg_1", "龙枪", "直线穿刺攻击", target_type="enemy", base_damage=400, cooldown=1),
    "drg_2": Skill("drg_2", "跳跃", "跳向目标造成伤害并返回", target_type="enemy", base_damage=550, cooldown=3),
    "drg_3": Skill("drg_3", "龙眼", "提升自身暴击率", target_type="self", buff_duration=2, buff_type="crit_up", cooldown=3),
    "drg_4": Skill("drg_4", "天龙点睛", "终结技，高额单体伤害", target_type="enemy", base_damage=900, cooldown=5),

    # ── 武僧 (Monk) ──
    "mnk_1": Skill("mnk_1", "连击", "基础攻击，连击后伤害递增", target_type="enemy", base_damage=300, cooldown=0),
    "mnk_2": Skill("mnk_2", "正拳", "高伤害单体攻击", target_type="enemy", base_damage=450, cooldown=1),
    "mnk_3": Skill("mnk_3", "崩拳", "强攻击并附加dot", target_type="enemy", base_damage=380, debuff_duration=2, buff_type="bleed", cooldown=2),
    "mnk_4": Skill("mnk_4", "斗气爆发", "提升自身攻击力", target_type="self", buff_duration=3, buff_type="damage_up", cooldown=4),

    # ── 黑魔导士 (Black Mage) ──
    "blm_1": Skill("blm_1", "火炎", "基础火系攻击", target_type="enemy", base_damage=380, cooldown=0),
    "blm_2": Skill("blm_2", "冰结", "冰系攻击，减速目标", target_type="enemy", base_damage=250, debuff_duration=2, buff_type="slow", cooldown=1),
    "blm_3": Skill("blm_3", "暴雷", "高伤害雷系攻击", target_type="enemy", base_damage=650, cooldown=2),
    "blm_4": Skill("blm_4", "火炎爆", "范围火系伤害", target_type="aoe", base_damage=500, aoe_radius=1, cooldown=3),
    "blm_5": Skill("blm_5", "核爆", "终极毁灭魔法", target_type="aoe", base_damage=1200, aoe_radius=1, cooldown=6),

    # ── 诗人 (Bard) ──
    "brd_1": Skill("brd_1", "连射", "远程箭矢攻击", target_type="enemy", base_damage=300, cooldown=0),
    "brd_2": Skill("brd_2", "毒咬箭", "附加持续伤害", target_type="enemy", base_damage=200, debuff_duration=3, buff_type="poison", cooldown=2),
    "brd_3": Skill("brd_3", "旅神之歌", "提升全队攻击力", target_type="party", buff_duration=3, buff_type="party_attack", cooldown=4),
    "brd_4": Skill("brd_4", "失意", "高暴击远程射击", target_type="enemy", base_damage=500, cooldown=2),
    "brd_5": Skill("brd_5", "极限技", "全队大幅强化", target_type="party", buff_duration=2, buff_type="party_burst", cooldown=7),

    # ── 白魔导士 (White Mage) ──
    "whm_1": Skill("whm_1", "治疗", "回复友方HP", target_type="ally", heal_power=600, cooldown=0),
    "whm_2": Skill("whm_2", "救疗", "大量回复HP", target_type="ally", heal_power=1000, cooldown=2),
    "whm_3": Skill("whm_3", "医济", "范围持续回复", target_type="party", heal_power=300, buff_duration=3, buff_type="regen", cooldown=4),
    "whm_4": Skill("whm_4", "神圣", "范围光属性伤害+眩晕", target_type="aoe", base_damage=350, aoe_radius=1, cooldown=3),
    "whm_5": Skill("whm_5", "天赐祝福", "将目标HP回满", target_type="ally", heal_power=99999, cooldown=6),

    # ── 学者 (Scholar) ──
    "sch_1": Skill("sch_1", "鼓舞", "为友方叠加护盾", target_type="ally", heal_power=300, buff_duration=2, buff_type="shield", cooldown=1),
    "sch_2": Skill("sch_2", "士气高扬", "范围护盾", target_type="party", heal_power=200, buff_duration=2, buff_type="party_shield", cooldown=3),
    "sch_3": Skill("sch_3", "不屈", "立即范围治疗", target_type="party", heal_power=400, cooldown=2),
    "sch_4": Skill("sch_4", "连环计", "标记目标受到额外伤害", target_type="enemy", base_damage=100, debuff_duration=2, buff_type="vulnerability", cooldown=4),
    "sch_5": Skill("sch_5", "召炎", "召唤小精灵辅助攻击", target_type="enemy", base_damage=200, buff_duration=3, buff_type="pet", cooldown=5),
}
