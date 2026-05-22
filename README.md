# Real-Time Commander Demo

一个纯文字版 **AI-native 半自主小队指挥玩法样机**。

核心不是“文字战棋”，而是验证：

> 玩家可以零指挥旁观，也可以用自然语言在关键时刻介入战术系统。  
> LLM 负责听懂人话，本地规则引擎负责战斗现实。

## 项目原则零

玩家不是每一秒都必须下命令。

低难度或稳定战况下，小队应当能根据默认战术、单位性格、枪种定位和 AI 副官建议自主推进。玩家可以：

- 完全旁观
- 只批准高风险行动
- 输入自然语言战术意图
- 修改整体方针
- 紧急 override

## 版权边界

本项目是原创玩法机制原型。

它不使用任何现有 IP 的角色、名称、Logo、美术、音乐、剧情设定、世界观术语或商标。

## 运行

```bash
python3 main.py
```

默认会使用本地启发式 fallback，便于无网络测试。  
要启用 DeepSeek LLM：

```bash
pip3 install openai
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
python3 main.py
```

也可以在项目根目录创建 `.env`：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

`.env` 已加入 `.gitignore`，不要提交真实 key。

默认使用：

```text
base_url = https://api.deepseek.com
model = deepseek-v4-pro
reasoning_effort = high
thinking.type = enabled
```

也可以用环境变量覆盖：

```bash
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_API_KEY="$DEEPSEEK_API_KEY"
export LLM_MODEL="deepseek-v4-pro"
export LLM_REASONING_EFFORT="high"
export LLM_THINKING="enabled"
python3 main.py
```

兼容 OpenAI / DeepSeek / Gemini-compatible proxy / Ollama / LM Studio 等 OpenAI-compatible Chat Completions API。

## 操作示例

```text
MG 压制中路，SMG 先别冲，RF 先打无人机，HG 等破盾再处决
```

或直接回车：

```text
Commander >
```

回车代表零指挥，本 tick 由 AI 副官/默认战术接管。

## 本地验证

不访问 LLM、只跑本地规则和 fallback 解析：

```bash
python3 scripts/smoke_demo.py
```

## 战斗底盘校准

先不测试 LLM 或人类指令，单独校准自动战斗的胜负底盘。

`0.1` 是确定性同归/近同归 baseline：

```bash
python3 scripts/baseline_sim.py --config 0.1
```

`0.2` 加入命中、暴击和伤害浮动，但双方参数仍保持对称，用批量运行检查五五开：

```bash
python3 scripts/baseline_sim.py --config 0.2 --runs 1000
```

这个阶段的目标是先得到一个可统计的 zero-ai baseline，再比较后续 LLM 低频介入或人类接入是否改变胜率。

镜像 3v3 小地图 baseline：

```bash
python3 scripts/mirror_map_sim.py
```

双方各 3 个完全相同的单位，在 7x3 小地图上按同一套自动规则移动和交火。无随机时应同归；加入对称伤害浮动后，批量胜率应接近五五开：

```bash
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1
```

这个小地图底盘支持最小状态机命令协议：

```text
mode = attack_nearest | focus_weakest | focus_target | hold_position | hold_line | keep_range | retreat | advance
     | cower
target = enemy_id | role | weakest | nearest | None
```

命令不会直接加数值，只改变选目标和移动方式。当前内置 policy：

```text
dumb        默认傻瓜自动：打最近，够射程就打，不会集火
good_focus  常识指挥：前排卡线，中后排集火残血/保持距离
bad_charge  危险指令：全员无视眼前目标，硬追对面后排
hold_all    全员原地不动
cower_all   全员卧倒/发呆：原地不动且不攻击
```

对比命令是否真的影响胜率：

```bash
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy good_focus --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy bad_charge --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy cower_all --blue-policy dumb
```

## 1.0 验收目标

1.0 要验证的不是“LLM 会写漂亮战报”，而是：

> LLM 驱动的自然语言指挥游戏是可玩的；玩家说的话会被压缩成有限状态机命令，并真实改变胜率。

核心链路：

```text
自然语言输入
-> LLM command interpreter / unit subagent
-> 有限 policy / FSM mode
-> 镜像 3v3 小地图纯规则模拟
-> 批量胜率统计
```

1.0 测试矩阵：

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
                 -> no_op / hesitation
                 -> 不应自动变成好策略，胜率应不高于 baseline
```

这里的重点是：自然语言入口很宽，但底层执行空间很窄。LLM 只负责理解、压缩和分发命令；胜负必须由纯规则模拟产生。

实时观看一场每 tick 间隔 5 秒的自动战斗：

```bash
python3 scripts/realtime_demo.py
```

默认是 `zero-ai` 模式：不调用 LLM，只运行本地规则、默认战术和 AI 副官。这对应“碾压局 / 简单局不需要介入”。

均势或复杂局面可以使用低频 AI 介入。LLM 只按较长间隔读取战场并可能发出指令，不是每 tick 高频监控：

```bash
python3 scripts/realtime_demo.py --mode ai-interval --ai-every 4
```

模拟人类接入时，使用 `human-script` 模式。它会把普通、模糊、危险和零指挥输入交给 LLM 解析：

```bash
python3 scripts/realtime_demo.py --mode human-script
```

所有模式都可以强制离线，不调用 LLM：

```bash
python3 scripts/realtime_demo.py --offline
```

调整刷新间隔：

```bash
python3 scripts/realtime_demo.py --interval 0.5
```

快速只跑前 2 个 tick / 输入：

```bash
python3 scripts/realtime_demo.py --limit 2
```
