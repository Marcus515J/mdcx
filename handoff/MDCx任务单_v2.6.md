# MDCx 任务单 v2.6（2026-10-19）：合并 v2.4；javlibrary 遇 429 改为退避重试 + 最小请求间隔；查 missav 的 400

> 背景只认 `handoff/MDCx交接文档_v2.6.md` 加本单第 0 节。执行方可能是 Antigravity 或 Codex，按本单照做即可。
> 来源标注：【已查证】= 文件路径 + 行号或命令输出；【已实测】= 谁、在哪台机器、跑了什么；【推测】= 未验证。
> 本单分三段：**A 合并**（用户已批准）→ **B 先查后改**（只改 429 处理和 javlibrary 请求间隔两处）→ **C 只查**（missav 400）。

---

## 0. 问题与证据（全部【已实测】，用户 10-19 Windows，测试包 `MDCx-v1.1.1-TEST-09911e2`，配置 javlibrary `custom_url` 为空 = 官网，3 部片 SSNI-126 / PDVIJ-001 / PRED-110，并发 3，线程延时 5 秒）

- v2.4 修复生效：SSNI-126 选中普通版 `https://www.javlibrary.com/ja/javli4yg4i.html`，未选蓝光 `javli4yg4m`（MDCx 日志 15:38:04、15:38:08）。
- 官网列表链接现为 `./javli4yg4i.html` 格式（用户浏览器拿到的官网搜索页 HTML），不再是 `/?v=jav`。
- **429 来自 javlibrary 站点本身**：NAS bypass 容器日志 07:38:09–10（UTC，= 本地 15:38）`Using cached cookies` 后 `Request to www.javlibrary.com completed with status 429 in 764ms`，`Response size: 7560 bytes`。07:28:15、07:29:43 两次同样（均在数秒内连发 6–8 个 javlibrary 请求之后）。
- 随后 MDCx 日志：`↩️ mirror 失败，回退 /html: mirror HTTP 429` → `/html` 约 27 秒后 `HTTP 500`（容器：`Cloudflare challenge detected` → `Failed to solve Cloudflare challenge`）→ `🚫 [断路器] javlibrary 本次运行停用：允许的请求尝试已耗尽，未取得页面`。结果 SSNI-126、PRED-110 本轮 javlibrary 全空。
- missav：MDCx 日志 15:38:02 `missav.ws ⚠️ mirror 返回终态 HTTP 400，跳过 /html 回退` → 断路器停用 missav。**同一时段容器日志里没有任何 missav 请求记录**（容器日志里 07:38 段只有 javlibrary）。15:29 那轮 missav mirror 成功过。
- 容器日志每个请求后都有 `WARNING: Unsupported upgrade request.` / `No supported WebSocket library detected`。是否与 MDCx 发出的请求头有关未知。
- 已知代码位置（交接文档 v2.4 / 汇报 v2.3）：mirror 终态码跳过 /html `mdcx/web_async.py:1239`、停止重试 `:1454`、终态判定 `:842`；断路器 `mdcx/crawlers/base/base.py:120/132`。行号以当前 master 为准重新核对。

## A. 合并 v2.4（先做）

1. 用户已批准把 `fix/javlibrary-mirror-list-match`（`09911e2`）合并进 `master`。用 PR 合并，PR 标题 `fix(javlibrary): 列表页匹配兼容 jav*.html 链接`，正文写明「用户 10-19 实测通过：官网 SSNI-126 选中普通版」。
2. 不发正式版、不打 tag。汇报写出合并后的 master 提交号。

## B. 先查后改：javlibrary 的 429

### B1 只查，回答后再动手（汇报里写清）

| # | 问题 |
|---|---|
| Q1 | MDCx 现在拿到 mirror 返回的 429 时走哪条路径？为什么会回退 /html？429 是否计入断路器的「尝试次数」？贴代码位置 + 行号 |
| Q2 | 直连请求（不经 bypass）拿到 429 时又是怎么处理的？是否有现成的 `Retry-After` 解析或退避逻辑可复用？ |
| Q3 | 现有的「bypass 冷却中 x.xs」是怎么算的（按站点还是全局、固定还是随机）？有没有按站点设置最小请求间隔或站点并发上限的现成配置项？列出配置项名、默认值、行号 |
| Q4 | 一部片在 javlibrary 实际发几次请求（搜索页、ja 详情、cn/zh_cn 详情…）？列出来源行号 |

### B2 改（只改这两处，复用优先，不加需求外的配置项）

1. **429 处理**：bypass（mirror 或直连）拿到 429 时：
   - 不回退 /html（/html 对 429 无效，日志已证）；
   - 按 `Retry-After`（有就用，上限 30 秒）或指数退避（例如 5s、10s，最多 2 次）后重试同一 URL；
   - 429 及其重试**不计入**断路器的失败次数；退避重试用尽后才按一次失败计；
   - 等待时间仍受现有 `site_total_timeout`（120 秒）约束，不得绕过。
   - 日志新增文案，写进汇报：例如 `⏳ [限流] javlibrary 返回 429，等待 Ns 后重试 (k/2)`。
