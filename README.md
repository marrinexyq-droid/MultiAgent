# 多智能体战术对抗推演平台

基于六边形网格的多智能体战术对抗仿真平台，支持实时可视化、战斗回放和统计分析。

## 功能特性

### 推演引擎
- **六边形网格系统** — 轴向坐标的距离计算、寻路、视线(LOS)、AoE范围判定
- **8 种地形** — 开阔/道路/森林/城区/水域/崎岖/沼泽/山脉，各有不同的移动消耗、掩护加成、隐蔽度和视野阻挡
- **回合制战斗** — 移动、攻击、技能施放、buff/debuff、伤害/治疗结算
- **战争迷雾** — 按队伍独立的可见性网格，地形成熟度影响视野
- **LB 极限技** — 团队共享能量槽（每回合基础+3，每承受200伤害额外+1）

### AI 决策
- **混合 LLM+规则 AI** — 接入 OpenAI 兼容 API 时使用 LLM 决策，否则降级为角色专属规则策略
- **共享记忆池** — 基于概率置信度的信念系统，支持多源交叉验证、按角色加权的信源信任度、逐回合衰减
- **6 种角色** — 指挥官、侦察兵、突击手、防御者、支援、控制器，各自的上下文裁剪和决策逻辑不同

### 可视化
- **SVG 六边形渲染** — 3D 斜角效果 + 对角线光照（军事科技主题）
- **魔幻模式** — FF14 风格的 8 人小队对战，40+ 技能、连击链、职业系统
- **战斗回放** — 逐帧对比、差异叠加、关键事件自动暂停
- **伤害数字** — 浮动伤害/治疗/暴击指示器，CSS 动画
- **施法条** — 单位头顶施法进度条
- **DPS/HPS 图表** — 实时柱状图，弹性过渡动画
- **交互地图** — 悬停提示、Buff 图标、死亡标记、AoE 危险区域

### 统计与分析
- 累计伤害输出/承受/治疗量
- DPS/HPS/承伤实时统计
- 战斗结算 MVP 计算
- 彩色战斗日志（红=攻击，绿=治疗，金=结果）

## 技术栈

| 层 | 技术 |
|-------|-----------|
| 前端 | Vue 3 + TypeScript + Vite |
| 后端 | Python + FastAPI |
| AI | OpenAI 兼容 API（SiliconFlow）+ 规则降级 |
| 部署 | FastAPI 单服务 + 静态前端 |

## 快速启动

### 后端

```bash
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn
python -m src.battle.api_server
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

### 魔幻模式

启动 API 服务器后，导航到 `/fantasy` 路由。魔幻模式使用同一后端，独立的 agent 配置和 8 人小队格式。

## 项目结构

```
src/
├── battle/
│   ├── env.py                # 基础战场环境
│   ├── ff14_env.py           # 魔幻模式战斗引擎（8v8，40+ 技能）
│   ├── grid_rules.py         # 六边形网格数学（距离、视线、邻居）
│   ├── terrain.py            # 地形属性和预设生成器
│   ├── battle_types.py       # 共享数据模型
│   ├── stats.py              # 统计追踪
│   ├── memory.py             # 共享记忆池（信念 + 衰减）
│   ├── fantasy_api.py        # 魔幻模式 FastAPI 路由
│   ├── api_server.py         # 主 FastAPI 服务器
│   ├── ff14_skills.py        # 技能定义 + 连击链
│   └── ff14_roster.py        # 职业模板（8 种角色）
├── agents/
│   ├── ff14_agent.py         # 魔幻模式混合 LLM+规则 agent
│   ├── generic.py            # 规则驱动战术 agent
│   ├── red/                  # 红方 agent 实现
│   └── blue/                 # 蓝方 agent 实现
frontend/
├── src/
│   ├── components/
│   │   ├── FantasyMap.vue    # 魔幻地图（单位徽标、特效）
│   │   ├── HexBattleMap.vue  # 军事地图（3D 地形、迷雾）
│   │   ├── HexDamageNumber.vue # 浮动伤害数字
│   │   └── ...
│   ├── views/
│   │   ├── FantasyPage.vue   # 魔幻战斗主页面
│   │   ├── HexLabPage.vue    # 军事推演主页面
│   │   └── ...
│   └── styles.css            # 全局样式（暗色主题）
```

## 架构

```
Agent (LLM/规则) → 环境 (六边形网格 + 战斗) → 事件 → 统计 → 前端 (Vue 3)
       ↓
  共享记忆池 (信念 + 衰减 + 角色上下文裁剪)
```

本系统是一个**多智能体战术对抗仿真沙箱**：agent 基于战场态势做出决策，环境解析行动并生成结构化事件，前端提供逐帧回放和全量统计。

## 许可证

MIT
