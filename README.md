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
