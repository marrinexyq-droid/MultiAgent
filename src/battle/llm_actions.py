"""Validation boundary for LLM-generated agent actions.

LLMs are allowed to propose actions, but the simulator only accepts actions that
can be parsed and checked against map bounds and known targets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .battle_types import Action, ActionType, Position


@dataclass(frozen=True)
class ParsedAction:
    """Parsed action plus the reason a rule fallback was needed, if any."""

    action: Action
    ok: bool
    fallback_reason: str | None = None
    raw_payload: dict[str, Any] | None = None


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output, tolerating code fences."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1).replace("```", "", 1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("response did not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def _position_from_payload(payload: Any) -> Position | None:
    if not isinstance(payload, dict):
        return None
    if "x" not in payload or "y" not in payload:
        return None
    return Position(int(payload["x"]), int(payload["y"]))


def _in_bounds(pos: Position | None, width: int, height: int) -> bool:
    return pos is not None and 0 <= pos.x < width and 0 <= pos.y < height


def parse_llm_action_response(
    text: str,
    *,
    agent_id: str,
    width: int,
    height: int,
    valid_target_ids: set[str] | None = None,
) -> ParsedAction:
    """Parse and validate one OpenAI-compatible chat completion response."""
    valid_target_ids = valid_target_ids or set()
    try:
        data = extract_json_object(text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        # Invalid model output falls back to HOLD instead of breaking the turn.
        return ParsedAction(Action(agent_id, ActionType.HOLD), ok=False, fallback_reason=f"invalid_json:{exc}")

    raw_action_type = data.get("action_type", "hold")
    try:
        action_type = ActionType(raw_action_type)
    except ValueError:
        return ParsedAction(
            Action(agent_id, ActionType.HOLD),
            ok=False,
            fallback_reason=f"invalid_action_type:{raw_action_type}",
            raw_payload=data,
        )

    target = _position_from_payload(data.get("target"))
    skill_target = _position_from_payload(data.get("skill_target"))
    target_id = data.get("target_id")

    if action_type == ActionType.MOVE and not _in_bounds(target, width, height):
        # Movement is the highest-risk action because invalid coordinates can
        # corrupt environment state if not rejected before env.step().
        return ParsedAction(
            Action(agent_id, ActionType.HOLD),
            ok=False,
            fallback_reason="move_target_out_of_bounds",
            raw_payload=data,
        )

    if action_type in {ActionType.ATTACK, ActionType.SKILL} and target_id and valid_target_ids and target_id not in valid_target_ids:
        # Only visible/known target ids are accepted for direct hostile actions.
        return ParsedAction(
            Action(agent_id, ActionType.HOLD),
            ok=False,
            fallback_reason=f"invalid_target:{target_id}",
            raw_payload=data,
        )

    if skill_target is not None and not _in_bounds(skill_target, width, height):
        skill_target = None

    return ParsedAction(
        Action(
            agent_id=agent_id,
            action_type=action_type,
            target=target,
            target_id=target_id,
            skill_id=data.get("skill_id"),
            skill_target=skill_target,
            message=data.get("message"),
        ),
        ok=True,
        raw_payload=data,
    )
