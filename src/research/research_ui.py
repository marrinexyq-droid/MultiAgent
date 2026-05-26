import asyncio
import datetime
import threading
from pathlib import Path

import gradio as gr
from ddgs import DDGS
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.ollama import OllamaChatCompletionClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"


# ══════════════════════════════════════════
# 模型
# ══════════════════════════════════════════


def get_model():
    return OllamaChatCompletionClient(
        model="qwen2.5:7b",
        host="http://localhost:11434",
    )


# ══════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════


async def web_search(query: str, max_results: int = 3) -> str:
    """用 DuckDuckGo 搜索真实网页内容。"""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"【{r['title']}】\n{r['body']}\n来源: {r['href']}")
        if not results:
            return f"未找到关于 '{query}' 的搜索结果"
        return f"搜索 '{query}' 的结果：\n\n" + "\n\n---\n\n".join(results)
    except Exception as e:
        return f"搜索出错: {str(e)}"


async def analyze_comparison(topic_a: str, topic_b: str) -> str:
    """对比分析两个技术或概念的异同。"""
    return f"""对比分析 [{topic_a} vs {topic_b}]：
- 定位差异：{topic_a} 侧重框架层编排，{topic_b} 侧重协议层通信
- 互补性：单系统内多 Agent 用 {topic_a}，跨框架通信用 {topic_b}"""


async def save_report(title: str, content: str) -> str:
    """将研究报告保存为 Markdown 文件。"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = title.replace(" ", "_").replace("/", "-")[:30]
    filename = f"report_{safe_title}_{timestamp}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = REPORTS_DIR / filename
    full_content = f"# {title}\n\n> 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n> 由 AutoGen 多智能体系统自动生成\n\n---\n\n{content}\n"
    filepath.write_text(full_content, encoding="utf-8")
    return f"✅ 报告已保存到：{filepath.absolute()}"


# ══════════════════════════════════════════
# 核心：运行 Agent 团队，流式输出
# ══════════════════════════════════════════


async def run_research(question: str, progress_callback):
    """运行三 Agent 团队，通过 callback 实时推送消息"""

    planner = AssistantAgent(
        name="Planner",
        model_client=get_model(),
        system_message="""你是研究规划专家。
收到问题后制定研究计划：

【研究计划】
步骤1：搜索 <关键词A>
步骤2：搜索 <关键词B>
步骤3：对比分析 <主题A> 和 <主题B>

只输出计划，不做其他事情。""",
    )

    researcher = AssistantAgent(
        name="Researcher",
        model_client=get_model(),
        tools=[web_search, analyze_comparison],
        system_message="""你是研究执行专家，有 web_search 和 analyze_comparison 两个工具。
按照 Planner 的计划逐步调用工具。
全部完成后写"【研究完成】"并总结发现。""",
    )

    writer = AssistantAgent(
        name="Writer",
        model_client=get_model(),
        tools=[save_report],
        system_message="""你是技术报告撰写专家，有 save_report 工具。
根据研究结果写完整 Markdown 报告，然后调用 save_report 保存。
保存成功后输出 TERMINATE。""",
    )

    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(15)

    team = RoundRobinGroupChat(
        participants=[planner, researcher, writer],
        termination_condition=termination,
    )

    # 角色对应 emoji
    role_emoji = {
        "Planner": "🗓️ Planner",
        "Researcher": "🔍 Researcher",
        "Writer": "✍️ Writer",
    }

    collected = []

    async for message in team.run_stream(task=question):
        # 只处理有 source 的 TextMessage
        source = getattr(message, "source", None)
        content = getattr(message, "content", None)
        if source and content and isinstance(content, str):
            label = role_emoji.get(source, f"🤖 {source}")
            block = f"### {label}\n\n{content}\n\n---\n"
            collected.append(block)
            # 每次追加后调用回调，UI 实时更新
            progress_callback("\n".join(collected))

    return "\n".join(collected)


# ══════════════════════════════════════════
# Gradio UI
# ══════════════════════════════════════════


def launch_research(question, history):
    """Gradio 调用入口，同步包装异步函数并实时推送进度。"""
    if not question.strip():
        yield history, "⚠️ 请输入研究问题", build_status_html("empty"), get_reports_html()
        return

    history = history or []
    history.append({"role": "user", "content": question})
    yield history, "⏳ 研究中，请稍候...", build_status_html("running"), get_reports_html()

    output_chunks = []
    result_holder = {}

    def on_progress(text):
        output_chunks.clear()
        output_chunks.append(text)

    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_holder["result"] = loop.run_until_complete(
                run_research(question, on_progress)
            )
        except Exception as e:
            result_holder["result"] = f"❌ 出错：{e}"
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    import time

    while thread.is_alive():
        if output_chunks:
            yield (
                history,
                output_chunks[-1],
                build_status_html("running"),
                get_reports_html(),
            )
        time.sleep(0.6)

    thread.join()

    result = result_holder.get("result", "❌ 未知错误")
    history.append({"role": "assistant", "content": result})

    reports = list(REPORTS_DIR.glob("*.md")) if REPORTS_DIR.exists() else []
    status = "done"
    if reports:
        latest = max(reports, key=lambda p: p.stat().st_mtime)
        result += f"\n\n---\n📄 **报告已保存：** `{latest.name}`"
    if result.startswith("❌"):
        status = "error"

    yield history, result, build_status_html(status), get_reports_html()


def build_status_html(status: str) -> str:
    """生成状态卡 HTML。"""
    mapping = {
        "idle": ("待命中", "输入问题后，系统会开始规划、检索并生成报告。"),
        "empty": ("等待输入", "请先填写一个研究问题，再启动这一轮分析。"),
        "running": ("研究进行中", "Planner、Researcher、Writer 正在协作处理你的请求。"),
        "done": ("研究完成", "本轮结果已经返回，如有保存报告也已同步到右侧列表。"),
        "error": ("执行出错", "本轮运行遇到了异常，可以调整问题后重新尝试。"),
    }
    title, desc = mapping.get(status, mapping["idle"])
    return f"""
    <div class="status-card status-{status}">
      <div class="status-dot"></div>
      <div class="status-copy">
        <div class="status-title">{title}</div>
        <div class="status-desc">{desc}</div>
      </div>
    </div>
    """


def get_reports_html():
    """列出所有已生成的报告。"""
    if not REPORTS_DIR.exists():
        return """
        <div class="report-empty">
          <div class="report-empty-title">还没有生成报告</div>
          <div class="report-empty-text">完成一次研究后，Markdown 报告会出现在这里。</div>
        </div>
        """

    files = sorted(
        REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not files:
        return """
        <div class="report-empty">
          <div class="report-empty-title">还没有生成报告</div>
          <div class="report-empty-text">完成一次研究后，Markdown 报告会出现在这里。</div>
        </div>
        """

    cards = []
    for index, file in enumerate(files[:8], start=1):
        updated = datetime.datetime.fromtimestamp(file.stat().st_mtime).strftime(
            "%m-%d %H:%M"
        )
        cards.append(
            f"""
            <div class="report-item">
              <div class="report-item-top">
                <span class="report-index">{index:02d}</span>
                <span class="report-time">{updated}</span>
              </div>
              <div class="report-name">{file.name}</div>
            </div>
            """
        )
    return f'<div class="report-list">{"".join(cards)}</div>'


CUSTOM_CSS = """
:root {
    --page-bg:
        linear-gradient(180deg, #f4efea 0%, #f4efea 100%);
    --surface: #ffffff;
    --surface-strong: #ffffff;
    --surface-soft: #f8f8f7;
    --line: #a1a1a1;
    --line-strong: #383838;
    --text-main: #383838;
    --text-soft: #5f5f5f;
    --text-faint: #8b8b8b;
    --brand: #2ba5ff;
    --brand-deep: #1b7fc7;
    --brand-soft: rgba(43, 165, 255, 0.12);
    --brand-orange: #ff6719;
    --brand-yellow: #ffde00;
    --accent-link: #383838;
    --success: #0f9f6e;
    --warning: #d97706;
    --danger: #dc2626;
    --shadow-lg: none;
    --shadow-md: none;
    --radius-xl: 0px;
    --radius-lg: 2px;
    --radius-md: 2px;
}

.gradio-container {
    background: var(--page-bg);
    font-family: Aeonik, Inter, system-ui, "PingFang SC", "Hiragino Sans GB",
        "Noto Sans SC", "Microsoft YaHei", sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    color: var(--text-main) !important;
}

.app-shell {
    max-width: 1360px;
    margin: 0 auto;
    padding: 14px 16px 28px;
}

.app-header,
.workspace-card,
.side-card,
.footer-card {
    background: var(--surface);
    border: 2px solid var(--line-strong);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-lg);
}

.app-header {
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.9fr);
    gap: 18px;
    padding: 22px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}

.app-header::after {
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    width: 12px;
    height: 100%;
    background: linear-gradient(180deg, var(--brand-orange) 0%, var(--brand-yellow) 100%);
    pointer-events: none;
}

.brand-stack,
.hero-metrics {
    position: relative;
    z-index: 1;
}

.brand-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 2px;
    background: var(--brand-yellow);
    color: var(--text-main);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 14px;
}

.brand-title {
    margin: 0 0 12px;
    font-size: 56px;
    line-height: 1.1;
    font-weight: 400;
    letter-spacing: 0.02em;
    color: var(--text-main) !important;
}

.brand-copy {
    margin: 0;
    max-width: 760px;
    color: var(--text-soft) !important;
    font-size: 16px;
    line-height: 1.5;
}

.brand-copy strong {
    color: var(--text-main) !important;
    background: linear-gradient(transparent 58%, rgba(255, 222, 0, 0.7) 58%);
    font-weight: 600 !important;
}

.hero-metrics {
    display: grid;
    gap: 12px;
    align-content: start;
}

.metric-card {
    background: var(--surface-strong);
    border: 2px solid var(--line-strong);
    border-radius: var(--radius-lg);
    padding: 14px 16px;
    box-shadow: var(--shadow-md);
}

.metric-label {
    display: block;
    margin-bottom: 8px;
    color: var(--text-faint) !important;
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

.metric-value {
    color: var(--text-main) !important;
    font-size: 18px;
    font-weight: 700;
    line-height: 1.5;
}

.workspace-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.9fr);
    gap: 16px;
    align-items: start;
}

.left-stack,
.right-stack {
    display: grid;
    gap: 16px;
}

.workspace-card {
    padding: 18px;
}

.side-card {
    padding: 18px;
}

.section-kicker {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    border-radius: 2px;
    background: var(--surface-soft);
    color: var(--text-faint) !important;
    border: 1px solid var(--line);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 14px;
}

.section-title {
    margin: 0 0 8px;
    color: var(--text-main) !important;
    font-size: 24px;
    font-weight: 400;
    line-height: 1.2;
    letter-spacing: 0.02em;
}

.section-desc {
    margin: 0 0 16px;
    color: var(--text-soft) !important;
    font-size: 14px;
    line-height: 1.5;
}

#question_box,
#progress_box,
#reports_box,
#status_box,
#chatbot_card {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

#question_box textarea {
    background: var(--surface-soft) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 2px !important;
    min-height: 124px !important;
    padding: 16px 40px 16px 24px !important;
    font-size: 16px !important;
    line-height: 1.2 !important;
    color: var(--text-main) !important;
    font-family: Aeonik, Inter, system-ui, sans-serif !important;
}

#question_box textarea:focus {
    border-color: var(--brand) !important;
    box-shadow: inset 0 0 0 1px var(--brand) !important;
}

#question_box label,
#chatbot_card label {
    color: var(--text-main) !important;
    font-weight: 700 !important;
}

#question_box textarea::placeholder {
    color: #7a8495 !important;
    opacity: 1 !important;
}

#submit_btn button,
#refresh_btn button,
#clear_btn button {
    min-height: 48px !important;
    border-radius: 2px !important;
    font-weight: 400 !important;
    font-size: 16px !important;
    line-height: 1.5 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    transition: opacity 0.16s ease !important;
    box-shadow: none !important;
}

#submit_btn button {
    background: var(--brand) !important;
    color: #ffffff !important;
    border: 2px solid var(--brand) !important;
}

#clear_btn button,
#refresh_btn button {
    background: #ffffff !important;
    color: var(--text-main) !important;
    border: 2px solid var(--line-strong) !important;
}

#submit_btn button:hover,
#clear_btn button:hover,
#refresh_btn button:hover {
    opacity: 0.9;
}

.example-wrap {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px dashed rgba(25, 36, 56, 0.12);
}

.example-wrap .prose,
.example-wrap .prose *,
.example-wrap label,
.example-wrap .label-wrap,
.example-wrap .label-wrap * {
    color: var(--text-soft) !important;
    opacity: 1 !important;
}

.example-wrap .examples button,
.example-wrap .examples button *,
.example-wrap .examples [role="button"] * {
    color: #314055 !important;
    opacity: 1 !important;
}

.example-wrap .examples button {
    border-radius: 2px !important;
    border: 1px solid var(--line) !important;
    background: #ffffff !important;
    padding: 11px 14px !important;
    min-height: 42px !important;
}

.chat-shell {
    padding: 12px;
    border-radius: 0;
    background: var(--surface-soft);
    border: 2px solid var(--line-strong);
    box-shadow: none;
}

.chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding: 2px 4px 10px;
    border-bottom: 1px solid var(--line);
}

.chat-header-title {
    color: var(--text-main) !important;
    font-size: 15px;
    font-weight: 600;
}

.chat-header-note {
    color: var(--text-faint) !important;
    font-size: 12px;
    font-family: "Aeonik Mono", "Fira Code", monospace;
}

.chat-wrap .message,
.chat-wrap .bubble {
    border-radius: 2px !important;
    box-shadow: none !important;
}

.chat-wrap [role="log"] {
    background: #f7f9fb;
    border: 1px solid var(--line);
    border-radius: 0;
    padding: 8px;
}

.chat-wrap .message *,
.chat-wrap .bubble * {
    color: inherit !important;
    opacity: 1 !important;
}

.chat-wrap .placeholder,
.chat-wrap [data-testid="chatbot-placeholder"] {
    color: var(--text-faint) !important;
}

.chat-wrap [data-testid="assistant"] .message,
.chat-wrap [data-testid="assistant"] .bubble,
.chat-wrap [data-testid="bot"] .message,
.chat-wrap [data-testid="bot"] .bubble {
    background: #ffffff !important;
    border: 1px solid var(--line) !important;
    color: var(--text-main) !important;
}

.chat-wrap [data-testid="user"] .message,
.chat-wrap [data-testid="user"] .bubble {
    background: var(--brand) !important;
    border: 1px solid var(--brand) !important;
    color: #ffffff !important;
}

.chat-wrap a,
#progress_box a,
#reports_box a {
    color: var(--accent-link) !important;
    text-decoration-thickness: 2px;
}

#progress_box {
    background: var(--surface-soft) !important;
    border: 2px solid var(--line-strong) !important;
    border-radius: 0 !important;
    padding: 18px 18px 10px !important;
    min-height: 320px;
}

#progress_box,
#progress_box .prose,
#progress_box p,
#progress_box li,
#progress_box span,
#progress_box strong,
#progress_box code {
    color: #223046 !important;
    opacity: 1 !important;
}

#progress_box h3 {
    font-size: 16px;
    color: var(--brand-deep) !important;
    font-weight: 600 !important;
}

#progress_box hr {
    border-color: rgba(25, 36, 56, 0.08) !important;
}

.status-card {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 18px;
    border-radius: 22px;
    border: 2px solid var(--line-strong);
    background: #ffffff;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    margin-top: 6px;
    background: var(--text-faint);
    box-shadow: none;
    flex: 0 0 auto;
}

.status-running .status-dot {
    background: var(--warning);
}

.status-done .status-dot {
    background: var(--success);
}

.status-error .status-dot {
    background: var(--danger);
}

.status-title {
    color: var(--text-main);
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 6px;
}

.status-desc {
    color: var(--text-soft);
    font-size: 14px;
    line-height: 1.7;
}

.report-list {
    display: grid;
    gap: 12px;
}

.report-item {
    padding: 14px 16px;
    border-radius: 0;
    border: 2px solid var(--line-strong);
    background: #ffffff;
    box-shadow: none;
}

.report-item-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
}

.report-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 36px;
    height: 28px;
    padding: 0 10px;
    border-radius: 2px;
    background: var(--brand-yellow);
    color: var(--text-main);
    font-size: 12px;
    font-weight: 700;
}

.report-time {
    color: var(--text-faint);
    font-size: 12px;
}

.report-name {
    color: var(--text-main);
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;
}

.report-empty {
    padding: 18px;
    border-radius: 0;
    border: 2px dashed var(--line);
    background: #ffffff;
}

.report-empty-title {
    color: var(--text-main);
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 6px;
}

.report-empty-text {
    color: var(--text-soft);
    font-size: 14px;
    line-height: 1.7;
}

.footer-card {
    margin-top: 18px;
    padding: 16px 18px;
    background: var(--surface);
}

.footer-card strong {
    color: var(--text-main) !important;
}

@media (max-width: 900px) {
    .app-header,
    .workspace-grid {
        grid-template-columns: 1fr;
    }

    .brand-title {
        font-size: 32px;
    }

    .app-shell {
        padding: 16px 8px 28px;
    }
}
"""

theme = gr.themes.Soft(
    primary_hue="teal",
    secondary_hue="emerald",
    neutral_hue="slate",
).set(
    body_background_fill="transparent",
    block_background_fill="rgba(255,255,255,0.78)",
    block_border_width="1px",
    block_border_color="rgba(148,163,184,0.18)",
    block_radius="24px",
    button_primary_background_fill="#0f766e",
    button_primary_background_fill_hover="#115e59",
    button_primary_border_color="#0f766e",
    button_primary_text_color="white",
    input_background_fill="rgba(255,255,255,0.92)",
)

with gr.Blocks(title="AutoGen 研究助手") as demo:
    with gr.Column(elem_classes="app-shell"):
        gr.Markdown(
            """
            <div class="app-header">
              <div class="brand-stack">
                <div class="brand-chip">AutoGen Research Workspace</div>
                <h1 class="brand-title">多智能体研究助手</h1>
                <p class="brand-copy">
                  这是一个围绕“规划、检索、成稿”构建的研究工作台。
                  输入一个问题后，<strong>Planner</strong> 先拆解任务，
                  <strong>Researcher</strong> 负责搜索与分析，<strong>Writer</strong>
                  负责整理并保存为 Markdown 报告。
                </p>
              </div>
              <div class="hero-metrics">
                <div class="metric-card">
                  <span class="metric-label">Research Flow</span>
                  <span class="metric-value">三阶段 Agent 协作链</span>
                </div>
                <div class="metric-card">
                  <span class="metric-label">Model Runtime</span>
                  <span class="metric-value">本地 qwen2.5:7b + Ollama</span>
                </div>
                <div class="metric-card">
                  <span class="metric-label">Deliverable</span>
                  <span class="metric-value">可复用 Markdown 报告</span>
                </div>
              </div>
            </div>
            """
        )

        with gr.Group(elem_classes="workspace-grid"):
            with gr.Column(elem_classes="left-stack"):
                with gr.Column(elem_classes="workspace-card"):
                    gr.Markdown(
                        """
                        <div class="section-kicker">Research Input</div>
                        <h2 class="section-title">开始一轮研究</h2>
                        <p class="section-desc">
                          适合研究技术路线、框架比较、趋势分析或概念梳理。问题越清晰，报告越稳定。
                        </p>
                        """
                    )
                    question_input = gr.Textbox(
                        placeholder="例如：分析多智能体系统在企业知识管理中的应用前景",
                        label="研究问题",
                        lines=3,
                        elem_id="question_box",
                    )
                    with gr.Row():
                        submit_btn = gr.Button(
                            "开始研究", variant="primary", scale=1, elem_id="submit_btn"
                        )
                        clear_btn = gr.Button(
                            "清空对话",
                            variant="secondary",
                            scale=1,
                            elem_id="clear_btn",
                        )
                    with gr.Column(elem_classes="example-wrap"):
                        gr.Examples(
                            examples=[
                                "分析大语言模型 Agent 的发展趋势与挑战",
                                "比较 MCP 与 A2A 在多 Agent 协作中的定位",
                                "研究本地部署 AI 助手在企业内部知识库中的可行性",
                            ],
                            inputs=question_input,
                        )

                with gr.Column(elem_classes="workspace-card"):
                    gr.Markdown(
                        """
                        <div class="section-kicker">Conversation Trace</div>
                        <h2 class="section-title">Agent 对话过程</h2>
                        <p class="section-desc">
                          这里展示三个 Agent 的协作轨迹，方便观察每一步是如何展开的。
                        </p>
                        """
                    )
                    with gr.Column(elem_classes="chat-shell"):
                        gr.Markdown(
                            """
                            <div class="chat-header">
                              <div class="chat-header-title">实时协作面板</div>
                              <div class="chat-header-note">Planner → Researcher → Writer</div>
                            </div>
                            """
                        )
                        chatbot = gr.Chatbot(
                            label="Agent 对话过程",
                            show_label=False,
                            height=560,
                            layout="bubble",
                            placeholder="研究完成后，对话过程会显示在这里。",
                            elem_classes="chat-wrap",
                            elem_id="chatbot_card",
                        )

            with gr.Column(elem_classes="right-stack"):
                with gr.Column(elem_classes="side-card"):
                    gr.Markdown(
                        """
                        <div class="section-kicker">Runtime Status</div>
                        <h2 class="section-title">系统状态</h2>
                        <p class="section-desc">
                          这里会提示当前是否空闲、运行中、完成或发生异常。
                        </p>
                        """
                    )
                    status_box = gr.HTML(
                        build_status_html("idle"), elem_id="status_box"
                    )

                with gr.Column(elem_classes="side-card"):
                    gr.Markdown(
                        """
                        <div class="section-kicker">Progress Feed</div>
                        <h2 class="section-title">实时进度流</h2>
                        <p class="section-desc">
                          用来查看阶段性输出、工具调用结果和最终归纳内容。
                        </p>
                        """
                    )
                    progress_box = gr.Markdown(
                        "等待输入研究问题...", elem_id="progress_box"
                    )

                with gr.Column(elem_classes="side-card"):
                    gr.Markdown(
                        """
                        <div class="section-kicker">Saved Reports</div>
                        <h2 class="section-title">已生成报告</h2>
                        <p class="section-desc">
                          最近输出的 Markdown 文件会出现在这里，便于回看和复用。
                        </p>
                        """
                    )
                    reports_box = gr.HTML(get_reports_html(), elem_id="reports_box")
                    refresh_btn = gr.Button("刷新报告列表", elem_id="refresh_btn")

        with gr.Column(elem_classes="footer-card"):
            gr.Markdown(
                """
                **使用提示**：首次运行通常会稍慢，因为需要拉起本地模型。稳定后，单次研究一般会在 30 到 60 秒内完成。
                """
            )

    # 事件绑定
    submit_btn.click(
        fn=launch_research,
        inputs=[question_input, chatbot],
        outputs=[chatbot, progress_box, status_box, reports_box],
    )
    question_input.submit(
        fn=launch_research,
        inputs=[question_input, chatbot],
        outputs=[chatbot, progress_box, status_box, reports_box],
    )
    clear_btn.click(
        fn=lambda: (
            [],
            "",
            "等待输入研究问题...",
            build_status_html("idle"),
            get_reports_html(),
        ),
        outputs=[chatbot, question_input, progress_box, status_box, reports_box],
    )
    refresh_btn.click(fn=get_reports_html, outputs=reports_box)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=False,
        theme=theme,
        css=CUSTOM_CSS,
    )
