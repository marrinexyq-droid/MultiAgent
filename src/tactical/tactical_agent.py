"""
AutoGen 多兵种联合作战推演系统
=====================================
架构：IntelAgent → CommanderAgent → [AirAgent + GroundAgent + MissileAgent] → ExecutorAgent
"""

import asyncio
import datetime
import json
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AFSIM_COMMANDS_DIR = PROJECT_ROOT / "outputs" / "afsim_commands"


# ══════════════════════════════════════════
# Mock 战场态势数据
# ══════════════════════════════════════════

BATTLEFIELD_STATE = {
    "mission_time": "T+00:15:00",
    "scenario": "多兵种联合防御作战",
    "friendly_forces": [
        {
            "id": "F-001", "type": "战斗机", "platform": "J-20",
            "position": {"x": 120.5, "y": 35.2, "alt": 8000},
            "status": "patrol", "fuel": 85, "weapons": {"PL-15": 4, "PL-10": 2},
        },
        {
            "id": "F-002", "type": "战斗机", "platform": "J-20",
            "position": {"x": 121.0, "y": 35.5, "alt": 7500},
            "status": "patrol", "fuel": 78, "weapons": {"PL-15": 4, "PL-10": 2},
        },
        {
            "id": "G-001", "type": "地面防空", "platform": "HQ-9",
            "position": {"x": 119.8, "y": 34.9, "alt": 50},
            "status": "standby", "ammo": 8, "radar": "active",
        },
        {
            "id": "G-002", "type": "装甲部队", "platform": "99A坦克",
            "position": {"x": 119.5, "y": 34.7, "alt": 30},
            "status": "advancing", "health": 100, "ammo": 40,
        },
        {
            "id": "G-003", "type": "步兵营", "platform": "步兵",
            "position": {"x": 119.3, "y": 34.6, "alt": 20},
            "status": "defending", "health": 90, "strength": 500,
        },
    ],
    "enemy_forces": [
        {
            "id": "E-001", "type": "战斗机", "platform": "F-16",
            "position": {"x": 125.2, "y": 36.1, "alt": 9000},
            "status": "approaching", "heading": 270, "speed": 800,
            "threat_level": "HIGH",
        },
        {
            "id": "E-002", "type": "轰炸机", "platform": "B-52",
            "position": {"x": 126.5, "y": 35.8, "alt": 12000},
            "status": "approaching", "heading": 260, "speed": 600,
            "threat_level": "CRITICAL",
        },
        {
            "id": "E-003", "type": "装甲集群", "platform": "M1A2",
            "position": {"x": 122.1, "y": 34.8, "alt": 35},
            "status": "advancing", "heading": 270, "speed": 45,
            "threat_level": "HIGH", "count": 20,
        },
        {
            "id": "E-004", "type": "巡航导弹", "platform": "Tomahawk",
            "position": {"x": 124.0, "y": 35.0, "alt": 100},
            "status": "inbound", "heading": 265, "speed": 900,
            "threat_level": "CRITICAL",
        },
    ],
    "environment": {
        "weather": "多云", "visibility": 15,
        "wind": {"direction": 180, "speed": 12},
        "time_of_day": "白天",
    },
}


# ══════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════

async def get_battlefield_state() -> str:
    """
    获取当前战场态势数据（来自 AFSIM 仿真输出）。
    返回所有兵力位置、状态和威胁评估。
    """
    return f"""
=== 战场态势报告 ===
任务时间：{BATTLEFIELD_STATE['mission_time']}
场景：{BATTLEFIELD_STATE['scenario']}

【我方兵力】
{json.dumps(BATTLEFIELD_STATE['friendly_forces'], ensure_ascii=False, indent=2)}

【敌方兵力】
{json.dumps(BATTLEFIELD_STATE['enemy_forces'], ensure_ascii=False, indent=2)}

【环境条件】
{json.dumps(BATTLEFIELD_STATE['environment'], ensure_ascii=False, indent=2)}
"""


