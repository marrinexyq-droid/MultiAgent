import json
import re
import time

try:
    import gradio as gr
except ImportError:  # pragma: no cover - depends on local runtime
    gr = None

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on local runtime
    OpenAI = None

import src.battle.battle_ui_v2 as v2
from src.battle.config import config


ADVICE_CACHE: dict[str, str] = {}


def _record_visible_enemy_contacts(agents, env, memory_red, memory_blue, turn: int) -> int:
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
        memory_pool = memory_red if agent.state.team == v2.Team.RED else memory_blue
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


def _reason_text(reason: str) -> str:
    return {
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
    }.get(reason, reason)


def _winner_text(result: dict) -> tuple[str, str]:
    if not result or not result.get("winner"):
        return "平局", "summary-draw"
    winner_key = result["winner"].value
    if winner_key == "red":
        return "红队", "summary-red"
    if winner_key == "blue":
        return "蓝队", "summary-blue"
    return "平局", "summary-draw"


def _metric_label(metric_key: str) -> str:
    return {
        "elimination_score": "减员压制",
        "survival_score": "生存保持",
        "objective_score": "目标控制",
        "initiative_score": "态势主动",
        "coordination_score": "协同质量",
    }.get(metric_key, metric_key)


def _build_breakdown_rows(team_key: str, breakdown: dict) -> str:
    team_class = "team-red" if team_key == "red" else "team-blue"
    if not breakdown:
        return '<div class="settlement-empty">暂无分项数据</div>'
    rows = []
    for metric, value in breakdown.items():
        width = max(6, min(100, round(float(value) * 100)))
        rows.append(
            f"""
            <div class="score-row {team_class}">
              <div class="score-row-head">
                <span class="score-metric">{_metric_label(metric)}</span>
                <span class="score-value">{value:.2f}</span>
              </div>
              <div class="score-bar-track">
                <div class="score-bar-fill {team_class}" style="width:{width}%;"></div>
              </div>
            </div>
            """
        )
    return "".join(rows)


def _build_merit_cards(agent_merits: dict, team_key: str) -> str:
    team_class = "team-red" if team_key == "red" else "team-blue"
    items = [(agent_id, merit) for agent_id, merit in agent_merits.items() if merit.get("team") == team_key][:3]
    if not items:
        return '<div class="settlement-empty">暂无功勋记录</div>'
    cards = []
    for rank, (agent_id, merit) in enumerate(items, start=1):
        badges = " · ".join(merit.get("commendations", [])) or "常规贡献"
        stats = merit.get("stats", {})
        role_text = {
            "commander": "协调",
            "scout": "侦察",
            "attacker": "攻击手",
            "defender": "防御手",
        }.get(merit.get("role"), merit.get("role", "-"))
        cards.append(
            f"""
            <div class="merit-card {team_class}">
              <div class="merit-rank">#{rank}</div>
              <div class="merit-head">
                <div>
                  <div class="merit-id">{v2.escape(agent_id)}</div>
                  <div class="merit-meta">{role_text} · {badges}</div>
                </div>
                <div class="merit-score">{merit.get("merit_score", 0):.2f}</div>
              </div>
              <div class="merit-stats">
                <span>伤害 <strong>{stats.get('damage_dealt', 0)}</strong></span>
                <span>侦获 <strong>{stats.get('enemy_spotted', 0)}</strong></span>
                <span>任务 <strong>{stats.get('tasks_completed', 0)}</strong></span>
                <span>控点 <strong>{stats.get('control_turns', 0)}</strong></span>
              </div>
              <div class="merit-explanation">{v2.escape(merit.get("explanation", "暂无解释"))}</div>
            </div>
            """
        )
    return "".join(cards)


def _team_agents(env, team):
    return {aid: agent for aid, agent in env.agents.items() if agent.team == team}


def _survival_rate(agents: dict) -> float:
    total_hp = sum(agent.hp for agent in agents.values() if agent.alive)
    max_hp = sum(agent.max_hp for agent in agents.values()) or 1
    return total_hp / max_hp


def _control_points_pressure(env, team) -> int:
    pressure = 0
    for point in env._control_points():
        for agent in env.agents.values():
            if agent.alive and agent.team != team and agent.pos.distance_to(point) <= 2:
                pressure += 1
    return pressure


def _base_advice_text(item: dict) -> str:
    action_names = {
        "focus_primary_threat": "优先集火主威胁",
        "tighten_control_zone": "收缩防线稳住控制区",
        "refresh_recon": "补充侦察刷新态势",
        "push_active_task": "推进活跃任务",
        "reassign_tasks": "重新分配任务",
    }
    team_names = {"red": "红队", "blue": "蓝队"}
    role_names = {
        "coordinator": "协调",
        "scout": "侦察",
        "attacker": "攻击手",
        "defender": "防御手",
        "support": "支援",
        "jammer": "干扰",
        "controller": "控制",
        "assaulter": "突击",
    }
    team_text = team_names.get(item.get("target_team"), item.get("target_team", ""))
    role_text = role_names.get(item.get("target_role"), "单位")
    action_text = action_names.get(item.get("action"), item.get("action", "调整行动"))
    reason = item.get("reason_text", item.get("reason", "当前态势发生变化"))
    evidence = item.get("evidence_text")
    suffix = f" 依据：{evidence}" if evidence else ""
    return f"建议{team_text}{role_text}{action_text}，原因是{reason}。{suffix}".strip()


def _polish_advice_text(item: dict) -> str:
    base_text = _base_advice_text(item)
    if not config.api_key or OpenAI is None:
        return base_text

    cache_key = json.dumps(
        {
            "team": item.get("target_team"),
            "role": item.get("target_role"),
            "action": item.get("action"),
            "reason": item.get("reason"),
            "evidence": item.get("evidence_text"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    if cache_key in ADVICE_CACHE:
        return ADVICE_CACHE[cache_key]

    try:
        client = OpenAI(api_key=config.api_key, base_url=config.api_base_url)
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是对抗演练指挥辅助系统。请将结构化建议改写成一句简洁、明确、可执行的中文建议，不要改变建议对象和核心意图。",
                },
                {"role": "user", "content": base_text},
            ],
            temperature=0.3,
            max_tokens=80,
        )
        text = response.choices[0].message.content.strip()
        polished = text if _looks_like_valid_advice(text) else base_text
    except Exception:
        polished = base_text

    ADVICE_CACHE[cache_key] = polished
    return polished


def _looks_like_valid_advice(text: str) -> bool:
    if not text or len(text.strip()) < 6:
        return False
    lowered = text.lower()
    if "kukuk" in lowered:
        return False
    if re.search(r"[?]{3,}", text):
        return False
    if re.search(r"([a-z]{2,}\?){2,}", lowered):
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_word_count = len(re.findall(r"[A-Za-z]{3,}", text))
    if cjk_count == 0 and ascii_word_count > 4:
        return False
    return True


def _build_advice_items(env, memory_red, memory_blue) -> list[dict]:
    judge = v2.BattleJudge()
    red_agents = _team_agents(env, v2.Team.RED)
    blue_agents = _team_agents(env, v2.Team.BLUE)
    red_scores = judge._team_scores(v2.Team.RED, red_agents, blue_agents, env, memory_red)
    blue_scores = judge._team_scores(v2.Team.BLUE, blue_agents, red_agents, env, memory_blue)
    red_summary = memory_red.read_summary()
    blue_summary = memory_blue.read_summary()
    items: list[dict] = []

    def add_item(item: dict):
        key = (item["target_team"], item["target_role"], item["action"])
        if any((old["target_team"], old["target_role"], old["action"]) == key for old in items):
            return
        item["rendered_text"] = _polish_advice_text(item)
        items.append(item)

    if red_summary.get("primary_threat"):
        add_item(
            {
                "priority": "high",
                "target_team": "red",
                "target_role": "attacker",
                "action": "focus_primary_threat",
                "reason": "confirmed_threat_window",
                "reason_text": f"当前已锁定主威胁 {red_summary['primary_threat']}",
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
                "reason_text": "当前情报衰减，红队缺少新鲜敌情",
                "evidence": {"memory_health": red_summary.get("memory_health")},
                "evidence_text": f"记忆状态：{red_summary.get('memory_health')}",
                "turn": env.turn,
            }
        )

    blue_pressure = _control_points_pressure(env, v2.Team.BLUE)
    if blue_pressure > 0 and (blue_scores["objective_score"] <= red_scores["objective_score"] or _survival_rate(blue_agents) < _survival_rate(red_agents)):
        add_item(
            {
                "priority": "high",
                "target_team": "blue",
                "target_role": "defender",
                "action": "tighten_control_zone",
                "reason": "control_zone_pressure",
                "reason_text": "控制区周边出现接敌压力，蓝队需要先稳住阵地",
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
                "reason_text": "蓝队情报更新偏弱，需要先补足态势感知",
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
                "reason_text": "当前任务链路已经形成，需要协调单位继续推进执行",
                "evidence": {
                    "active_tasks": coord_summary.get("active_tasks", 0),
                    "focus": coord_summary.get("recommended_focus"),
                },
                "evidence_text": f"活跃任务 {coord_summary.get('active_tasks', 0)}，当前建议：{coord_summary.get('recommended_focus')}",
                "turn": env.turn,
            }
        )

    return items[:3]


