# realme.md

# Real-Time Commander Text Demo

> 一个纯文字版本的“实时战场指挥官 + 半自主战术人形 + LLM/sub-agent 决策”玩法 demo。
>
> 目标不是做一个完整游戏，而是先验证一个核心问题：
>
> **玩家不亲自开枪，只通过指挥、调度、授权和约束人形行动，这个玩法能不能成立？**

---

## 1. 项目定位

这是一个本地可运行的纯文字战场调度 demo。

它不是 CS2，不是 Overwatch，不是传统 TPS，也不是战棋。

它要验证的是一种更适合“少女前线式 IP”的玩法：

- 玩家身份是 **指挥官**，不是亲自上阵的枪手。
- 角色是 **战术人形 / 武器拟人**，不是普通 FPS 里的 NPC。
- 战斗不是玩家亲自瞄准开火，而是由人形自主执行。
- 玩家通过自然语言或结构化命令参与战术决策。
- 不同人形有不同性格、枪种定位、风险偏好和执行方式。
- LLM 可以作为“战术副官 / 命令编译器 / sub-agent 管理器”。

一句话：

> 这是一个“你说人话，人形自己打，但她们会根据性格和战术规则理解你的命令”的文字战场 demo。

---

## 2. 核心设计命题

传统射击游戏问的是：

> 玩家枪法准不准？

这个 demo 要问的是：

> 指挥官能不能把一群有性格、有武器定位、有自主性的战术人形组织成一个有效战斗系统？

因此 demo 的核心不是“杀敌爽感”，而是：

- 命令是否有意义
- 人形是否真的会根据命令改变行为
- 不同性格是否造成可感知差异
- 玩家是否能通过调度改变战局
- 战斗日志是否让玩家感到“我真的在指挥”

---

## 3. 最小可行玩法

### 3.1 玩家视角

玩家看到的是文字战场状态，例如：

```text
[回合 07 / 实时节拍 07]
地点：废弃街区 A 区

敌方：
- 装甲突击兵 x2，正在推进，距离中
- 轻装步兵 x4，部分进入掩体
- 无人机 x1，正在侦察

我方：
- 沙漠之鹰：HP 82%，位置：右侧掩体，状态：等待处决窗口
- M249：HP 91%，位置：二楼窗口，状态：压制中，弹药 62%
- UMP45：HP 74%，位置：左侧巷道，状态：准备绕后
- 春田：HP 88%，位置：后方高点，状态：寻找射击窗口

战场态势：
- 敌方中路被部分压制
- 左翼存在绕后机会
- 我方推进过快会暴露侧翼
```

玩家输入自然语言命令：

```text
M249 继续压制中路，45 先别冲，等敌方装甲破盾后沙鹰再上去处决。春田优先打无人机。
```

系统输出执行结果：

```text
[战术副官解析]
- M249：维持压制，不追击
- UMP45：取消主动突入，改为隐蔽等待
- 沙漠之鹰：设置处决条件：敌方装甲破盾
- 春田：目标优先级改为无人机 > 精英单位 > 暴露步兵

[执行]
M249 持续压制中路，敌方轻装步兵行动效率下降。
春田等待 2 秒后击落无人机。
UMP45 没有贸然突入，避免被侧翼火力发现。
沙漠之鹰保持手枪出力窗口，等待破盾机会。
```

---

## 4. 核心循环

```text
1. 系统生成当前战场状态
2. 各人形 sub-agent 根据自身性格、枪种、状态提出行动倾向
3. 敌方 AI 推进行动计划
4. 玩家输入自然语言命令
5. LLM 将玩家命令编译为结构化战术指令
6. 战术规则引擎校验命令是否合法
7. 各人形根据：
   - 玩家命令
   - 自身性格
   - 枪种定位
   - 当前战场压力
   - 信任度 / 熟练度
   执行动作
8. 系统结算战斗
9. 输出战场日志
10. 进入下一节拍
```

---

## 5. Agent 架构

### 5.1 主控 Agent：Game Master

职责：

- 维护战场状态
- 控制节拍推进
- 调用各 sub-agent
- 汇总行动
- 进行战斗结算
- 输出玩家可读日志
- 判断胜负