async def assess_threat(unit_id: str) -> str:
    """
    对指定敌方单位进行威胁评估。

    Args:
        unit_id: 敌方单位ID，例如 E-001
    Returns:
        威胁评估报告
    """
    enemy = next(
        (u for u in BATTLEFIELD_STATE["enemy_forces"] if u["id"] == unit_id),
        None
    )
    if not enemy:
        return f"未找到单位 {unit_id}"

    assessments = {
        "E-001": "F-16 战斗机，高速接近，具备空对空打击能力，威胁我方巡逻机",
        "E-002": "B-52 轰炸机，携带大量精确制导弹药，威胁我方地面目标，优先级最高",
        "E-003": "M1A2 装甲集群共20辆，正向我方防线推进，预计45分钟抵达接触线",
        "E-004": "Tomahawk 巡航导弹，低空突防，速度极快，需立即拦截",
    }
    return f"""
威胁评估 [{unit_id}]：
- 平台：{enemy['platform']}
- 当前位置：{enemy['position']}
- 速度/航向：{enemy.get('speed', 'N/A')} km/h / {enemy.get('heading', 'N/A')}°
- 威胁等级：{enemy['threat_level']}
- 评估：{assessments.get(unit_id, '需要进一步侦察')}
"""


async def calculate_intercept(friendly_id: str, enemy_id: str) -> str:
    """
    计算拦截方案，输出拦截航路和预计接触时间。

    Args:
        friendly_id: 我方单位ID
        enemy_id: 敌方单位ID
    Returns:
        拦截方案
    """
    friendly = next(
        (u for u in BATTLEFIELD_STATE["friendly_forces"] if u["id"] == friendly_id),
        None
    )
    enemy = next(
        (u for u in BATTLEFIELD_STATE["enemy_forces"] if u["id"] == enemy_id),
        None
    )
    if not friendly or not enemy:
        return "无法计算：单位不存在"

    # Mock 计算
    intercept_plans = {
        ("F-001", "E-001"): {"eta": "8分钟", "heading": "055", "alt": 9500, "action": "BVR导弹攻击"},
        ("F-001", "E-002"): {"eta": "12分钟", "heading": "070", "alt": 11000, "action": "PL-15远程攻击"},
        ("F-002", "E-001"): {"eta": "10分钟", "heading": "050", "alt": 9000, "action": "双机协同夹击"},
        ("F-002", "E-004"): {"eta": "3分钟", "heading": "080", "alt": 2000, "action": "低空追击"},
        ("G-001", "E-004"): {"eta": "1.5分钟", "heading": "090", "alt": 0, "action": "HQ-9导弹拦截"},
    }
    plan = intercept_plans.get(
        (friendly_id, enemy_id),
        {"eta": "未知", "heading": 0, "alt": 0, "action": "需要进一步规划"}
    )
    return f"""
拦截方案 [{friendly_id} → {enemy_id}]：
- 我方平台：{friendly['platform']} (燃油:{friendly.get('fuel', 'N/A')}%)
- 目标平台：{enemy['platform']}
- 预计接触时间：{plan['eta']}
- 建议航向：{plan['heading']}°
- 建议高度：{plan['alt']} 米
- 建议行动：{plan['action']}
"""


async def generate_afsim_command(
    unit_id: str,
    action: str,
    target_id: str = "",
    params: str = ""
) -> str:
    """
    将战术决策转换为 AFSIM 脚本指令并保存。

    Args:
        unit_id: 执行单位ID
        action: 行动类型 (INTERCEPT/ATTACK/DEFEND/WITHDRAW/HOLD)
        target_id: 目标单位ID（可选）
        params: 附加参数，如航向、高度等
    Returns:
        生成的 AFSIM 指令
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 生成 AFSIM 格式指令
    afsim_script = f"""# AutoGen 生成的 AFSIM 战术指令
# 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 任务时间: {BATTLEFIELD_STATE['mission_time']}

platform_command {unit_id} {{
    action = {action}
    {"target = " + target_id if target_id else ""}
    {"parameters = " + params if params else ""}
    execute_time = now
}}
"""

    # 保存指令文件
    AFSIM_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = AFSIM_COMMANDS_DIR / f"cmd_{unit_id}_{action}_{timestamp}.scenario"
    filepath.write_text(afsim_script, encoding="utf-8")

    return f"""
✅ AFSIM 指令已生成：
{afsim_script}
文件保存至：{filepath}
"""


# ══════════════════════════════════════════
# 构建 Agent 团队
# ══════════════════════════════════════════

def get_model():
    return OllamaChatCompletionClient(
        model="qwen2.5:7b",
        host="http://localhost:11434",
    )


async def main():
    # 1. 情报分析 Agent
    intel_agent = AssistantAgent(
        name="IntelAgent",
        model_client=get_model(),
        tools=[get_battlefield_state, assess_threat],
        system_message="""你是战场情报分析官。
