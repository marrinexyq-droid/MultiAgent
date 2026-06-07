# LLM Agent 多智能体策略评测与可观测平台

面向 AI 应用工程师场景的多智能体策略评测平台，支持可配置推演场景、Rule / LLM / Hybrid 决策策略、共享记忆、LLM 决策追踪、战斗回放和自动化评测报告。

## 功能特性

### Agent 评测闭环
- **策略对比** — 支持 Rule / LLM / Hybrid 决策策略的批量仿真与指标对比。
- **自动化评测报告** — 输出胜率、平均回合数、任务完成率、侦察情报使用量、无效行动率等指标。
- **确定性场景** — 内置 balanced、scout pressure、assault breakthrough 等评测场景，支持固定 seed 复现。

### LLM 决策工程化
- **结构化输出校验** — 对 LLM action JSON 进行解析、越界校验和无效目标拦截。
- **规则兜底** — 模型异常、超时、非法动作时自动 fallback 到规则策略，保证推演不中断。
- **决策 Trace** — 记录每个 Agent 的 latency、token usage、fallback reason 和最终动作。

### 多智能体记忆
- **共享记忆池** — 管理 observations、beliefs、risk zones、tasks 和 summaries。
- **置信度衰减** — 支持按回合衰减、低置信度清理和多源交叉验证。
- **角色上下文裁剪** — 按侦察、攻击、防御、支援等角色读取不同粒度的团队记忆。

### 可视化复盘
- **Evaluation Dashboard** — 作为主入口展示策略指标、场景分解和运行样本。
- **战斗回放** — 支持逐帧播放、速度控制、关键事件跳转和帧差查看。
- **LLM Trace / Memory Inspector** — 在复盘中查看模型决策、共享记忆和关键转折。

## 技术栈

| 层 | 技术 |
|-------|-----------|
| 前端 | Vue 3 + TypeScript + Vite |
| 后端 | Python + FastAPI |
| AI | OpenAI 兼容 API（SiliconFlow）+ 规则降级 |
| 评测 | Deterministic scenarios + JSON / Markdown reports |
| 部署 | FastAPI API + Vue 前端 |

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 9+

### 后端

macOS / Linux:

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.battle.api_server
```

Windows PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.battle.api_server
```

健康检查:

```sh
curl http://localhost:8000/api/health
```

### 前端

```sh
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

推荐主入口：`http://localhost:5173/evaluation`。

### LLM 配置

