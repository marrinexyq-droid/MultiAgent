# 多智能体网络攻防演练系统总结文档

## 一、系统概述

### 1.1 项目背景与目标

本系统是一个基于多智能体的网络攻防对抗仿真平台，旨在模拟真实网络环境中的红蓝对抗场景。系统采用 8×8 网格化网络靶场，通过多智能体协作实现自动化攻防演练验证。

**核心目标：**
- 验证多智能体角色协作链是否能正常运行
- 支持 LLM（大语言模型）与规则模式双驱动
- 提供终端、网页、日志三种输出方式

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    入口层 (runner.py / battle_ui.py)    │
├─────────────────────────────────────────────────────────┤
│                    智能体层 (agents/)                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │ RedCommander│ │  RedScout   │ │ RedAttacker │        │
│  └─────────────┘ └─────────────┘ └─────────────┘        │
│  ┌─────────────┐                                      │
│  │BlueDefender │ × 2                                  │
│  └─────────────┘                                      │
├─────────────────────────────────────────────────────────┤
│                    共享记忆池 (memory.py)               │
├─────────────────────────────────────────────────────────┤
│                    环境层 (env.py)                      │
│    - 网格世界     - 动作执行     - 态势观测             │
├─────────────────────────────────────────────────────────┤
│                    判定层 (judge.py)                    │
└─────────────────────────────────────────────────────────┘
```

---

## 二、智能体详解

### 2.1 攻击方 (Red Team)

| 智能体 | 角色 | 节点ID | 起始位置 | 职责 |
|--------|------|--------|----------|------|
| RedCommander | 编排节点 | red_orchestrator | (1,1) | 协调攻击链，分配任务 |
| RedScout | 侦察节点 | red_recon | (2,2) | 扫描暴露资产，收集情报 |
| RedAttacker | 利用节点 | red_operator | (1,2) | 利用目标，推进攻击 |

### 2.2 防守方 (Blue Team)

| 智能体 | 角色 | 节点ID | 起始位置 | 职责 |
|--------|------|--------|----------|------|
| BlueDefender | 防护节点 | blue_soc_1 / blue_soc_2 | (6,6) / (6,5) | 保护关键资产区，检测入侵 |

### 2.3 智能体属性

| 属性 | 说明 | 典型值 |
|------|------|--------|
| HP (完整性) | 节点生命值 | 80-120 |
| Ammo (载荷) | 攻击次数 | 5 |
| Vision Range (扫描范围) | 可观测距离 | 2-4 |
| Attack Range (利用范围) | 攻击距离 | 1 |
| Attack Power | 攻击伤害 | 15-30 |

---

## 三、核心提示词 (Prompts)

### 3.1 基础动作提示词

系统在 `agents/base.py` 中定义了统一的 LLM 提示词模板：

```python
role_priority = {
    Role.COMMANDER: "coordinate the intrusion chain, assign tasks, and prioritize key assets",
    Role.SCOUT: "scan exposed services, collect intelligence, and reveal defender positions",
    Role.ATTACKER: "exploit exposed assets, pivot laterally, and pressure the target zone",
    Role.DEFENDER: "protect the critical asset zone at (6,5)-(6,6), detect intrusions, and contain attackers",
}