它不负责“文学发挥”，而负责保证系统稳定。

---

### 5.2 战术副官 Agent：Command Interpreter

职责：

- 读取玩家自然语言命令
- 转换成结构化命令
- 识别目标、单位、行动、条件、限制
- 当命令模糊时进行合理补全
- 输出 JSON 或 Python dict

示例输出：

```json
{
  "orders": [
    {
      "unit": "M249",
      "action": "suppress",
      "target": "middle_lane",
      "constraints": ["do_not_advance"]
    },
    {
      "unit": "UMP45",
      "action": "hold",
      "condition": "until_enemy_armor_shield_broken",
      "constraints": ["stay_hidden"]
    },
    {
      "unit": "Desert Eagle",
      "action": "execute",
      "target": "armored_enemy",
      "condition": "enemy_shield_broken"
    },
    {
      "unit": "Springfield",
      "action": "prioritize_target",
      "target": "drone"
    }
  ]
}
```

---

### 5.3 人形 sub-agent

每个人形都是一个轻量 sub-agent。

职责：

- 根据自身性格解释命令
- 根据枪种定位选择行动
- 判断是否需要请求确认
- 在没有明确命令时自主行动
- 生成行动意图

每个人形至少包含：

```yaml
name: Desert Eagle
weapon_type: HG
personality: bold
risk_preference: high
discipline: medium
initiative: high
accuracy: medium
mobility: medium
role: finisher
traits:
  - elite_killer
  - short_window_burst
  - overconfident
```

---

### 5.4 敌方 Agent

职责：

- 推进敌方单位
- 制造压力
- 不需要太聪明
- 只要能形成战场变化即可

MVP 里可以先用规则：

- 步兵会找掩体并推进
- 装甲单位会压中路
- 无人机会侦察并提高敌方命中
- 精英单位会优先攻击暴露目标

---

### 5.5 裁判 / 规则引擎

职责：

- 不允许 LLM 直接决定胜负
- 所有战斗结果必须经过规则结算
- LLM 可以解释命令，但不能凭空宣布成功
- 伤害、命中、压制、掩体、士气、弹药都由规则系统处理

这点非常重要：

> LLM 是副官，不是上帝。
>
> 游戏规则才是战场物理。

---

## 6. 数据结构草案

### 6.1 Unit

```python
@dataclass
class Unit:
    id: str
    name: str
    side: str
    weapon_type: str
    hp: int
    ammo: int
    position: str
    cover: int
    morale: int
    status: list[str]
    personality: str
    role: str
    risk_preference: int
    discipline: int
    initiative: int
    accuracy: int
    mobility: int
    traits: list[str]
```

---

### 6.2 Battlefield

```python
@dataclass
class Battlefield:
    tick: int
    location: str
    friendly_units: list[Unit]
    enemy_units: list[Unit]
    lanes: dict
    global_status: list[str]
    log: list[str]
```

---

### 6.3 Order

```python
@dataclass
class Order:
    unit: str
    action: str
    target: str | None = None
    condition: str | None = None
    constraints: list[str] = field(default_factory=list)
    priority: int = 1
```

---

## 7. 行动类型

MVP 只需要少量高层命令：

### 基础命令

- `hold`：守住当前位置
- `advance`：推进到下一个掩体/目标点
- `suppress`：压制目标区域
- `flank`：尝试绕后
- `retreat`：撤退到安全位置
- `focus_fire`：集火目标
- `prioritize_target`：调整目标优先级
- `reserve_skill`：保留技能
- `execute`：满足条件后处决高价值目标
- `free_fire`：自由开火
- `do_not_chase`：禁止追击

### 条件命令

- 等敌人破盾
- 等机枪压制成功
- 等烟雾展开
- 等敌人进入开阔地
- HP 低于某阈值撤退
- 弹药低于某阈值停止压制

---

## 8. 性格系统

性格必须影响战斗，而不是只影响台词。

### 8.1 鲁莽型 bold

特点：

- 主动抓机会
- 更容易推进
- 更容易打出高爆发
- 更容易暴露
- 更容易追击过深

