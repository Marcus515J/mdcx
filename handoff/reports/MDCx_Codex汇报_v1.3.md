# MDCx Codex 汇报 v1.3 — 需求 C

日期：2026-10-17（Asia/Shanghai）。任务单：handoff/MDCx任务单_v1.3.md；交接规则：handoff/README.md。仅实现 C-1～C-4。以下“已查证”指当前源码，“已实测”指本次 Mac 上真实执行；没有连接真实 NAS。

## 1. 交付与仓库状态

- 基线：master `6da10c5464efcd39252ce12ce88ec9957d89d4e6`（v1.1.0）。
- 功能分支：`codex/cf-bypass-run-budget`，已推送。
- C-2 独立提交：`f3077fb` — 进程级 `/html` FIFO 限流、90 秒超时、固定一次尝试。
- C-3/C-4 独立提交：`989b825e3e68b240231f15b9a2240ceb8d4eee1e` — 运行级断路器、单站单番号总预算、测试夹具和实测脚本。
- 草稿 PR：[Marcus515J/mdcx#9](https://github.com/Marcus515J/mdcx/pull/9)。保持草稿，等待验收，未合并 master。
- 本报告独立提交至 handoff，仅新增本报告文件；没有修改任务单、交接文档或该分支其他文件。报告提交号可由 handoff 分支中该文件的最近一次提交获取，避免在文件内填写自身尚未生成的提交号。
- Windows EXE：未构建。本机是 macOS arm64，没有 Windows 构建环境；没有触发会发布正式版本的 release 工作流。

## 2. §3 四项核实结果

### 2.1 是否存在同域名排队；新限流的最坏等待

【已查证】`AsyncWebClient._try_bypass_cloudflare()` 使用 `_cf_host_locks[host]`，持锁范围覆盖 mirror、强制刷新 mirror、`/html` 和退避。同一客户端内，检测和刮削使用同域名时会排在该锁后。GUI 的检测与刮削提交到同一个后台 executor；配置重载会保留旧客户端，原有域名锁只属于各自客户端。

旧 `/html` 通过普通 `request()` 发出，没有显式 `retry_count`，会继承设置中的 5 次总尝试；另有 2 次 bypass 内部尝试、2 轮外层 bypass。因此存在远超单次 45 秒的等待路径。这里只确认排队机制；没有本次读取原始 10-11 全量日志，不能断言 18:59:30～19:05:30 的全部时间都由同域名排队造成。

【已查证】新 `/html` FIFO 队列在模块级共享，以 `threading.Lock` 保护队列，可跨客户端/配置重载和事件循环共享一个名额；排队不占 HTTP 超时，取消排队会移除票据。

【估算，限定六个检测各触发一次 `/html`】若每次耗尽 90 秒，最后一个检测纯排队约 5×90=450 秒，六次 `/html` 总计约 540 秒。刮削若恰好排在全部六个检测后，纯名额等待可接近 540 秒。还需加普通请求、mirror、重定向、冷却和调度时间，这不是任意负载下的进程总耗时保证。C-4 会把刮削本站本番号的实际等待截在 120 秒，超限按失败打开断路器；检测不受刮削总预算限制。

【已实测】六个检测各冷启动 60 秒，总耗时与刮削排队实测见 §5；排在首站检测后的刮削等约 60 秒后走 mirror 成功，排在后部站点检测后的刮削在约 120 秒退出，后续番号零新增请求。

### 2.2 mirror 约 5 秒的来源

【已查证】`core/network_check.py:_diagnostic_timeout()` 返回 `max(min(config.timeout or 5, 5.0), 2.0)`。设置为 10 时，检测传入普通请求的仍是 5 秒；正常 CF 挑战分支把这个 `timeout` 继续传给 mirror。因此检测日志的 mirror 约 5 秒可由客户端直接解释。

另一条文本挑战回退 `_try_bypass_for_check()` 显式传 `timeout=None`。刮削请求没有单独覆盖超时时也走 `None`；这些 mirror 在基线的客户端回退值为 45 秒。此次保留 45 秒，只把 `/html` 默认改为 90 秒。没有改 `_diagnostic_timeout()` 或普通“单次超时”。如果所指 5 秒来自刮削而非检测，单凭本仓库源码不能确认服务端是否另设 5 秒超时；未连接 NAS，不把服务端推测写成事实。

### 2.3 “重试次数=5”改后作用范围

【已查证】普通 `request()` 仍使用 `retry_count` 显式覆盖值或 `client.retry`；设置 5 表示最多 5 次总尝试，原有 HTTP 状态判断、连接错误重试和退避保持原样。`get_text/get_content/get_json/post_text/post_json` 等最终走同一入口，已有显式覆盖继续有效。检测仍显式 `retry_count=1`。mirror 的内部尝试上限保留原来的 2，独立于用户的 5；GET 一旦回退 `/html` 后失败就终止该 bypass，不进入第二轮强刷。

【已查证、已实测】`/html` 显式 `retry_count=1`，另以 `asyncio.timeout(cf_bypass_timeout)` 约束真实等待，外层 CF fallback 轮数改为 1。设置 retry=5 时，延迟 100 秒的假服务器只收到 1 次 `/html`，客户端约 90 秒失败，没有第二轮。真实 Jav321Crawler 对本地超时 POST 保留 5 次普通尝试，日志出现 `(5/5)`；同轮后两个番号零请求。

### 2.4 可复用的计数、限流与跳过机制

【已查证】复用现有 `_cf_host_locks`、2 秒同域名冷却、`AsyncWebLimiters`、连接池、mirror 和状态码判断。现有 `FileScraper._call_crawlers()` 的 `failed` 集合仅覆盖单文件/语言，不能充当整轮跨番号断路器。

复用 `CrawlerProvider` 的运行生命周期：`start_new_scrape()` 每次创建新 provider，每站仅一个爬虫实例；provider.close() 清空实例。断路器放在这个实例上，新运行自然重置，不污染网络客户端，也不影响检测。`ContextVar` 仅在 crawler.run() 范围记录请求最终失败；每次退出都恢复上下文。已有并发任务在真正发出下一次 HTTP 前再次检查本站断路状态，避免断路后继续重试。

## 3. 实现边界与配置

| 配置项 | 默认值 | 范围与生效方式 |
|---|---:|---|
| `cf_bypass_timeout` | 90 秒 | 正整数；`/html` 取得全局名额后的等待上限，固定一次尝试 |
| `site_total_timeout` | 120 秒 | 正整数；单站、单番号的累计活动时间，包含域名/FIFO/连接池排队、HTTP、重试、退避与爬虫处理 |

仅新增以上两项，无依赖变更。模型、内置 JSON 模板和运行客户端已贯通，旧配置缺项使用默认值。可在关闭软件后编辑当前 JSON 配置，重启后生效；未新增 UI 控件或额外开关。

同番号的多语言/字段调用共用预算，并发调用共享截止时间；处理其他站点而本站没有活动调用的间隔不消耗预算。某站最终未取得页面或总预算超限，整轮停用；404（含 mirror 终态 404）与 HTTP 200 正常搜索无结果不触发断路。拿到页面但解析失败本身不打开断路器。检测失败没有爬虫运行上下文，刮削仍有一次完整机会。

没有改任何 NFO、需求 A/B、NAS 或 CF Bypass 容器。原有 mirror 挑战页先强刷的行为保留；禁止的是 `/html` 失败后的重开和外层第二轮。

## 4. 改动文件

| 文件 | 用途 |
|---|---|
| `mdcx/web_async.py` | `/html` 进程 FIFO、单次超时/尝试；抓取结果记录和发请求前断路检查 |
| `mdcx/crawlers/base/base.py` | 每轮站点断路、每番号共享预算和跳过日志 |
| `mdcx/config/models.py` | 两个正整数配置字段 |
| `mdcx/config/computed.py` | 配置传入实际客户端 |
| `resources/config/default_config.json` | 90/120 默认值 |
| `tests/test_web_async_cf_bypass.py` | 更新单轮语义，补跨客户端串行、取消排队与不重开测试 |
| `tests/cf_fake_server.py` | 标准库回环 HTTP 假服务器，保留实际 curl 传输 |
| `tests/test_crawl_circuit.py` | 断路/重置/404/预算/检测隔离/缓存/Jav321 实测 |
| `scripts/verify_cf_bypass.py` | 不压缩时间的 60/90/100/120 秒验收 |

代码差异仅以上九个文件。handoff 分支仅新增 `handoff/reports/MDCx_Codex汇报_v1.3.md`。

## 5. 实际运行结果

环境：macOS 27.0.1 arm64，CPython 3.13.14，仓库 uv.lock 锁定依赖。通过 `uv sync --frozen --offline --python 3.13` 从本机缓存建立环境，没有增改 pyproject.toml 或 uv.lock。假服务器只绑定 127.0.0.1，curl 的静态 RESOLVE 与空 PROXY 强制 `*.test` 走回环，未访问 NAS/真实刮削站点。

复现命令（在功能分支仓库根目录）：

```sh
uv sync --frozen --offline --python 3.13
.venv/bin/pytest -q tests/test_crawl_circuit.py --tb=short
.venv/bin/python -u -m scripts.verify_cf_bypass
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q --tb=short
.venv/bin/ruff check
.venv/bin/ruff format --check
git diff --check
```

首次获取依赖的其他机器可去掉 `--offline`。沙箱禁止监听端口时，需要在允许本地回环监听的终端运行以上实测命令；本次已实际获得该执行权限并完成，不以静态检查代替。

| §5 项目 | 结果与证据 |
|---|---|
| 1. 六站 `/html` 并发 | 6 站均实际走 TCP/HTTP；服务器记录峰值 `1`，12 条开始/结束事件无重叠，见下表 |
| 2. 60/100 秒超时 | 六次 60 秒均成功；100 秒延迟在 `90.007` 秒失败，retry=5 时 `/html` 总数仍为 1，无第二轮 |
| 3. 冷缓存 | 首次 `/html` 成功后，同站 FIRST 和 WARM 请求均走 mirror，未再调用 `/html`；另有专项测试覆盖 |
| 4. 断路/重置/检测隔离 | 专项集实际验证跨番号零请求、每站一条跳过日志、新 provider 重置、检测失败后刮削完整机会；真实 Jav321 首部 5 次，后两部总次数仍为 5 |
| 5. 120 秒总上限 | 130 秒直接 HTTP 在 `120.003` 秒截断；同域名排队在 `120.002` 秒截断；两者均进入断路器，后续番号零请求 |
| 6. 无此番号 | 本地直接 404、mirror 404、200 搜索无结果均不打开断路器 |
| 7. 快速路径回归 | 与 v1.1.0 实发对照：非 CF 一次成功、mirror 一次成功，2 通过、0 失败，状态及请求序列相同 |
| 8. 检测总耗时/刮削排队 | 六站各 60 秒冷启动总计 `360.164` 秒；首站刮削等待 `59.806` 秒成功；后部站点 `120.002` 秒按总上限退出 |
| 9. 全量回归 | **769 通过、0 失败、14 跳过**，本地 115.66 秒；专项断路器集 **13 通过、0 失败** |

跨客户端单元测试已覆盖取消队列票据；另外实际运行 6 线程/6 事件循环/6 客户端的门控探针，峰值=1，1 通过、0 失败。这个辅助探针只替代传输以隔离线程共享门控；以上六站验收没有替代 HTTP 传输。

GitHub CI 同一提交 `989b825`：[运行 39012765687](https://github.com/Marcus515J/mdcx/actions/runs/39012765687)，Code Quality 与 Tests 均 success；Linux 测试日志 **769 passed, 14 skipped, 2 warnings in 120.93s**。本地 ruff check、ruff format --check 和 git diff --check 均通过。

各站服务器时间戳（从该轮假服务器启动计，秒）：

| 站点 | /html 开始 | /html 结束 | 结束后的在途数 |
|---|---:|---:|---:|
| cold0.test | 0.006 | 60.008 | 0 |
| cold1.test | 60.038 | 120.040 | 0 |
| cold2.test | 120.063 | 180.063 | 0 |
| cold3.test | 180.117 | 240.118 | 0 |
| cold5.test | 240.126 | 300.127 | 0 |
| cold4.test | 300.163 | 360.164 | 0 |


### 关键日志

```text
15:11:57 🚫 [断路器] jav321 本次运行停用：单站单番号总等待超限 (120s)，番号=LAST
15:11:57 🚫 [断路器] jav321 本次运行停用：单站单番号总等待超限 (120s)，番号=CAP
15:11:57 ⏭ [断路器] jav321 本次运行跳过后续番号：单站单番号总等待超限 (120s)，番号=CAP
15:11:57 ⏭ [断路器] jav321 本次运行跳过后续番号：单站单番号总等待超限 (120s)，番号=LAST
15:15:57 网络检测已完成：正常 6，警告 0，失败 0，跳过 0，用时 360.16 秒
15:17:27 🛡️ [CF] cold0.test ⚠️ bypass 失败: mirror: mirror HTTP 503; html: /html 等待超时 (90s)
15:17:37 PASS 100s delay fails at 90.007s, /html count=1; no second round; scrape remains eligible
```

真实 Jav321Crawler 对本地延迟服务器的日志：

```text
🔴 POST http://plain.test:60677/search 失败: 连接超时 (1/5)
🔴 POST http://plain.test:60677/search 失败: 连接超时 (2/5)
🔴 POST http://plain.test:60677/search 失败: 连接超时 (3/5)
🔴 POST http://plain.test:60677/search 失败: 连接超时 (4/5)
🔴 POST http://plain.test:60677/search 失败: 连接超时 (5/5)
🚫 [断路器] jav321 本次运行停用：允许的请求尝试已耗尽，未取得页面
AFTER SSNI-126: total_requests=5
⏭ [断路器] jav321 本次运行跳过后续番号：允许的请求尝试已耗尽，未取得页面
AFTER PDVIJ-001: total_requests=5
AFTER PRED-110: total_requests=5
```

### 回归过程中的失败与处理

首次全量回归为 744 通过、23 失败、14 跳过。23 个失败都是新增超时属性与已有轻量假客户端不兼容，已在本次范围内修正为兼容默认值，没有修改站点解析逻辑或削弱测试。随后爬虫集 126 通过、0 失败、4 跳过；完整回归 768 通过、0 失败、14 跳过；再补真实 Jav321 超时用例后，最终完整统计见上表。首次真延迟脚本的自定义分组未被检测调度器识别，修正测试夹具后重新执行；最终证据来自最终实现重新启动的完整实测。

两条成功路径还加载了 `6da10c5:mdcx/web_async.py` 与当前客户端，对同一个本地服务器实际发送请求：两者都是非 CF 直接请求 1 次成功；CF 挑战后 mirror 1 次成功、`/html` 0 次；状态/错误字符串/请求序列相同，2 通过、0 失败。

## 6. 未覆盖与未改的无关事项

- 没有用户 Windows、真实 NAS、真实冷缓存或真实三部媒体的端到端测试；§6 用户实测仍待验收。未构建 Windows EXE，当前交付为代码分支、草稿 PR、可复现实测脚本及本报告。
- 14 个回归跳过保留原有条件：4 个缺少 HTML 样本，10 个限 Windows 平台（9 个路径用例、1 个 UI 路径用例）；没有为获得通过而关闭测试。
- `/html` 的“在途 ≤1”是 MDCx 客户端 HTTP 请求级保证。客户端超时/取消不能杀掉 NAS 已启动的浏览器。本次假服务特意在断开后继续处理，100 秒场景中客户端 90 秒放弃后服务器还继续约 10 秒；没有声称服务器浏览器数也被限制为 1。
- 检测可以排队数分钟；刮削可能在等检测时耗尽 120 秒并按决定打开断路器，即使检测稍后成功预热也不会自动恢复该轮站点，下一轮才重置。
- 全量回归有 zhconv/pkg_resources 弃用警告及已有 AsyncLimiter 跨事件循环复用警告；只列出，没有扩大本次改动修复。
- mirror 400、DMM 403/404、MTES 重复刮削、Windows 软链接权限和翻译遗留项保持交接文档原状；没有把任务单里的历史记录冒充本次现场复现。

验收时从功能分支出 Windows 测试构建后，按任务单 §6 对 SSNI-126、PDVIJ-001、PRED-110 记录检测耗时、每文件耗时及 NAS 状态；不要合并 handoff 或功能分支进 master，待用户验收。
