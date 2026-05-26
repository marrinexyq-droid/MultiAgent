export type TeamKey = "red" | "blue";
export type GridType = "square" | "hex";
export type TerrainType = "open" | "road" | "forest" | "urban" | "water" | "rough" | "marsh" | "mountain";

export interface TerrainCell {
  type: TerrainType;
  elevation?: number;
}

export type RoleKey =
  | "coordinator"
  | "scout"
  | "attacker"
  | "defender"
  | "support"
  | "jammer"
  | "controller"
  | "assaulter";

export interface RectZone {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ScenarioConfig {
  width: number;
  height: number;
  grid_type?: GridType;
  red_spawn_zones: RectZone[];
  blue_spawn_zones: RectZone[];
  control_zones: RectZone[];
  terrain_grid?: TerrainCell[][];
  terrain_preset?: string;
}

export interface RoleTemplate {
  role: RoleKey;
  group: "core_combat" | "command_support" | "special_tactics";
  label: string;
  description: string;
  ui_hint: string;
  effect_key: string;
  recommended_count: string;
  hp: number;
  ammo: number;
  vision_range: number;
  attack_range: number;
  attack_power: number;
  move_speed: number;
  skill_name: string;
  skill_description: string;
  skill_cooldown: number;
  bounds: Record<string, [number, number]>;
  defaults: {
    task_priority: number;
    target_preference: string;
    risk_preference: number;
    coordination_preference: number;
    mobility_bias: number;
    hold_bias: number;
    skill_trigger_threshold: number;
  };
  target_preference_options: string[];
}

export interface TeamRoleConfig {
  count: number;
  hp: number;
  ammo: number;
  vision_range: number;
  attack_power: number;
  move_speed: number;
  task_priority: number;
  target_preference: string;
  risk_preference: number;
  coordination_preference: number;
  mobility_bias: number;
  hold_bias: number;
  skill_trigger_threshold: number;
}

export type TeamConfigPayload = Record<TeamKey, Record<RoleKey, TeamRoleConfig>>;

export interface SelectedZoneRef {
  team: TeamKey | "control";
  index: number;
}

export type BattlePanelTab = TeamKey;

export interface RolesResponse {
  default_max_turns: number;
  roles: Record<RoleKey, RoleTemplate>;
  default_team_config: Record<TeamKey, Record<RoleKey, TeamRoleConfig>>;
  default_scenario_config: ScenarioConfig;
  default_hex_scenario_config?: ScenarioConfig;
  terrain_presets?: Record<string, { label: string; description: string }>;
}

export interface BattleFrame {
  turn: number;
  mode: string;
  phase: string;
  status: string;
  events: string[];
  events_structured: Array<{
    turn: number;
    type: string;
    actor_id?: string | null;
    team?: TeamKey | null;
    target_id?: string | null;
    target_position?: { x: number; y: number } | null;
    summary: string;
    markers: string[];
    metadata: Record<string, unknown>;
  }>;
  timeline_markers: Array<{
    id: string;
    turn: number;
    type: string;
    label: string;
    actor_id?: string | null;
    target_id?: string | null;
    target_position?: { x: number; y: number } | null;
    summary: string;
  }>;
  map: {
    width: number;
    height: number;
    grid_type?: GridType;
    grid_size: number;
    cells: (null | {
      agent_id: string;
      team: TeamKey;
      role: RoleKey;
      role_label: string;
      label: string;
    })[][];
    terrain: TerrainCell[][] | null;
    visibility?: Record<TeamKey, boolean[][]>;
    control_points: { x: number; y: number }[];
    control_zones: RectZone[];
    red_spawn_zones: RectZone[];
    blue_spawn_zones: RectZone[];
    effects: Array<Record<string, unknown>>;
  };
  units: Array<{
    agent_id: string;
    team: TeamKey;
    role: RoleKey;
    role_label: string;
    alive: boolean;
    pos: { x: number; y: number };
    hp: number;
    max_hp: number;
    ammo: number;
    max_ammo: number;
    vision_range: number;
    attack_range: number;
    attack_power: number;
    move_speed: number;
    movement_points: number;
    remaining_mp: number;
    task_priority: number;
    target_preference: string;
    risk_preference: number;
    coordination_preference: number;
    mobility_bias: number;
    hold_bias: number;
    skill_trigger_threshold: number;
    skill_name: string;
    skill_description: string;
    skill_cooldown_remaining: number;
    exposed_turns_remaining: number;
    jammed_turns_remaining: number;
    control_zone_turns_remaining: number;
    stealth_turns_remaining: number;
    effect_radius: number;
    status_flags: string[];
  }>;
  effect_details: Array<{
    effect_type: string;
    skill_name: string;
    source_id?: string;
    target_ids: string[];
    target_positions: Array<{ x: number; y: number }>;
    duration_remaining: number;
    impact_summary: string;
  }>;
  memory: Record<TeamKey, {
    summary: {
      primary_threat?: string | null;
      active_tasks?: number;
      recommended_focus?: string;
      memory_health?: string;
      risk_zone_count?: number;
      [key: string]: unknown;
    };
    beliefs: Array<{
      target_id?: string;
      last_known_position?: { x?: number; y?: number };
      hp_estimate?: number;
      trend?: string;
      threat_level?: string;
      confidence_score?: number;
      last_seen_turn?: number;
      [key: string]: unknown;
    }>;
    tasks: Array<{
      task_id?: string;
      task?: string;
      status?: string;
      assignee?: string;
      assigner?: string;
      target_id?: string;
      target_position?: { x?: number; y?: number };
      confidence?: number;
      updated_turn?: number;
      [key: string]: unknown;
    }>;
    risk_zones: Array<{
      zone_key?: string;
      reason?: string;
      reporter?: string;
      confidence?: number;
      timestamp?: number;
      [key: string]: unknown;
    }>;
    jammed_zones: Array<Record<string, unknown>>;
    control_blocks: Array<Record<string, unknown>>;
    support_links: Array<Record<string, unknown>>;
    engage_targets: Array<Record<string, unknown>>;
    observations: Array<{
      obs_type?: string;
      target_id?: string;
      source_agent_id?: string;
      position?: { x?: number; y?: number };
      confidence?: number;
      timestamp?: number;
      [key: string]: unknown;
    }>;
  }>;
  advice_items: Array<{
    priority: string;
    target_team: TeamKey;
    target_role: RoleKey;
    action: string;
    reason: string;
    reason_text: string;
    evidence_text: string;
    rendered_text: string;
    turn: number;
  }>;
}