def build_advice_panel(advice_items: list[dict]) -> str:
    if not advice_items:
        return """
        <div class="advice-panel">
          <div class="advice-panel-title">实时建议</div>
          <div class="advice-empty">当前没有额外建议，态势相对稳定。</div>
        </div>
        """

    rows = []
    for item in advice_items:
        team_class = "team-red" if item.get("target_team") == "red" else "team-blue"
        rows.append(
            f"""
            <div class="advice-card {team_class}">
              <div class="advice-head">
                <span class="advice-priority priority-{item.get('priority', 'medium')}">{v2.escape(item.get('priority', 'medium').upper())}</span>
                <span class="advice-target">{v2.escape(item.get('target_team', '-').upper())} · {v2.escape(item.get('target_role', '-'))}</span>
              </div>
              <div class="advice-text">{v2.escape(item.get('rendered_text', ''))}</div>
              <div class="advice-evidence">{v2.escape(item.get('evidence_text', ''))}</div>
            </div>
            """
        )
    return f'<div class="advice-panel"><div class="advice-panel-title">实时建议</div>{"".join(rows)}</div>'


def capture_frame_v3(env, mode_label: str, phase_label: str, memory_red, memory_blue) -> dict:
    frame = v2.capture_frame(env, mode_label, phase_label, memory_red, memory_blue)
    advice_items = _build_advice_items(env, memory_red, memory_blue)
    frame["advice_items"] = advice_items
    frame["advice_html"] = build_advice_panel(advice_items)
    return frame


def build_summary_v3(result: dict | None, running: bool = False) -> str:
    if running or result is None:
        return """
        <div class="summary-card settlement-shell">
          <div class="summary-title">结算总览</div>
          <div class="settlement-empty">演练进行中，等待团队评分与功勋生成。</div>
        </div>
        """

    winner_text, winner_class = _winner_text(result)
    breakdown = result.get("score_breakdown", {})
    red_breakdown = breakdown.get("red", {})
    blue_breakdown = breakdown.get("blue", {})
    agent_merits = result.get("agent_merits", {})

    return f"""
    <div class="summary-card settlement-shell">
      <div class="summary-title">结算总览 V3</div>
      <div class="settlement-hero">
        <div class="settlement-main">
          <div class="summary-label">最终判定</div>
          <div class="settlement-winner {winner_class}">{winner_text}</div>
          <div class="settlement-reason">{v2.escape(_reason_text(result.get('reason', 'draw')))}</div>
        </div>
        <div class="settlement-meta-grid">
          <div class="settlement-meta-card team-red">
            <span class="summary-label">红队总分</span>
            <span class="settlement-meta-value">{result.get('red_score', 0):.3f}</span>
          </div>
          <div class="settlement-meta-card team-blue">
            <span class="summary-label">蓝队总分</span>
            <span class="settlement-meta-value">{result.get('blue_score', 0):.3f}</span>
          </div>
          <div class="settlement-meta-card">
            <span class="summary-label">回合数</span>
            <span class="settlement-meta-value">{result.get('turn', '-')}</span>
          </div>
          <div class="settlement-meta-card">
            <span class="summary-label">主导胜因</span>
            <span class="settlement-meta-value">{v2.escape(_reason_text(result.get('dominant_reason', result.get('reason', 'draw'))))}</span>
          </div>
        </div>
      </div>
      <div class="settlement-score-grid">
        <div class="settlement-score-panel team-red">
          <div class="settlement-panel-title">红队评分分解</div>
          {_build_breakdown_rows('red', red_breakdown)}
        </div>
        <div class="settlement-score-panel team-blue">
          <div class="settlement-panel-title">蓝队评分分解</div>
          {_build_breakdown_rows('blue', blue_breakdown)}
        </div>
      </div>
      <div class="settlement-merit-grid">
        <div class="settlement-merit-panel team-red">
          <div class="settlement-panel-title">红队功勋榜</div>
          {_build_merit_cards(agent_merits, 'red')}
        </div>
        <div class="settlement-merit-panel team-blue">
          <div class="settlement-panel-title">蓝队功勋榜</div>
          {_build_merit_cards(agent_merits, 'blue')}
        </div>
      </div>
    </div>
    """


