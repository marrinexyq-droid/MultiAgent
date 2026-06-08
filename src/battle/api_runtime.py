from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .battle_types import Message, Position, Role, Team, TerrainCell
from .config import config
from .grid_rules import distance as grid_distance
from .terrain import TERRAIN_PRESETS
from .judge import BattleJudge
from .memory import SharedMemoryPool
from .runtime_advice import build_advice_items, record_visible_enemy_contacts
from .storage import BattleStorage
from .roster import (
    ROLE_LABELS,
    ROLE_TEMPLATES,
    build_agents_from_team_config,
    default_scenario_config,
    default_team_config,
    normalize_team_config,
    normalize_scenario_config,
)

TEAM_ORDER = [Team.RED, Team.BLUE]
ROLE_ORDER = list(ROLE_TEMPLATES.keys())


def serialize_role_templates() -> dict[str, dict[str, Any]]:
    return {
        role.value: {
            "role": role.value,
            "label": template.label,
            "description": template.description,
            "ui_hint": template.ui_hint,
            "effect_key": template.effect_key,
            "group": template.group,
            "recommended_count": template.recommended_count,
            "hp": template.hp,
            "ammo": template.ammo,
            "vision_range": template.vision_range,
            "attack_range": template.attack_range,
            "attack_power": template.attack_power,
            "move_speed": template.movement_points,
            "movement_points": template.movement_points,
            "skill_name": template.skill_name,
            "skill_description": template.skill_description,
            "skill_cooldown": template.skill_cooldown,
            "bounds": {
                "hp": list(template.hp_bounds),
                "ammo": list(template.ammo_bounds),
                "vision_range": list(template.vision_bounds),
                "attack_power": list(template.attack_bounds),
                "move_speed": list(template.speed_bounds),
                "preference": list(template.preference_bounds),
            },
            "defaults": {
                "task_priority": template.task_priority,
                "target_preference": template.target_preference,
                "risk_preference": template.risk_preference,
                "coordination_preference": template.coordination_preference,
                "mobility_bias": template.mobility_bias,
                "hold_bias": template.hold_bias,
                "skill_trigger_threshold": template.skill_trigger_threshold,
            },
            "target_preference_options": list(template.target_preference_options),
        }
        for role, template in ROLE_TEMPLATES.items()
    }


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value


def serialize_default_team_config() -> dict[str, dict[str, dict[str, int]]]:
    team_config = default_team_config()
    return {
        team.value: {
            role.value: {
                "count": spec["count"],
                "hp": spec["hp"],
                "ammo": spec["ammo"],
                "vision_range": spec["vision_range"],
                "attack_power": spec["attack_power"],
                "move_speed": spec["move_speed"],
                "movement_points": spec["move_speed"],
                "task_priority": spec["task_priority"],
                "target_preference": spec["target_preference"],
                "risk_preference": spec["risk_preference"],
                "coordination_preference": spec["coordination_preference"],
                "mobility_bias": spec["mobility_bias"],
                "hold_bias": spec["hold_bias"],
                "skill_trigger_threshold": spec["skill_trigger_threshold"],
            }
            for role, spec in team_config[team].items()
        }
        for team in TEAM_ORDER
    }


def serialize_default_scenario_config() -> dict[str, Any]:
    return default_scenario_config(config.grid_size, config.grid_size).to_dict()


def serialize_default_hex_scenario_config(terrain_preset: str = "plains") -> dict[str, Any]:
    return default_scenario_config(10, 8, grid_type="hex", terrain_preset=terrain_preset).to_dict()


def _memory_view_for_team(team: Team, env, memory_pool: SharedMemoryPool) -> dict:
    alive_agent = next((agent for agent in env.agents.values() if agent.team == team and agent.alive), None)
    agent_id = alive_agent.agent_id if alive_agent else f"{team.value}_viewer"
    return memory_pool.read(agent_id)