role_specific_instruction = {
    Role.COMMANDER: "Act like a red-team orchestrator: correlate intel and direct the next intrusion step.",
    Role.SCOUT: "Act like a recon operator: scan first, then feed fresh intel back to the team.",
    Role.ATTACKER: "Act like an exploitation operator: move toward the target zone and compromise defenders when adjacent.",
    Role.DEFENDER: "Act like a blue-team analyst: patrol the key asset zone, detect movement, and contain compromises quickly.",
}
```

### 3.2 完整 Prompt 结构

```python
prompt = (
    f"You are a {self.state.role.value} node (ID: {self.state.agent_id}) in an 8x8 cyber range.\n\n"
    f"Your status: position=({x},{y}), Integrity={hp}, Payloads={ammo}\n"
    f"Known enemy positions from team: {json.dumps(enemies)}\n"
    f"Available actions:\n"
    f"- move: pivot to an adjacent network segment\n"
    f"- hold: remain in the current segment\n"
    f"- attack: exploit an adjacent hostile node (distance=1)\n"
    f"- scout: scan for hostile nodes when no target is confirmed\n"
    f"- communicate: share fresh intel with the team\n\n"
    f'Respond with ONLY a JSON object:\n'
    f'{{"action_type": "move|hold|attack|scout|communicate", "target": {{"x": 1, "y": 1}}}}'
)
```

---

## 四、运行过程中的 Skill 使用

### 4.1 当前系统使用的 Skill

本系统在开发过程中使用了以下技能（来自 Claude Code / ECC）：

| Skill 名称 | 用途 |
|-------------|------|
| tdd-workflow | 测试驱动开发工作流 |
| python-patterns | Python 代码规范与模式 |
| coding-standards | 跨项目编码规范 |
| cpp-coding-standards | C++ 编码标准 |
| python-testing | Python 测试策略 |

### 4.2 未直接使用但相关的 Skill

| Skill 名称 | 潜在应用场景 |
|------------|--------------|
| ai-regression-testing | 回归测试策略 |
| verification-loop | 验证循环 |
| deep-research | 深度研究 |

---

## 五、关键函数详解

### 5.1 环境层 (env.py)

| 函数名 | 作用 | 关键逻辑 |
|--------|------|----------|
| `reset()` | 初始化环境 | 创建红蓝双方节点，设置初始位置 |
| `step()` | 推进一回合 | 按 scout → move → attack → communicate 顺序执行 |
| `get_observation()` | 获取观测 | 根据视野范围返回可见的敌我节点 |
| `_is_valid_action()` | 校验动作 | 检查移动距离、攻击范围、弹药是否合法 |
| `_resolve_move_actions()` | 解决冲突 | 处理多节点移动时的位置冲突 |
| `_execute_attack()` | 执行攻击 | 计算伤害，扣除目标 HP，更新存活状态 |
| `_check_termination()` | 判定终止 | 检查是否一方全灭或达到最大回合 |
| `render()` | 渲染态势 | 输出 ASCII 格式的网络态势图 |

### 5.2 记忆池层 (memory.py)

| 函数名 | 作用 | 关键逻辑 |
|--------|------|----------|
| `write()` | 写入情报 | 去重检查 → 按类型存储（enemy_spot/risk_zone/task_assign） |
| `read()` | 读取情报 | 按置信度过滤 → 返回团队视图 |
| `decay()` | 置信度衰减 | 每3回合衰减 0.85，低于 0.1 删除 |
| `create_message()` | 创建消息 | 生成带唯一 ID 的 Message 对象 |

### 5.3 智能体层 (base.py)

| 函数名 | 作用 | 关键逻辑 |
|--------|------|----------|
| `choose_action()` | 选择动作 | LLM 模式 / 规则模式双路径 |
| `_sync_state_from_obs()` | 同步状态 | 从观测更新内部状态 |
| `_build_prompt()` | 构建提示词 | 组装系统提示 + 角色定义 + 观测数据 |
| `_llm_action()` | LLM 决策 | 调用 OpenAI API 解析 JSON 响应 |
| `_rule_action()` | 规则决策 | 基于启发式的动作选择 |
| `_avoid_oscillation()` | 避免震荡 | 防止在两点间反复移动 |

### 5.4 入口层 (runner.py)

| 函数名 | 作用 |
|--------|------|
| `create_agents()` | 创建并初始化所有智能体 |
| `main()` | 主循环：获取观测 → 选择动作 → 执行 → 渲染 → 判定 |

---

## 六、记忆池与信息池机制详解

### 6.1 设计背景

在多智能体网络对抗中，各节点需要共享情报以实现协同作战。记忆池（SharedMemoryPool）承担了这一职责，实现了团队内的情报共享与传递。

### 6.2 实现规则

#### 6.2.1 消息类型

系统支持三种消息类型：

| 类型 | 用途 | 内容结构 |
|------|------|----------|
| `enemy_spot` | 敌情上报 | target_id, pos, hp |
| `risk_zone` | 风险区域 | x, y, reason |
| `task_assign` | 任务分配 | assignee, task, target_id, target_pos |

#### 6.2.2 消息属性

```python
@dataclass
class Message:
    msg_id: str              # 唯一标识
    sender_id: str           # 发送者ID
    sender_role: Role        # 发送者角色
    content: dict            # 消息内容
    timestamp: int           # 时间戳（回合数）
    confidence: float        # 置信度（初始1.0）
```

### 6.3 实现方式

#### 6.3.1 写入流程 (`write` 方法)

```python
def write(self, msg: Message) -> bool:
    # 1. 去重检查
    if msg.msg_id in self.processed_msg_ids:
        return False
    self.processed_msg_ids.add(msg.msg_id)
    
    # 2. 按类型存储
    if msg_type == "enemy_spot":
        self.enemy_tracks[target_id].append({...})
    elif msg_type == "risk_zone":
        self.risk_zones[zone_key] = {...}
    elif msg_type == "task_assign":
        self.team_tasks[task_id] = {...}
    
    return True
```

#### 6.3.2 读取流程 (`read` 方法)

```python
def read(self, agent_id: str, min_confidence: float = 0.3) -> dict:
    # 过滤低置信度情报
    filtered_tracks = {
        tid: [r for r in reports if r["confidence"] >= 0.3]
        for tid, reports in self.enemy_tracks.items()
    }
    
    # 返回团队视图
    return {
        "enemy_tracks": filtered_tracks,
        "risk_zones": filtered_risks,
        "team_tasks": filtered_tasks,
    }
```

#### 6.3.3 衰减机制 (`decay` 方法)

```python
def decay(self):
    # 每 3 回合执行一次
    decay_rate = 0.85
    
    # 所有情报置信度衰减
    for target_id in self.enemy_tracks:
        self.enemy_tracks[target_id] = [
            {**r, "confidence": r["confidence"] * 0.85}
            for r in self.enemy_tracks[target_id]
        ]
    
    # 删除低置信度情报
    self.enemy_tracks = {
        k: v for k, v in self.enemy_tracks.items()
        if any(r["confidence"] > 0.1 for r in v)
    }
```

### 6.4 当前实现的缺点

| 缺点 | 说明 |
|------|------|
| **去重机制简单** | 仅基于 `msg_id` 去重，无法识别语义重复的情报 |
| **衰减策略单一** | 固定 0.85 衰减率，不区分情报类型和来源 |
| **无优先级区分** | 所有情报一视同仁，无法区分关键任务 vs 一般情报 |
| **无时效性建模** | 仅用回合数作为时间戳，无法处理实时性要求 |
| **缺乏信任传播** | 不同报告者的情报应有不同权重，当前未实现 |
| **信息池独立** | 红蓝双方各自独立，无法实现欺骗与反欺骗 |

### 6.5 后续改造建议

#### 6.5.1 情报去重与融合

```python
# 引入语义相似度计算
def compute_similarity(self, msg1: dict, msg2: dict) -> float:
    # 基于位置、时间、类型计算相似度
    pass

def fuse_reports(self, reports: list[dict]) -> dict:
    # 融合多个报告，综合位置和 HP 信息
    pass
```

#### 6.5.2 自适应衰减

```python
def adaptive_decay(self, msg_type: str, source_role: Role) -> float:
    # 根据情报类型和来源动态调整衰减率
    decay_rates = {
        "enemy_spot": 0.9,      # 敌情衰减慢
        "risk_zone": 0.7,        # 风险区域衰减快
        "task_assign": 0.95,     # 任务衰减最慢
    }
    return decay_rates.get(msg_type, 0.85)