任务开始时：
1. 调用 get_battlefield_state() 获取战场态势
2. 对所有 CRITICAL 威胁调用 assess_threat() 进行威胁评估
3. 输出简明的【情报摘要】，列出：
   - 最紧迫威胁（按优先级排序）
   - 我方可用兵力状态
   - 建议指挥官重点关注的方向
只做情报分析，不做决策。""",
    )

    # 2. 指挥官 Agent
    commander_agent = AssistantAgent(
        name="CommanderAgent",
        model_client=get_model(),
        system_message="""你是联合作战指挥官。
根据 IntelAgent 的情报摘要，制定【作战命令】：

作战命令格式：
- 总体态势判断（1-2句）
- 空中作战任务（分配给空军）
- 地面作战任务（分配给地面部队）
- 导弹防御任务（分配给防空部队）
- 各兵种协同要点

命令要具体：指定单位、目标、优先级。
不要自己执行，让各兵种 Agent 去落实。""",
    )

    # 3. 空军 Agent
    air_agent = AssistantAgent(
        name="AirAgent",
        model_client=get_model(),
        tools=[calculate_intercept, generate_afsim_command],
        system_message="""你是空军作战参谋。
根据指挥官命令，负责空中兵力：
1. 对空中威胁调用 calculate_intercept() 计算拦截方案
2. 调用 generate_afsim_command() 生成空军作战指令
   - action 用：INTERCEPT（拦截）或 ATTACK（攻击）
3. 输出【空军作战指令】摘要

只处理 F-001、F-002 这两架战斗机。""",
    )

    # 4. 地面部队 Agent
    ground_agent = AssistantAgent(
        name="GroundAgent",
        model_client=get_model(),
        tools=[generate_afsim_command],
        system_message="""你是地面作战参谋。
根据指挥官命令，负责地面兵力 G-002（坦克）和 G-003（步兵）：
1. 分析地面威胁 E-003（装甲集群）
2. 调用 generate_afsim_command() 生成地面作战指令
   - action 用：DEFEND（防御）、ADVANCE（推进）或 HOLD（固守）
3. 输出【地面作战指令】摘要

只处理 G-002、G-003。""",
    )

    # 5. 防空 Agent
    missile_agent = AssistantAgent(
        name="MissileAgent",
        model_client=get_model(),
        tools=[calculate_intercept, generate_afsim_command],
        system_message="""你是防空作战参谋。
负责地面防空系统 G-001（HQ-9）：
1. 针对 E-004（Tomahawk 巡航导弹）计算拦截方案
2. 调用 generate_afsim_command() 生成防空拦截指令
   - action 用：INTERCEPT
3. 输出【防空指令】摘要

优先级最高：巡航导弹必须立即拦截！只处理 G-001。""",
    )

    # 6. 执行汇总 Agent
    executor_agent = AssistantAgent(
        name="ExecutorAgent",
        model_client=get_model(),
        system_message="""你是作战执行官。
收集所有兵种的作战指令后，输出最终【作战执行报告】：

# 联合作战执行报告
## 任务时间
## 威胁评估摘要
## 空中作战指令
## 地面作战指令
## 防空拦截指令
## 各兵种协同时间轴
## 预期作战效果

报告写完后输出 TERMINATE。""",
    )

    # 终止条件
    termination = (
        TextMentionTermination("TERMINATE")
        | MaxMessageTermination(20)
    )

    # 按顺序编排 Agent
    team = RoundRobinGroupChat(
        participants=[
            intel_agent,
            commander_agent,
            air_agent,
            ground_agent,
            missile_agent,
            executor_agent,
        ],
        termination_condition=termination,
    )

    print("\n" + "=" * 60)
    print("⚔️  多兵种联合作战推演系统启动")
    print(f"📡  场景：{BATTLEFIELD_STATE['scenario']}")
    print(f"🕐  任务时间：{BATTLEFIELD_STATE['mission_time']}")
    print("=" * 60 + "\n")

    await Console(team.run_stream(
        task="开始推演：分析当前战场态势，制定并执行联合作战方案"
    ))

    # 显示生成的指令文件
    if AFSIM_COMMANDS_DIR.exists():
        files = list(AFSIM_COMMANDS_DIR.glob("*.scenario"))
        print(f"\n📁 已生成 {len(files)} 个 AFSIM 指令文件：")
        for f in files:
            print(f"   - {f.name}")


if __name__ == "__main__":
    asyncio.run(main())
