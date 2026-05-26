from dataclasses import dataclass

from .battle_types import AgentState, Position, RectZone, Role, ScenarioConfig, Team, TerrainCell, TerrainType
from .agents.generic import GenericRoleAgent
from .terrain import generate_terrain


ROLE_LABELS = {
    Role.COORDINATOR: "协调",
    Role.SCOUT: "侦察",
    Role.ATTACKER: "攻击手",
    Role.DEFENDER: "防御手",
    Role.SUPPORT: "支援",
    Role.JAMMER: "干扰",
    Role.CONTROLLER: "控制",
    Role.ASSAULTER: "突击",
}


@dataclass(frozen=True)
class RoleTemplate:
    role: Role
    group: str
    label: str
    description: str
    ui_hint: str
    effect_key: str
    recommended_count: str
    hp: int
    ammo: int
    vision_range: int
    attack_range: int
    attack_power: int
    move_speed: int
    movement_points: int
    skill_name: str
    skill_description: str
    skill_cooldown: int
    hp_bounds: tuple[int, int]
    ammo_bounds: tuple[int, int]
    vision_bounds: tuple[int, int]
    attack_bounds: tuple[int, int]
    speed_bounds: tuple[int, int]
    task_priority: int
    target_preference: str
    risk_preference: int
    coordination_preference: int
    mobility_bias: int
    hold_bias: int
    skill_trigger_threshold: int
    preference_bounds: tuple[int, int] = (0, 100)
    target_preference_options: tuple[str, ...] = ("balanced", "frontline", "backline", "marked", "control")


