# Phase 1 MVP 实现计划

## 概述

构建多智能体对抗演练系统的最小可运行版本，验证架构可行性。

## 目标

- 8x8 网格化对抗场景，按回合推进
- 红队 3 单位（协调 + 侦测 + 执行），蓝队 2 单位（应对）
- LLM 决策（SiliconFlow API），无 API Key 时降级为规则策略
- 共享记忆池（信息去重 + 时间戳 + 置信度衰减）
- 终端与网页可视化输出当前对抗态势

## 文件结构

```text
src/battle/
├── __init__.py
├── battle_types.py      # 数据类型：Position, AgentState, Action, Message, Role, Team, ActionType
├── config.py            # 配置：网格大小、API 密钥、模型参数、日志目录
├── env.py               # 对抗环境：reset/step/观测/动作验证/执行/渲染
├── memory.py            # 共享信息池：写入去重/读取过滤/置信度衰减
├── judge.py             # 胜负判定：全失效判定/状态值比较
├── runner.py            # 控制台运行入口
├── battle_ui.py         # 网页回放入口
└── agents/
    ├── __init__.py
    ├── base.py
    ├── red/
    │   ├── commander.py
    │   ├── scout.py
    │   └── attacker.py
    └── blue/
        └── defender.py
```

## 核心设计

### 1. 数据类型

- `Position`: 表示位置坐标
- `AgentState`: 表示单位状态，包含状态值、资源、观测范围、行动范围等
- `Action`: 表示动作，包含移动、驻留、侦测、对抗、通信
- `Message`: 表示共享信息，支持唯一 ID、时间戳和置信度

### 2. 环境

- `reset`: 初始化红队与蓝队单位
- `step`: 按 `scout -> move -> attack -> communicate` 顺序推进一回合
- `get_observation`: 根据观测范围返回局部可见单位
- `_is_valid_action`: 校验动作合法性（距离、资源、占用）
- `render`: 输出 ASCII 对抗态势图、事件日志和单位状态

### 3. 共享记忆池

- `write`: 写入侦测和任务消息，消息去重
- `read`: 过滤低置信度信息并返回团队视图
- `decay`: 每 3 回合衰减旧信息置信度
- `create_message`: 创建带唯一 ID 的共享消息

### 4. 智能体

- 协调单位：分配任务，维护整体节奏
- 侦测单位：观察局势并上报信息
- 执行单位：根据信息推进并压制目标
- 应对单位：围绕控制区巡逻、拦截和稳态维持

### 5. 运行流程

```text
初始化环境 -> 初始化智能体 -> 初始化记忆池
for turn in 1..40:
    每个在线单位获取观测 + 共享信息 -> 选择动作
    通信动作写入记忆池
    环境执行所有动作
    每 3 回合记忆衰减
    渲染输出
    检查终止条件
判定胜负 -> 输出结果 -> 写入日志
```

## 运行方式

规则模式：

```bash
cd /root/autogen-research
python3 -m src.battle.runner
```

LLM 模式：

```bash
cd /root/autogen-research
./venv/bin/python -m src.battle.runner
```

网页回放：

```bash
cd /root/autogen-research
./venv/bin/python -m src.battle.battle_ui
```

## 验证标准

- 环境可正常启动，无报错
- 双方单位可在场景中移动、侦测、对抗
- 侦测单位可发现目标并上报
- 信息池可去重、读取、衰减
- 胜负判定正确
- 终端和网页输出清晰的对抗态势

## 后续阶段

- Phase 2: 协同增强（任务闭环、通信约束、对抗节奏优化）
- Phase 3: 学习型原型（轨迹记录、奖励函数、策略训练）
- Phase 4: 研究平台（对手建模、课程学习、分层决策、并行采样）