def _serialize_map(env) -> dict[str, Any]:
    cells = []
    for y in range(env.height):
        row = []
        for x in range(env.width):
            agent = next(
                (current for current in env.agents.values() if current.alive and current.pos.x == x and current.pos.y == y),
                None,
            )
            if agent is None:
                row.append(None)
            else:
                row.append(
                    {
                        "agent_id": agent.agent_id,
                        "team": agent.team.value,
                        "role": agent.role.value,
                        "role_label": ROLE_LABELS.get(agent.role, agent.role.value),
                        "label": agent.agent_id.split("_")[-1],
                    }
                )
        cells.append(row)
    terrain_data = None
    if env.terrain_grid:
        terrain_data = []
        for y in range(env.height):
            trow = []
            for x in range(env.width):
                if y < len(env.terrain_grid) and x < len(env.terrain_grid[y]):
                    tc = env.terrain_grid[y][x]
                    if isinstance(tc, TerrainCell):
                        trow.append(tc.to_dict())
                    else:
                        trow.append({"type": "open", "elevation": 0})
                else:
                    trow.append({"type": "open", "elevation": 0})
            terrain_data.append(trow)
    visibility = None
    if hasattr(env, 'compute_team_visibility'):
        from .battle_types import Team
        try:
            visibility = {
                "red": env.compute_team_visibility(Team.RED),
                "blue": env.compute_team_visibility(Team.BLUE),
            }
        except Exception:
            visibility = None
    return {
        "width": env.width,
        "height": env.height,
        "grid_size": env.grid_size,
        "grid_type": getattr(env, "grid_type", "square"),
        "cells": cells,
        "terrain": terrain_data,
        "visibility": visibility,
        "control_points": [{"x": point.x, "y": point.y} for point in env._control_points()],
        "control_zones": [zone.to_dict() for zone in env.scenario.control_zones],
        "red_spawn_zones": [zone.to_dict() for zone in env.scenario.red_spawn_zones],
        "blue_spawn_zones": [zone.to_dict() for zone in env.scenario.blue_spawn_zones],
        "effects": list(env.active_effects),
    }


def _serialize_structured_events(env) -> list[dict[str, Any]]:
    return [event.to_dict() for event in env.structured_events]


def _serialize_timeline_markers(env) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for index, event in enumerate(env.structured_events):
        marker_set = event.markers or [event.type]
        markers.append(
            {
                "id": f"{env.turn}-{index}-{event.type.lower()}",
                "turn": event.turn,
                "type": event.type,
                "label": marker_set[0],
                "actor_id": event.actor_id,
                "target_id": event.target_id,
                "target_position": event.target_position,
                "summary": event.summary,
            }
        )
    return markers


