from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TerrainType(Enum):
    OPEN = "open"
    ROAD = "road"
    FOREST = "forest"
    URBAN = "urban"
    WATER = "water"
    ROUGH = "rough"
    MARSH = "marsh"
    MOUNTAIN = "mountain"


@dataclass
class TerrainCell:
    type: TerrainType = TerrainType.OPEN
    elevation: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "elevation": self.elevation,
        }


class Role(Enum):
    COORDINATOR = "coordinator"
    COMMANDER = "coordinator"
    SCOUT = "scout"
    ATTACKER = "attacker"
    DEFENDER = "defender"
    SUPPORT = "support"
    JAMMER = "jammer"
    CONTROLLER = "controller"
    ASSAULTER = "assaulter"


class Team(Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class RectZone:
    x: int
    y: int
    width: int
    height: int

    def contains(self, pos: "Position") -> bool:
        return self.x <= pos.x < self.x + self.width and self.y <= pos.y < self.y + self.height

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class ScenarioConfig:
    width: int
    height: int
    red_spawn_zones: list[RectZone]
    blue_spawn_zones: list[RectZone]
    control_zones: list[RectZone]
    grid_type: str = "square"
    terrain_grid: list[list[TerrainCell]] | None = None

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "grid_type": self.grid_type,
            "red_spawn_zones": [zone.to_dict() for zone in self.red_spawn_zones],
            "blue_spawn_zones": [zone.to_dict() for zone in self.blue_spawn_zones],
            "control_zones": [zone.to_dict() for zone in self.control_zones],
            "terrain_grid": [[cell.to_dict() for cell in row] for row in self.terrain_grid] if self.terrain_grid else None,
        }

    def get_terrain(self, x: int, y: int) -> TerrainType:
        if self.terrain_grid and 0 <= y < len(self.terrain_grid) and 0 <= x < len(self.terrain_grid[y]):
            return self.terrain_grid[y][x].type
        return TerrainType.OPEN


@dataclass
class TacticalEvent:
    turn: int
    type: str
    actor_id: Optional[str] = None
    team: Optional[str] = None
    target_id: Optional[str] = None
    target_position: Optional[dict] = None
    summary: str = ""
    markers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "type": self.type,
            "actor_id": self.actor_id,
            "team": self.team,
            "target_id": self.target_id,
            "target_position": self.target_position,
            "summary": self.summary,
            "markers": self.markers,
            "metadata": self.metadata,
        }


class ActionType(Enum):
    MOVE = "move"
    HOLD = "hold"
    SCOUT = "scout"
    ATTACK = "attack"
    SKILL = "skill"
    COMMUNICATE = "communicate"


@dataclass
class Position:
    x: int
    y: int

    def distance_to(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def __eq__(self, other):
        if not isinstance(other, Position):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))


@dataclass
class AgentState:
    agent_id: str
    team: Team
    role: Role
    pos: Position
    hp: int = 100
    max_hp: int = 100
    ammo: int = 5
    max_ammo: int = 5
    vision_range: int = 2
    attack_range: int = 1
    attack_power: int = 25
    move_speed: int = 1
    movement_points: int = 0
    remaining_mp: int = 0
    task_priority: int = 50
    target_preference: str = "balanced"
    risk_preference: int = 50
    coordination_preference: int = 50
    mobility_bias: int = 50
    hold_bias: int = 50
    skill_trigger_threshold: int = 50
    skill_name: str = ""
    skill_description: str = ""
    skill_cooldown: int = 0
    skill_cooldown_remaining: int = 0
    defense_bonus: float = 0.0
    defense_bonus_turns: int = 0
    effect_radius: int = 0
    effect_turns_remaining: int = 0
    exposed_turns_remaining: int = 0
    jammed_turns_remaining: int = 0
    control_zone_turns_remaining: int = 0
    stealth_turns_remaining: int = 0
    rally_target: Optional["Position"] = None
    rally_turns_remaining: int = 0
    alive: bool = True

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "team": self.team.value,
            "role": self.role.value,
            "pos": {"x": self.pos.x, "y": self.pos.y},
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ammo": self.ammo,
            "max_ammo": self.max_ammo,
            "vision_range": self.vision_range,
            "attack_range": self.attack_range,
            "attack_power": self.attack_power,
            "move_speed": self.move_speed,
            "movement_points": self.movement_points or self.move_speed * 3,
            "task_priority": self.task_priority,
            "target_preference": self.target_preference,
            "risk_preference": self.risk_preference,
            "coordination_preference": self.coordination_preference,
            "mobility_bias": self.mobility_bias,
            "hold_bias": self.hold_bias,
            "skill_trigger_threshold": self.skill_trigger_threshold,
            "skill_name": self.skill_name,
            "skill_description": self.skill_description,
            "skill_cooldown": self.skill_cooldown,
            "skill_cooldown_remaining": self.skill_cooldown_remaining,
            "defense_bonus": self.defense_bonus,
            "defense_bonus_turns": self.defense_bonus_turns,
            "effect_radius": self.effect_radius,
            "effect_turns_remaining": self.effect_turns_remaining,
            "exposed_turns_remaining": self.exposed_turns_remaining,
            "jammed_turns_remaining": self.jammed_turns_remaining,
            "control_zone_turns_remaining": self.control_zone_turns_remaining,
            "stealth_turns_remaining": self.stealth_turns_remaining,
            "rally_target": {"x": self.rally_target.x, "y": self.rally_target.y} if self.rally_target else None,
            "rally_turns_remaining": self.rally_turns_remaining,
            "alive": self.alive,
        }


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    cooldown: int = 3
    target_type: str = "enemy"
    base_damage: int = 0
    heal_power: int = 0
    buff_duration: int = 0
    debuff_duration: int = 0
    buff_type: str = ""
    aoe_radius: int = 0
    mp_cost: int = 0

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "cooldown": self.cooldown,
            "target_type": self.target_type,
            "base_damage": self.base_damage,
            "heal_power": self.heal_power,
            "buff_duration": self.buff_duration,
            "buff_type": self.buff_type,
            "aoe_radius": self.aoe_radius,
            "mp_cost": self.mp_cost,
        }


@dataclass
class Action:
    agent_id: str
    action_type: ActionType
    target: Optional[Position] = None
    target_id: Optional[str] = None
    skill_id: Optional[str] = None
    skill_target: Optional[Position] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "agent_id": self.agent_id,
            "action_type": self.action_type.value,
        }
        if self.target:
            result["target"] = {"x": self.target.x, "y": self.target.y}
        if self.target_id:
            result["target_id"] = self.target_id
        if self.skill_id:
            result["skill_id"] = self.skill_id
        if self.skill_target:
            result["skill_target"] = {"x": self.skill_target.x, "y": self.skill_target.y}
        if self.message:
            result["message"] = self.message
        return result


@dataclass
class Message:
    msg_id: str
    sender_id: str
    sender_role: Role
    content: dict
    timestamp: int
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }
