import asyncio
import datetime
from pathlib import Path
from ddgs import DDGS
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"


def get_model():
    return OllamaChatCompletionClient(
        model="qwen2.5:7b",
        host="http://localhost:11434",
    )


# ══════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════

async def web_search(query: str, max_results: int = 3) -> str:
    """
    用 DuckDuckGo 搜索真实网页内容。
    
    Args:
        query: 搜索关键词
        max_results: 返回结果数量，默认3条
        
    Returns:
        搜索结果字符串
    """
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"【{r['title']}】\n{r['body']}\n来源: {r['href']}"
                )
        if not results:
            return f"未找到关于 '{query}' 的搜索结果"
        return f"搜索 '{query}' 的结果：\n\n" + "\n\n---\n\n".join(results)
    except Exception as e:
        return f"搜索出错: {str(e)}，请尝试其他关键词"


async def analyze_comparison(topic_a: str, topic_b: str) -> str:
    """
    对比分析两个技术或概念的异同。
    
    Args:
        topic_a: 第一个对比对象
        topic_b: 第二个对比对象
        
    Returns:
        对比分析结果
    """
    return f"""对比分析 [{topic_a} vs {topic_b}]：
- 定位差异：{topic_a} 侧重框架层编排，{topic_b} 侧重协议层通信
- 技术栈：{topic_a} 基于 Python API，{topic_b} 基于 HTTP + JSON-RPC  
- 互补性：单系统内多 Agent 用 {topic_a}，跨框架通信用 {topic_b}
- 结合方案：用 {topic_a} 构建 Agent 内部逻辑，用 {topic_b} 暴露对外接口"""


async def save_report(title: str, content: str) -> str:
    """
    将研究报告保存为 Markdown 文件。
    
    Args:
        title: 报告标题（用作文件名）
        content: 报告正文内容
        
    Returns:
        保存结果和文件路径
    """
    # 生成带时间戳的文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = title.replace(" ", "_").replace("/", "-")[:30]
    filename = f"report_{safe_title}_{timestamp}.md"

    # 保存到 outputs/reports 目录
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = REPORTS_DIR / filename

    # 写入文件头 + 内容
    full_content = f"""# {title}

> 生成时间：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
> 由 AutoGen 多智能体系统自动生成

---

{content}
"""
    filepath.write_text(full_content, encoding="utf-8")
    return f"✅ 报告已保存到：{filepath.absolute()}"


# ══════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════

async def main():
    # Planner：拆解研究任务
    planner = AssistantAgent(
        name="Planner",
        model_client=get_model(),
        system_message="""你是研究规划专家。
收到问题后制定研究计划，格式如下：

【研究计划】
步骤1：搜索 <关键词A>
步骤2：搜索 <关键词B>  
步骤3：对比分析 <主题A> 和 <主题B>

只输出计划，不要做其他事情。""",
    )

    # Researcher：执行搜索和分析
    researcher = AssistantAgent(
        name="Researcher",
        model_client=get_model(),
        tools=[web_search, analyze_comparison],
        system_message="""你是研究执行专家，有 web_search 和 analyze_comparison 两个工具。
按照 Planner 的计划逐步调用工具收集信息。
每步完成后简述发现，全部完成后写"【研究完成】"并总结所有发现。
注意：直接调用工具，不要空想。""",
    )

    # Writer：整理报告并保存
    writer = AssistantAgent(
        name="Writer",
        model_client=get_model(),
        tools=[save_report],
        system_message="""你是技术报告撰写专家，有 save_report 工具可以保存报告。
根据 Researcher 的发现，先写出完整报告内容（Markdown 格式）：

# 报告标题
## 核心结论
## 详细分析
## 总结建议

然后调用 save_report(title="报告标题", content="完整报告内容") 保存文件。
保存成功后输出 TERMINATE。""",
    )

    # 终止条件
    termination = (
        TextMentionTermination("TERMINATE")
        | MaxMessageTermination(15)
    )

    # 三 Agent 团队
    team = RoundRobinGroupChat(
        participants=[planner, researcher, writer],
        termination_condition=termination,
    )

    # ── 在这里修改你的研究问题 ──
    question = "研究 AutoGen 多智能体框架的最新特性和实际应用场景"

    print("\n" + "=" * 60)
    print(f"🔬 研究问题：{question}")
    print("=" * 60 + "\n")

    await Console(team.run_stream(task=question))

    # 提示报告位置
    reports = list(REPORTS_DIR.glob("*.md")) if REPORTS_DIR.exists() else []
    if reports:
        latest = max(reports, key=lambda p: p.stat().st_mtime)
        print(f"\n📄 最新报告：{latest.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
