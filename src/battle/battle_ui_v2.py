import base64
import json
import time
import uuid
from html import escape
from pathlib import Path

try:
    import gradio as gr
except ImportError:  # pragma: no cover - depends on local runtime
    gr = None

from src.battle.battle_types import Message, Role, Team
from src.battle.config import config
from src.battle.env import BattlefieldEnv
from src.battle.judge import BattleJudge
from src.battle.memory import SharedMemoryPool
from src.battle.roster import ROLE_LABELS, ROLE_TEMPLATES, build_agents_from_team_config, default_scenario_config, default_team_config


ROLE_ORDER = [Role.COORDINATOR, Role.SCOUT, Role.ATTACKER, Role.DEFENDER]
TEAM_ORDER = [Team.RED, Team.BLUE]
TEAM_LABELS = {Team.RED: "红队", Team.BLUE: "蓝队"}
TEAM_CLASSES = {Team.RED: "team-red", Team.BLUE: "team-blue"}
TEAM_KEYS = {Team.RED: "red", Team.BLUE: "blue"}
ROLE_KEYS = {role: role.value for role in ROLE_ORDER}
ROLE_SHORT_LABELS = {
    Role.COORDINATOR: "协",
    Role.SCOUT: "侦",
    Role.ATTACKER: "攻",
    Role.DEFENDER: "守",
}
ROLE_ICON_FILES = {
    Role.COORDINATOR: "commander.svg",
    Role.SCOUT: "scout.svg",
    Role.ATTACKER: "attacker.svg",
    Role.DEFENDER: "defender.svg",
}
ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"


def _svg_data_uri(filename: str) -> str:
    icon_path = ICON_DIR / filename
    try:
        encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    except FileNotFoundError:
        return ""
    return f"data:image/svg+xml;base64,{encoded}"


ROLE_ICON_URIS = {role: _svg_data_uri(filename) for role, filename in ROLE_ICON_FILES.items()}


def build_role_detail_header(team: Team, role: Role) -> str:
    template = ROLE_TEMPLATES[role]
    team_class = TEAM_CLASSES[team]
    icon_uri = ROLE_ICON_URIS.get(role, "")
    emblem_style = f' style="--role-icon:url(\'{icon_uri}\')"' if icon_uri else ""
    return f"""
    <div class="job-detail-head {team_class}">
      <div class="job-detail-emblem role-{role.value} {team_class}"{emblem_style}></div>
      <div class="job-detail-copy">
        <div class="job-detail-kicker">{TEAM_LABELS[team]} / {template.label}</div>
        <div class="job-detail-title">{template.label}</div>
        <div class="job-detail-description">{template.description}</div>
      </div>
    </div>
    """


def build_role_icon_styles() -> str:
    rules = []
    for role in ROLE_ORDER:
        uri = ROLE_ICON_URIS.get(role, "")
        if not uri:
            continue
        rules.append(
            f"""
.job-card-button.role-{role.value}::after,
.job-detail-emblem.role-{role.value} {{
  --role-icon: url("{uri}");
}}
"""
        )
    return "\n".join(rules)


def _slider_update(**kwargs):
    return gr.update(**kwargs) if gr is not None else kwargs


def build_role_card_label(team: Team, role: Role, count: int) -> str:
    template = ROLE_TEMPLATES[role]
    return "\n".join(
        [
            f"{TEAM_LABELS[team]} {template.label}",
            template.description,
            f"技能：{template.skill_name}",
            f"数量：{int(count)}",
        ]
    )


def adjust_count(team_key: str, role_key: str, current: float | int, delta: int) -> tuple[int, str]:
    team = Team(team_key)
    role = Role(role_key)
    updated = max(0, min(4, int(current) + int(delta)))
    return updated, build_role_card_label(team, role, updated)


def _panel_visibility_updates(active_key: str | None) -> list[dict]:
    updates = []
    for team in TEAM_ORDER:
        for role in ROLE_ORDER:
            key = f"{team.value}:{role.value}"
            updates.append(_slider_update(visible=(key == active_key)))
    return updates


def open_role_panel(team_key: str, role_key: str) -> list[dict]:
    return _panel_visibility_updates(f"{team_key}:{role_key}")


def close_role_panels() -> list[dict]:
    return _panel_visibility_updates(None)


def _build_team_config_from_inputs(*values) -> dict[Team, dict[Role, dict]]:
    config_map = default_team_config()
    index = 0
    for team in TEAM_ORDER:
        for role in ROLE_ORDER:
            config_map[team][role] = {
                "count": int(values[index]),
                "hp": int(values[index + 1]),
                "ammo": int(values[index + 2]),
                "vision_range": int(values[index + 3]),
                "attack_power": int(values[index + 4]),
                "move_speed": int(values[index + 5]),
            }
            index += 6
    return config_map


def build_roster_preview(*values) -> str:
    team_config = _build_team_config_from_inputs(*values)
    lines = ["### 阵容预览"]
    for team in TEAM_ORDER:
        lines.append(f"- {TEAM_LABELS[team]}：")
        total = 0
        for role in ROLE_ORDER:
            spec = team_config[team][role]
            if spec["count"] <= 0:
                continue
            template = ROLE_TEMPLATES[role]
            total += spec["count"]
            lines.append(
                f"  - {template.label} x{spec['count']} | 生命 {spec['hp']} | 资源 {spec['ammo']} | "
                f"视野 {spec['vision_range']} | 攻击 {spec['attack_power']} | 移速 {spec['move_speed']} | "
                f"技能 {template.skill_name}"
            )
        if total == 0:
            lines.append("  - 暂无单位")
    return "\n".join(lines)


def build_skill_reference() -> str:
    lines = ["### 角色与技能"]
    for role in ROLE_ORDER:
        template = ROLE_TEMPLATES[role]
        lines.append(
            f"- {template.label}：{template.description} 主动技能 `{template.skill_name}`，冷却 {template.skill_cooldown} 回合。"
        )
    return "\n".join(lines)


def build_summary(result: dict | None, running: bool = False) -> str:
    if running or result is None:
        return """
        <div class="summary-card summary-running">
          <div class="summary-title">演练结果</div>
          <div class="summary-grid">
            <div class="summary-item">
              <span class="summary-label">状态</span>
              <span class="summary-value">进行中</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">说明</span>
              <span class="summary-value">等待最终胜负判定</span>
            </div>
          </div>
        </div>
        """
    winner_name = {"red": "红队", "blue": "蓝队", "draw": "平局"}
    reason_names = {
        "red_eliminated": "红队全部失效",
        "blue_eliminated": "蓝队全部失效",
        "higher_survival_rate": "存活率更高",
        "stalemate_adjudication": "僵局裁决",
        "elimination_score": "减员压制占优",
        "survival_score": "生存表现占优",
        "objective_score": "目标控制占优",
        "initiative_score": "态势主动性占优",
        "coordination_score": "协同质量占优",
        "draw": "平局",
    }
    winner_key = result["winner"].value if result["winner"] else "draw"
    winner_class = "summary-draw"
    if winner_key == "red":
        winner_class = "summary-red"
    elif winner_key == "blue":
        winner_class = "summary-blue"
    parts = [
        '<div class="summary-card">',
        '<div class="summary-title">演练结果</div>',
        '<div class="summary-grid">',
        f'<div class="summary-item"><span class="summary-label">获胜方</span><span class="summary-value {winner_class}">{winner_name[winner_key]}</span></div>',
        f'<div class="summary-item"><span class="summary-label">原因</span><span class="summary-value">{reason_names.get(result["reason"], result["reason"])}</span></div>',
        f'<div class="summary-item"><span class="summary-label">回合数</span><span class="summary-value">{result["turn"]}</span></div>',
        f'<div class="summary-item team-red"><span class="summary-label">红队总分</span><span class="summary-value">{result.get("red_score", "-")}</span></div>',
        f'<div class="summary-item team-blue"><span class="summary-label">蓝队总分</span><span class="summary-value">{result.get("blue_score", "-")}</span></div>',
    ]
    if "red_rate" in result:
        parts.append(f'<div class="summary-item team-red"><span class="summary-label">红队存活率</span><span class="summary-value">{result["red_rate"]}</span></div>')
        parts.append(f'<div class="summary-item team-blue"><span class="summary-label">蓝队存活率</span><span class="summary-value">{result["blue_rate"]}</span></div>')
    if result.get("score_breakdown"):
        red_breakdown = " / ".join(f"{k.replace('_score','')} {v}" for k, v in result["score_breakdown"]["red"].items())
        blue_breakdown = " / ".join(f"{k.replace('_score','')} {v}" for k, v in result["score_breakdown"]["blue"].items())
        parts.append(f'<div class="summary-item team-red"><span class="summary-label">红队分解</span><span class="summary-value">{escape(red_breakdown)}</span></div>')
        parts.append(f'<div class="summary-item team-blue"><span class="summary-label">蓝队分解</span><span class="summary-value">{escape(blue_breakdown)}</span></div>')
    if result.get("agent_merits"):
        top_merits = "".join(
            f'<div class="summary-item"><span class="summary-label">{escape(agent_id)}</span><span class="summary-value">{merit["merit_score"]} · {escape(",".join(merit["commendations"]))}</span></div>'
            for agent_id, merit in list(result["agent_merits"].items())[:3]
        )
        parts.append(top_merits)
    parts.append("</div></div>")
    return "".join(parts)


def build_turn_header(turn: int | None, mode_label: str, phase_label: str) -> str:
    turn_text = "等待开始" if turn is None else f"第 {turn} 回合视图"
    return f"""
    <div class="turn-header">
      <div>
        <div class="turn-eyebrow">Confrontation Stage</div>
        <div class="turn-title">{turn_text}</div>
      </div>
      <div class="turn-badges">
        <span class="turn-badge badge-mode">{escape(mode_label)}</span>
        <span class="turn-badge badge-phase">{escape(phase_label)}</span>
      </div>
    </div>
    """


def build_events_html(events: str) -> str:
    lines = [line for line in events.splitlines() if line.strip()]
    if not lines:
        lines = ["本回合无事件"]
    items = []
    for line in lines:
        css_class = "event-item"
        if "技能" in line:
            css_class += " event-skill"
        elif "失效" in line:
            css_class += " event-elim"
        elif "位置阻塞" in line:
            css_class += " event-block"
        items.append(f'<div class="{css_class}">{escape(line)}</div>')
    return f'<div class="event-feed">{"".join(items)}</div>'


def build_map_html(env: BattlefieldEnv, mode_label: str, phase_label: str) -> str:
    cells = []
    for y in range(env.grid_size):
        for x in range(env.grid_size):
            agent = next(
                (current for current in env.agents.values() if current.alive and current.pos.x == x and current.pos.y == y),
                None,
            )
            if agent is None:
                cells.append('<div class="grid-cell grid-empty"><span class="cell-coord"></span></div>')
                continue
            team_class = TEAM_CLASSES[agent.team]
            state_class = "cell-offline" if not agent.alive else ""
            label = ROLE_SHORT_LABELS.get(agent.role, agent.role.value[:1].upper())
            tooltip = f"{agent.agent_id} | {TEAM_LABELS[agent.team]} | {ROLE_LABELS[agent.role]}"
            cells.append(
                f'<div class="grid-cell {team_class} {state_class}" title="{escape(tooltip)}">'
                f'<span class="cell-label">{escape(label)}</span>'
                f'<span class="cell-sub">{escape(agent.agent_id.split("_")[-1])}</span>'
                f"</div>"
            )
    legend = """
    <div class="map-legend">
      <span class="legend-chip team-red">红队</span>
      <span class="legend-chip team-blue">蓝队</span>
    </div>
    """
    return f"""
    <div class="map-stage">
      {build_turn_header(env.turn, mode_label, phase_label)}
      {legend}
      <div class="map-grid" style="grid-template-columns: repeat({env.grid_size}, minmax(0, 1fr));">
        {''.join(cells)}
      </div>
    </div>
    """


def build_unit_cards(env: BattlefieldEnv) -> str:
    sections = []
    for team in TEAM_ORDER:
        cards = []
        team_agents = [agent for agent in env.agents.values() if agent.team == team]
        for agent in team_agents:
            team_class = TEAM_CLASSES[agent.team]
            status_text = "在线" if agent.alive else "已失效"
            hp_text = f"{agent.hp}/{agent.max_hp}" if agent.alive else f"0/{agent.max_hp}"
            ammo_text = str(agent.ammo) if agent.alive else "-"
            cards.append(
                f"""
                <div class="unit-card {team_class} {'offline' if not agent.alive else ''}">
                  <div class="unit-card-top">
                    <div>
                      <div class="unit-id">{escape(agent.agent_id)}</div>
                      <div class="unit-meta">{TEAM_LABELS[agent.team]} / {ROLE_LABELS[agent.role]}</div>
                    </div>
                    <span class="unit-status {'status-offline' if not agent.alive else 'status-online'}">{status_text}</span>
                  </div>
                  <div class="unit-stats">
                    <span>位置 <strong>({agent.pos.x},{agent.pos.y})</strong></span>
                    <span>状态值 <strong>{hp_text}</strong></span>
                    <span>资源 <strong>{ammo_text}</strong></span>
                    <span>移速 <strong>{agent.move_speed}</strong></span>
                  </div>
                  <div class="unit-skill-row">
                    <span class="skill-name">{escape(agent.skill_name or '无技能')}</span>
                    <span class="skill-cd">CD {agent.skill_cooldown_remaining}</span>
                  </div>
                </div>
                """
            )
        sections.append(
            f"""
            <div class="unit-team-group {TEAM_CLASSES[team]}">
              <div class="unit-team-title">{TEAM_LABELS[team]}</div>
              <div class="unit-card-list">{''.join(cards) if cards else '<div class="unit-empty">暂无单位</div>'}</div>
            </div>
            """
        )
    return f'<div class="unit-panel">{"".join(sections)}</div>'


def _format_confidence(value: float) -> str:
    return f"{value:.2f}"


def _memory_view_for_team(team: Team, env: BattlefieldEnv, memory_pool: SharedMemoryPool) -> dict:
    alive_agent = next((agent for agent in env.agents.values() if agent.team == team and agent.alive), None)
    agent_id = alive_agent.agent_id if alive_agent else f"{team.value}_viewer"
    return memory_pool.read(agent_id)


def build_memory_panel(team: Team, memory_view: dict) -> str:
    team_class = TEAM_CLASSES[team]
    summary_data = memory_view.get("summary", {})
    beliefs = memory_view.get("beliefs", {})
    risk_zones = memory_view.get("risk_zones", {})
    tasks = memory_view.get("tasks", memory_view.get("team_tasks", {}))
    observations = memory_view.get("observations", [])
    primary_threat = summary_data.get("primary_threat") or "暂无"
    recommended_focus = summary_data.get("recommended_focus") or "维持侦察并收集新情报"
    memory_health = summary_data.get("memory_health") or "stale"

    summary = f"""
    <div class="memory-summary-grid">
      <div class="memory-summary-item">
        <span class="memory-summary-label">主威胁</span>
        <span class="memory-summary-value">{escape(str(primary_threat))}</span>
      </div>
      <div class="memory-summary-item">
        <span class="memory-summary-label">活跃任务</span>
        <span class="memory-summary-value">{summary_data.get("active_tasks", len(tasks))}</span>
      </div>
      <div class="memory-summary-item">
        <span class="memory-summary-label">记忆状态</span>
        <span class="memory-summary-value">{escape(str(memory_health))}</span>
      </div>
    </div>
    <div class="memory-empty" style="margin-bottom:14px;">当前建议：{escape(str(recommended_focus))}</div>
    """

    belief_items = []
    for target_id, belief in list(beliefs.items())[:4]:
        pos = belief.get("last_known_position") or {"x": "-", "y": "-"}
        belief_items.append(
            f"""
            <div class="memory-item">
              <div class="memory-item-title">{escape(target_id)}</div>
              <div class="memory-item-meta">
                位置 ({pos.get('x', '-')},{pos.get('y', '-')}) ·
                状态估计 {belief.get('hp_estimate', '-')} ·
                趋势 {escape(str(belief.get('trend', 'uncertain')))} ·
                威胁 {escape(str(belief.get('threat_level', 'low')))} ·
                T{belief.get('last_seen_turn', '-')} ·
                置信 {_format_confidence(float(belief.get('confidence_score', 0)))}
              </div>
            </div>
            """
        )

    task_items = []
    for task_id, task in list(tasks.items())[:4]:
        target_pos = task.get("target_position") or task.get("target_pos") or {"x": "-", "y": "-"}
        task_items.append(
            f"""
            <div class="memory-item">
              <div class="memory-item-title">{escape(str(task.get('task', task_id)))}</div>
              <div class="memory-item-meta">
                状态 {escape(str(task.get('status', 'pending')))} ·
                执行者 {escape(str(task.get('assignee', '-')))} ·
                分配者 {escape(str(task.get('assigner', '-')))} ·
                目标 {escape(str(task.get('target_id', '-')))} ·
                位置 ({target_pos.get('x', '-')},{target_pos.get('y', '-')}) ·
                T{task.get('updated_turn', task.get('timestamp', '-'))} ·
                置信 {_format_confidence(float(task.get('confidence', 0)))}
              </div>
            </div>
            """
        )

    observation_items = []
    for obs in observations[:4]:
        pos = obs.get("position") or {"x": "-", "y": "-"}
        observation_items.append(
            f"""
            <div class="memory-item">
              <div class="memory-item-title">{escape(str(obs.get('target_id') or obs.get('obs_type', 'unknown')))}</div>
              <div class="memory-item-meta">
                类型 {escape(str(obs.get('obs_type', 'unknown')))} ·
                位置 ({pos.get('x', '-')},{pos.get('y', '-')}) ·
                上报者 {escape(str(obs.get('source_agent_id', '-')))} ·
                T{obs.get('timestamp', '-')} ·
                置信 {_format_confidence(float(obs.get('confidence', 0)))}
              </div>
            </div>
            """
        )

    risk_items = []
    for zone_key, risk in list(risk_zones.items())[:3]:
        risk_items.append(
            f"""
            <div class="memory-item">
              <div class="memory-item-title">风险区 {escape(zone_key)}</div>
              <div class="memory-item-meta">
                原因 {escape(str(risk.get('reason', '未标注')))} ·
                上报者 {escape(str(risk.get('reporter', '-')))} ·
                T{risk.get('timestamp', '-')} ·
                置信 {_format_confidence(float(risk.get('confidence', 0)))}
              </div>
            </div>
            """
        )

    def _section(title: str, items: list[str], empty_text: str) -> str:
        body = "".join(items) if items else f'<div class="memory-empty">{empty_text}</div>'
        return f"""
        <div class="memory-section">
          <div class="memory-section-title">{title}</div>
          <div class="memory-list">{body}</div>
        </div>
        """

    return f"""
    <div class="memory-card {team_class}">
      <div class="memory-card-title">{TEAM_LABELS[team]}情报池</div>
      {summary}
      {_section("态势判断", belief_items, "暂无判断")}
      {_section("任务流", task_items, "暂无任务")}
      {_section("最近观测", observation_items, "暂无观测")}
      {_section("风险区", risk_items, "暂无风险区")}
    </div>
    """


def capture_frame(env: BattlefieldEnv, mode_label: str, phase_label: str, memory_red: SharedMemoryPool, memory_blue: SharedMemoryPool) -> dict:
    events = "\n".join(env.events) if env.events else "本回合无事件"
    red_view = _memory_view_for_team(Team.RED, env, memory_red)
    blue_view = _memory_view_for_team(Team.BLUE, env, memory_blue)
    return {
        "turn": env.turn,
        "map": build_map_html(env, mode_label, phase_label),
        "events_text": events,
        "events_html": build_events_html(events),
        "units": build_unit_cards(env),
        "memory_red": build_memory_panel(Team.RED, red_view),
        "memory_blue": build_memory_panel(Team.BLUE, blue_view),
    }


def build_status_html(state: str, llm_enabled: bool) -> str:
    mapping = {
        "idle": ("待命中", "配置阵容后即可开始演练。"),
        "computing": ("计算中", "当前模式会先计算整局，再自动回放。"),
        "running": ("实时推演中", "每回合完成后都会立刻刷新界面。"),
        "done": ("演练结束", "现在可以回看任意回合。"),
    }
    title, desc = mapping.get(state, mapping["idle"])
    if llm_enabled:
        desc += " LLM 模式下每回合可能会有明显等待。"
    return f"""
    <div class="battle-status battle-status-{state}">
      <div class="battle-status-title">{title}</div>
      <div class="battle-status-desc">{desc}</div>
    </div>
    """


def render_turn(frames: list[dict], turn_index: int, summary: str):
    if not frames:
        return (
            build_turn_header(None, "待命", "未开始"),
            '<div class="map-stage empty-stage"><div class="empty-stage-text">点击“开始演练”后，这里会显示对抗态势。</div></div>',
            "等待开始演练...",
            '<div class="unit-panel"><div class="unit-empty">暂无单位状态</div></div>',
            summary or build_summary(None, running=True),
            '<div class="memory-card team-red"><div class="memory-card-title">红队情报池</div><div class="memory-empty">暂无情报</div></div>',
            '<div class="memory-card team-blue"><div class="memory-card-title">蓝队情报池</div><div class="memory-empty">暂无情报</div></div>',
        )

    turn_index = max(0, min(turn_index, len(frames) - 1))
    frame = frames[turn_index]
    return (
        build_turn_header(frame["turn"], "回看模式", "帧回放"),
        frame["map"],
        frame["events_html"],
        frame["units"],
        summary,
        frame["memory_red"],
        frame["memory_blue"],
    )


def _create_runtime(team_config: dict[Team, dict[Role, dict]], max_turns: int):
    scenario = default_scenario_config(config.grid_size, config.grid_size)
    agents, red_states, blue_states = build_agents_from_team_config(team_config, scenario_config=scenario)
    env = BattlefieldEnv(scenario_config=scenario)
    env.max_turns = max_turns
    env.reset(red_states, blue_states)
    return (
        agents,
        env,
        SharedMemoryPool(Team.RED, battle_stats=env.stats),
        SharedMemoryPool(Team.BLUE, battle_stats=env.stats),
    )


def _build_actions(agents, env, memory_red, memory_blue, turn: int):
    actions = []
    for agent_id, agent in agents.items():
        if not agent.state.alive:
            continue

        obs = env.get_observation(agent_id)
        if not obs:
            continue

        shared_mem = memory_red.read(agent_id) if agent.state.team == Team.RED else memory_blue.read(agent_id)
        action = agent.choose_action(obs, shared_mem)
        actions.append(action)

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
    return actions


def run_battle_v2(mode: str, max_turns: int, *values):
    team_config = _build_team_config_from_inputs(*values)
    max_turns = int(max_turns)
    llm_enabled = bool(config.api_key)
    agents, env, memory_red, memory_blue = _create_runtime(team_config, max_turns)
    phase_label = "实时推演" if mode == "实时推演" else "演练后回放"
    frames = [capture_frame(env, mode, phase_label, memory_red, memory_blue)]
    total = 0

    if mode == "演练后回放":
        yield (
            frames,
            build_summary(None, running=True),
            _slider_update(minimum=0, maximum=0, value=0, interactive=False),
            build_turn_header(0, mode, "计算中"),
            frames[0]["map"],
            frames[0]["events_html"],
            frames[0]["units"],
            build_summary(None, running=True),
            frames[0]["memory_red"],
            frames[0]["memory_blue"],
            build_status_html("computing", llm_enabled),
        )

        for turn in range(1, max_turns + 1):
            actions = _build_actions(agents, env, memory_red, memory_blue, turn)
            _, done = env.step(actions)
            memory_red.update_task_progress(env.agents, env.turn)
            memory_blue.update_task_progress(env.agents, env.turn)
            if turn % 3 == 0:
                memory_red.decay()
                memory_blue.decay()
            frames.append(capture_frame(env, mode, "计算完成", memory_red, memory_blue))
            if done:
                break

        result = BattleJudge().evaluate(env, memory_red, memory_blue)
        summary = build_summary(result)
        total = len(frames) - 1
        for idx in range(len(frames)):
            title, map_md, events, units, summary_md = render_turn(frames, idx, summary)
            yield (
                frames,
                summary,
                _slider_update(minimum=0, maximum=total, value=idx, interactive=True),
                title,
                map_md,
                events,
                units,
                summary_md,
                frames[idx]["memory_red"],
                frames[idx]["memory_blue"],
                build_status_html("done" if idx == total else "computing", llm_enabled),
            )
            time.sleep(0.18)
        return

    summary = build_summary(None, running=True)
    yield (
        frames,
        summary,
        _slider_update(minimum=0, maximum=0, value=0, interactive=False),
        build_turn_header(0, mode, "实时推演中"),
        frames[0]["map"],
        frames[0]["events_html"],
        frames[0]["units"],
        summary,
        frames[0]["memory_red"],
        frames[0]["memory_blue"],
        build_status_html("running", llm_enabled),
    )

    for turn in range(1, max_turns + 1):
        actions = _build_actions(agents, env, memory_red, memory_blue, turn)
        _, done = env.step(actions)
        memory_red.update_task_progress(env.agents, env.turn)
        memory_blue.update_task_progress(env.agents, env.turn)
        if turn % 3 == 0:
            memory_red.decay()
            memory_blue.decay()
        frames.append(capture_frame(env, mode, "实时推演中", memory_red, memory_blue))
        total = len(frames) - 1
        frame = frames[-1]
        yield (
            frames,
            summary,
            _slider_update(minimum=0, maximum=total, value=total, interactive=False),
            build_turn_header(frame["turn"], mode, "实时推演中"),
            frame["map"],
            frame["events_html"],
            frame["units"],
            summary,
            frame["memory_red"],
            frame["memory_blue"],
            build_status_html("running", llm_enabled),
        )
        if done:
            break

    result = BattleJudge().evaluate(env, memory_red, memory_blue)
    summary = build_summary(result)
    final_frame = frames[-1]
    yield (
        frames,
        summary,
        _slider_update(minimum=0, maximum=len(frames) - 1, value=len(frames) - 1, interactive=True),
        build_turn_header(final_frame["turn"], mode, "已结束"),
        final_frame["map"],
        final_frame["events_html"],
        final_frame["units"],
        summary,
        final_frame["memory_red"],
        final_frame["memory_blue"],
        build_status_html("done", llm_enabled),
    )


CUSTOM_CSS = """
.gradio-container {
  background:
    radial-gradient(circle at top left, rgba(239, 68, 68, 0.12), transparent 18%),
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.12), transparent 18%),
    linear-gradient(160deg, #020617 0%, #050b14 34%, #08101a 68%, #020617 100%);
  color: #e2e8f0;
  position: relative;
}
.gradio-container::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    repeating-linear-gradient(
      to bottom,
      rgba(148, 163, 184, 0.035) 0,
      rgba(148, 163, 184, 0.035) 1px,
      transparent 1px,
      transparent 5px
    );
  opacity: 0.4;
}
.app-shell {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 18px 40px;
}
.hero-card, .panel-card, .footer-card {
  background:
    linear-gradient(180deg, rgba(7, 12, 24, 0.92) 0%, rgba(6, 10, 20, 0.82) 100%);
  border: 1px solid rgba(59, 130, 246, 0.16);
  border-radius: 22px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.03),
    0 0 0 1px rgba(15, 23, 42, 0.3),
    0 20px 45px rgba(2, 6, 23, 0.45);
  backdrop-filter: blur(12px);
}
.hero-card { padding: 24px 26px; margin-bottom: 18px; }
.panel-card { padding: 18px 18px 14px; }
.footer-card { padding: 14px 18px; margin-top: 18px; }
.battle-status {
  border-radius: 18px;
  padding: 16px 18px;
  background: linear-gradient(145deg, rgba(11, 18, 32, 0.95), rgba(13, 20, 36, 0.76));
  border: 1px solid rgba(56, 189, 248, 0.22);
  box-shadow: inset 0 0 0 1px rgba(14, 165, 233, 0.08);
}
.battle-status-title { font-size: 18px; font-weight: 700; color: #f8fafc; }
.battle-status-desc { margin-top: 6px; font-size: 14px; color: #a5b4fc; }
#battle_events_v2 textarea { font-family: "IBM Plex Mono", "Fira Code", monospace; }
.turn-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.turn-eyebrow {
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #67e8f9;
}
.turn-title {
  font-size: 26px;
  font-weight: 700;
  color: #f8fafc;
}
.turn-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.turn-badge {
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.badge-mode {
  background: rgba(6, 182, 212, 0.12);
  border: 1px solid rgba(34, 211, 238, 0.35);
  color: #67e8f9;
}
.badge-phase {
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.35);
  color: #c4b5fd;
}
.map-stage {
  border-radius: 20px;
  padding: 16px;
  border: 1px solid rgba(56, 189, 248, 0.16);
  background:
    radial-gradient(circle at top, rgba(8, 47, 73, 0.26), transparent 35%),
    linear-gradient(180deg, rgba(4, 10, 19, 0.95), rgba(6, 12, 23, 0.84));
}
.empty-stage {
  min-height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-stage-text {
  color: #94a3b8;
  font-size: 15px;
  letter-spacing: 0.04em;
}
.map-legend {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.legend-chip {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
}
.map-grid {
  display: grid;
  gap: 8px;
}
.grid-cell {
  aspect-ratio: 1 / 1;
  min-height: 50px;
  border-radius: 14px;
  border: 1px solid rgba(100, 116, 139, 0.18);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(15, 23, 42, 0.54));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  position: relative;
  overflow: hidden;
}
.grid-cell::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(255,255,255,0.05), transparent 40%);
  opacity: 0.6;
}
.grid-empty {
  opacity: 0.55;
}
.grid-cell.team-red {
  border-color: rgba(248, 113, 113, 0.45);
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.12), 0 0 16px rgba(239, 68, 68, 0.08);
}
.grid-cell.team-blue {
  border-color: rgba(96, 165, 250, 0.45);
  box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.12), 0 0 16px rgba(59, 130, 246, 0.08);
}
.cell-label {
  position: relative;
  z-index: 1;
  font-size: 20px;
  font-weight: 800;
}
.team-red .cell-label, .team-red.legend-chip {
  color: #fca5a5;
}
.team-blue .cell-label, .team-blue.legend-chip {
  color: #93c5fd;
}
.cell-sub {
  position: relative;
  z-index: 1;
  font-size: 11px;
  color: #cbd5e1;
}
.summary-card {
  border-radius: 18px;
  padding: 18px;
  background:
    linear-gradient(180deg, rgba(5, 9, 19, 0.96), rgba(10, 15, 27, 0.82));
  border: 1px solid rgba(56, 189, 248, 0.18);
}
.summary-title {
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
  margin-bottom: 14px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.summary-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-radius: 14px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.66);
  border: 1px solid rgba(71, 85, 105, 0.35);
  min-width: 0;
}
.summary-label {
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #94a3b8;
}
.summary-value {
  font-size: 16px;
  font-weight: 800;
  color: #f8fafc;
  word-break: break-word;
}
.summary-red { color: #fda4af; }
.summary-blue { color: #93c5fd; }
.summary-draw { color: #fde68a; }
.unit-panel {
  max-height: 720px;
  overflow-y: auto;
  padding-right: 4px;
}
.memory-card {
  border-radius: 18px;
  padding: 16px;
  background:
    linear-gradient(180deg, rgba(5, 9, 19, 0.96), rgba(10, 15, 27, 0.82));
  border: 1px solid rgba(71, 85, 105, 0.28);
}
.memory-card.team-red {
  border-color: rgba(239, 68, 68, 0.28);
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.08);
}
.memory-card.team-blue {
  border-color: rgba(59, 130, 246, 0.28);
  box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.08);
}
.memory-card-title {
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
  margin-bottom: 12px;
}
.memory-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}
.memory-summary-item {
  border-radius: 12px;
  padding: 10px;
  background: rgba(15, 23, 42, 0.62);
  border: 1px solid rgba(71, 85, 105, 0.25);
}
.memory-summary-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.memory-summary-value {
  display: block;
  margin-top: 4px;
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
}
.memory-section + .memory-section {
  margin-top: 14px;
}
.memory-section-title {
  font-size: 13px;
  font-weight: 800;
  color: #cbd5e1;
  margin-bottom: 8px;
  letter-spacing: 0.05em;
}
.memory-list {
  display: grid;
  gap: 8px;
}
.memory-item {
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.58);
  border: 1px solid rgba(71, 85, 105, 0.24);
}
.memory-item-title {
  font-size: 13px;
  font-weight: 700;
  color: #f8fafc;
}
.memory-item-meta {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #94a3b8;
}
.memory-empty {
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.44);
  border: 1px dashed rgba(71, 85, 105, 0.26);
  color: #94a3b8;
  font-size: 12px;
}
.roster-side {
  padding-bottom: 18px;
}
.roster-header {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(9, 13, 24, 0.88));
  border: 1px solid rgba(71, 85, 105, 0.24);
}
.roster-header.team-red {
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.08);
}
.roster-header.team-blue {
  box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.08);
}
.roster-header-kicker {
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #94a3b8;
}
.roster-header-title {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 800;
  color: #f8fafc;
}
.job-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.job-card-button {
  min-height: 156px;
  border-radius: 20px !important;
  border: 1px solid rgba(100, 116, 139, 0.24) !important;
  background:
    radial-gradient(circle at top, rgba(255,255,255,0.06), transparent 32%),
    linear-gradient(180deg, rgba(12, 19, 34, 0.96), rgba(9, 13, 24, 0.88)) !important;
  white-space: pre-line !important;
  text-align: left !important;
  justify-content: flex-start !important;
  align-items: flex-start !important;
  padding: 18px !important;
  line-height: 1.55 !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  position: relative;
  overflow: hidden;
  padding-right: 88px !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.04),
    0 18px 30px rgba(2, 6, 23, 0.32);
}
.job-card-button::before {
  content: "";
  position: absolute;
  right: 14px;
  top: 14px;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(196, 181, 253, 0.08), rgba(15, 23, 42, 0.32)),
    linear-gradient(180deg, rgba(49, 46, 129, 0.12), rgba(15, 23, 42, 0.02));
  border: 1px solid rgba(226, 232, 240, 0.16);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 0 0 1px rgba(214, 182, 122, 0.18),
    0 10px 24px rgba(2, 6, 23, 0.26);
}
.job-card-button::after {
  content: "";
  position: absolute;
  right: 24px;
  top: 24px;
  width: 36px;
  height: 36px;
  background-image: var(--role-icon);
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
  filter: drop-shadow(0 2px 8px rgba(214, 182, 122, 0.25));
}
.job-card-button:hover {
  transform: translateY(-2px);
  filter: brightness(1.04);
}
.job-card-button.team-red {
  box-shadow:
    inset 0 0 0 1px rgba(239, 68, 68, 0.14),
    0 18px 30px rgba(2, 6, 23, 0.32),
    0 0 24px rgba(239, 68, 68, 0.08);
}
.job-card-button.team-blue {
  box-shadow:
    inset 0 0 0 1px rgba(59, 130, 246, 0.14),
    0 18px 30px rgba(2, 6, 23, 0.32),
    0 0 24px rgba(59, 130, 246, 0.08);
}
.job-card-button.team-red::before {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 0 0 1px rgba(239, 68, 68, 0.18),
    0 10px 24px rgba(2, 6, 23, 0.26);
}
.job-card-button.team-blue::before {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 0 0 1px rgba(59, 130, 246, 0.18),
    0 10px 24px rgba(2, 6, 23, 0.26);
}
.job-detail-panel {
  margin-top: 16px;
  padding: 18px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(255,255,255,0.05), transparent 20%),
    linear-gradient(180deg, rgba(8, 12, 24, 0.98), rgba(11, 16, 30, 0.9));
  border: 1px solid rgba(71, 85, 105, 0.3);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.03),
    0 24px 40px rgba(2, 6, 23, 0.34);
}
.job-detail-panel.team-red {
  box-shadow:
    inset 0 0 0 1px rgba(239, 68, 68, 0.1),
    0 24px 40px rgba(2, 6, 23, 0.34);
}
.job-detail-panel.team-blue {
  box-shadow:
    inset 0 0 0 1px rgba(59, 130, 246, 0.1),
    0 24px 40px rgba(2, 6, 23, 0.34);
}
.job-detail-head {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.job-detail-copy {
  min-width: 0;
}
.job-detail-emblem {
  flex: 0 0 72px;
  width: 72px;
  height: 72px;
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.08), rgba(15, 23, 42, 0.18)),
    linear-gradient(180deg, rgba(68, 64, 60, 0.28), rgba(15, 23, 42, 0.04));
  border: 1px solid rgba(226, 232, 240, 0.14);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 0 0 1px rgba(214, 182, 122, 0.16),
    0 16px 28px rgba(2, 6, 23, 0.26);
  background-image: var(--role-icon), linear-gradient(180deg, rgba(255,255,255,0.06), rgba(15, 23, 42, 0.08));
  background-repeat: no-repeat, no-repeat;
  background-position: center, center;
  background-size: 42px 42px, cover;
}
.job-detail-emblem.team-red {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 0 0 1px rgba(239, 68, 68, 0.16),
    0 16px 28px rgba(2, 6, 23, 0.26);
}
.job-detail-emblem.team-blue {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 0 0 1px rgba(59, 130, 246, 0.16),
    0 16px 28px rgba(2, 6, 23, 0.26);
}
.job-detail-kicker {
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #94a3b8;
}
.job-detail-title {
  margin-top: 4px;
  font-size: 34px;
  font-weight: 800;
  color: #f8fafc;
}
.job-detail-description {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #cbd5e1;
}
.job-close-button {
  margin-bottom: 14px;
}
.job-close-button.team-red {
  border-color: rgba(239, 68, 68, 0.28) !important;
}
.job-close-button.team-blue {
  border-color: rgba(59, 130, 246, 0.28) !important;
}
.job-count-row {
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.job-count-btn {
  min-width: 54px !important;
  font-size: 24px !important;
  font-weight: 800 !important;
}
.job-count-display {
  max-width: 140px;
}
.job-skill-panel {
  margin-top: 12px;
  border-radius: 16px;
  padding: 14px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.48));
  border: 1px solid rgba(71, 85, 105, 0.24);
}
.job-skill-title {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
}
.job-skill-name {
  margin-top: 6px;
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
}
.job-skill-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #c4b5fd;
}
.job-skill-desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #cbd5e1;
}
.unit-team-group + .unit-team-group {
  margin-top: 16px;
}
.unit-team-title {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.unit-card-list {
  display: grid;
  gap: 10px;
}
.unit-card {
  border-radius: 16px;
  padding: 14px;
  background: linear-gradient(180deg, rgba(8, 14, 28, 0.95), rgba(13, 18, 30, 0.82));
  border: 1px solid rgba(100, 116, 139, 0.22);
  position: relative;
  overflow: hidden;
}
.unit-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 3px;
}
.unit-card.team-red::before {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.95), rgba(251, 146, 60, 0.85));
}
.unit-card.team-blue::before {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.95), rgba(34, 211, 238, 0.85));
}
.unit-card.offline {
  opacity: 0.65;
}
.unit-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.unit-id {
  font-size: 15px;
  font-weight: 800;
  color: #f8fafc;
}
.unit-meta {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}
.unit-status {
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.status-online {
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.26);
}
.status-offline {
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.22);
}
.unit-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-top: 12px;
  font-size: 12px;
  color: #cbd5e1;
}
.unit-stats strong {
  color: #f8fafc;
  font-size: 13px;
}
.unit-skill-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.26);
}
.skill-name {
  color: #67e8f9;
  font-weight: 700;
  font-size: 12px;
}
.skill-cd {
  color: #c4b5fd;
  font-size: 12px;
  font-weight: 700;
}
.event-feed {
  display: grid;
  gap: 8px;
}
.event-item {
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  color: #dbeafe;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(71, 85, 105, 0.28);
}
.event-skill {
  border-color: rgba(250, 204, 21, 0.35);
  color: #fde68a;
}
.event-elim {
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}
.event-block {
  border-color: rgba(148, 163, 184, 0.35);
  color: #cbd5e1;
}
.unit-empty {
  border-radius: 14px;
  padding: 16px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.54);
  border: 1px dashed rgba(71, 85, 105, 0.35);
}
.gr-button-primary {
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.22);
}
@media (max-width: 1024px) {
  .summary-grid,
  .unit-stats,
  .memory-summary-grid {
    grid-template-columns: 1fr;
  }
  .job-card-grid {
    grid-template-columns: 1fr;
  }
  .turn-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .job-detail-head {
    flex-direction: column;
  }
}
"""

CUSTOM_CSS += build_role_icon_styles()


def _role_controls(team: Team):
    controls = []
    panels = []
    bindings = []
    defaults = default_team_config()[team]
    team_class = TEAM_CLASSES[team]

    with gr.Column(elem_classes=["panel-card", "roster-side", team_class]):
        gr.HTML(
            f"""
            <div class="roster-header {team_class}">
              <div class="roster-header-kicker">{TEAM_LABELS[team]} Roster Console</div>
              <div class="roster-header-title">{TEAM_LABELS[team]}阵容</div>
            </div>
            """
        )
        with gr.Row(elem_classes="job-card-grid"):
            for role in ROLE_ORDER:
                template = ROLE_TEMPLATES[role]
                count_default = defaults[role]["count"]
                card = gr.Button(
                    build_role_card_label(team, role, count_default),
                    elem_classes=["job-card-button", team_class, f"role-{role.value}"],
                )
                bindings.append({"card": card, "team": team, "role": role})

        for binding in bindings:
            role = binding["role"]
            card = binding["card"]
            template = ROLE_TEMPLATES[role]
            count_default = defaults[role]["count"]
            panel = gr.Column(visible=False, elem_classes=["job-detail-panel", team_class, f"panel-{role.value}"])
            with panel:
                gr.HTML(
                    build_role_detail_header(team, role)
                )
                close_btn = gr.Button("收起职业面板", elem_classes=["job-close-button", team_class])
                with gr.Row(elem_classes="job-count-row"):
                    minus_btn = gr.Button("−", elem_classes=["job-count-btn", team_class])
                    count = gr.Number(value=count_default, precision=0, label="数量", interactive=False, elem_classes="job-count-display")
                    plus_btn = gr.Button("+", elem_classes=["job-count-btn", team_class])
                hp = gr.Slider(minimum=template.hp_bounds[0], maximum=template.hp_bounds[1], step=5, value=template.hp, label="生命值")
                ammo = gr.Slider(minimum=template.ammo_bounds[0], maximum=template.ammo_bounds[1], step=1, value=template.ammo, label="资源数")
                vision = gr.Slider(minimum=template.vision_bounds[0], maximum=template.vision_bounds[1], step=1, value=template.vision_range, label="视野范围")
                attack = gr.Slider(minimum=template.attack_bounds[0], maximum=template.attack_bounds[1], step=1, value=template.attack_power, label="攻击力")
                speed = gr.Slider(minimum=template.speed_bounds[0], maximum=template.speed_bounds[1], step=1, value=template.move_speed, label="移动速度")
                gr.HTML(
                    f"""
                    <div class="job-skill-panel {team_class}">
                      <div class="job-skill-title">主动技能</div>
                      <div class="job-skill-name">{template.skill_name}</div>
                      <div class="job-skill-meta">冷却 {template.skill_cooldown} 回合</div>
                      <div class="job-skill-desc">{template.skill_description}</div>
                    </div>
                    """
                )
                controls.extend([count, hp, ammo, vision, attack, speed])
                panels.append(panel)
                binding["panel"] = panel
                binding["close_btn"] = close_btn
                binding["count"] = count
                binding["minus_btn"] = minus_btn
                binding["plus_btn"] = plus_btn

    return controls, panels, bindings


if gr is not None:
    theme = gr.themes.Soft(
        primary_hue="amber",
        secondary_hue="slate",
        neutral_hue="slate",
    ).set(
        body_background_fill="#0f172a",
        block_background_fill="rgba(15,23,42,0.72)",
        block_border_color="rgba(148,163,184,0.22)",
        button_primary_background_fill="#d97706",
        button_primary_background_fill_hover="#b45309",
    )

    with gr.Blocks(title="对抗演练控制台 2.0") as demo:
        frames_state = gr.State([])
        summary_state = gr.State(build_summary(None, running=True))

        with gr.Column(elem_classes="app-shell"):
            gr.Markdown(
                """
                <div class="hero-card">
                  <div style="display:flex; gap:10px; align-items:center; margin-bottom:8px;">
                    <span class="legend-chip team-red">RED</span>
                    <span class="legend-chip team-blue">BLUE</span>
                    <span style="font-size:13px; letter-spacing:0.12em; text-transform:uppercase; color:#67e8f9;">Confrontation Console 2.0</span>
                  </div>
                  <h1 style="margin:8px 0 10px; font-size:36px;">多智能体对抗演练控制台 2.0</h1>
                  <p style="margin:0; color:#cbd5e1; max-width:900px;">
                    旧版回放页仍然保留。这个 2.0 页面支持配置红蓝双方阵容、调整角色属性，并在实时推演和演练后回放两种模式之间切换。
                  </p>
                </div>
                """
            )

            with gr.Row():
                red_controls, red_panels, red_bindings = _role_controls(Team.RED)
                blue_controls, blue_panels, blue_bindings = _role_controls(Team.BLUE)

            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Column(elem_classes="panel-card"):
                        mode_input = gr.Radio(["实时推演", "演练后回放"], value="实时推演", label="播放模式")
                        max_turns_input = gr.Slider(minimum=10, maximum=80, step=5, value=config.max_turns, label="最大回合数")
                        preview_btn = gr.Button("预览阵容")
                        start_btn = gr.Button("开始演练", variant="primary")
                        roster_preview = gr.Markdown("### 阵容预览\n- 还未生成")
                        skill_reference = gr.Markdown(build_skill_reference())

                    with gr.Column(elem_classes="panel-card"):
                        turn_slider = gr.Slider(minimum=0, maximum=0, step=1, value=0, label="回合回看", interactive=False)
                        turn_title = gr.HTML(build_turn_header(None, "待命", "未开始"))
                        map_box = gr.HTML('<div class="map-stage empty-stage"><div class="empty-stage-text">点击“开始演练”后，这里会显示对抗态势。</div></div>')

                    with gr.Column(elem_classes="panel-card"):
                        events_box = gr.HTML(build_events_html("等待开始演练..."))

                with gr.Column(scale=1):
                    with gr.Column(elem_classes="panel-card"):
                        status_box = gr.HTML(build_status_html("idle", bool(config.api_key)))
                    with gr.Column(elem_classes="panel-card"):
                        summary_box = gr.HTML(build_summary(None, running=True))
                    with gr.Column(elem_classes="panel-card"):
                        units_box = gr.HTML('<div class="unit-panel"><div class="unit-empty">暂无单位状态</div></div>')
                    with gr.Column(elem_classes="panel-card"):
                        memory_red_box = gr.HTML('<div class="memory-card team-red"><div class="memory-card-title">红队情报池</div><div class="memory-empty">暂无情报</div></div>')
                    with gr.Column(elem_classes="panel-card"):
                        memory_blue_box = gr.HTML('<div class="memory-card team-blue"><div class="memory-card-title">蓝队情报池</div><div class="memory-empty">暂无情报</div></div>')

            with gr.Column(elem_classes="footer-card"):
                gr.Markdown(
                    """
                    旧版网页入口仍可使用：`./venv/bin/python -m src.battle.battle_ui`
                    2.0 入口：`./venv/bin/python -m src.battle.battle_ui_v2`
                    """
                )

        all_controls = red_controls + blue_controls
        all_panels = red_panels + blue_panels
        all_bindings = red_bindings + blue_bindings

        for binding in all_bindings:
            binding["card"].click(
                fn=lambda team_key=binding["team"].value, role_key=binding["role"].value: open_role_panel(team_key, role_key),
                outputs=all_panels,
            )
            binding["close_btn"].click(fn=close_role_panels, outputs=all_panels)
            binding["minus_btn"].click(
                fn=lambda current, team_key=binding["team"].value, role_key=binding["role"].value: adjust_count(team_key, role_key, current, -1),
                inputs=binding["count"],
                outputs=[binding["count"], binding["card"]],
            )
            binding["plus_btn"].click(
                fn=lambda current, team_key=binding["team"].value, role_key=binding["role"].value: adjust_count(team_key, role_key, current, 1),
                inputs=binding["count"],
                outputs=[binding["count"], binding["card"]],
            )

        preview_btn.click(fn=build_roster_preview, inputs=all_controls, outputs=roster_preview)
        start_btn.click(
            fn=run_battle_v2,
            inputs=[mode_input, max_turns_input] + all_controls,
            outputs=[
                frames_state,
                summary_state,
                turn_slider,
                turn_title,
                map_box,
                events_box,
                units_box,
                summary_box,
                memory_red_box,
                memory_blue_box,
                status_box,
            ],
        )
        turn_slider.change(
            fn=render_turn,
            inputs=[frames_state, turn_slider, summary_state],
            outputs=[turn_title, map_box, events_box, units_box, summary_box, memory_red_box, memory_blue_box],
        )
else:
    demo = None


if __name__ == "__main__":
    if gr is None:
        raise SystemExit("未检测到 gradio，请使用项目虚拟环境启动：./venv/bin/python -m src.battle.battle_ui_v2")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7862,
        share=False,
        inbrowser=False,
        theme=theme,
        css=CUSTOM_CSS,
    )