规则修正：

```text
advance 倾向 +20
initiative +15
被压制抗性 +10
暴露风险 +15
违抗“保守命令”的概率 +5
```

---

### 8.2 谨慎型 cautious

特点：

- 更重视掩体
- 命中率更高
- 更少冒进
- 推进速度慢
- 可能错过窗口

规则修正：

```text
accuracy +15
cover_usage +20
advance 倾向 -15
reaction_speed -5
被突袭时损失 -10
```

---

### 8.3 老练型 veteran

特点：

- 能补全模糊命令
- 自主选择更合理站位
- 不容易浪费技能
- 指令成本低

规则修正：

```text
order_interpretation +20
skill_timing +15
discipline +15
```

---

### 8.4 新人型 rookie

特点：

- 需要明确命令
- 容易误解模糊指令
- 成长空间大

规则修正：

```text
order_interpretation -15
panic_risk +10
growth_rate +20
```

---

## 9. 枪种定位

### HG 手枪

不是靠现实火力压制全场，而是承担：

- buff
- 标记
- 处决
- 指挥链增强
- 短窗口爆发
- 高价值目标补刀

### SMG 冲锋枪

- 近距离突入
- 绕后
- 吸引火力
- 掩护撤退
- 巷战强势

### AR 突击步枪

- 稳定输出
- 泛用推进
- 中距离压制
- 战线骨架

### MG 机枪

- 区域压制
- 破盾
- 阻止敌方推进
- 但弹药消耗高，机动差

### RF 步枪/狙击

- 高价值目标清除
- 反无人机
- 远距离弱点打击
- 需要视野和射击窗口

### SG 霰弹枪

- 近距离防线
- 抗压
- 守门
- 推进尖兵

---

## 10. 文字战斗结算规则

MVP 可以采用简化规则。

### 10.1 命中率

```text
base_accuracy
+ unit.accuracy
+ cover_bonus_if_cautious
+ target_exposed_bonus
- target_cover
- suppression_penalty
- movement_penalty
```

### 10.2 压制

压制不一定造成高伤害，但会影响敌方：

- 推进速度下降
- 命中率下降
- 暴露时间增加
- 更容易被 flank
- 更容易被处决

### 10.3 掩体

掩体减少伤害并提高存活率。

谨慎型更会利用掩体。

鲁莽型更容易离开掩体。

### 10.4 士气 / 稳定度

士气过低会导致：

- 命中下降
- 推进失败
- 撤退
- 请求指挥官重新确认命令

---

## 11. LLM 接入方式

### 11.1 推荐模式

不要让 LLM 直接写战斗结果。

LLM 只做三件事：

1. 理解玩家命令
2. 生成结构化 orders
3. 为人形生成简短行动理由 / 战术日志

结算仍由本地规则完成。

### 11.2 可选本地模型

可以支持任意 OpenAI-compatible API，例如：

- Ollama
- LM Studio
- llama.cpp server
- OpenAI API
- DeepSeek API
- Gemini API

环境变量示例：

```bash
export LLM_BASE_URL="http://localhost:11434/v1"
export LLM_API_KEY="ollama"
export LLM_MODEL="qwen2.5:7b"
```

---

## 12. 项目文件结构建议

```text
real-time-commander-demo/
├── realme.md
├── main.py
├── game/
│   ├── __init__.py
│   ├── state.py
│   ├── units.py
│   ├── battlefield.py
│   ├── rules.py
│   ├── orders.py
│   ├── logger.py
│   └── scenario.py
├── agents/
│   ├── __init__.py
│   ├── command_interpreter.py
│   ├── doll_agent.py
│   ├── enemy_agent.py
│   └── game_master.py
├── prompts/
│   ├── command_interpreter.md
│   ├── doll_agent.md
│   └── battle_narrator.md
├── data/
│   ├── dolls.yaml
│   ├── enemies.yaml
│   └── scenarios.yaml
└── README.md
```

---

## 13. 第一版 demo 范围

第一版不要贪。

只做一个场景：

> 废弃街区遭遇战

我方 4 人：