项目默认可在无 API Key 时使用规则策略运行。需要启用 OpenAI-compatible LLM 决策时，复制 `.env.example` 为 `.env` 并填写：

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
```

旧版 `SILICONFLOW_API_KEY` / `SILICONFLOW_BASE_URL` / `SILICONFLOW_MODEL` 仍然兼容。

### 测试

```sh
python -m unittest
cd frontend
npm run build
```

### 策略评测

运行内置的多智能体策略评测，生成 JSON 和 Markdown 报告：

```sh
python -m src.battle.eval_runner --runs 20
```

输出文件：

- `reports/eval_latest.json`
- `reports/eval_latest.md`

报告包含胜率、平均回合数、任务完成率、侦察情报使用量和无效行动率，可作为简历项目中的量化指标来源。

### 实验模式

`/fantasy` 和早期 square grid 页面保留为实验入口，不作为当前项目主线展示。当前主线聚焦于 Agent 策略评测、LLM 决策追踪和多智能体记忆分析。

## 项目结构

```
src/
├── battle/
│   ├── env.py                # 基础战场环境
│   ├── grid_rules.py         # 六边形网格数学（距离、视线、邻居）
│   ├── terrain.py            # 地形属性和预设生成器
│   ├── battle_types.py       # 共享数据模型
│   ├── stats.py              # 统计追踪
│   ├── memory.py             # 共享记忆池（信念 + 衰减）
│   ├── llm_actions.py        # LLM action 解析、校验与 fallback
│   ├── eval_runner.py        # 策略评测 runner 和报告生成
│   ├── api_server.py         # 主 FastAPI 服务器
│   └── agents/
│       ├── base.py           # LLM / rule 混合决策基类
│       └── generic.py        # 规则驱动战术 agent
frontend/
├── src/
│   ├── components/
│   │   ├── BattleReplayControls.vue # 回放控制
│   │   ├── LlmDecisionTracePanel.vue # LLM 决策追踪
│   │   ├── HexBattleMap.vue  # 军事地图（3D 地形、迷雾）
│   │   └── ...
│   ├── views/
│   │   ├── EvaluationPage.vue # 策略评测仪表盘
│   │   ├── DeploymentPage.vue # 场景配置
│   │   ├── BattlePage.vue    # 推演运行
│   │   ├── ReviewPage.vue    # 复盘分析
│   │   └── ...
│   └── styles.css            # 全局样式
```

## 核心挑战

| 问题 | 方案 | 效果 |
|------|------|------|
| 多智能体共享上下文导致信息污染 | 独立记忆池（`SharedMemoryPool`），每 agent 按角色裁剪上下文 | 指挥官视野完整，侦察兵仅关注目标验证，互不干扰 |
| 同质化决策导致战术单一 | 角色加权信源信任度 + 规则降级策略 | Scout 情报权重 x1.15，不同角色决策路径不同 |
| 旧情报干扰判断 | 逐回合 confidence 衰减 x0.85，低于阈值 0.1 自动清除 | 信息有效期约 12-14 回合，过期自动蒸发 |
| 单一信源不可靠 | 多源交叉验证（≥2 agent 确认才置 verified=true） | 冲突位置自动降权 0.08，减少误导 |

## 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Layer                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │Commander │  │  Scout   │  │ Attacker │  │ Defender │  ...      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │              │                │
│       ▼              ▼              ▼              ▼                │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              SharedMemoryPool                        │          │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │          │
│  │  │observations│ │ beliefs  │ │risk_zones│ │ tasks  │ │          │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │          │
│  │  • confidence 衰减 x0.85/回合                        │          │
│  │  • 多源交叉验证 (≥2 sources → +0.08)                │          │
│  │  • 角色上下文裁剪 (scout:4信念,attacker:3信念)      │          │
│  └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Decision Layer                               │
│  • 角色加权信源信任度表 (coordinator 1.0 / scout 1.15 / ...)       │
│  • LLM API 调用 (OpenAI-compatible) 或 规则兜底                    │
│  • 目标选择 (距离/血量/威胁度/角色优先级)                           │
│  • 结构化 action 校验 (JSON/越界/无效目标/fallback)                │
│  • 走位规划 (掩护/LOS/危险区回避)                                  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Action Layer                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  MOVE    │  │  SKILL   │  │  ATTACK  │  │  WAIT / SPECIAL  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Environment Layer                                │
│  • Hex Grid (轴向坐标/距离/LOS/寻路)                               │
│  • 8 种地形 (移动消耗/掩护加成/隐蔽/视野阻挡)                     │
│  • 战斗裁定 (伤害公式/buff/debuff/冷却)                            │
│  • 战争迷雾 (按队伍独立可见性)                                     │
│  • 任务完成、控制区和情报利用统计                                  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Event Layer                                    │
│  structured_events: [{type, agent, target, skill, damage, ...}]    │
│  → 前端逐帧回放 + 统计计算 + 战斗日志                              │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Replay Layer (Vue 3 Frontend)                  │
│  • SVG Hex 渲染 + 3D 斜角 + 迷雾                                   │
│  • 逐帧对比/差异叠加/自动暂停                                       │
│  • 伤害数字/施法条/Buff图标/死亡标记                                │
│  • DPS/HPS/承伤实时图表 + 彩色日志                                 │
│  • 战斗结算 MVP 统计                                               │
└─────────────────────────────────────────────────────────────────────┘
```

## 项目指标

| 指标 | 数值 |
|------|------|
| 推演角色 | 8 种 (Coordinator/Scout/Attacker/Defender/Support/Jammer/Controller/Assaulter) |
| 默认评测场景 | 3 个 (balanced / scout pressure / assault breakthrough) |
| 评测策略 | rule_only / hybrid |
| 单局回合数 | 默认 20-40 回合，可配置上限 80 |
| 地形类型 | 8 种 |
| 信源权重系数 | 0.85-1.15 (按角色/消息类型) |
| 衰减率 | 0.85/回合 |
| 置信度阈值 | 0.1 (删除) / 0.3 (读取) |
| 记忆上限 | 80 条 observation / 20 条 summary |
| 评测报告 | JSON + Markdown |
| 前端包体积 | 见 `npm run build` 输出 |

## 许可证

MIT