def _serialize_units(env) -> list[dict[str, Any]]:
    items = []
    for agent in env.agents.values():
        status_flags: list[str] = []
        if agent.exposed_turns_remaining > 0:
            status_flags.append("exposed")
        if agent.jammed_turns_remaining > 0:
            status_flags.append("jammed")
        if agent.defense_bonus_turns > 0 or agent.defense_bonus > 0:
            status_flags.append("guarded")
        if agent.stealth_turns_remaining > 0:
            status_flags.append("engaging")
        if any(effect.get("type") == "support_link" and effect.get("target_id") == agent.agent_id for effect in env.active_effects):
            status_flags.append("supported")
        if any(effect.get("type") == "control_zone" and _effect_covers(effect, agent.pos.x, agent.pos.y, getattr(env, "grid_type", "square")) and effect.get("team") != agent.team.value for effect in env.active_effects):
            status_flags.append("blocked")
        if any(event.type in {"ATTACK", "ENGAGE", "SPOT"} and event.target_id == agent.agent_id for event in env.structured_events):
            status_flags.append("locked")
        items.append(
            {
                "agent_id": agent.agent_id,
                "team": agent.team.value,
                "role": agent.role.value,
                "role_label": ROLE_LABELS.get(agent.role, agent.role.value),
                "alive": agent.alive,
                "pos": {"x": agent.pos.x, "y": agent.pos.y},
                "hp": agent.hp,
                "max_hp": agent.max_hp,
                "ammo": agent.ammo,
                "max_ammo": agent.max_ammo,
                "attack_range": agent.attack_range,
                "attack_power": agent.attack_power,
                "vision_range": agent.vision_range,
                "move_speed": agent.move_speed,
                "movement_points": agent.movement_points,
                "remaining_mp": agent.remaining_mp,
                "task_priority": agent.task_priority,
                "target_preference": agent.target_preference,
                "risk_preference": agent.risk_preference,
                "coordination_preference": agent.coordination_preference,
                "mobility_bias": agent.mobility_bias,
                "hold_bias": agent.hold_bias,
                "skill_trigger_threshold": agent.skill_trigger_threshold,
                "skill_name": agent.skill_name,
                "skill_cooldown_remaining": agent.skill_cooldown_remaining,
                "exposed_turns_remaining": agent.exposed_turns_remaining,
                "jammed_turns_remaining": agent.jammed_turns_remaining,
                "control_zone_turns_remaining": agent.control_zone_turns_remaining,
                "stealth_turns_remaining": agent.stealth_turns_remaining,
                "effect_radius": agent.effect_radius,
                "skill_description": agent.skill_description,
                "status_flags": status_flags,
            }
        )
    return items


def _effect_covers(effect: dict[str, Any], x: int, y: int, grid_type: str = "square") -> bool:
    center = effect.get("center")
    if not center:
        return False
    radius = int(effect.get("radius", 0))
    return grid_distance(Position(center["x"], center["y"]), Position(x, y), grid_type) <= radius