ROLE_TEMPLATES: dict[Role, RoleTemplate] = {
    Role.COORDINATOR: RoleTemplate(
        role=Role.COORDINATOR,
        group="command_support",
        label="协调",
        description="信息聚合与任务分配，适合作为编队核心。",
        ui_hint="提升局部协同效率",
        effect_key="coordination_pulse",
        recommended_count="1-2",
        hp=105,
        ammo=5,
        vision_range=3,
        attack_range=1,
        attack_power=16,
        move_speed=6,
        movement_points=6,
        skill_name="协同脉冲",
        skill_description="强化周边友军的任务响应与集火倾向，降低行动冲突。",
        skill_cooldown=4,
        hp_bounds=(80, 130),
        ammo_bounds=(3, 6),
        vision_bounds=(2, 4),
        attack_bounds=(10, 22),
        speed_bounds=(4, 8),
        task_priority=85,
        target_preference="control",
        risk_preference=35,
        coordination_preference=95,
        mobility_bias=40,
        hold_bias=55,
        skill_trigger_threshold=45,
    ),
    Role.SCOUT: RoleTemplate(
        role=Role.SCOUT,
        group="core_combat",
        label="侦察",
        description="远视野，高情报获取，负责发现关键目标。",
        ui_hint="生存弱，需避免正面接触",
        effect_key="scan_pulse",
        recommended_count="1-2",
        hp=78,
        ammo=4,
        vision_range=5,
        attack_range=1,
        attack_power=10,
        move_speed=10,
        movement_points=10,
        skill_name="强化扫描",
        skill_description="扩大临时视野并揭示高价值目标，便于队友锁定。",
        skill_cooldown=3,
        hp_bounds=(60, 100),
        ammo_bounds=(2, 5),
        vision_bounds=(4, 7),
        attack_bounds=(8, 18),
        speed_bounds=(7, 14),
        task_priority=70,
        target_preference="backline",
        risk_preference=25,
        coordination_preference=55,
        mobility_bias=85,
        hold_bias=15,
        skill_trigger_threshold=35,
    ),
    Role.ATTACKER: RoleTemplate(
        role=Role.ATTACKER,
        group="core_combat",
        label="攻击手",
        description="高输出，主力突破，适合快速压制暴露目标。",
        ui_hint="依赖情报与协同",
        effect_key="fireline",
        recommended_count="1-3",
        hp=96,
        ammo=4,
        vision_range=3,
        attack_range=1,
        attack_power=34,
        move_speed=7,
        movement_points=7,
        skill_name="集火强袭",
        skill_description="对已暴露或被标记目标造成更高打击并强化集火。",
        skill_cooldown=3,
        hp_bounds=(80, 120),
        ammo_bounds=(2, 5),
        vision_bounds=(2, 4),
        attack_bounds=(24, 42),
        speed_bounds=(5, 10),
        task_priority=80,
        target_preference="marked",
        risk_preference=60,
        coordination_preference=75,
        mobility_bias=45,
        hold_bias=20,
        skill_trigger_threshold=50,
    ),
    Role.DEFENDER: RoleTemplate(
        role=Role.DEFENDER,
        group="core_combat",
        label="防御手",
        description="高生存，稳住阵线，守点与护卫能力强。",
        ui_hint="适合维持局部安全区",
        effect_key="shield_ring",
        recommended_count="1-3",
        hp=126,
        ammo=5,
        vision_range=3,
        attack_range=1,
        attack_power=22,
        move_speed=5,
        movement_points=5,
        skill_name="护卫固守",
        skill_description="提升区域防御和减伤，保护附近关键单位。",
        skill_cooldown=4,
        hp_bounds=(105, 150),
        ammo_bounds=(3, 6),
        vision_bounds=(2, 4),
        attack_bounds=(16, 28),
        speed_bounds=(3, 7),
        task_priority=75,
        target_preference="frontline",
        risk_preference=35,
        coordination_preference=65,
        mobility_bias=20,
        hold_bias=90,
        skill_trigger_threshold=40,
    ),
    Role.SUPPORT: RoleTemplate(
        role=Role.SUPPORT,
        group="command_support",
        label="支援",
        description="维持续航与状态恢复，优先保障关键单位。",
        ui_hint="适合中后场跟随支援",
        effect_key="repair_beam",
        recommended_count="1-2",
        hp=88,
        ammo=6,
        vision_range=3,
        attack_range=1,
        attack_power=8,
        move_speed=6,
        movement_points=6,
        skill_name="修复补给",
        skill_description="恢复友军状态值与资源，延长持续作战能力。",
        skill_cooldown=3,
        hp_bounds=(70, 110),
        ammo_bounds=(4, 8),
        vision_bounds=(2, 4),
        attack_bounds=(4, 14),
        speed_bounds=(4, 8),
        task_priority=65,
        target_preference="backline",
        risk_preference=20,
        coordination_preference=80,
        mobility_bias=35,
        hold_bias=40,
        skill_trigger_threshold=35,
    ),
    Role.JAMMER: RoleTemplate(
        role=Role.JAMMER,
        group="special_tactics",
        label="干扰",
        description="扰乱观测与协同，可制造误判和延迟。",
        ui_hint="适合打乱对手节奏",
        effect_key="jam_pulse",
        recommended_count="0-2",
        hp=84,
        ammo=5,
        vision_range=4,
        attack_range=1,
        attack_power=9,
        move_speed=7,
        movement_points=7,
        skill_name="链路干扰",
        skill_description="降低敌方记忆置信度与协同效率，制造信息噪波。",
        skill_cooldown=4,
        hp_bounds=(70, 105),
        ammo_bounds=(3, 6),
        vision_bounds=(3, 5),
        attack_bounds=(5, 14),
        speed_bounds=(5, 10),
        task_priority=60,
        target_preference="backline",
        risk_preference=30,
        coordination_preference=70,
        mobility_bias=50,
        hold_bias=35,
        skill_trigger_threshold=40,
    ),
    Role.CONTROLLER: RoleTemplate(
        role=Role.CONTROLLER,
        group="special_tactics",
        label="控制",
        description="限制敌方移动与执行，擅长封锁关键区域。",
        ui_hint="适合阵地与控点战",
        effect_key="control_zone",
        recommended_count="1-2",
        hp=102,
        ammo=5,
        vision_range=3,
        attack_range=2,
        attack_power=18,
        move_speed=6,
        movement_points=6,
        skill_name="封锁场",
        skill_description="生成封锁或减速区域，限制敌方推进与转移。",
        skill_cooldown=4,
        hp_bounds=(85, 125),
        ammo_bounds=(3, 6),
        vision_bounds=(2, 4),
        attack_bounds=(12, 24),
        speed_bounds=(4, 8),
        task_priority=70,
        target_preference="control",
        risk_preference=45,
        coordination_preference=60,
        mobility_bias=25,
        hold_bias=85,
        skill_trigger_threshold=45,
    ),
    Role.ASSAULTER: RoleTemplate(
        role=Role.ASSAULTER,
        group="special_tactics",
        label="突击",
        description="高机动，高风险高收益，擅长切后排与破局。",
        ui_hint="依赖时机与情报支持",
        effect_key="dash_trail",
        recommended_count="0-2",
        hp=82,
        ammo=4,
        vision_range=3,
        attack_range=1,
        attack_power=28,
        move_speed=9,
        movement_points=9,
        skill_name="破阵闪击",
        skill_description="快速切入后排并对高价值目标形成爆发压制。",
        skill_cooldown=4,
        hp_bounds=(65, 100),
        ammo_bounds=(2, 5),
        vision_bounds=(2, 4),
        attack_bounds=(20, 36),
        speed_bounds=(6, 12),
        task_priority=75,
        target_preference="backline",
        risk_preference=80,
        coordination_preference=55,
        mobility_bias=90,
        hold_bias=10,
        skill_trigger_threshold=55,
    ),
}


DEFAULT_TEAM_LAYOUT = {
    Team.RED: {
        Role.COORDINATOR: {"count": 1},
        Role.SCOUT: {"count": 1},
        Role.ATTACKER: {"count": 1},
        Role.DEFENDER: {"count": 0},
        Role.SUPPORT: {"count": 0},
        Role.JAMMER: {"count": 0},
        Role.CONTROLLER: {"count": 0},
        Role.ASSAULTER: {"count": 1},
    },
    Team.BLUE: {
        Role.COORDINATOR: {"count": 1},
        Role.SCOUT: {"count": 0},
        Role.ATTACKER: {"count": 0},
        Role.DEFENDER: {"count": 2},
        Role.SUPPORT: {"count": 1},
        Role.JAMMER: {"count": 0},
        Role.CONTROLLER: {"count": 1},
        Role.ASSAULTER: {"count": 0},
    },
}


def default_scenario_config(
    width: int = 8,
    height: int = 8,
    grid_type: str = "square",
    terrain_preset: str = "plains",
) -> ScenarioConfig:
    return ScenarioConfig(
        width=width,
        height=height,
        red_spawn_zones=[RectZone(0, 0, min(3, width), height)],
        blue_spawn_zones=[RectZone(max(0, width - min(3, width)), 0, min(3, width), height)],
        control_zones=[RectZone(max(1, width // 2 - 1), max(1, height // 2 - 1), min(2, width), min(2, height))],
        grid_type="hex" if grid_type == "hex" else "square",
        terrain_grid=generate_terrain(terrain_preset, width, height),
    )


def default_team_config() -> dict[Team, dict[Role, dict]]:
    result: dict[Team, dict[Role, dict]] = {}
    for team, role_map in DEFAULT_TEAM_LAYOUT.items():
        result[team] = {}
        for role, defaults in role_map.items():
            template = ROLE_TEMPLATES[role]
            result[team][role] = {
                "count": defaults["count"],
                "hp": template.hp,
                "ammo": template.ammo,
                "vision_range": template.vision_range,
                "attack_power": template.attack_power,
                "move_speed": template.movement_points,
                "task_priority": template.task_priority,
                "target_preference": template.target_preference,
                "risk_preference": template.risk_preference,
                "coordination_preference": template.coordination_preference,
                "mobility_bias": template.mobility_bias,
                "hold_bias": template.hold_bias,
                "skill_trigger_threshold": template.skill_trigger_threshold,
            }
    return result


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(bounds[1], int(value)))


def _normalize_zones(raw_zones: list[dict] | None, width: int, height: int, fallback: list[RectZone]) -> list[RectZone]:
    if not raw_zones:
        return fallback
    zones: list[RectZone] = []
    for raw in raw_zones:
        x = max(0, min(width - 1, int(raw.get("x", 0))))
        y = max(0, min(height - 1, int(raw.get("y", 0))))
        zone_width = max(1, min(width - x, int(raw.get("width", 1))))
        zone_height = max(1, min(height - y, int(raw.get("height", 1))))
        zones.append(RectZone(x, y, zone_width, zone_height))
    return zones or fallback


def normalize_scenario_config(payload: dict | None) -> ScenarioConfig:
    if not payload:
        return default_scenario_config()
    width = max(6, min(24, int(payload.get("width", 8))))
    height = max(6, min(24, int(payload.get("height", 8))))
    grid_type = "hex" if payload.get("grid_type") == "hex" else "square"
    terrain_preset = payload.get("terrain_preset", "plains") or "plains"
    fallback = default_scenario_config(width, height, grid_type=grid_type, terrain_preset=terrain_preset)
    return ScenarioConfig(
        width=width,
        height=height,
        red_spawn_zones=_normalize_zones(payload.get("red_spawn_zones"), width, height, fallback.red_spawn_zones),
        blue_spawn_zones=_normalize_zones(payload.get("blue_spawn_zones"), width, height, fallback.blue_spawn_zones),
        control_zones=_normalize_zones(payload.get("control_zones"), width, height, fallback.control_zones),
        grid_type=grid_type,
        terrain_grid=fallback.terrain_grid,
    )


def normalize_team_config(payload: dict | None) -> dict[Team, dict[Role, dict]]:
    base = default_team_config()
    if not payload:
        return base
    for team in (Team.RED, Team.BLUE):
        raw_team = payload.get(team.value, {})
        for role, template in ROLE_TEMPLATES.items():
            raw_role = raw_team.get(role.value, {})
            base[team][role] = {
                "count": max(0, int(raw_role.get("count", base[team][role]["count"]))),
                "hp": _clamp(raw_role.get("hp", base[team][role]["hp"]), template.hp_bounds),
                "ammo": _clamp(raw_role.get("ammo", base[team][role]["ammo"]), template.ammo_bounds),
                "vision_range": _clamp(raw_role.get("vision_range", base[team][role]["vision_range"]), template.vision_bounds),
                "attack_power": _clamp(raw_role.get("attack_power", base[team][role]["attack_power"]), template.attack_bounds),
                "move_speed": _clamp(raw_role.get("move_speed", base[team][role]["move_speed"]), template.speed_bounds),
                "task_priority": _clamp(raw_role.get("task_priority", base[team][role]["task_priority"]), template.preference_bounds),
                "target_preference": raw_role.get("target_preference", base[team][role]["target_preference"])
                if raw_role.get("target_preference", base[team][role]["target_preference"]) in template.target_preference_options
                else template.target_preference,
                "risk_preference": _clamp(raw_role.get("risk_preference", base[team][role]["risk_preference"]), template.preference_bounds),
                "coordination_preference": _clamp(raw_role.get("coordination_preference", base[team][role]["coordination_preference"]), template.preference_bounds),
                "mobility_bias": _clamp(raw_role.get("mobility_bias", base[team][role]["mobility_bias"]), template.preference_bounds),
                "hold_bias": _clamp(raw_role.get("hold_bias", base[team][role]["hold_bias"]), template.preference_bounds),
                "skill_trigger_threshold": _clamp(raw_role.get("skill_trigger_threshold", base[team][role]["skill_trigger_threshold"]), template.preference_bounds),
            }
    return base


def _spawn_positions(zones: list[RectZone], total: int) -> list[Position]:
    positions: list[Position] = []
    for zone in zones:
        for x in range(zone.x, zone.x + zone.width):
            for y in range(zone.y, zone.y + zone.height):
                positions.append(Position(x, y))
    if total > len(positions):
        raise ValueError(f"当前出生区仅支持 {len(positions)} 个单位，无法容纳 {total} 个单位")
    return positions[:total]


def _build_state(team: Team, role: Role, index: int, position: Position, config: dict) -> AgentState:
    template = ROLE_TEMPLATES[role]
    hp = _clamp(config["hp"], template.hp_bounds)
    ammo = _clamp(config["ammo"], template.ammo_bounds)
    vision_range = _clamp(config["vision_range"], template.vision_bounds)
    attack_power = _clamp(config["attack_power"], template.attack_bounds)
    move_speed_val = _clamp(config["move_speed"], template.speed_bounds)
    target_preference = config.get("target_preference", template.target_preference)
    if target_preference not in template.target_preference_options:
        target_preference = template.target_preference
    agent_id = f"{team.value}_{role.value}_{index}"
    return AgentState(
        agent_id=agent_id,
        team=team,
        role=role,
        pos=position,
        hp=hp,
        max_hp=hp,
        ammo=ammo,
        max_ammo=ammo,
        vision_range=vision_range,
        attack_range=template.attack_range,
        attack_power=attack_power,
        move_speed=move_speed_val,
        movement_points=move_speed_val,
        remaining_mp=move_speed_val,
        task_priority=_clamp(config.get("task_priority", template.task_priority), template.preference_bounds),
        target_preference=target_preference,
        risk_preference=_clamp(config.get("risk_preference", template.risk_preference), template.preference_bounds),
        coordination_preference=_clamp(config.get("coordination_preference", template.coordination_preference), template.preference_bounds),
        mobility_bias=_clamp(config.get("mobility_bias", template.mobility_bias), template.preference_bounds),
        hold_bias=_clamp(config.get("hold_bias", template.hold_bias), template.preference_bounds),
        skill_trigger_threshold=_clamp(config.get("skill_trigger_threshold", template.skill_trigger_threshold), template.preference_bounds),
        skill_name=template.skill_name,
        skill_description=template.skill_description,
        skill_cooldown=template.skill_cooldown,
    )


def _build_agent(state: AgentState):
    return GenericRoleAgent(state)


def build_agents_from_team_config(
    team_config: dict[Team, dict[Role, dict]],
    scenario_config: ScenarioConfig | None = None,
) -> tuple[dict[str, object], list[AgentState], list[AgentState]]:
    scenario = scenario_config or default_scenario_config()
    red_specs = team_config.get(Team.RED, {})
    blue_specs = team_config.get(Team.BLUE, {})

    red_total = sum(max(0, spec.get("count", 0)) for spec in red_specs.values())
    blue_total = sum(max(0, spec.get("count", 0)) for spec in blue_specs.values())
    if red_total == 0 or blue_total == 0:
        raise ValueError("红蓝双方至少各需要 1 个单位")

    red_positions = _spawn_positions(scenario.red_spawn_zones, red_total)
    blue_positions = _spawn_positions(scenario.blue_spawn_zones, blue_total)

    red_states: list[AgentState] = []
    blue_states: list[AgentState] = []
    red_index_map = {role: 1 for role in Role}
    blue_index_map = {role: 1 for role in Role}

    red_pos_cursor = 0
    for role in ROLE_TEMPLATES:
        spec = red_specs.get(role, {"count": 0})
        for _ in range(max(0, spec.get("count", 0))):
            state = _build_state(Team.RED, role, red_index_map[role], red_positions[red_pos_cursor], spec)
            red_states.append(state)
            red_index_map[role] += 1
            red_pos_cursor += 1

    blue_pos_cursor = 0
    for role in ROLE_TEMPLATES:
        spec = blue_specs.get(role, {"count": 0})
        for _ in range(max(0, spec.get("count", 0))):
            state = _build_state(Team.BLUE, role, blue_index_map[role], blue_positions[blue_pos_cursor], spec)
            blue_states.append(state)
            blue_index_map[role] += 1
            blue_pos_cursor += 1

    agents = {}
    for state in red_states + blue_states:
        agents[state.agent_id] = _build_agent(state)

    return agents, red_states, blue_states