def run_battle_v3(mode: str, max_turns: int, *values):
    team_config = v2._build_team_config_from_inputs(*values)
    max_turns = int(max_turns)
    llm_enabled = bool(config.api_key)
    agents, env, memory_red, memory_blue = v2._create_runtime(team_config, max_turns)
    phase_label = "实时推演" if mode == "实时推演" else "演练后回放"
    frames = [capture_frame_v3(env, mode, phase_label, memory_red, memory_blue)]
    total = 0

    if mode == "演练后回放":
        yield (
            frames,
            build_summary_v3(None, running=True),
            v2._slider_update(minimum=0, maximum=0, value=0, interactive=False),
            v2.build_turn_header(0, mode, "计算中"),
            frames[0]["map"],
            frames[0]["events_html"],
            frames[0]["units"],
            build_summary_v3(None, running=True),
            frames[0]["memory_red"],
            frames[0]["memory_blue"],
            frames[0]["advice_html"],
            v2.build_status_html("computing", llm_enabled),
        )

        for turn in range(1, max_turns + 1):
            actions = v2._build_actions(agents, env, memory_red, memory_blue, turn)
            _record_visible_enemy_contacts(agents, env, memory_red, memory_blue, turn)
            _, done = env.step(actions)
            memory_red.update_task_progress(env.agents, env.turn)
            memory_blue.update_task_progress(env.agents, env.turn)
            if turn % 3 == 0:
                memory_red.decay()
                memory_blue.decay()
            frames.append(capture_frame_v3(env, mode, "计算完成", memory_red, memory_blue))
            if done:
                break

        result = v2.BattleJudge().evaluate(env, memory_red, memory_blue)
        summary = build_summary_v3(result)
        total = len(frames) - 1
        for idx in range(len(frames)):
            title, map_md, events, units, _, memory_red_html, memory_blue_html = v2.render_turn(frames, idx, summary)
            yield (
                frames,
                summary,
                v2._slider_update(minimum=0, maximum=total, value=idx, interactive=True),
                title,
                map_md,
                events,
                units,
                summary,
                memory_red_html,
                memory_blue_html,
                frames[idx]["advice_html"],
                v2.build_status_html("done" if idx == total else "computing", llm_enabled),
            )
            time.sleep(0.18)
        return

    summary = build_summary_v3(None, running=True)
    yield (
        frames,
        summary,
        v2._slider_update(minimum=0, maximum=0, value=0, interactive=False),
        v2.build_turn_header(0, mode, "实时推演中"),
        frames[0]["map"],
        frames[0]["events_html"],
        frames[0]["units"],
        summary,
        frames[0]["memory_red"],
        frames[0]["memory_blue"],
        frames[0]["advice_html"],
        v2.build_status_html("running", llm_enabled),
    )

    for turn in range(1, max_turns + 1):
        actions = v2._build_actions(agents, env, memory_red, memory_blue, turn)
        _record_visible_enemy_contacts(agents, env, memory_red, memory_blue, turn)
        _, done = env.step(actions)
        memory_red.update_task_progress(env.agents, env.turn)
        memory_blue.update_task_progress(env.agents, env.turn)
        if turn % 3 == 0:
            memory_red.decay()
            memory_blue.decay()
        frames.append(capture_frame_v3(env, mode, "实时推演中", memory_red, memory_blue))
        total = len(frames) - 1
        frame = frames[-1]
        yield (
            frames,
            summary,
            v2._slider_update(minimum=0, maximum=total, value=total, interactive=False),
            v2.build_turn_header(frame["turn"], mode, "实时推演中"),
            frame["map"],
            frame["events_html"],
            frame["units"],
            summary,
            frame["memory_red"],
            frame["memory_blue"],
            frame["advice_html"],
            v2.build_status_html("running", llm_enabled),
        )
        if done:
            break

    result = v2.BattleJudge().evaluate(env, memory_red, memory_blue)
    summary = build_summary_v3(result)
    final_frame = frames[-1]
    yield (
        frames,
        summary,
        v2._slider_update(minimum=0, maximum=len(frames) - 1, value=len(frames) - 1, interactive=True),
        v2.build_turn_header(final_frame["turn"], mode, "已结束"),
        final_frame["map"],
        final_frame["events_html"],
        final_frame["units"],
        summary,
        final_frame["memory_red"],
        final_frame["memory_blue"],
        final_frame["advice_html"],
        v2.build_status_html("done", llm_enabled),
    )


def render_turn_v3(frames: list[dict], turn_index: int, summary: str):
    title, map_md, events, units, _, memory_red_html, memory_blue_html = v2.render_turn(frames, turn_index, summary)
    if not frames:
        advice_html = build_advice_panel([])
    else:
        turn_index = max(0, min(turn_index, len(frames) - 1))
        advice_html = frames[turn_index].get("advice_html", build_advice_panel([]))
    return title, map_md, events, units, summary, memory_red_html, memory_blue_html, advice_html