def _serialize_effect_details(env) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for effect in env.active_effects:
        details.append(
            {
                "effect_type": effect.get("type"),
                "skill_name": effect.get("skill_name", ""),
                "source_id": effect.get("source_id"),
                "target_ids": [effect.get("target_id")] if effect.get("target_id") else list(effect.get("affected_ids", [])),
                "target_positions": [effect.get("center")] if effect.get("center") else [],
                "duration_remaining": effect.get("turns_remaining", 0),
                "impact_summary": effect.get("impact_summary", ""),
            }
        )
    for event in env.structured_events:
        if event.type not in {"TASK", "SPOT", "BLOCK", "JAM", "ENGAGE"}:
            continue
        details.append(
            {
                "effect_type": event.type.lower(),
                "skill_name": event.metadata.get("effect", event.type),
                "source_id": event.actor_id,
                "target_ids": [event.target_id] if event.target_id else [item.get("agent_id") for item in event.metadata.get("targets", []) if item.get("agent_id")],
                "target_positions": [event.target_position] if event.target_position else [item.get("pos") for item in event.metadata.get("targets", []) if item.get("pos")],
                "duration_remaining": 1,
                "impact_summary": event.metadata.get("impact_summary", event.summary),
            }
        )
    unique: list[dict[str, Any]] = []
    seen = set()
    for detail in details:
        key = (
            detail.get("effect_type"),
            detail.get("skill_name"),
            detail.get("source_id"),
            tuple(detail.get("target_ids", [])),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(detail)
    return unique


def _serialize_memory(memory_view: dict, env=None, team: Team | None = None) -> dict[str, Any]:
    beliefs = []
    for target_id, belief in memory_view.get("beliefs", {}).items():
        beliefs.append({"target_id": target_id, **belief})
    tasks = []
    for task_id, task in memory_view.get("tasks", {}).items():
        tasks.append({"task_id": task_id, **task})
    risk_zones = []
    for zone_key, zone in memory_view.get("risk_zones", {}).items():
        risk_zones.append({"zone_key": zone_key, **zone})
    jammed_zones = []
    control_blocks = []
    support_links = []
    engage_targets = []
    if env is not None and team is not None:
        for effect in env.active_effects:
            zone_payload = {
                "source_id": effect.get("source_id"),
                "target_id": effect.get("target_id"),
                "center": effect.get("center"),
                "radius": effect.get("radius", 0),
                "turns_remaining": effect.get("turns_remaining", 0),
            }
            if effect.get("type") == "jam_zone" and effect.get("team") != team.value:
                jammed_zones.append(zone_payload)
            if effect.get("type") == "control_zone":
                control_blocks.append({**zone_payload, "team": effect.get("team")})
            if effect.get("type") == "support_link" and effect.get("team") == team.value:
                support_links.append(zone_payload)
        for event in env.structured_events:
            if event.type == "ENGAGE" and event.team == team.value:
                engage_targets.append(
                    {
                        "actor_id": event.actor_id,
                        "target_id": event.target_id,
                        "target_position": event.target_position,
                    }
                )
    summary = dict(memory_view.get("summary", {}))
    if jammed_zones:
        summary["memory_health"] = "jammed" if summary.get("memory_health") != "fresh" else "degrading"
    summary["jammed_zone_count"] = len(jammed_zones)
    summary["control_block_count"] = len(control_blocks)
    summary["support_link_count"] = len(support_links)
    summary["engage_target_count"] = len(engage_targets)
    return {
        "summary": summary,
        "beliefs": beliefs,
        "tasks": tasks,
        "risk_zones": risk_zones,
        "jammed_zones": jammed_zones,
        "control_blocks": control_blocks,
        "support_links": support_links,
        "engage_targets": engage_targets,
        "observations": memory_view.get("observations", []),
    }


def _llm_mode_enabled(agents: dict[str, Any] | None = None) -> bool:
    if agents:
        return any(getattr(agent, "client", None) is not None for agent in agents.values())
    return bool(config.api_key)


def capture_structured_frame(
    env,
    mode_label: str,
    phase_label: str,
    memory_red: SharedMemoryPool,
    memory_blue: SharedMemoryPool,
    *,
    llm_decision_traces: list[dict[str, Any]] | None = None,
    llm_mode_enabled: bool | None = None,
) -> dict[str, Any]:
    red_view = _memory_view_for_team(Team.RED, env, memory_red)
    blue_view = _memory_view_for_team(Team.BLUE, env, memory_blue)
    visibility_red = env.compute_team_visibility(Team.RED) if hasattr(env, 'compute_team_visibility') else None
    visibility_blue = env.compute_team_visibility(Team.BLUE) if hasattr(env, 'compute_team_visibility') else None
    return {
        "turn": env.turn,
        "mode": mode_label,
        "phase": phase_label,
        "status": phase_label,
        "events": list(env.events),
        "events_structured": _serialize_structured_events(env),
        "timeline_markers": _serialize_timeline_markers(env),
        "map": _serialize_map(env),
        "units": _serialize_units(env),
        "effect_details": _serialize_effect_details(env),
        "memory": {
            "red": _serialize_memory(red_view, env=env, team=Team.RED),
            "blue": _serialize_memory(blue_view, env=env, team=Team.BLUE),
        },
        "advice_items": build_advice_items(env, memory_red, memory_blue),
        "llm_mode_enabled": bool(llm_mode_enabled) if llm_mode_enabled is not None else _llm_mode_enabled(),
        "llm_decision_traces": llm_decision_traces or [],
    }


def _build_actions(agents, env, memory_red, memory_blue, turn: int):
    actions = []
    llm_decision_traces: list[dict[str, Any]] = []
    for agent_id, agent in agents.items():
        if not agent.state.alive:
            continue
        obs = env.get_observation(agent_id)
        if not obs:
            continue
        shared_mem = memory_red.read(agent_id) if agent.state.team == Team.RED else memory_blue.read(agent_id)
        action = agent.choose_action(obs, shared_mem)
        actions.append(action)
        if getattr(agent, "client", None) is not None and getattr(agent, "last_llm_trace", None):
            trace = dict(agent.last_llm_trace)
            trace["turn"] = turn
            trace["team"] = agent.state.team.value
            trace["role"] = agent.state.role.value
            trace["decision_action_type"] = action.action_type.value
            llm_decision_traces.append(trace)
        if action.action_type.value == "communicate":
            try:
                content = json.loads(action.message)
                msg_content = content if isinstance(content, dict) else {"type": "enemy_spot", "message": action.message}
            except (json.JSONDecodeError, TypeError):
                msg_content = {"type": "enemy_spot", "message": action.message}
            msg = Message(
                msg_id=str(uuid.uuid4())[:8],
                sender_id=agent_id,
                sender_role=agent.state.role,
                content=msg_content,
                timestamp=turn,
            )
            if agent.state.team == Team.RED:
                memory_red.write(msg)
            else:
                memory_blue.write(msg)
    return actions, llm_decision_traces


def _write_event_to_memory(memory_pool: SharedMemoryPool, sender_id: str, sender_role: Role, payload: dict[str, Any], turn: int) -> None:
    msg = Message(
        msg_id=str(uuid.uuid4())[:8],
        sender_id=sender_id,
        sender_role=sender_role,
        content=payload,
        timestamp=turn,
    )
    memory_pool.write(msg)


def _bridge_structured_events_to_memory(session: "BattleSession", turn: int) -> None:
    env = session.env
    for index, event in enumerate(env.structured_events):
        if not event.actor_id or not event.team:
            continue
        actor = env.agents.get(event.actor_id)
        if not actor:
            continue
        memory_pool = session.memory_red if actor.team == Team.RED else session.memory_blue
        if event.type == "TASK":
            assignees = event.metadata.get("assignees") or [event.actor_id]
            for assignee in assignees:
                _write_event_to_memory(
                    memory_pool,
                    sender_id=event.actor_id,
                    sender_role=actor.role,
                    payload={
                        "type": "task_assign",
                        "task_id": f"{turn}-{index}-{assignee}",
                        "assignee": assignee,
                        "task": event.metadata.get("task", "协同推进"),
                        "task_type": "coordination",
                        "target_pos": event.target_position,
                        "priority": "high",
                    },
                    turn=turn,
                )
        if event.type == "SPOT":
            targets = event.metadata.get("targets", [])
            for target in targets:
                _write_event_to_memory(
                    memory_pool,
                    sender_id=event.actor_id,
                    sender_role=actor.role,
                    payload={
                        "type": "enemy_spot",
                        "target_id": target.get("agent_id"),
                        "pos": target.get("pos"),
                        "hp": target.get("hp"),
                    },
                    turn=turn,
                )
                pos = target.get("pos")
                if pos:
                    _write_event_to_memory(
                        memory_pool,
                        sender_id=event.actor_id,
                        sender_role=actor.role,
                        payload={
                            "type": "risk_zone",
                            "x": pos["x"],
                            "y": pos["y"],
                            "reason": "侦察发现高价值目标",
                        },
                        turn=turn,
                    )
        if event.type in {"BLOCK", "JAM", "ENGAGE"} and event.target_position:
            reason_map = {
                "BLOCK": "封锁区域已生效",
                "JAM": "干扰区域已生效",
                "ENGAGE": "高风险接敌区域",
            }
            _write_event_to_memory(
                memory_pool,
                sender_id=event.actor_id,
                sender_role=actor.role,
                payload={
                    "type": "risk_zone",
                    "x": event.target_position["x"],
                    "y": event.target_position["y"],
                    "reason": reason_map[event.type],
                },
                turn=turn,
            )


@dataclass
class BattleSession:
    battle_id: str
    mode: str
    max_turns: int
    team_config_payload: dict[str, Any]
    scenario_config_payload: dict[str, Any]
    agents: dict[str, Any]
    env: Any
    memory_red: SharedMemoryPool
    memory_blue: SharedMemoryPool
    storage: BattleStorage | None = None
    status: str = "created"
    frames: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    started: bool = False

    def start(self) -> None:
        if self.status == "done":
            return
        self.started = True
        self.status = "running" if self.mode == "实时推演" else "computing"

    def pause(self) -> None:
        if self.status == "running":
            self.status = "paused"
            self.persist_run()

    def resume(self) -> None:
        if self.status == "paused":
            self.status = "running"
            self.persist_run()

    def ensure_initial_frame(self):
        if not self.frames:
            self.frames.append(
                capture_structured_frame(
                    self.env,
                    self.mode,
                    self.status,
                    self.memory_red,
                    self.memory_blue,
                    llm_mode_enabled=_llm_mode_enabled(self.agents),
                )
            )
            self.persist_frame(0, self.frames[0])
            self.persist_run()

    def step_once(self, turn: int) -> tuple[dict[str, Any], bool]:
        actions, llm_decision_traces = _build_actions(self.agents, self.env, self.memory_red, self.memory_blue, turn)
        record_visible_enemy_contacts(self.agents, self.env, self.memory_red, self.memory_blue, turn)
        _, done = self.env.step(actions)
        _bridge_structured_events_to_memory(self, self.env.turn)
        self.memory_red.update_task_progress(self.env.agents, self.env.turn)
        self.memory_blue.update_task_progress(self.env.agents, self.env.turn)
        if turn % 3 == 0:
            self.memory_red.decay()
            self.memory_blue.decay()
        phase = "实时推演中" if self.mode == "实时推演" else "计算完成"
        frame = capture_structured_frame(
            self.env,
            self.mode,
            phase if not done else "已结束",
            self.memory_red,
            self.memory_blue,
            llm_decision_traces=llm_decision_traces,
            llm_mode_enabled=_llm_mode_enabled(self.agents),
        )
        self.frames.append(frame)
        self.persist_frame(len(self.frames) - 1, frame)
        if done:
            self.complete()
        else:
            self.persist_run()
        return frame, done

    def run_all(self) -> list[dict[str, Any]]:
        self.ensure_initial_frame()
        if self.result is not None:
            return self.frames
        self.start()
        for turn in range(1, self.max_turns + 1):
            _, done = self.step_once(turn)
            if done:
                break
        if self.result is None:
            self.complete()
        return self.frames

    def complete(self) -> None:
        if self.result is None:
            self.result = BattleJudge().evaluate(self.env, self.memory_red, self.memory_blue)
        self.status = "done"
        self.persist_run()

    def summary_payload(self) -> dict[str, Any]:
        return {
            "battle_id": self.battle_id,
            "status": self.status,
            "mode": self.mode,
            "max_turns": self.max_turns,
            "scenario_config": self.scenario_config_payload,
            "frame_count": len(self.frames),
            "result": to_jsonable(self.result),
        }

    def persist_run(self) -> None:
        if self.storage is None:
            return
        self.storage.upsert_run(
            battle_id=self.battle_id,
            status=self.status,
            mode=self.mode,
            max_turns=self.max_turns,
            frame_count=len(self.frames),
            team_config=self.team_config_payload,
            scenario_config=self.scenario_config_payload,
            summary=self.summary_payload(),
        )

    def persist_frame(self, turn_index: int, frame: dict[str, Any]) -> None:
        if self.storage is None:
            return
        self.storage.upsert_frame(self.battle_id, turn_index, frame)


@dataclass
class StoredBattleSession:
    battle_id: str
    mode: str
    max_turns: int
    scenario_config_payload: dict[str, Any]
    frames: list[dict[str, Any]]
    status: str = "done"
    result: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    started: bool = True

    def start(self) -> None:
        return

    def pause(self) -> None:
        return

    def resume(self) -> None:
        return

    def ensure_initial_frame(self):
        return

    def step_once(self, turn: int) -> tuple[dict[str, Any], bool]:
        raise RuntimeError("stored replay sessions cannot be advanced")

    def run_all(self) -> list[dict[str, Any]]:
        return self.frames

    def complete(self) -> None:
        return

    def summary_payload(self) -> dict[str, Any]:
        if self.summary:
            return self.summary
        return {
            "battle_id": self.battle_id,
            "status": self.status,
            "mode": self.mode,
            "max_turns": self.max_turns,
            "scenario_config": self.scenario_config_payload,
            "frame_count": len(self.frames),
            "result": to_jsonable(self.result),
        }


class BattleSessionManager:
    def __init__(self, storage: BattleStorage | None = None):
        self.sessions: dict[str, BattleSession] = {}
        self.storage = storage if storage is not None else BattleStorage(config.battle_db_path)

    def create_session(self, mode: str, max_turns: int, team_config_payload: dict | None = None, scenario_config_payload: dict | None = None) -> BattleSession:
        team_config = normalize_team_config(team_config_payload)
        scenario_config = normalize_scenario_config(scenario_config_payload)
        agents, red_states, blue_states = build_agents_from_team_config(team_config, scenario_config=scenario_config)
        from .env import BattlefieldEnv

        env = BattlefieldEnv(scenario_config=scenario_config)
        env.max_turns = int(max_turns)
        env.reset(red_states, blue_states)
        battle_id = str(uuid.uuid4())[:8]
        session = BattleSession(
            battle_id=battle_id,
            mode=mode,
            max_turns=int(max_turns),
            team_config_payload={
                team.value: {role.value: spec for role, spec in team_map.items()}
                for team, team_map in team_config.items()
            },
            scenario_config_payload=scenario_config.to_dict(),
            agents=agents,
            env=env,
            memory_red=SharedMemoryPool(Team.RED, battle_stats=env.stats),
            memory_blue=SharedMemoryPool(Team.BLUE, battle_stats=env.stats),
            storage=self.storage,
        )
        session.ensure_initial_frame()
        self.sessions[battle_id] = session
        return session

    def get(self, battle_id: str) -> BattleSession | StoredBattleSession:
        if battle_id in self.sessions:
            return self.sessions[battle_id]
        stored = self.load_stored_session(battle_id)
        if stored is None:
            raise KeyError(battle_id)
        return stored

    def load_stored_session(self, battle_id: str) -> StoredBattleSession | None:
        run = self.storage.load_run(battle_id)
        if run is None:
            return None
        frames = self.storage.load_frames(battle_id)
        summary = run.get("summary")
        result = summary.get("result") if isinstance(summary, dict) else None
        return StoredBattleSession(
            battle_id=battle_id,
            mode=run["mode"],
            max_turns=run["max_turns"],
            scenario_config_payload=run.get("scenario_config") or {},
            frames=frames,
            status=run["status"],
            result=result,
            summary=summary,
        )

    def list_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.storage.list_runs(limit=limit)


manager = BattleSessionManager()


def sse_event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(to_jsonable(data), ensure_ascii=False)}\n\n"


def stream_battle(session: BattleSession):
    if not session.started:
        session.start()
    session.ensure_initial_frame()
    yield sse_event("frame", {"battle_id": session.battle_id, "frame": session.frames[0], "summary": session.result})
    if session.result is not None:
        yield sse_event("done", session.summary_payload())
        return
    for turn in range(1, session.max_turns + 1):
        while session.status == "paused":
            time.sleep(0.1)
        if session.status == "done":
            break
        frame, done = session.step_once(turn)
        yield sse_event("frame", {"battle_id": session.battle_id, "frame": frame, "summary": session.result})
        time.sleep(0.05)
        if done:
            break
    yield sse_event("done", session.summary_payload())