2. **javlibrary 最小请求间隔**：若 Q3 查到已有按站点的间隔/并发配置，**只调 javlibrary 的默认值**（建议起点：同站相邻请求间隔 ≥ 3 秒，或同站并发 1，二选一，汇报说明为什么选它）；若没有现成机制，在现有「bypass 冷却」逻辑上加一个按站点的最小间隔，javlibrary 默认 3 秒，其他站行为不变。不新增 GUI 配置项。

### B3 离线测试

| # | 场景 | 期望 |
|---|---|---|
| T1 | mirror 首次 429（带 `Retry-After: 2`），重试 200 | 返回 200 页面；未调用 /html；断路器计数不变 |
| T2 | mirror 连续 429 超过重试上限 | 不调用 /html；按一次失败计入断路器；日志含限流文案 |
| T3 | 429 不带 `Retry-After` | 用退避时间；总等待不超过 `site_total_timeout` |
| T4 | 原有行为回归：mirror 终态 400 | 仍跳过 /html、停止重试（与 master 一致） |
| T5 | 原有行为回归：mirror 一般失败（如 5xx）| 仍按原逻辑回退 /html |
| T6 | 同站最小间隔 | javlibrary 相邻两次请求的发出时间差 ≥ 设定值；另一个站不受影响（用 mock 时钟） |

全量测试修改前后各跑一次，失败数不得增加。打 Windows 测试包，命名 `MDCx-v<版本>-TEST-<短哈希>`，不合并 master。分支从合并 v2.4 后的 master 切出，名 `fix/javlibrary-429-backoff`。

## C. 只查：missav 的 400

| # | 问题 |
|---|---|
| Q5 | MDCx 日志里「mirror 返回终态 HTTP 400」的 400 是从哪里来的：容器返回的、MDCx 本地校验产生的、还是别的组件？给出能产生这条文案的全部路径（行号）|
| Q6 | MDCx 发给容器的 mirror 请求带了哪些请求头？有没有 `Upgrade` / `Connection: Upgrade` 之类会让 uvicorn 打 `Unsupported upgrade request` 的头？这与 400 有没有关系？ |
| Q7 | 给出用户可在 Windows PowerShell 复现 MDCx 那次 missav 请求的 `curl.exe` 命令（地址、请求头按代码原样），供下一轮手测 |

**C 段不改代码**，结论写进汇报，修不修下一轮再定。

## 3. 不要做的事

- 不改 `score` 站点优先级、不碰评分刻度换算（另有挂起事项）。
- 不改 javlibrary `custom_url` 等用户配置，不替用户刮削。
- 不改 cloudflare-bypass 容器或其源码（已否决）。
- 不顺手修无关问题；列在汇报末尾「另见」。

## 4. 汇报

- 文件 `handoff/reports/MDCx_执行汇报_v2.6.md`，推到 `handoff` 分支。
- 结构：头部（执行方、日期、合并后 master 提交、新分支名与最终提交）→ A 合并结果 → B1 Q1–Q4 → B2 改动说明（贴改动函数全文）→ B3 测试表 → 全量测试前后对比 → 测试包位置 → C Q5–Q7 → 另见。
- 每条结论标【已查证】/【已实测】/【推测】，代码位置写仓库相对路径 + 行号。

## 5. 机械核对清单

| # | 核对项 | 通过标准 |
|---|---|---|
| 1 | 合并 | master 含 `09911e2` 的改动，汇报写出合并提交号与 PR 链接；无新 tag |
| 2 | 新分支基线 | `fix/javlibrary-429-backoff` 从合并后的 master 切出 |
| 3 | 改动范围 | `git diff --stat master...HEAD` 只涉及 429 处理、站点间隔相关文件和新测试，贴输出 |
| 4 | Q1–Q4 | 每问有行号和代码片段 |
| 5 | 429 不回退 /html | T1、T2 通过 |
| 6 | 断路器 | T1 计数不变；T2 只计一次 |
| 7 | 超时约束 | T3 通过；总等待不超过 `site_total_timeout` |
| 8 | 回归 | T4、T5 通过 |
| 9 | 间隔 | T6 通过；汇报说明选间隔还是并发 1 及理由 |
| 10 | 全量测试 | 前后汇总都贴出，失败数未增加 |
| 11 | 测试包 | 命名与下载位置；未合并 master |
| 12 | missav | Q5–Q7 有作答，Q7 给出可直接粘贴的命令；C 段无代码改动 |
| 13 | 无密钥 | 代码、测试、汇报无 Key、Cookie、代理账号 |

## 6. 执行方启动提示词

```
仓库 Marcus515J/mdcx。切到 handoff 分支，阅读 handoff/README.md、handoff/MDCx交接文档_v2.6.md 和 handoff/MDCx任务单_v2.6.md，按任务单执行：A 用 PR 把 fix/javlibrary-mirror-list-match 合并进 master（用户已批准，不打 tag）；B 先回答 Q1–Q4，再从合并后的 master 切 fix/javlibrary-429-backoff 修 429 退避与 javlibrary 最小请求间隔，写离线测试 T1–T6，打 Windows 测试包，不合并；C 只查 missav 的 400，不改代码。汇报写到 handoff/reports/MDCx_执行汇报_v2.6.md 并推到 handoff 分支。这是新开任务。
```