V3_CSS = v2.CUSTOM_CSS + """
.gradio-container {
  background:
    radial-gradient(circle at top left, rgba(244, 63, 94, 0.08), transparent 22%),
    radial-gradient(circle at 85% 10%, rgba(56, 189, 248, 0.08), transparent 20%),
    linear-gradient(180deg, #09090b 0%, #0f1014 44%, #151720 100%);
}
.app-shell.v3-shell {
  max-width: 1480px;
  gap: 28px;
  padding-bottom: 36px;
}
.aw-header {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 18px;
  align-items: stretch;
}
.aw-hero {
  border-radius: 28px;
  padding: 34px 36px 30px;
  background:
    linear-gradient(135deg, rgba(20, 20, 24, 0.94), rgba(28, 29, 35, 0.86)),
    linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0));
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.28);
}
.aw-kicker {
  font-size: 11px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: #a5b4fc;
  margin-bottom: 20px;
}
.aw-title {
  margin: 0;
  font-size: clamp(42px, 5vw, 76px);
  line-height: 0.94;
  letter-spacing: -0.06em;
  color: #fafaf9;
  max-width: 8ch;
}
.aw-copy {
  margin: 18px 0 0;
  max-width: 56ch;
  color: #d4d4d8;
  font-size: 15px;
  line-height: 1.7;
}
.aw-side-stack {
  display: grid;
  gap: 18px;
}
.aw-meta-card {
  border-radius: 28px;
  padding: 24px;
  background: linear-gradient(180deg, rgba(18, 18, 23, 0.92), rgba(24, 25, 31, 0.84));
  border: 1px solid rgba(255, 255, 255, 0.07);
}
.aw-meta-label {
  display: block;
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #a1a1aa;
}
.aw-meta-value {
  display: block;
  margin-top: 10px;
  font-size: 24px;
  font-weight: 800;
  color: #fafaf9;
}
.aw-section {
  display: grid;
  gap: 14px;
}
.aw-section-head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
}
.aw-section-kicker {
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: #a1a1aa;
}
.aw-section-title {
  margin-top: 6px;
  font-size: 30px;
  line-height: 1;
  letter-spacing: -0.04em;
  color: #fafaf9;
}
.aw-section-copy {
  color: #a1a1aa;
  font-size: 14px;
  max-width: 52ch;
}
.aw-surface {
  border-radius: 28px;
  padding: 22px;
  background: linear-gradient(180deg, rgba(17, 17, 22, 0.92), rgba(25, 27, 34, 0.86));
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 22px 60px rgba(0, 0, 0, 0.18);
}
.aw-deployment-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.aw-battle-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.65fr);
  gap: 18px;
  align-items: start;
}
.aw-battle-main,
.aw-intel-stack {
  display: grid;
  gap: 18px;
}
.aw-controls-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}
.panel-card {
  border-radius: 24px;
  padding: 20px;
  background: linear-gradient(180deg, rgba(17, 17, 22, 0.9), rgba(24, 25, 31, 0.82));
  border: 1px solid rgba(255,255,255,0.08);
}
.settlement-shell {
  display: grid;
  gap: 14px;
}
.settlement-hero {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 12px;
}
.settlement-main {
  border-radius: 16px;
  padding: 14px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.84), rgba(9, 13, 24, 0.72));
  border: 1px solid rgba(71, 85, 105, 0.3);
}
.settlement-winner {
  margin-top: 8px;
  font-size: 34px;
  font-weight: 900;
  letter-spacing: -0.04em;
}
.settlement-reason {
  margin-top: 8px;
  color: #cbd5e1;
  font-size: 14px;
}
.settlement-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.settlement-meta-card {
  border-radius: 14px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.66);
  border: 1px solid rgba(71, 85, 105, 0.32);
}
.settlement-meta-value {
  display: block;
  margin-top: 6px;
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
}
.settlement-score-grid,
.settlement-merit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.settlement-score-panel,
.settlement-merit-panel {
  border-radius: 16px;
  padding: 14px;
  background: rgba(15, 23, 42, 0.58);
  border: 1px solid rgba(71, 85, 105, 0.28);
}
.settlement-score-panel.team-red,
.settlement-merit-panel.team-red,
.settlement-meta-card.team-red {
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.08);
}
.settlement-score-panel.team-blue,
.settlement-merit-panel.team-blue,
.settlement-meta-card.team-blue {
  box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.08);
}
.settlement-panel-title {
  font-size: 14px;
  font-weight: 800;
  color: #f8fafc;
  margin-bottom: 10px;
  letter-spacing: 0.05em;
}
.score-row + .score-row,
.merit-card + .merit-card {
  margin-top: 10px;
}
.score-row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.score-metric {
  font-size: 12px;
  color: #cbd5e1;
}
.score-value {
  font-size: 12px;
  color: #f8fafc;
  font-weight: 800;
}
.score-bar-track {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(51, 65, 85, 0.7);
}
.score-bar-fill {
  height: 100%;
  border-radius: inherit;
}
.score-bar-fill.team-red {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.96), rgba(251, 146, 60, 0.84));
}
.score-bar-fill.team-blue {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.96), rgba(34, 211, 238, 0.84));
}
.merit-card {
  position: relative;
  border-radius: 14px;
  padding: 12px;
  background: linear-gradient(180deg, rgba(8, 14, 28, 0.95), rgba(13, 18, 30, 0.82));
  border: 1px solid rgba(100, 116, 139, 0.22);
}
.merit-rank {
  position: absolute;
  right: 12px;
  top: 10px;
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
}
.merit-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.merit-id {
  font-size: 14px;
  font-weight: 800;
  color: #f8fafc;
}
.merit-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #cbd5e1;
}
.merit-score {
  font-size: 18px;
  font-weight: 900;
  color: #fde68a;
}
.merit-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-top: 12px;
  font-size: 12px;
  color: #94a3b8;
}
.merit-stats strong {
  color: #f8fafc;
}
.merit-explanation {
  margin-top: 10px;
  font-size: 12px;
  color: #a1a1aa;
  line-height: 1.6;
}
.settlement-empty {
  border-radius: 14px;
  padding: 14px;
  background: rgba(15, 23, 42, 0.54);
  border: 1px dashed rgba(71, 85, 105, 0.35);
  color: #94a3b8;
}
.advice-panel {
  display: grid;
  gap: 12px;
}
.advice-panel-title {
  font-size: 14px;
  font-weight: 800;
  color: #fafaf9;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.advice-card {
  border-radius: 18px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255,255,255,0.08);
}
.advice-card.team-red {
  box-shadow: inset 0 0 0 1px rgba(244, 63, 94, 0.08);
}
.advice-card.team-blue {
  box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.08);
}
.advice-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.advice-priority {
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.priority-high {
  background: rgba(244, 63, 94, 0.12);
  color: #fecdd3;
}
.priority-medium {
  background: rgba(250, 204, 21, 0.12);
  color: #fde68a;
}
.advice-target {
  font-size: 11px;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}
.advice-text {
  color: #fafaf9;
  font-size: 14px;
  line-height: 1.7;
}
.advice-evidence {
  margin-top: 8px;
  font-size: 12px;
  color: #a1a1aa;
}
.advice-empty {
  border-radius: 16px;
  padding: 14px;
  background: rgba(255,255,255,0.03);
  border: 1px dashed rgba(255,255,255,0.1);
  color: #a1a1aa;
}
.dock-anchor {
  position: relative;
  top: -28px;
  display: block;
  height: 0;
  width: 0;
}
.floating-dock {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 60;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 22px;
  background: rgba(24, 24, 29, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(18px);
}
.dock-brand {
  min-width: 58px;
  height: 58px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #23242a;
  color: #fafaf9;
  font-size: 18px;
  font-weight: 900;
  text-decoration: none;
  letter-spacing: -0.04em;
}
.dock-group {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.05);
}
.dock-link,
.dock-action,
.dock-menu summary,
.dock-role-btn {
  border: 0;
  outline: none;
  appearance: none;
  min-height: 44px;
  padding: 0 16px;
  border-radius: 14px;
  background: transparent;
  color: #f4f4f5;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}
.dock-link:hover,
.dock-action:hover,
.dock-menu summary:hover,
.dock-role-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}
.dock-action.is-primary {
  background: #f5f5f4;
  color: #18181b;
}
.dock-action.is-primary:hover {
  background: #ffffff;
}
.dock-menu {
  position: relative;
}
.dock-menu summary {
  list-style: none;
}
.dock-menu summary::-webkit-details-marker {
  display: none;
}
.dock-role-grid {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  min-width: 178px;
  padding: 8px;
  border-radius: 18px;
  background: rgba(24, 24, 29, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.24);
  display: grid;
  gap: 6px;
}
.dock-role-btn {
  width: 100%;
  justify-content: flex-start;
}
.dock-role-btn.team-red:hover {
  background: rgba(244, 63, 94, 0.12);
}
.dock-role-btn.team-blue:hover {
  background: rgba(56, 189, 248, 0.12);
}
@media (max-width: 1180px) {
  .floating-dock {
    width: min(calc(100vw - 18px), 920px);
    overflow-x: auto;
    justify-content: flex-start;
  }
}
@media (max-width: 1024px) {
  .aw-header,
  .aw-deployment-grid,
  .aw-battle-grid,
  .settlement-hero,
  .settlement-score-grid,
  .settlement-merit-grid,
  .settlement-meta-grid,
  .merit-stats {
    grid-template-columns: 1fr;
  }
  .floating-dock {
    width: calc(100vw - 16px);
    left: 8px;
    right: 8px;
    bottom: 8px;
    transform: none;
    border-radius: 18px;
  }
}
"""


