"""
AutoGen 红蓝对抗推演系统
======================
红方（进攻）vs 蓝方（防御），多轮自动对抗，裁判实时更新战场。
"""

import asyncio
import datetime
import random
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WARGAME_LOG_DIR = PROJECT_ROOT / "outputs" / "wargame_logs"


# ══════════════════════════════════════════
# 战场状态（全局可变，每轮更新）
# ══════════════════════════════════════════

GAME_STATE = {
    "round": 1,
    "max_rounds": 5,
    "winner": None,
    "red_forces": {
        "fighters": {"count": 4, "health": 100, "ammo": 100, "type": "F-16"},
        "bombers":  {"count": 2, "health": 100, "ammo": 100, "type": "B-52"},
        "armor":    {"count": 20, "health": 100, "ammo": 100, "type": "M1A2"},
        "missiles": {"count": 8, "health": 100, "ammo": 100, "type": "Tomahawk"},
    },
    "blue_forces": {
        "fighters": {"count": 2, "health": 100, "ammo": 100, "type": "J-20"},
        "air_defense": {"count": 3, "health": 100, "ammo": 100, "type": "HQ-9"},
        "armor":    {"count": 10, "health": 100, "ammo": 100, "type": "99A"},
        "infantry": {"count": 500, "health": 100, "ammo": 100, "type": "步兵营"},
    },
    "battle_log": [],
    "territory": {
        "red_controlled": 20,   # 百分比
        "blue_controlled": 80,
        "contested": 0,
    },
}


# ══════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════

async def get_battle_state() -> str:
    """获取当前红蓝双方战场态势，包括兵力、损失和战线情况。"""
    r = GAME_STATE["red_forces"]
    b = GAME_STATE["blue_forces"]
    t = GAME_STATE["territory"]
    log = GAME_STATE["battle_log"]
    last_events = log[-3:] if log else ["暂无交战记录"]

    return f"""
=== 第 {GAME_STATE['round']} / {GAME_STATE['max_rounds']} 轮 战场态势 ===

【🔴 红方兵力】
- 战斗机 {r['fighters']['type']}: {r['fighters']['count']}架，状态{r['fighters']['health']}%，弹药{r['fighters']['ammo']}%
- 轰炸机 {r['bombers']['type']}:  {r['bombers']['count']}架，状态{r['bombers']['health']}%，弹药{r['bombers']['ammo']}%
- 装甲   {r['armor']['type']}: {r['armor']['count']}辆，状态{r['armor']['health']}%，弹药{r['armor']['ammo']}%
- 导弹   {r['missiles']['type']}: {r['missiles']['count']}枚，剩余{r['missiles']['ammo']}%

【🔵 蓝方兵力】
- 战斗机 {b['fighters']['type']}: {b['fighters']['count']}架，状态{b['fighters']['health']}%，弹药{b['fighters']['ammo']}%
- 防空   {b['air_defense']['type']}: {b['air_defense']['count']}套，状态{b['air_defense']['health']}%，弹药{b['air_defense']['ammo']}%
- 装甲   {b['armor']['type']}: {b['armor']['count']}辆，状态{b['armor']['health']}%，弹药{b['armor']['ammo']}%
- 步兵   {b['infantry']['type']}: {b['infantry']['count']}人，状态{b['infantry']['health']}%

【战线态势】
- 红方控制区域: {t['red_controlled']}%
- 蓝方控制区域: {t['blue_controlled']}%
- 争夺中区域:   {t['contested']}%

【最近战况】
{chr(10).join(f'  - {e}' for e in last_events)}
"""


async def red_action(
    primary_target: str,
    attack_type: str,
    units_used: str
) -> str:
    """
    红方执行进攻行动。

    Args:
        primary_target: 攻击目标，如 'fighters'/'air_defense'/'armor'/'infantry'
        attack_type: 攻击方式，如 'air_strike'/'missile_strike'/'armor_assault'/'combined'
        units_used: 使用的兵种，如 'fighters,bombers' 或 'missiles,armor'
    Returns:
        行动执行结果
    """
    valid_targets = list(GAME_STATE["blue_forces"].keys())
    if primary_target not in valid_targets:
        primary_target = random.choice(valid_targets)

    action_record = f"🔴 红方 [{attack_type}] 攻击蓝方 [{primary_target}]，投入兵力：{units_used}"
    GAME_STATE["battle_log"].append(action_record)

    return f"""
红方行动已记录：
- 主攻目标：{primary_target}
- 攻击方式：{attack_type}
- 投入兵力：{units_used}
- 状态：等待裁判计算结果
"""


