import json
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.battle.battle_types import AgentState, Position, Role, Team, Message
from src.battle.config import config
from src.battle.env import BattlefieldEnv
from src.battle.memory import SharedMemoryPool
from src.battle.judge import BattleJudge
from src.battle.agents.red.commander import RedCommander
from src.battle.agents.red.scout import RedScout
from src.battle.agents.red.attacker import RedAttacker
from src.battle.agents.blue.defender import BlueDefender


def create_agents():
    red_states = [
        AgentState("red_coordinator", Team.RED, Role.COMMANDER, Position(1, 1), hp=120, max_hp=120, vision_range=2, attack_range=1, attack_power=20),
        AgentState("red_probe", Team.RED, Role.SCOUT, Position(2, 2), hp=80, max_hp=80, vision_range=4, attack_range=1, attack_power=15),
        AgentState("red_striker", Team.RED, Role.ATTACKER, Position(1, 2), hp=100, max_hp=100, vision_range=2, attack_range=1, attack_power=30),
    ]
    blue_states = [
        AgentState("blue_guard_1", Team.BLUE, Role.DEFENDER, Position(6, 6), hp=100, max_hp=100, vision_range=2, attack_range=1, attack_power=25),
        AgentState("blue_guard_2", Team.BLUE, Role.DEFENDER, Position(6, 5), hp=100, max_hp=100, vision_range=2, attack_range=1, attack_power=25),
    ]

    agents = {
        "red_coordinator": RedCommander(red_states[0]),
        "red_probe": RedScout(red_states[1]),
        "red_striker": RedAttacker(red_states[2]),
        "blue_guard_1": BlueDefender(blue_states[0]),
        "blue_guard_2": BlueDefender(blue_states[1]),
    }

    return agents, red_states, blue_states


def main():
    print("=" * 60)
    print("        多智能体对抗演练系统 - Phase 1 MVP")
    print("=" * 60)

    if not config.api_key:
        print("\n[警告] 未设置 SILICONFLOW_API_KEY，将使用规则策略。")
        print("       设置环境变量可启用 LLM 决策。\n")
    else:
        print(f"\n[信息] 使用 LLM: {config.model}")
        print(f"[信息] API 地址: {config.api_base_url}\n")

    agents, red_states, blue_states = create_agents()

    env = BattlefieldEnv(grid_size=config.grid_size)
    env.reset(red_states, blue_states)

    memory_red = SharedMemoryPool(Team.RED, battle_stats=env.stats)
    memory_blue = SharedMemoryPool(Team.BLUE, battle_stats=env.stats)
    log_lines: list[str] = []

    initial_render = env.render()
    print(initial_render)
    log_lines.append(initial_render)
    print("\n" + "-" * 40 + "\n")
    log_lines.append("\n" + "-" * 40 + "\n")

    for turn in range(1, config.max_turns + 1):
        actions = []

        for agent_id, agent in agents.items():
            if not agent.state.alive:
                continue

            obs = env.get_observation(agent_id)
            if not obs:
                continue

            team = agent.state.team
            shared_mem = memory_red.read(agent_id) if team == Team.RED else memory_blue.read(agent_id)

            action = agent.choose_action(obs, shared_mem)
            actions.append(action)

            if action.action_type.value == "communicate":
                try:
                    content = json.loads(action.message)
                    if isinstance(content, dict):
                        msg_content = content
                    else:
                        msg_content = {"type": "enemy_spot", "message": action.message}
                except (json.JSONDecodeError, TypeError):
                    msg_content = {"type": "enemy_spot", "message": action.message}

                msg = Message(
                    msg_id=str(uuid.uuid4())[:8],
                    sender_id=agent_id,
                    sender_role=agent.state.role,
                    content=msg_content,
                    timestamp=turn,
                )
                if team == Team.RED:
                    memory_red.write(msg)
                else:
                    memory_blue.write(msg)

        obs, done = env.step(actions)
        memory_red.update_task_progress(env.agents, env.turn)
        memory_blue.update_task_progress(env.agents, env.turn)

        if turn % 3 == 0:
            memory_red.decay()
            memory_blue.decay()

        turn_render = env.render()
        print(turn_render)
        log_lines.append(turn_render)
        print("\n" + "-" * 40 + "\n")
        log_lines.append("\n" + "-" * 40 + "\n")

        if done:
            break

    result = BattleJudge().evaluate(env, memory_red, memory_blue)
    print("=" * 60)
    winner_name = {"red": "红队", "blue": "蓝队", None: "平局"}
    reason_names = {
        "red_eliminated": "红队全部失效",
        "blue_eliminated": "蓝队全部失效",
        "higher_survival_rate": "存活率更高",
        "draw": "平局"
    }
    print(f"  演练结果: 获胜方 = {winner_name.get(result['winner'].value if result['winner'] else 'draw', '平局')}")
    print(f"  原因: {reason_names.get(result['reason'], result['reason'])}")
    print(f"  回合数: {result['turn']}")
    print(f"  红队总分: {result['red_score']}, 蓝队总分: {result['blue_score']}")
    print(f"  红队存活率: {result['red_rate']}, 蓝队存活率: {result['blue_rate']}")
    print(f"  主导胜因: {result['dominant_reason']}")
    print("  团队分解:")
    for team_key, label in (("red", "红队"), ("blue", "蓝队")):
        breakdown = result["score_breakdown"][team_key]
        print(f"    {label}: {breakdown}")
    print("  功勋前列:")
    for agent_id, merit in list(result["agent_merits"].items())[:3]:
        print(f"    {agent_id}: 分数={merit['merit_score']}, 称号={','.join(merit['commendations'])}")
    print("=" * 60)
    log_lines.extend(
        [
            "=" * 60,
            f"  演练结果: 获胜方 = {winner_name.get(result['winner'].value if result['winner'] else 'draw', '平局')}",
            f"  原因: {reason_names.get(result['reason'], result['reason'])}",
            f"  回合数: {result['turn']}",
            f"  红队总分: {result['red_score']}, 蓝队总分: {result['blue_score']}",
            f"  红队存活率: {result['red_rate']}, 蓝队存活率: {result['blue_rate']}",
            f"  主导胜因: {result['dominant_reason']}",
            f"  团队分解: red={result['score_breakdown']['red']}, blue={result['score_breakdown']['blue']}",
        ]
    )
    for agent_id, merit in list(result["agent_merits"].items())[:5]:
        log_lines.append(f"  功勋: {agent_id} => 分数={merit['merit_score']}, 称号={','.join(merit['commendations'])}")
    log_lines.append("=" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(config.log_dir, f"confrontation_{timestamp}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"[日志] 已保存到: {log_path}")


if __name__ == "__main__":
    main()
