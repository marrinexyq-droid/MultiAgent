import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient


def get_model():
    return OllamaChatCompletionClient(
        model="qwen2.5:7b",
        host="http://localhost:11434",
    )


# ── 工具函数 ──────────────────────────────────────────
async def search_topic(query: str) -> str:
    """模拟搜索某个话题，返回相关知识点"""
    knowledge = {
        "autogen": "AutoGen 是微软开源的多智能体框架，v0.4 采用分层架构：Core/AgentChat/Extensions，支持异步消息、工具调用和多种编排模式。",
        "a2a": "A2A（Agent-to-Agent）是 Google 提出的跨框架 Agent 通信协议，基于 HTTP+JSON-RPC，通过 AgentCard 描述能力。",
        "llm": "大语言模型（LLM）是基于 Transformer 架构的大规模预训练语言模型，代表有 GPT-4、Claude、Qwen 等。",
        "多智能体": "多智能体系统让多个 AI Agent 协作完成任务，每个 Agent 有独立角色，通过消息传递协调工作。",
    }
    query_lower = query.lower()
    for key, value in knowledge.items():
        if key in query_lower:
            return f"搜索结果 [{query}]：{value}"
    return f"搜索结果 [{query}]：这是一个关于 {query} 的重要技术领域，需要结合实际应用场景深入分析。"


async def analyze_comparison(topic_a: str, topic_b: str) -> str:
    """对比分析两个技术或概念"""
    return f"""对比分析 [{topic_a} vs {topic_b}]：
- 定位：{topic_a} 侧重于框架层编排，{topic_b} 侧重于协议层通信
- 互补性：两者可以结合使用，{topic_a} 负责内部逻辑，{topic_b} 负责跨系统通信
- 适用场景：单系统多 Agent 用 {topic_a}，跨框架集成用 {topic_b}"""


async def summarize(content: str, style: str = "技术报告") -> str:
    """将内容整理成指定风格的摘要"""
    return f"[{style}摘要] {content[:100]}... （已提炼核心要点）"


# ── 主程序 ──────────────────────────────────────────
async def main():
    # Planner：负责拆解任务
    planner = AssistantAgent(
        name="Planner",
        model_client=get_model(),
        system_message="""你是研究规划专家。
            收到研究问题后，制定一个3步研究计划，格式如下：
            【研究计划】
            步骤1：...
            步骤2：
            步骤3：...
            只输出计划，不要执行，不要写其他内容。""",
    )

    # Researcher：负责执行研究，可以调用工具
    researcher = AssistantAgent(
        name="Researcher",
        model_client=get_model(),
        tools=[search_topic, analyze_comparison, summarize],
        system_message="""你是研究执行专家，拥有搜索、对比分析、总结三种工具。
                        根据 Planner 的计划，调用工具逐步完成研究。
                        每步研究完成后输出发现，全部完成后写"【研究完成】"。""",
    )

    # Writer：负责整理成报告
    writer = AssistantAgent(
        name="Writer",
        model_client=get_model(),
        system_message="""你是技术报告撰写专家。
                    收到研究结果后，整理成结构清晰的报告：
                    # 报告标题
                    ## 核心结论
                    ## 详细分析
                    ## 总结建议
                    报告写完后输出 TERMINATE。""",
    )

    # 终止条件
    termination = (
        TextMentionTermination("TERMINATE")
        | MaxMessageTermination(12)
    )

    # 三个 Agent 轮流协作
    team = RoundRobinGroupChat(
        participants=[planner, researcher, writer],
        termination_condition=termination,
    )

    # 研究问题
    question = "AutoGen是一个什么样的架构"

    print("\n" + "="*60)
    print(f"🔬 研究问题：{question}")
    print("="*60 + "\n")

    await Console(team.run_stream(task=question))


if __name__ == "__main__":
    asyncio.run(main())