```

#### 6.5.3 信任传播机制

```python
def compute_source_trust(self, source_role: Role) -> float:
    trust_scores = {
        Role.SCOUT: 0.9,      # 侦察节点报告可信度高
        Role.COMMANDER: 1.0,  # 编排节点任务最可信
        Role.ATTACKER: 0.7,   # 利用节点信息次之
    }
    return trust_scores.get(source_role, 0.5)
```

#### 6.5.4 跨团队信息池（高级）

- 实现蜜罐机制：防守方可发布虚假情报诱骗攻击方
- 实现反间谍机制：攻击方可渗透并监听防守方通信
- 增加不确定性建模：用概率分布而非确定值表示情报

---

## 七、动作类型与策略

### 7.1 动作枚举

```python
class ActionType(Enum):
    MOVE = "move"        # 横向移动
    HOLD = "hold"       # 驻留
    SCOUT = "scout"     # 扫描
    ATTACK = "attack"   # 利用
    COMMUNICATE = "communicate"  # 通信
```

### 7.2 各角色策略

| 角色 | 首选动作 | 策略描述 |
|------|----------|----------|
| RedCommander | MOVE → ATTACK | 移动到目标区域，有敌人则攻击或分配任务 |
| RedScout | SCOUT → COMMUNICATE | 优先扫描，发现敌人则上报情报 |
| RedAttacker | MOVE → ATTACK | 接收任务或根据情报移动，接近后利用 |
| BlueDefender | MOVE → ATTACK | 巡逻关键区域(6,5)-(6,6)，发现入侵者则拦截 |

---

## 八、胜负判定机制

### 8.1 判定规则 (`judge.py`)

| 条件 | 获胜方 | 说明 |
|------|--------|------|
| red_alive == 0 | BLUE | 攻击方全灭 |
| blue_alive == 0 | RED | 防守方全灭 |
| 红方存活率 > 蓝方 + 5% | RED | 达到最大回合 |
| 蓝方存活率 > 红方 + 5% | BLUE | 达到最大回合 |
| 其他 | DRAW | 平局 |

### 8.2 存活率计算

```python
red_survival_rate = red_total_hp / red_max_hp
blue_survival_rate = blue_total_hp / blue_max_hp
```

---

## 九、运行方式

### 9.1 命令行规则模式

```bash
cd /root/autogen-research
python3 -m src.battle.runner
```

### 9.2 命令行 LLM 模式

```bash
cd /root/autogen-research
./venv/bin/python -m src.battle.runner
# 需要设置 SILICONFLOW_API_KEY 环境变量
```

### 9.3 网页回放

```bash
cd /root/autogen-research
./venv/bin/python -m src.battle.battle_ui
# 访问 http://localhost:7861
```

---

## 十、文件结构总览

```
src/battle/
├── __init__.py
├── battle_types.py      # 数据类型定义
├── config.py            # 配置管理
├── env.py               # 网络靶场环境
├── memory.py            # 共享记忆池
├── judge.py             # 胜负判定
├── runner.py            # 命令行入口
├── battle_ui.py         # 网页回放入口
├── memory.py            # 共享情报池
└── agents/
    ├── __init__.py
    ├── base.py          # 智能体基类
    ├── red/
    │   ├── __init__.py
    │   ├── commander.py # 编排节点
    │   ├── scout.py     # 侦察节点
    │   └── attacker.py # 利用节点
    └── blue/
        ├── __init__.py
        └── defender.py # 防护节点
```

---

## 十一、后续发展方向

1. **网络拓扑升级**：从 8×8 网格升级为真实企业网络资产拓扑
2. **攻防元素丰富**：增加漏洞、服务、告警、修复等真实攻防元素
3. **任务闭环完善**：支持更明确的编排 → 侦察 → 利用 → 防守反馈
4. **行为稳定性验证**：增加更多回放和统计验证 LLM 行为
5. **可视化分析工具**：增加结构化回放分析和交互控制

---

*文档更新时间：2026-04-09*