"""Runtime advice generation built from structured battle state.

This module replaced the old Gradio UI helpers. It keeps the API runtime focused
on simulation orchestration while this file owns memory updates and advice rules.
"""

from __future__ import annotations

from .battle_types import Team
from .judge import BattleJudge


def record_visible_enemy_contacts(agents, env, memory_red, memory_blue, turn: int) -> int:
    """Write visible enemy contacts into the corresponding team's shared memory."""
    written = 0
    for agent_id, agent in agents.items():
        if not agent.state.alive:
            continue
        obs = env.get_observation(agent_id)
        if not obs:
            continue
        visible_enemies = obs.get("visible_enemies", [])
        if not visible_enemies:
            continue
        memory_pool = memory_red if agent.state.team == Team.RED else memory_blue
        for enemy in visible_enemies:
            msg = memory_pool.create_message(
                sender_id=agent_id,
                sender_role=agent.state.role,
                content={
                    "type": "enemy_spot",
                    "target_id": enemy["agent_id"],
                    "pos": enemy["pos"],
                    "hp": enemy.get("hp"),
                },
                timestamp=turn,
            )
            if memory_pool.write(msg):
                written += 1
    return written


def _team_agents(env, team: Team) -> dict:
    return {agent_id: agent for agent_id, agent in env.agents.items() if agent.team == team}


def _survival_rate(agents: dict) -> float:
    total_hp = sum(agent.hp for agent in agents.values() if agent.alive)
    max_hp = sum(agent.max_hp for agent in agents.values()) or 1
    return total_hp / max_hp


def _control_points_pressure(env, team: Team) -> int:
    pressure = 0
    for point in env._control_points():
        for agent in env.agents.values():
            if agent.alive and agent.team != team and agent.pos.distance_to(point) <= 2:
                pressure += 1
    return pressure


def _render_advice_text(item: dict) -> str:
    team_names = {"red": "红方", "blue": "蓝方"}
    role_names = {
        "coordinator": "协同单元",
        "scout": "侦察单元",
        "attacker": "攻击单元",
        "defender": "防御单元",
    }
    action_names = {
        "focus_primary_threat": "优先压制已确认威胁",
        "tighten_control_zone": "收缩防线并稳住控制区",
        "refresh_recon": "刷新侦察情报",
        "push_active_task": "推进当前任务链路",
        "reassign_tasks": "重新分配任务目标",
    }
    team = team_names.get(item.get("target_team"), item.get("target_team", "队伍"))
    role = role_names.get(item.get("target_role"), item.get("target_role", "单元"))
    action = action_names.get(item.get("action"), item.get("action", "调整行动"))
    reason = item.get("reason_text") or item.get("reason") or "当前态势发生变化"
    evidence = item.get("evidence_text")
    suffix = f"依据：{evidence}" if evidence else ""
    return f"建议{team}{role}{action}，原因是{reason}。{suffix}".strip()


def build_advice_items(env, memory_red, memory_blue) -> list[dict]:
    """Build a small ranked set of actionable advice items for the current frame.

    The rules intentionally stay deterministic so evaluation runs remain
    reproducible even when LLM decision mode is enabled elsewhere.
    """
    judge = BattleJudge()
    red_agents = _team_agents(env, Team.RED)
    blue_agents = _team_agents(env, Team.BLUE)
    red_scores = judge._team_scores(Team.RED, red_agents, blue_agents, env, memory_red)
    blue_scores = judge._team_scores(Team.BLUE, blue_agents, red_agents, env, memory_blue)
    red_summary = memory_red.read_summary()
    blue_summary = memory_blue.read_summary()
    items: list[dict] = []

    def add_item(item: dict) -> None:
        key = (item["target_team"], item["target_role"], item["action"])
        if any((old["target_team"], old["target_role"], old["action"]) == key for old in items):
            return
        item["rendered_text"] = _render_advice_text(item)
        items.append(item)

    if red_summary.get("primary_threat"):
        add_item(
            {
                "priority": "high",
                "target_team": "red",
                "target_role": "attacker",
                "action": "focus_primary_threat",
                "reason": "confirmed_threat_window",
                "reason_text": f"当前已锁定主要威胁 {red_summary['primary_threat']}",
                "evidence": {"focus": red_summary.get("recommended_focus")},
                "evidence_text": f"建议焦点：{red_summary.get('recommended_focus', '推进压制')}",
                "turn": env.turn,
            }
        )
    elif red_summary.get("memory_health") == "stale":
        add_item(
            {
                "priority": "medium",
                "target_team": "red",
                "target_role": "scout",
                "action": "refresh_recon",
                "reason": "memory_stale",
                "reason_text": "红方情报衰减，缺少新鲜敌情",
                "evidence": {"memory_health": red_summary.get("memory_health")},
                "evidence_text": f"记忆状态：{red_summary.get('memory_health')}",
                "turn": env.turn,
            }
        )

    blue_pressure = _control_points_pressure(env, Team.BLUE)
    if blue_pressure > 0 and (
        blue_scores["objective_score"] <= red_scores["objective_score"]
        or _survival_rate(blue_agents) < _survival_rate(red_agents)
    ):
        add_item(
            {
                "priority": "high",
                "target_team": "blue",
                "target_role": "defender",
                "action": "tighten_control_zone",
                "reason": "control_zone_pressure",
                "reason_text": "控制区周边出现接敌压力，蓝方需要稳住阵地",
                "evidence": {"pressure": blue_pressure},
                "evidence_text": f"控制区压力目标数：{blue_pressure}",
                "turn": env.turn,
            }
        )
    elif blue_summary.get("memory_health") == "stale":
        add_item(
            {
                "priority": "medium",
                "target_team": "blue",
                "target_role": "defender",
                "action": "refresh_recon",
                "reason": "limited_awareness",
                "reason_text": "蓝方情报更新偏弱，需要补足态势感知",
                "evidence": {"memory_health": blue_summary.get("memory_health")},
                "evidence_text": f"记忆状态：{blue_summary.get('memory_health')}",
                "turn": env.turn,
            }
        )

    coord_team = None
    coord_summary = None
    if red_summary.get("active_tasks", 0) > 0:
        coord_team, coord_summary = "red", red_summary
    elif blue_summary.get("active_tasks", 0) > 0:
        coord_team, coord_summary = "blue", blue_summary
    elif red_summary.get("unverified_targets", 0) >= 2:
        coord_team, coord_summary = "red", red_summary
    elif blue_summary.get("unverified_targets", 0) >= 2:
        coord_team, coord_summary = "blue", blue_summary

    if coord_team and coord_summary:
        add_item(
            {
                "priority": "medium",
                "target_team": coord_team,
                "target_role": "coordinator",
                "action": "push_active_task" if coord_summary.get("active_tasks", 0) > 0 else "reassign_tasks",
                "reason": "coordination_window",
                "reason_text": "任务链路已经形成，需要协调单位继续推进执行",
                "evidence": {
                    "active_tasks": coord_summary.get("active_tasks", 0),
                    "focus": coord_summary.get("recommended_focus"),
                },
                "evidence_text": f"活跃任务 {coord_summary.get('active_tasks', 0)}，当前建议：{coord_summary.get('recommended_focus')}",
                "turn": env.turn,
            }
        )

    return items[:3]


# Backward-compatible aliases keep older tests and call sites readable while the
# implementation lives under non-UI names.
_build_advice_items = build_advice_items
_record_visible_enemy_contacts = record_visible_enemy_contacts
