# Real-Time Commander Demo

一个 **LLM 自然语言指挥影响胜率** 的最小证据 demo。

1.0 要验证的不是“LLM 会写漂亮战报”，而是：

> 玩家说自然语言，LLM 把它压缩成有限状态机命令；命令进入纯规则 3v3 小地图模拟；胜率真的随输入变化。

核心链路：

```text
自然语言输入
-> LLM command interpreter
-> 有限 policy / FSM mode
-> 镜像 3v3 小地图纯规则模拟
-> 批量胜率统计
```

## 1.0 主入口

先配置 DeepSeek：

```bash
pip3 install openai
cp .env.example .env
```

编辑 `.env`：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

运行自然语言胜率评估：

```bash
python3 scripts/nl_command_eval.py --runs 1000
```

这个脚本必须调用 LLM。若 LLM 不可用，自然语言指挥评估会直接失败；底层 zero-ai 战斗仍可用 `mirror_map_sim.py` 单独运行。

测试自定义一句话：

```bash
python3 scripts/nl_command_eval.py --command "前排顶住，中后排别冲，优先集火残血。"
```

## 1.0 测试矩阵

```text
zero_input       空输入 / 不说话
                 -> dumb/default
                 -> 接近 baseline

good_command     “前排顶住，中后排别冲，优先集火残血”
                 -> good_focus
                 -> 胜率显著提升

bad_charge       “所有人冲出去，不管阵型，直接追对面后排”
                 -> bad_charge
                 -> 胜率显著下降

cower_command    “全员趴下，不许开火”
                 -> cower_all
                 -> 普通交火中几乎必败

irrelevant_chat  “今天天气不错”
                 -> no_op
                 -> 不应自动变成好策略，胜率应不高于 baseline
```

## 3v3 小地图底盘

双方各 3 个完全相同的单位：

```text
front == front
mid   == mid
back  == back
```

它们在 7x3 小地图上按同一套规则移动和交火。无随机时应同归；加入对称伤害浮动后，批量胜率应接近五五开：

```bash
python3 scripts/mirror_map_sim.py
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1
```

底盘支持最小状态机命令协议：

```text
mode = attack_nearest | focus_weakest | focus_target | hold_position | hold_line
     | keep_range | retreat | advance | cower
target = enemy_id | role | weakest | nearest | None
```

命令不会直接加数值，只改变选目标和移动方式。

当前内置 policy：

```text
dumb        默认傻瓜自动：打最近，够射程就打，不会集火
good_focus  常识指挥：前排卡线，中后排集火残血/保持距离
bad_charge  危险指令：全员无视眼前目标，硬追对面后排
hold_all    全员原地不动，但仍会开火
cower_all   全员卧倒/发呆：原地不动且不攻击
no_op       无有效战术内容，回到默认傻瓜自动
```

手动验证 policy 是否影响胜率：

```bash
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy dumb --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy good_focus --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy bad_charge --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy cower_all --blue-policy dumb
```

## 抽象 baseline

`baseline_sim.py` 是更抽象的血条互殴校准工具，用来确认 0.1 / 0.2 的同归和五五开，不是 1.0 主证据。

```bash
python3 scripts/baseline_sim.py --config 0.1
python3 scripts/baseline_sim.py --config 0.2 --runs 1000
```

## 旧遭遇战归档

早期“四人战术小队 vs 装甲/无人机”的文字遭遇战已经归档到：

```text
archive/legacy_encounter/
```

它证明过 DeepSeek 能把战术中文翻译成结构化 orders，但不再是 1.0 主路径。当前主路径只保留：

```text
scripts/nl_command_eval.py
scripts/mirror_map_sim.py
scripts/baseline_sim.py
game/mirror_map_sim.py
game/baseline_sim.py
agents/llm_client.py
```

## 版权边界

本项目是原创玩法机制原型。

它不使用任何现有 IP 的角色、名称、Logo、美术、音乐、剧情设定、世界观术语或商标。
