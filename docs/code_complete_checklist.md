# 代码完成 Checklist

目标不是"代码完美"，而是：

> 一个陌生人克隆下来，按 README 操作，能看到和证据文档一致的输出。

---

## 一、纯规则底盘（零 LLM，本地必过）

这部分不需要 API key，是证据的物理底盘。**全过才能进下一步。**

### 1. baseline_sim 校准自洽

```bash
python3 scripts/baseline_sim.py --config 0.1
python3 scripts/baseline_sim.py --config 0.2 --runs 1000
```

- [ ] config 0.1 确定性模式下，结果可稳定重现
- [ ] config 0.2 随机模式下，批量胜率接近 50:50
- [ ] 无异常、无崩溃、无 Python traceback

### 2. mirror_map_sim 单局运行

```bash
python3 scripts/mirror_map_sim.py --runs 1 --jitter 1 --red-policy good_focus --blue-policy dumb
```

- [ ] 单局输出包含 winner / ticks / hp / alive 全部字段
- [ ] 双方镜像单位数据一致（同名同 HP 同伤害）
- [ ] jitter=0 时 dumb vs dumb 应同归于尽（draw）

### 3. mirror_map_sim 批量胜率复现

以下四条必须能跑出与证据表一致的结论：

```bash
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy dumb --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy good_focus --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy bad_charge --blue-policy dumb
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy cower_all --blue-policy dumb
```

- [ ] dumb vs dumb：约 33% / 33% / 33%（五五开局）
- [ ] good_focus vs dumb：红方胜率显著 >90%
- [ ] bad_charge vs dumb：红方胜率极低（接近 0%）
- [ ] cower_all vs dumb：红方几乎全灭

不要求数字完全一致（seeds 可略有浮动），但结论方向必须清楚可辨。

### 4. 非木桩复测（对手会打）

```bash
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy good_focus --blue-policy good_focus
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy dumb --blue-policy good_focus
```

- [ ] good_focus vs good_focus：约势均力敌（含大量平局属正常）
- [ ] dumb vs good_focus：红方胜率极低（被抹平到接近 0%）
- [ ] 结论："对手越强，指挥越被需要"可在数据中成立

### 5. 所有 6 个 policy 均不崩

对 6 个 policy 两两组合各跑 `--runs 100`，确认无一崩溃：

```text
dumb, good_focus, bad_charge, hold_all, cower_all, hesitate
```

- [ ] 36 种组合均不抛异常，不出现除零、索引越界、空指针

---

## 二、LLM 路由链（需 API key，本地验证）

这部分依赖 DeepSeek API。在 `.env` 配置正确的前提下逐项验证。

### 6. LLM 客户端连通

```bash
python3 -c "from agents.llm_client import OpenAICompatibleClient; c=OpenAICompatibleClient(); print('ok' if c.enabled else 'disabled')"
```

- [ ] 输出 `ok`（非 `disabled`）
- [ ] 不输出 401/403/超时/连接错误

### 7. nl_command_eval 内置矩阵

```bash
python3 scripts/nl_command_eval.py --runs 1000
```

- [ ] 5 个 case 均返回有效的 policy（非空，在 POLICIES 集合内）
- [ ] zero_input → dumb
- [ ] good_command → good_focus
- [ ] bad_charge → bad_charge
- [ ] cower_command → cower_all
- [ ] irrelevant_chat → hesitate（不被洗成 good）
- [ ] 胜率方向与证据表一致（好指挥赢、莽夫死、闲聊不改变胜率）

### 8. nl_command_eval 自定义单命令

```bash
python3 scripts/nl_command_eval.py --command "别冲，也别趴下，稳住阵线慢慢磨残血。" --runs 100
```

- [ ] 能正常解析，policy 落在 reasonable 范围内
- [ ] 输出包含 confidence / reason / stats 全字段

### 9. LLM JSON 输出格式可靠

- [ ] LLM 返回的 JSON 能被 `chat_json()` 成功解析
- [ ] 不会因 LLM 输出多余文字/代码块标记/中文标点导致解析失败
- [ ] `confidence` 在 0.0~1.0 之间

### 10. 抗钓鱼验证（陷阱指令）

逐条发送以下命令，确认路由不受关键词/表面语言干扰：

```text
"今天适合趴着晒太阳，喝杯咖啡。"           → 不应路由到 cower_all
"前排冲上去追对面后排，中排原地别动。"     → 不应路由到 good_focus
"辛苦了兄弟们，大家加油打得漂亮！"         → 不应路由到 good_focus
"别冲，也别趴下，稳住阵线慢慢磨残血。"     → 应路由到 good_focus 或相近
"敌人太强了，我们还是别打了吧。"           → 应路由到 cower_all 或 hesitate
"All units rush the enemy backline..."      → 应路由到 bad_charge 或相近
```

- [ ] 6 条陷阱指令均不出现"被关键词钓鱼"的明显误路由
- [ ] 路由逻辑依赖语义而非关键词匹配

