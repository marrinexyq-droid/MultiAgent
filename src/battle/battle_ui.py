import json
import time
import uuid

try:
    import gradio as gr
except ImportError:  # pragma: no cover - depends on local runtime
    gr = None

from src.battle.battle_types import Message, Team
from src.battle.config import config
from src.battle.judge import BattleJudge
from src.battle.memory import SharedMemoryPool
from src.battle.runner import create_agents
from src.battle.env import BattlefieldEnv


def build_unit_status(env: BattlefieldEnv) -> str:
    team_names = {"red": "红队", "blue": "蓝队"}
    role_names = {
        "commander": "协调",
        "scout": "侦测",
        "attacker": "执行",
        "defender": "应对",
    }
    lines = [
        "| 单位 | 阵营 | 角色 | 位置 | 状态值 | 资源 | 状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    for agent in env.agents.values():
        hp = f"{agent.hp}/{agent.max_hp}" if agent.alive else "0"
        ammo = str(agent.ammo) if agent.alive else "-"
        state = "在线" if agent.alive else "已失效"
        lines.append(
            f"| {agent.agent_id} | {team_names.get(agent.team.value, agent.team.value)} | "
            f"{role_names.get(agent.role.value, agent.role.value)} | "
            f"({agent.pos.x},{agent.pos.y}) | {hp} | {ammo} | {state} |"
        )
    return "\n".join(lines)


def build_summary(result: dict) -> str:
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
    parts = [
        f"### 演练结果",
        f"- 获胜方：{winner_name[winner_key]}",
        f"- 原因：{reason_names.get(result['reason'], result['reason'])}",
        f"- 回合数：{result['turn']}",
        f"- 红队总分：{result.get('red_score', '-')}",
        f"- 蓝队总分：{result.get('blue_score', '-')}",
    ]
    if "red_rate" in result:
        parts.append(f"- 红队存活率：{result['red_rate']}")
        parts.append(f"- 蓝队存活率：{result['blue_rate']}")
    if result.get("agent_merits"):
        parts.append("- 功勋前列：")
        for agent_id, merit in list(result["agent_merits"].items())[:3]:
            parts.append(f"  - {agent_id}：{merit['merit_score']} / {','.join(merit['commendations'])}")
    return "\n".join(parts)


def capture_frame(env: BattlefieldEnv) -> dict:
    events = "\n".join(env.events) if env.events else "本回合无事件"
    return {
        "turn": env.turn,
        "map": f"```text\n{env.render()}\n```",
        "events": events,
        "units": build_unit_status(env),
    }


def simulate_battle(max_turns: int) -> tuple[list[dict], str]:
    agents, red_states, blue_states = create_agents()
    env = BattlefieldEnv(grid_size=config.grid_size)
    env.max_turns = max_turns
    env.reset(red_states, blue_states)

    memory_red = SharedMemoryPool(Team.RED, battle_stats=env.stats)
    memory_blue = SharedMemoryPool(Team.BLUE, battle_stats=env.stats)
    frames = [capture_frame(env)]

    for turn in range(1, max_turns + 1):
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

        _, done = env.step(actions)
        memory_red.update_task_progress(env.agents, env.turn)
        memory_blue.update_task_progress(env.agents, env.turn)

        if turn % 3 == 0:
            memory_red.decay()
            memory_blue.decay()

        frames.append(capture_frame(env))
        if done:
            break

    result = BattleJudge().evaluate(env, memory_red, memory_blue)
    return frames, build_summary(result)


def render_turn(frames: list[dict], turn_index: int, summary: str):
    if not frames:
        return (
            "### 等待开始",
            "```text\n点击“开始演练”后，这里会显示对抗态势。\n```",
            "等待开始演练...",
            "| 单位 | 阵营 | 角色 | 位置 | 状态值 | 资源 | 状态 |\n|---|---|---|---|---|---|---|",
            summary or "### 演练结果\n- 尚未开始",
        )

    turn_index = max(0, min(turn_index, len(frames) - 1))
    frame = frames[turn_index]
    title = f"### 第 {frame['turn']} 回合视图"
    return title, frame["map"], frame["events"], frame["units"], summary


def run_battle_stream(max_turns: int):
    max_turns = int(max_turns)
    frames, summary = simulate_battle(max_turns)
    total = len(frames) - 1

    for idx in range(len(frames)):
        title, map_md, events, units, summary_md = render_turn(frames, idx, summary)
        yield (
            frames,
            summary,
            gr.update(minimum=0, maximum=total, value=idx, interactive=True),
            title,
            map_md,
            events,
            units,
            summary_md,
            build_status_html("running" if idx < total else "done"),
        )
        time.sleep(0.2)


def build_status_html(state: str) -> str:
    mapping = {
        "idle": ("待命中", "点击“开始演练”后，系统会自动播放每个回合。"),
        "running": ("演练进行中", "对抗态势、事件和单位状态正在按回合刷新。"),
        "done": ("演练结束", "你可以拖动滑杆回看任意回合。"),
    }
    title, desc = mapping.get(state, mapping["idle"])
    return f"""
    <div class="battle-status battle-status-{state}">
      <div class="battle-status-title">{title}</div>
      <div class="battle-status-desc">{desc}</div>
    </div>
    """


CUSTOM_CSS = """
.gradio-container {
  background:
    radial-gradient(circle at top left, rgba(212, 175, 55, 0.18), transparent 28%),
    linear-gradient(135deg, #0f172a 0%, #1e293b 46%, #334155 100%);
  color: #e2e8f0;
}
.app-shell {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 18px 40px;
}
.hero-card, .panel-card, .footer-card {
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 22px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(14px);
}
.hero-card {
  padding: 24px 26px;
  margin-bottom: 18px;
}
.panel-card {
  padding: 18px 18px 14px;
}
.footer-card {
  padding: 14px 18px;
  margin-top: 18px;
}
.battle-status {
  border-radius: 18px;
  padding: 16px 18px;
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.22);
}
.battle-status-title {
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
}
.battle-status-desc {
  margin-top: 6px;
  font-size: 14px;
  color: #cbd5e1;
}
#battle_events textarea {
  font-family: "IBM Plex Mono", "Fira Code", monospace;
}
"""


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

    with gr.Blocks(title="对抗演练回放台") as demo:
        frames_state = gr.State([])
        summary_state = gr.State("### 演练结果\n- 尚未开始")

        with gr.Column(elem_classes="app-shell"):
            gr.Markdown(
                """
                <div class="hero-card">
                  <div style="font-size:13px; letter-spacing:0.12em; text-transform:uppercase; color:#fbbf24;">Confrontation Replay Console</div>
                  <h1 style="margin:8px 0 10px; font-size:36px;">多智能体对抗演练网页回放台</h1>
                  <p style="margin:0; color:#cbd5e1;">
                    这个页面适合演示对抗过程。点击开始后，系统会自动推演并逐回合刷新对抗态势、
                    事件日志与单位状态；演练结束后，也可以通过滑杆回看任意回合。
                  </p>
                </div>
                """
            )

            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Column(elem_classes="panel-card"):
                        with gr.Row():
                            max_turns_input = gr.Slider(
                                minimum=10,
                                maximum=80,
                                step=5,
                                value=config.max_turns,
                                label="最大回合数",
                            )
                            start_btn = gr.Button("开始演练", variant="primary")
                        turn_slider = gr.Slider(
                            minimum=0,
                            maximum=0,
                            step=1,
                            value=0,
                            label="回合回看",
                            interactive=False,
                        )
                        turn_title = gr.Markdown("### 等待开始")
                        map_box = gr.Markdown("```text\n点击“开始演练”后，这里会显示对抗态势。\n```")

                    with gr.Column(elem_classes="panel-card"):
                        events_box = gr.Textbox(
                            label="回合事件",
                            lines=10,
                            interactive=False,
                            value="等待开始演练...",
                            elem_id="battle_events",
                        )

                with gr.Column(scale=1):
                    with gr.Column(elem_classes="panel-card"):
                        status_box = gr.HTML(build_status_html("idle"))
                    with gr.Column(elem_classes="panel-card"):
                        summary_box = gr.Markdown("### 演练结果\n- 尚未开始")
                    with gr.Column(elem_classes="panel-card"):
                        units_box = gr.Markdown(
                            "| 单位 | 阵营 | 角色 | 位置 | 状态值 | 资源 | 状态 |\n|---|---|---|---|---|---|---|"
                        )

            with gr.Column(elem_classes="footer-card"):
                gr.Markdown(
                    """
                    命令行仍然适合调试；这个网页更适合演示、录屏和汇报对抗过程。
                    启动方式：`./venv/bin/python -m src.battle.battle_ui`
                    """
                )

        start_btn.click(
            fn=run_battle_stream,
            inputs=max_turns_input,
            outputs=[
                frames_state,
                summary_state,
                turn_slider,
                turn_title,
                map_box,
                events_box,
                units_box,
                summary_box,
                status_box,
            ],
        )

        turn_slider.change(
            fn=render_turn,
            inputs=[frames_state, turn_slider, summary_state],
            outputs=[turn_title, map_box, events_box, units_box, summary_box],
        )
else:
    demo = None


if __name__ == "__main__":
    if gr is None:
        raise SystemExit("未检测到 gradio，请使用项目虚拟环境启动：./venv/bin/python -m src.battle.battle_ui")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        inbrowser=False,
        theme=theme,
        css=CUSTOM_CSS,
    )