if gr is not None:
    theme = v2.theme

    with gr.Blocks(title="对抗演练控制台 3.0") as demo:
        frames_state = gr.State([])
        summary_state = gr.State(build_summary_v3(None, running=True))

        with gr.Column(elem_classes=["app-shell", "v3-shell"]):
            gr.HTML('<span id="section-hero" class="dock-anchor"></span>')
            gr.HTML(
                """
                <div class="aw-header">
                  <div class="aw-hero">
                    <div class="aw-kicker">Confrontation Console / Editorial V3</div>
                    <h1 class="aw-title">多智能体 对抗演练 指挥控制台</h1>
                    <p class="aw-copy">
                      这一版将阵容部署、实时态势、团队结算、共享情报与战场建议统一到一个更像作品展示页的入口里。
                      它保留推演能力，但让“为什么这样打、为什么这样赢”更容易被看懂。
                    </p>
                  </div>
                  <div class="aw-side-stack">
                    <div class="aw-meta-card">
                      <span class="aw-meta-label">Version</span>
                      <span class="aw-meta-value">V3 / Merit + Advice</span>
                    </div>
                    <div class="aw-meta-card">
                      <span class="aw-meta-label">Style Direction</span>
                      <span class="aw-meta-value">Awwwards Inspired Editorial Layout</span>
                    </div>
                  </div>
                </div>
                """
            )

            gr.HTML('<span id="section-deployment" class="dock-anchor"></span>')
            gr.HTML(
                """
                <div class="aw-section-head">
                  <div>
                    <div class="aw-section-kicker">Deployment</div>
                    <div class="aw-section-title">战备部署</div>
                  </div>
                  <div class="aw-section-copy">先在这里编排红蓝阵容、调整角色参数，再进入演练。</div>
                </div>
                """
            )
            with gr.Row(elem_classes="aw-deployment-grid"):
                red_controls, red_panels, red_bindings = v2._role_controls(v2.Team.RED)
                blue_controls, blue_panels, blue_bindings = v2._role_controls(v2.Team.BLUE)

            gr.HTML('<span id="section-battle" class="dock-anchor"></span>')
            gr.HTML(
                """
                <div class="aw-section-head">
                  <div>
                    <div class="aw-section-kicker">Live Theatre</div>
                    <div class="aw-section-title">演练主舞台</div>
                  </div>
                  <div class="aw-section-copy">左侧负责操作、地图与事件，右侧聚合结算、情报与实时建议。</div>
                </div>
                """
            )
            with gr.Row(elem_classes="aw-battle-grid"):
                with gr.Column(elem_classes="aw-battle-main"):
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        mode_input = gr.Radio(["实时推演", "演练后回放"], value="实时推演", label="播放模式")
                        max_turns_input = gr.Slider(minimum=10, maximum=80, step=5, value=config.max_turns, label="最大回合数")
                        preview_btn = gr.Button("预览阵容", elem_id="dock-preview-target")
                        start_btn = gr.Button("开始演练", variant="primary", elem_id="dock-start-target")
                        roster_preview = gr.Markdown("### 阵容预览\n- 还未生成")
                        skill_reference = gr.Markdown(v2.build_skill_reference())

                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        turn_slider = gr.Slider(minimum=0, maximum=0, step=1, value=0, label="回合回看", interactive=False, elem_id="dock-turn-slider")
                        turn_title = gr.HTML(v2.build_turn_header(None, "待命", "未开始"))
                        map_box = gr.HTML('<div class="map-stage empty-stage"><div class="empty-stage-text">点击“开始演练”后，这里会显示对抗态势。</div></div>')

                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        events_box = gr.HTML(v2.build_events_html("等待开始演练..."))

                with gr.Column(elem_classes="aw-intel-stack"):
                    gr.HTML('<span id="section-intelligence" class="dock-anchor"></span>')
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        status_box = gr.HTML(v2.build_status_html("idle", bool(config.api_key)))
                    gr.HTML('<span id="section-settlement" class="dock-anchor"></span>')
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        summary_box = gr.HTML(build_summary_v3(None, running=True))
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        advice_box = gr.HTML(build_advice_panel([]))
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        units_box = gr.HTML('<div class="unit-panel"><div class="unit-empty">暂无单位状态</div></div>')
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        memory_red_box = gr.HTML('<div class="memory-card team-red"><div class="memory-card-title">红队情报池</div><div class="memory-empty">暂无情报</div></div>')
                    with gr.Column(elem_classes=["panel-card", "aw-surface"]):
                        memory_blue_box = gr.HTML('<div class="memory-card team-blue"><div class="memory-card-title">蓝队情报池</div><div class="memory-empty">暂无情报</div></div>')

            with gr.Column(elem_classes=["footer-card", "aw-surface"]):
                gr.Markdown(
                    """
                    旧版网页入口：`./venv/bin/python -m src.battle.battle_ui`
                    2.0 入口：`./venv/bin/python -m src.battle.battle_ui_v2`
                    3.0 入口：`./venv/bin/python -m src.battle.battle_ui_v3`
                    """
                )

            gr.HTML(
                """
                <div class="floating-dock" id="floating-dock">
                  <a class="dock-brand" href="#section-hero">W.</a>
                  <div class="dock-group">
                    <a class="dock-link" href="#section-deployment">部署</a>
                    <a class="dock-link" href="#section-battle">战场</a>
                    <a class="dock-link" href="#section-intelligence">情报</a>
                    <a class="dock-link" href="#section-settlement">结算</a>
                  </div>
                  <div class="dock-group">
                    <button class="dock-action" type="button" onclick="window.v3DockTrigger('preview')">预览</button>
                    <button class="dock-action is-primary" type="button" onclick="window.v3DockTrigger('start')">开始</button>
                    <button class="dock-action" type="button" onclick="window.v3DockTrigger('battle')">回看</button>
                    <button class="dock-action" type="button" onclick="window.v3DockTrigger('top')">顶部</button>
                  </div>
                  <div class="dock-group">
                    <details class="dock-menu">
                      <summary>Red +</summary>
                      <div class="dock-role-grid">
                        <button class="dock-role-btn team-red" type="button" onclick="window.v3DockTrigger('role:red:commander')">协调</button>
                        <button class="dock-role-btn team-red" type="button" onclick="window.v3DockTrigger('role:red:scout')">侦察</button>
                        <button class="dock-role-btn team-red" type="button" onclick="window.v3DockTrigger('role:red:attacker')">攻击手</button>
                        <button class="dock-role-btn team-red" type="button" onclick="window.v3DockTrigger('role:red:defender')">防御手</button>
                      </div>
                    </details>
                    <details class="dock-menu">
                      <summary>Blue +</summary>
                      <div class="dock-role-grid">
                        <button class="dock-role-btn team-blue" type="button" onclick="window.v3DockTrigger('role:blue:commander')">协调</button>
                        <button class="dock-role-btn team-blue" type="button" onclick="window.v3DockTrigger('role:blue:scout')">侦察</button>
                        <button class="dock-role-btn team-blue" type="button" onclick="window.v3DockTrigger('role:blue:attacker')">攻击手</button>
                        <button class="dock-role-btn team-blue" type="button" onclick="window.v3DockTrigger('role:blue:defender')">防御手</button>
                      </div>
                    </details>
                  </div>
                </div>
                <script>
                window.v3DockTrigger = function(action) {
                  const scrollToId = (id) => {
                    const node = document.getElementById(id);
                    if (node) node.scrollIntoView({behavior: "smooth", block: "start"});
                  };
                  if (action === "preview") {
                    document.getElementById("dock-preview-target")?.click();
                    return;
                  }
                  if (action === "start") {
                    document.getElementById("dock-start-target")?.click();
                    return;
                  }
                  if (action === "battle") {
                    scrollToId("section-battle");
                    return;
                  }
                  if (action === "top") {
                    scrollToId("section-hero");
                    return;
                  }
                  if (action.startsWith("role:")) {
                    const [, team, role] = action.split(":");
                    document.getElementById(`dock-open-${team}-${role}`)?.click();
                    document.querySelectorAll(".dock-menu[open]").forEach((node) => node.removeAttribute("open"));
                  }
                };
                </script>
                """
            )

        all_controls = red_controls + blue_controls
        all_panels = red_panels + blue_panels
        all_bindings = red_bindings + blue_bindings
        dock_role_triggers = {}

        with gr.Column(visible=False):
            for team in v2.TEAM_ORDER:
                for role in v2.ROLE_ORDER:
                    dock_role_triggers[(team.value, role.value)] = gr.Button(
                        value=f"open-{team.value}-{role.value}",
                        visible=False,
                        elem_id=f"dock-open-{team.value}-{role.value}",
                    )

        for binding in all_bindings:
            binding["card"].click(
                fn=lambda team_key=binding["team"].value, role_key=binding["role"].value: v2.open_role_panel(team_key, role_key),
                outputs=all_panels,
            )
            binding["close_btn"].click(fn=v2.close_role_panels, outputs=all_panels)
            binding["minus_btn"].click(
                fn=lambda current, team_key=binding["team"].value, role_key=binding["role"].value: v2.adjust_count(team_key, role_key, current, -1),
                inputs=binding["count"],
                outputs=[binding["count"], binding["card"]],
            )
            binding["plus_btn"].click(
                fn=lambda current, team_key=binding["team"].value, role_key=binding["role"].value: v2.adjust_count(team_key, role_key, current, 1),
                inputs=binding["count"],
                outputs=[binding["count"], binding["card"]],
            )

        for (team_key, role_key), trigger in dock_role_triggers.items():
            trigger.click(
                fn=lambda team_key=team_key, role_key=role_key: v2.open_role_panel(team_key, role_key),
                outputs=all_panels,
            )

        preview_btn.click(fn=v2.build_roster_preview, inputs=all_controls, outputs=roster_preview)
        start_btn.click(
            fn=run_battle_v3,
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
                advice_box,
                status_box,
            ],
        )
        turn_slider.change(
            fn=render_turn_v3,
            inputs=[frames_state, turn_slider, summary_state],
            outputs=[turn_title, map_box, events_box, units_box, summary_box, memory_red_box, memory_blue_box, advice_box],
        )
else:
    demo = None


if __name__ == "__main__":
    if gr is None:
        raise SystemExit("未检测到 gradio，请使用项目虚拟环境启动：./venv/bin/python -m src.battle.battle_ui_v3")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7863,
        share=False,
        inbrowser=False,
        theme=theme,
        css=V3_CSS,
    )