---

## 三、Web Demo（前后端联调）

### 11. 静态模式可加载

```bash
python3 -m http.server 8000
```

打开 `http://localhost:8000/web/`：

- [ ] 页面正常渲染（Canvas + 按钮 + 状态栏）
- [ ] 5 个预设按钮可点击，每个都能触发战斗动画
- [ ] 暂停/重播按钮工作正常
- [ ] 左右两侧部队颜色区分清晰（红/蓝）
- [ ] 无浏览器 console 报错

### 12. 实时 LLM 模式可调用

```bash
python3 scripts/web_server.py --port 8001
```

- [ ] `GET /api/health` 返回 `{"ok": true}`
- [ ] 页面加载后上方 Live LLM 输入框可见
- [ ] 输入命令 + 点击"LLM 解析并播放"能正常返回策略并播放
- [ ] 无 LLM 时返回 503 而非崩溃

---

## 四、卫生检查（公开前必须全过）

### 13. .env 被排除

- [ ] `.env` 不在 `git ls-files` 中
- [ ] `.gitignore` 包含 `.env` / `.env.*` 且保留 `!.env.example`
- [ ] `.env.example` 不含真实 API key

### 14. 无硬编码敏感信息

对全仓库扫描：

```text
- [ ] 无真实 API key / token / password
- [ ] 无个人邮箱 / 手机号 / QQ
- [ ] 无本地绝对路径（/Users/xxx、/home/xxx）
- [ ] 无聊天记录、私人日志
- [ ] 无无关二进制大文件
```

### 15. 无遗留调试痕迹

- [ ] 代码中无 `TODO`、`FIXME`、`HACK`、`XXX` 等标记（有意保留的除外）
- [ ] 无 `print(debug)` / `console.log(debug)` 临时输出
- [ ] 无注释掉的旧代码块

### 16. 文件命名一致

- [ ] 无 `new_final_v3.py` / `draft.md` / `最终版2.pdf` 之类文件名
- [ ] `docs/` 下文件命名与证据文档交叉引用一致
- [ ] `archive/` 明确标注为旧代码归档

---

## 五、部署验证（陌生人视角模拟）

用干净环境模拟"陌生人克隆后能不能跑"：

```bash
git clone https://github.com/Corrame/real-time-commander-demo.git /tmp/rtcd-test
cd /tmp/rtcd-test
pip install openai
cp .env.example .env
# 填入 API key
python3 scripts/mirror_map_sim.py --runs 10000 --jitter 1 --red-policy good_focus --blue-policy dumb
```

### 17. 零 LLM 裸跑可过

- [ ] 上述流程中 `mirror_map_sim.py` 在干净环境正常输出
- [ ] 不需要额外 pip install 除了 `openai` 之外的包
- [ ] 不需要手动创建目录、修改 sys.path

### 18. LLM 完整链路可跑

- [ ] 填入有效 API key 后 `nl_command_eval.py` 5 场景矩阵全部通过
- [ ] `web_server.py` 可启动并提供完整功能

### 19. README 与代码一致

- [ ] README 中的每条命令都能原样复制粘贴并运行成功
- [ ] README 中的参数名、默认值与代码一致
- [ ] README 中的 policy 名称与代码 `POLICIES` 集合一致

---

## 六、判定规则

### 硬条件（全过才能公开）

```text
[ ] 纯规则模拟的 5 个 policy 组合胜率方向成立（第 3-4 项）
[ ] .env 不在版本控制中（第 13 项）
[ ] 无硬编码敏感信息（第 14 项）
[ ] 干净环境裸跑能通过（第 17 项）
[ ] README 与代码一致（第 19 项）
```

### 建议条件（尽量过）

```text
[ ] LLM 路由内置矩阵 5/5 通过（第 7 项）
[ ] 抗钓鱼 6/6 无明显误路由（第 10 项）
[ ] Web demo 静态模式正常工作（第 11 项）
[ ] 淘汰旧文件名（第 16 项）
```

### 过度打磨线（不是公开前置）

- 录屏 / GIF
- UI 美化
- 新 policy 扩充
- 更复杂的战斗规则
- 统计显著性检验
- 单元测试框架

---

## 公开仓库策略

当前仓库为私有开发仓库。公开时有两种方案：

**方案 A：直接公开**
```bash
gh repo edit --visibility public
```
风险：git history 中可能有不需要暴露的草稿、个人记录、敏感信息残留。

**方案 B：fork 净化公开（推荐）**
1. 清理当前仓库的 git history（如有需要）
2. 在 GitHub 上创建新公开 repo
3. 从当前工作区直接推送到公开 repo（不携带历史）
```bash
git remote add public https://github.com/Corrame/real-time-commander-demo-public.git
git push public master
```
优点：干净起点，只有最终状态，无历史包袱。

---

做到这里，代码就是"写完"了——不是完美，而是**可验证、可复现、可被陌生人跑通**。
