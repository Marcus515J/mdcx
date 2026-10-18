# MDCx 任务单 v2.0（2026-10-18）：查清 DeepSeek 思考模式的请求与读取

> 背景只认 `handoff/MDCx交接文档_v1.9.md` 第 5 节第 1 条。执行方可能是 Antigravity 或 Codex，按本单照做即可。
> **本单只查不改**：不改仓库任何代码、配置、文档；不新建分支；不发版。唯一产出是汇报文件。
> 来源标注：【已查证】= 附文件路径 + 行号或命令输出；【已实测】= 写明谁、在哪台机器、跑了什么；【推测】= 未验证。

---

## 0. 为什么查

DeepSeek 官方文档（https://api-docs.deepseek.com/guides/thinking_mode/）说：`deepseek-flash` 默认开启思考；思考模式下 `temperature` 等采样参数不生效；用 `{"thinking": {"type": "disabled"}}` 关闭（OpenAI SDK 放 `extra_body`）；思考过程在 `reasoning_content`，答案在 `content`。

我们要知道 MDCx 现在实际发出去的是什么、读回来的是什么，才能决定要不要加「关闭思考」开关。

## 1. 准备

1. 基于 `master` 最新提交工作（应为 `5eb64ef` 或之后）。汇报里写出实际的 `git rev-parse HEAD`。
2. 不需要 API Key，不需要联网调用 DeepSeek。**禁止**把任何 Key 写进汇报或提交。

## 2. 要回答的问题（逐条回答，每条带证据）

**Q1 调用入口**：大模型翻译请求是在哪个文件、哪个函数里发出的？用的是 OpenAI SDK（`openai` 包）、`httpx`/`requests` 直发，还是别的？列出路径和行号。

**Q2 请求体有没有 `thinking`**：
- 在整个 `mdcx/` 目录执行下列搜索，把**完整输出原样贴进汇报**（无结果也要写「无输出」）：
  ```
  git grep -n -i "thinking" -- mdcx/
  git grep -n "extra_body" -- mdcx/
  git grep -n "reasoning" -- mdcx/
  ```
- 结论写成三选一：A 完全没有发送 `thinking`；B 发送了，值是什么、在什么条件下；C 无法确定（说明原因）。

**Q3 请求体实际带了哪些字段**：列出发给厂商的全部参数（`model`、`messages`、`temperature`、`max_tokens`、`stream` 等），注明每个值来自哪个配置项。特别说明：是否所有厂商（DeepSeek、GLM、本机模型）都用同一段代码、同一组参数。

**Q4 读结果读的是哪个字段**：
- 解析响应的代码路径和行号。
- 是只读 `choices[0].message.content`，还是也读 `reasoning_content`？如果是流式（`stream=True`），是只拼 `delta.content` 吗？
- 有没有对 `<think>...</think>` 之类的标签做过滤？（GLM、本机模型可能把思考写进 content。）有就贴出代码位置，没有就写「无」。

**Q5 超时与重试**：60 秒超时和「尝试次数 2」分别在代码哪里生效？超时是整次请求的总时长，还是连接/读取超时？

**Q6 机械验证（本地离线，强烈建议做）**：在仓库**之外**的临时目录写一个脚本，mock 掉网络层（例如 monkeypatch OpenAI 客户端的 `create` 方法或用 `httpx.MockTransport`），让 MDCx 的翻译函数按 DeepSeek 配置走一遍，捕获实际发出的请求体，并喂回一个同时含 `reasoning_content: "思考XXX"` 和 `content: "译文YYY"` 的假响应。贴出：
- 捕获到的请求体 JSON（Key 打码）；
- 翻译函数的返回值——应只含「译文YYY」，若混入「思考XXX」即为问题。
- 脚本本身贴进汇报附录，不提交进仓库。
做不了（例如函数耦合太深）就说明卡在哪，不要硬改代码去迁就。

## 3. 不要做的事

- 不加开关、不改参数、不改超时，哪怕改动只有一行。是否加开关等用户决定后另出任务单。
- 不顺手修无关问题；发现了列在汇报末尾「另见」里。
- 不重新讨论交接文档第 6 节「已否决」里的内容。

## 4. 汇报

- 文件：`handoff/reports/MDCx_执行汇报_v2.0.md`，推到 `handoff` 分支。
- 结构：头部写 HEAD 提交号、执行方名称、日期；然后 Q1–Q6 逐条；最后「另见」。
- 每条结论标【已查证】/【已实测】/【推测】。

## 5. 机械核对清单（Claude 审核时逐项对照）

| # | 核对项 | 通过标准 |
|---|---|---|
| 1 | HEAD 提交号 | 是 master 上 `5eb64ef` 或之后的提交 |
| 2 | 三条 git grep 原样输出 | 三条都在，含「无输出」的也写明 |
| 3 | Q2 结论 | 明确为 A / B / C 之一 |
| 4 | Q1、Q3、Q4、Q5 | 每条都有路径 + 行号 |
| 5 | Q6 | 有捕获的请求体和返回值；或写明为什么做不了 |
| 6 | 仓库无改动 | `git status` 在 master 上干净，贴输出；handoff 分支只新增汇报文件 |
| 7 | 无密钥 | 汇报中无任何 Key |

## 6. 执行方启动提示词

```
仓库 Marcus515J/mdcx。切到 handoff 分支，阅读 handoff/README.md 和 handoff/MDCx任务单_v2.0.md，按任务单执行。本单只查不改：代码在 master 上读，不改任何代码；唯一产出是 handoff/reports/MDCx_执行汇报_v2.0.md，推到 handoff 分支。这是新开任务。
```
