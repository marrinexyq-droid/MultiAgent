from dataclasses import dataclass, field

from .battle_types import Position, RectZone, Role, Team, ScenarioConfig


@dataclass(frozen=True)
class Ff14Job:
    role: str
    label: str
    icon: str
    group: str
    hp: int
    attack_power: int
    heal_power: int
    vision_range: int
    attack_range: int
    movement_points: int
    description: str
    skill_ids: list[str]


FF14_JOBS: dict[str, Ff14Job] = {
    "dark_knight": Ff14Job(
        role="dark_knight", label="暗黑骑士", icon="🛡", group="mt",
        hp=10000, attack_power=300, heal_power=0,
        vision_range=2, attack_range=1, movement_points=5,
        description="暗黑骑士，使用暗黑之力守护队友",
        skill_ids=["dk_1", "dk_2", "dk_3", "dk_4", "dk_5"],
    ),
    "warrior": Ff14Job(
        role="warrior", label="战士", icon="⚔", group="st",
        hp=9000, attack_power=350, heal_power=0,
        vision_range=2, attack_range=1, movement_points=5,
        description="战士，以狂暴战意撕碎敌人",
        skill_ids=["wr_1", "wr_2", "wr_3", "wr_4", "wr_5"],
    ),
    "dragoon": Ff14Job(
        role="dragoon", label="龙骑士", icon="🐉", group="dps",
        hp=6000, attack_power=450, heal_power=0,
        vision_range=3, attack_range=2, movement_points=8,
        description="龙骑士，驾驭龙族之力跳跃突袭",
        skill_ids=["drg_1", "drg_2", "drg_3", "drg_4"],
    ),
    "monk": Ff14Job(
        role="monk", label="武僧", icon="👊", group="dps",
        hp=6200, attack_power=480, heal_power=0,
        vision_range=2, attack_range=1, movement_points=9,
        description="武僧，以连击技压制对手",
        skill_ids=["mnk_1", "mnk_2", "mnk_3", "mnk_4"],
    ),
    "black_mage": Ff14Job(
        role="black_mage", label="黑魔导士", icon="🔮", group="dps",
        hp=4800, attack_power=550, heal_power=0,
        vision_range=4, attack_range=3, movement_points=5,
        description="黑魔导士，掌控毁灭之力远程轰炸",
        skill_ids=["blm_1", "blm_2", "blm_3", "blm_4", "blm_5"],
    ),
    "bard": Ff14Job(
        role="bard", label="诗人", icon="🎵", group="dps",
        hp=5200, attack_power=350, heal_power=0,
        vision_range=4, attack_range=3, movement_points=6,
        description="诗人，以歌声鼓舞队友削弱敌人",
        skill_ids=["brd_1", "brd_2", "brd_3", "brd_4", "brd_5"],
    ),
    "white_mage": Ff14Job(
        role="white_mage", label="白魔导士", icon="✨", group="healer",
        hp=5500, attack_power=120, heal_power=800,
        vision_range=3, attack_range=2, movement_points=5,
        description="白魔导士，以神圣之力治愈万物",
        skill_ids=["whm_1", "whm_2", "whm_3", "whm_4", "whm_5"],
    ),
    "scholar": Ff14Job(
        role="scholar", label="学者", icon="📖", group="healer",
        hp=5500, attack_power=100, heal_power=700,
        vision_range=3, attack_range=2, movement_points=5,
        description="学者，以计谋布阵护佑团队",
        skill_ids=["sch_1", "sch_2", "sch_3", "sch_4", "sch_5"],
    ),
}

FANTASY_TEAM_LAYOUT = {
    Team.RED: {
        "dark_knight": 1, "warrior": 1,
        "dragoon": 1, "monk": 1,
        "black_mage": 1, "bard": 1,
        "white_mage": 1, "scholar": 1,
    },
    Team.BLUE: {
        "dark_knight": 1, "warrior": 1,
        "dragoon": 1, "monk": 1,
        "black_mage": 1, "bard": 1,
        "white_mage": 1, "scholar": 1,
    },
}


def fantasy_scenario_config() -> ScenarioConfig:
    return ScenarioConfig(
        width=12,
        height=10,
        red_spawn_zones=[RectZone(0, 0, 4, 10)],
        blue_spawn_zones=[RectZone(8, 0, 4, 10)],
        control_zones=[RectZone(5, 4, 2, 2)],
        grid_type="hex",
    )