async def blue_action(
    defense_priority: str,
    defense_type: str,
    units_deployed: str
) -> str:
    """
    蓝方执行防御/反击行动。

    Args:
        defense_priority: 防御重点，如 'air_defense'/'armor_defense'/'counterattack'
        defense_type: 防御方式，如 'intercept'/'fortify'/'counter_strike'/'withdraw'
        units_deployed: 部署的兵种，如 'fighters,air_defense' 或 'armor,infantry'
    Returns:
        行动执行结果
    """
    action_record = f"🔵 蓝方 [{defense_type}] 应对，重点：[{defense_priority}]，部署：{units_deployed}"
    GAME_STATE["battle_log"].append(action_record)

    return f"""
蓝方行动已记录：
- 防御重点：{defense_priority}
- 防御方式：{defense_type}
- 部署兵力：{units_deployed}
- 状态：等待裁判计算结果
"""


async def calculate_round_result() -> str:
    """
    裁判计算本轮交战结果，更新双方损失和战场态势。
    基于双方行动和兵力对比进行仿真计算。
    """
    log = GAME_STATE["battle_log"]
    if len(log) < 2:
        return "本轮无有效行动记录"

    red = GAME_STATE["red_forces"]
    blue = GAME_STATE["blue_forces"]
    territory = GAME_STATE["territory"]

    # 计算兵力对比
    red_air_power = (
        red["fighters"]["count"] * red["fighters"]["health"] / 100
        + red["bombers"]["count"] * red["bombers"]["health"] / 100
        + red["missiles"]["ammo"] / 100 * 5
    )
    blue_air_defense = (
        blue["fighters"]["count"] * blue["fighters"]["health"] / 100 * 1.2
        + blue["air_defense"]["count"] * blue["air_defense"]["health"] / 100 * 2.5
    )
    red_ground = red["armor"]["count"] * red["armor"]["health"] / 100
    blue_ground = (
        blue["armor"]["count"] * blue["armor"]["health"] / 100 * 1.5
        + blue["infantry"]["count"] / 100 * blue["infantry"]["health"] / 100
    )

    # 计算空战结果
    air_ratio = red_air_power / max(blue_air_defense, 1)
    if air_ratio > 1.2:
        # 红方空中占优
        blue["fighters"]["health"] = max(0, blue["fighters"]["health"] - random.randint(15, 30))
        blue["air_defense"]["health"] = max(0, blue["air_defense"]["health"] - random.randint(10, 25))
        red["fighters"]["health"] = max(0, red["fighters"]["health"] - random.randint(5, 15))
        red["fighters"]["ammo"] = max(0, red["fighters"]["ammo"] - random.randint(20, 35))
        air_result = f"空战：红方占优，蓝方战机损失{30 - blue['fighters']['health']}%，防空受损"
    else:
        # 蓝方防空有效
        red["fighters"]["health"] = max(0, red["fighters"]["health"] - random.randint(15, 30))
        red["bombers"]["health"] = max(0, red["bombers"]["health"] - random.randint(20, 40))
        blue["air_defense"]["ammo"] = max(0, blue["air_defense"]["ammo"] - random.randint(25, 40))
        air_result = f"空战：蓝方防空有效，拦截红方轰炸机，红方空中力量受损"

    # 计算地面结果
    ground_ratio = red_ground / max(blue_ground, 1)
    if ground_ratio > 1.3:
        red["armor"]["health"] = max(0, red["armor"]["health"] - random.randint(5, 15))
        blue["armor"]["health"] = max(0, blue["armor"]["health"] - random.randint(20, 35))
        blue["infantry"]["health"] = max(0, blue["infantry"]["health"] - random.randint(10, 20))
        territory["red_controlled"] = min(100, territory["red_controlled"] + random.randint(5, 15))
        territory["blue_controlled"] = max(0, territory["blue_controlled"] - random.randint(5, 15))
        ground_result = f"地面：红方装甲突破，蓝方防线后退，红方控制区+{15}%"
    else:
        red["armor"]["health"] = max(0, red["armor"]["health"] - random.randint(15, 25))
        red["armor"]["count"] = max(0, red["armor"]["count"] - random.randint(1, 4))
        blue["armor"]["ammo"] = max(0, blue["armor"]["ammo"] - random.randint(15, 25))
        ground_result = f"地面：蓝方防线稳固，击毁红方坦克 {random.randint(1, 4)} 辆"

    # 导弹攻击结果
    if red["missiles"]["ammo"] > 20:
        hit_rate = random.uniform(0.3, 0.7)
        damage = int(red["missiles"]["count"] * hit_rate * 10)
        red["missiles"]["ammo"] = max(0, red["missiles"]["ammo"] - 25)
        blue["infantry"]["health"] = max(0, blue["infantry"]["health"] - damage // 10)
        missile_result = f"导弹：Tomahawk 打击效果 {int(hit_rate*100)}%，蓝方后勤受损"
    else:
        missile_result = "导弹：红方导弹库存不足，本轮未使用"

    # 更新战场记录
    round_summary = f"第{GAME_STATE['round']}轮结果：{air_result} | {ground_result} | {missile_result}"
    GAME_STATE["battle_log"].append(round_summary)

    # 检查胜负条件
    victory_msg = ""
    if blue["fighters"]["health"] <= 10 and blue["air_defense"]["health"] <= 10:
        GAME_STATE["winner"] = "RED"
        victory_msg = "\n🔴🏆 红方获胜：蓝方制空权丧失！"
    elif red["fighters"]["health"] <= 10 and red["bombers"]["health"] <= 10:
        GAME_STATE["winner"] = "BLUE"
        victory_msg = "\n🔵🏆 蓝方获胜：红方空中力量被消灭！"
    elif territory["red_controlled"] >= 60:
        GAME_STATE["winner"] = "RED"
        victory_msg = f"\n🔴🏆 红方获胜：控制区域达到{territory['red_controlled']}%！"
    elif GAME_STATE["round"] >= GAME_STATE["max_rounds"] and not GAME_STATE["winner"]:
        # 按控制区域判定
        if territory["red_controlled"] > territory["blue_controlled"]:
            GAME_STATE["winner"] = "RED"
            victory_msg = "\n🔴🏆 推演结束：红方按控制区域判定获胜"
        else:
            GAME_STATE["winner"] = "BLUE"
            victory_msg = "\n🔵🏆 推演结束：蓝方成功防御，判定获胜"

    return f"""
=== 第 {GAME_STATE['round']} 轮 交战结果 ===

【空中作战】{air_result}
【地面作战】{ground_result}
【导弹打击】{missile_result}

【兵力现状】
🔴 红方：战机{red['fighters']['health']}% | 轰炸机{red['bombers']['health']}% | 装甲{red['armor']['count']}辆/{red['armor']['health']}%
🔵 蓝方：战机{blue['fighters']['health']}% | 防空{blue['air_defense']['health']}% | 装甲{blue['armor']['health']}%

【战线变化】
红方控制：{territory['red_controlled']}% | 蓝方控制：{territory['blue_controlled']}%
{victory_msg}
"""


# ══════════════════════════════════════════
# 单轮推演
# ══════════════════════════════════════════

def get_model():
    return OllamaChatCompletionClient(
        model="qwen2.5:7b",
        host="http://localhost:11434",
    )


async def run_one_round(round_num: int):
    """运行一轮红蓝对抗"""
    print(f"\n{'='*60}")
    print(f"⚔️  第 {round_num} 轮对抗开始")
    print(f"{'='*60}")

    red_commander = AssistantAgent(
        name="RedCommander",
        model_client=get_model(),
        tools=[get_battle_state, red_action],
        system_message="""你是🔴红方进攻指挥官。
任务：
1. 调用 get_battle_state() 了解当前态势
2. 分析我方优势和蓝方弱点
3. 调用 red_action() 下达本轮进攻命令
   - primary_target: 选择最薄弱的蓝方目标
   - attack_type: 根据兵力选择最优攻击方式
   - units_used: 列出投入的兵种
4. 简述你的战术意图（1-2句）

目标：突破蓝方防线，扩大控制区域。""",
    )

    blue_commander = AssistantAgent(
        name="BlueCommander",
        model_client=get_model(),
        tools=[get_battle_state, blue_action],
        system_message="""你是🔵蓝方防御指挥官。
任务：
1. 分析红方的进攻意图（从战场态势判断）
2. 调用 blue_action() 下达本轮防御命令
   - defense_priority: 判断最需要保护的方向
   - defense_type: 选择防御/拦截/反击
   - units_deployed: 部署相应兵力
3. 简述你的防御思路（1-2句）

目标：守住防线，消耗红方有生力量。""",
    )

    referee = AssistantAgent(
        name="Referee",
        model_client=get_model(),
        tools=[calculate_round_result],
        system_message="""你是⚖️战场裁判官。
任务：
1. 调用 calculate_round_result() 计算本轮交战结果
2. 公正评述双方表现（各1句）
3. 指出对下一轮的关键影响
4. 如果有获胜方，宣布结果并输出 ROUND_END
   如果未分胜负，直接输出 ROUND_END

保持客观，基于数据评判。""",
    )

    termination = (
        TextMentionTermination("ROUND_END")
        | MaxMessageTermination(8)
    )

    team = RoundRobinGroupChat(
        participants=[red_commander, blue_commander, referee],
        termination_condition=termination,
    )

    await Console(team.run_stream(
        task=f"第{round_num}轮推演开始，红蓝双方各自行动，裁判计算结果"
    ))


# ══════════════════════════════════════════
# 主循环：多轮对抗
# ══════════════════════════════════════════

async def main():
    # 保存推演记录
    WARGAME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = WARGAME_LOG_DIR / f"wargame_{timestamp}.txt"

    print("\n" + "🔴" * 15 + " VS " + "🔵" * 15)
    print("      AutoGen 红蓝对抗推演系统")
    print("🔴" * 15 + " VS " + "🔵" * 15)
    print(f"\n共 {GAME_STATE['max_rounds']} 轮对抗，每轮双方各自决策")
    print("胜利条件：控制区域 ≥ 60% 或摧毁对方主要兵力\n")

    # 多轮推演主循环
    for round_num in range(1, GAME_STATE["max_rounds"] + 1):
        GAME_STATE["round"] = round_num

        await run_one_round(round_num)

        # 检查是否已分出胜负
        if GAME_STATE["winner"]:
            break

        # 轮间间隔提示
        if round_num < GAME_STATE["max_rounds"]:
            print(f"\n⏸  第 {round_num} 轮结束，准备下一轮...\n")

    # 最终结果
    print("\n" + "=" * 60)
    print("📊 推演总结")
    print("=" * 60)

    winner = GAME_STATE["winner"]
    territory = GAME_STATE["territory"]
    red = GAME_STATE["red_forces"]
    blue = GAME_STATE["blue_forces"]

    summary = f"""
🏆 最终结果：{"🔴 红方获胜" if winner == "RED" else "🔵 蓝方获胜"}

【最终兵力对比】
🔴 红方剩余：
  - 战斗机：{red['fighters']['count']}架 ({red['fighters']['health']}%)
  - 轰炸机：{red['bombers']['count']}架 ({red['bombers']['health']}%)
  - 装甲：  {red['armor']['count']}辆 ({red['armor']['health']}%)

🔵 蓝方剩余：
  - 战斗机：{blue['fighters']['count']}架 ({blue['fighters']['health']}%)
  - 防空：  {blue['air_defense']['count']}套 ({blue['air_defense']['health']}%)
  - 装甲：  {blue['armor']['count']}辆 ({blue['armor']['health']}%)

【战线结果】
  红方控制：{territory['red_controlled']}%
  蓝方控制：{territory['blue_controlled']}%

【完整战斗记录】
"""
    for i, event in enumerate(GAME_STATE["battle_log"], 1):
        summary += f"  {i}. {event}\n"

    print(summary)

    # 保存记录
    log_file.write_text(summary, encoding="utf-8")
    print(f"\n📁 推演记录已保存：{log_file}")


if __name__ == "__main__":
    asyncio.run(main())