- 沙漠之鹰：HG，鲁莽/自信，处决型
- M249：MG，火力压制型
- UMP45：SMG，老练绕后型
- 春田：RF，谨慎狙击型

敌方：

- 轻装步兵 x4
- 装甲突击兵 x2
- 无人机 x1

胜利条件：

- 清除敌方装甲单位
- 或坚持 12 个 tick 并守住阵地

失败条件：

- 我方 2 人以上失去战斗能力
- 或敌人突破核心区域

---

## 14. 示例游玩流程

```text
Game Master:
你的小队进入废弃街区。敌方装甲单位正在中路推进，无人机正在上空侦察。
M249 已经找到二楼窗口，但弹药有限。
UMP45 发现左翼巷道可以绕后。
沙漠之鹰请求处决授权。
春田报告无人机干扰了视野。

Commander >
M249 压住中路，春田先打无人机，45 不要急着上，沙鹰等破盾再处决。

Game Master:
[命令解析完成]

M249 架设火力，开始压制中路。敌方步兵推进速度下降。
春田等待无人机进入稳定窗口，一枪击落目标。
UMP45 停在左翼阴影中，没有暴露。
沙漠之鹰保持武器低垂，等待装甲单位破盾。

敌方装甲仍在推进，但因为无人机被击落，命中下降。
```

---

## 15. 设计原则

### 15.1 指挥官不是装饰

玩家必须真的能影响战斗。

不是剧情里叫你指挥官，战斗里却让你亲自打枪。

### 15.2 人形不是棋子

人形应有一定自主性。

她们会执行命令，也会根据性格、经验、压力做出不同选择。

### 15.3 性格不是台词

性格必须影响战术执行。

鲁莽、谨慎、老练、新人，都应该改变战斗结果。

### 15.4 武器拟人不是皮肤

枪种定位必须进入玩法。

手枪不需要在火力上赢机枪，但可以在处决、指挥、标记、短窗口爆发里有独特位置。

### 15.5 LLM 不是规则本身

LLM 可以理解语言，可以生成日志，可以扮演副官。

但胜负和结算必须由规则系统控制。

---

## 16. 未来扩展

如果 MVP 成立，可以继续加：

- 多小队调度
- 不同地图
- 夜战 / 视野 / 侦察
- 弹药补给
- 电子战
- 人形信任度
- 人形对指挥官风格的适应
- 指挥官声望
- 任务后复盘
- 角色关系影响协同
- 自然语言作战计划
- 战斗中断点保存
- Web UI 或 TUI
- 自动生成战报

---

## 17. 对 coding agent 的任务说明

请先实现一个最小可运行版本：

1. 用 Python 写一个纯命令行 demo。
2. 不需要图形界面。
3. 支持一场固定战斗。
4. 每个 tick 输出战场状态。
5. 玩家输入自然语言命令。
6. 先用简单规则/关键词解析命令，不强制接 LLM。
7. 预留 LLM Command Interpreter 接口。
8. 每个人形有性格和枪种定位。
9. 玩家命令能改变人形行为。
10. 战斗结算必须由规则引擎完成。
11. 输出清晰战斗日志。
12. 保持代码结构简单，方便继续扩展。

优先实现：

- hold
- advance
- suppress
- flank
- retreat
- focus_fire
- prioritize_target
- execute
- do_not_chase

不要第一版就追求完美自然语言理解。

第一版的目标只有一个：

> 跑起来，并让玩家感觉“我不是在亲自开枪，而是在指挥她们”。

---

## 18. 成功标准

这个 demo 如果能让玩家产生以下感觉，就算第一阶段成功：

- 我真的在指挥，而不是在操作角色
- 人形有自主性，但没有完全失控
- 不同性格会造成不同执行结果
- 我的命令改变了战场
- 武器定位有意义
- 纯文字也能感受到战术节奏
- 这个玩法值得继续做下去

---

## 19. 项目一句话

> 用纯文字先验证一种真正属于“战术人形 / 武器拟人 / 指挥官”的玩法：玩家下达战术意图，人形根据性格与枪种自主执行，战场由规则系统实时结算。
