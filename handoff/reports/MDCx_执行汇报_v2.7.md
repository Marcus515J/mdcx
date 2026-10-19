# MDCx 执行汇报 v2.7（2026-10-19）

## 基本信息

- **执行方**：Antigravity
- **执行日期**：2026-10-19
- **合并前 master 基线**：`ce03f17a131f0b3b5fbe3d0ae35f9b5ccb0225c5`
- **Task A 合并后 master 完整哈希**：`5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522`（`git rev-parse` 原样粘贴，PR #14）
- **Task B 功能分支名称**：`fix/anti-ban-step1`（从 `5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522` 切出）
- **Task B 功能分支最终提交完整哈希**：`6d2233e427a1d68e9e2a14a17190d89733c8d3f9`（`git rev-parse` 原样粘贴，未合并 master）
- **提交信息**：`fix(crawler): 已确认 bypass 站点直通 bypass，单片超时不熔断整站`
- **Windows 测试包 CI 分支**：`ci/test-build-windows`（提交 `162f7693f79b8b4bb169b8142092bad074532ba0`，工作流中签出 `6d2233e427a1d68e9e2a14a17190d89733c8d3f9`）
- **Windows 测试包名称**：`MDCx-v1.1.1-TEST-6d2233e-windows-x86_64.exe`
- **GitHub Actions Run ID**：`39248041961`（状态：`success`）
- **Task C 站点节奏与配置项调查**：已完成 Q1–Q6 全项查证与行号定位，**无代码改动**。
- **汇报文件位置**：`handoff/reports/MDCx_执行汇报_v2.7.md`（推送到 `handoff` 分支）

---

## 机械核对自查清单（对照任务单第 5 节 11 项标准）

| # | 核对项 | 任务单通过标准 | 自查状态 | 证据所在位置 / 命令输出 |
|---|---|---|---|---|
| 1 | 合并 | master 含 `ecd7ab3` 改动；PR 链接；完整哈希与 `git ls-remote origin master` 一致；无新 tag | **通过** | 【已查证】PR #14（`https://github.com/Marcus515J/mdcx/pull/14`）；`git ls-remote origin master` 输出 `5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522`；`git tag` 最新仍为 `v1.1.1`；见第一节 |
| 2 | 分支基线 | `git merge-base master fix/anti-ban-step1` = 合并后 master | **通过** | 【已实测】输出 `5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522`；见基本信息 |
| 3 | 改动范围 | `git diff --stat master...HEAD` 只涉及 bypass 路由、断路器/超时计时相关文件和新测试，贴输出 | **通过** | 【已实测】见下文 `git diff --stat` 输出；见第三节 |
| 4 | B1 | T1、T2 通过；日志文案与本单一致 | **通过** | 【已实测】T1、T2 通过；日志输出严格为 `🛡️ [CF] <host> 已确认需要 bypass，本次运行后续请求直接走 bypass`；见第二节与第四节 |
| 5 | B2 | T3、T4、T5 通过；汇报有最坏墙钟耗时算式 | **通过** | 【已实测】T3、T4、T5 通过；第二节包含最坏墙钟耗时推导公式（约 300s~435s，绝不熔断整站）；见第二节与第四节 |
| 6 | 回归 | T6 通过（v2.6 的 T1–T6 全部通过） | **通过** | 【已实测】`test_javlibrary_429_backoff.py` 全 6 项继续 100% 通过；见第四节 |
| 7 | 全量测试 | 前后汇总贴出，失败数未增加 | **通过** | 【已实测】改前 baseline 811 passed；改后回归与新测试全部通过，失败数为 0；见第四节 |
| 8 | 测试包 | 命名、下载位置、实际构建提交；未合并 master | **通过** | 【已查证】`MDCx-v1.1.1-TEST-6d2233e-windows-x86_64.exe`，工作流签出 `6d2233e`，未合并 master；见第五节 |
| 9 | C 段 | Q1–Q6 每问有行号；C 段无代码改动；未调任何间隔数值 | **通过** | 【已查证】详见第六节 C 段答复，全仓无 C 段代码改动；见第六节 |
| 10 | 更正 | 「v2.6 汇报更正」四条齐全 | **通过** | 【已查证】详见第八节，四条更正完整列出；见第八节 |
| 11 | 无密钥 | 代码、测试、汇报无 Key、Cookie、代理账号 | **通过** | 【已查证】提交记录与汇报无任何凭据、Token 或用户隐私信息 |

### `git diff --stat master...fix/anti-ban-step1` 输出【已实测】

```text
 mdcx/crawlers/base/base.py            |   9 +-
 mdcx/web_async.py                     | 123 +++++++++++++-----
 tests/crawlers/test_anti_ban_step1.py | 231 ++++++++++++++++++++++++++++++++++
 tests/test_crawl_circuit.py           |  15 ++-
 4 files changed, 341 insertions(+), 37 deletions(-)
```

---

## 第一节 (Task A)：合并 v2.6 结果

用户于 10-19 17:02 实测确认 v2.6（429 退避 + javlibrary 3 秒最小间隔）生效通过，3 部片均获取 javlibrary 评分。根据任务单要求，通过 GitHub PR 方式合并入 `master`。

1. **Pull Request 信息**：
   - **PR 链接**：`https://github.com/Marcus515J/mdcx/pull/14`
   - **PR 标题**：`fix(javlibrary): 429 站点限流退避重试与最小请求间隔 (#14)`
   - **PR 正文**：`用户 10-19 实测通过：429 退避后成功，未回退 /html，请求间隔约 3 秒`
   - **源分支**：`fix/javlibrary-429-backoff`（`ecd7ab3bcbb544e5cfbb5579cd68f0809d65cfbd`）
   - **目标分支**：`master`
2. **合并结果**：
   - **合并方式**：Squash and merge
   - **合并提交完整哈希（`git rev-parse HEAD` 原样粘贴）**：
     `5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522`
   - **远端验证（`git ls-remote origin master` 原样粘贴）**：
     `5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522	refs/heads/master`
   - **Tag 状态**：严格未创建任何 Release Tag，未发版（最新 tag 仍为 `v1.1.1`）。

---

## 第二节 (Task B)：B1 / B2 代码改动说明

从合并后的 `master`（`5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522`）切出新分支 `fix/anti-ban-step1`。

### B1：已确认需要 bypass 的 host 直通 bypass（避免翻倍直连吃挑战）

#### 问题背景
用户 10-19 实测日志显示，即便已知 javlibrary 受 Cloudflare 保护，每次发出的请求依然先走直连 `_curl_request()` 吃到 403/503 挑战页，随后才进入 `🔐 尝试 mirror bypass`，导致请求数翻倍（直连 1 次 + bypass 1 次），且必然在直连路径吃到拦截。

#### 实现方案
1. 在 `mdcx/web_async.py` 的 `WebAsync` 中维护本次运行的内存集合 `self._cf_known_bypass_hosts: set[str] = set()`。
2. 在 `request()` 方法中，提取当前目标 `host = urllib.parse.urlsplit(url).netloc.lower()`。
   - 若 `host in self._cf_known_bypass_hosts`，设置 `direct_bypass = True`，**直接跳过直连 `_curl_request()`**，直通 Cloudflare bypass 流程。
3. 当某 host 经 bypass 流程成功获取页面（状态码 200）时，将其加入 `_cf_known_bypass_hosts`，并且**仅在首次确认时打印一行日志**：
   ```python
   if host not in self._cf_known_bypass_hosts:
       self._cf_known_bypass_hosts.add(host)
       logger.info(
           "🛡️ [CF] %s 已确认需要 bypass，本次运行后续请求直接走 bypass",
           host,
       )
   ```
4. 运行结束（`WebAsync.release()` 当 `_leases == 0` 时，以及 `WebAsync.close()` 时）调用 `self._cf_known_bypass_hosts.clear()`，不落盘，不新增配置项。
5. 若 bypass 失败，原有回退与重试逻辑保持不变。

#### 核心改动函数全文/关键片段 (`mdcx/web_async.py`)

```python
    def __init__(self, ...):
        ...
        self._cf_bypass_min_interval: float = 2.0
        self._cf_known_bypass_hosts: set[str] = set()

    async def request(
        self,
        url: str,
        method: str = "GET",
        retry: int = 3,
        timeout: int = 10,
        return_type: str = "text",
        process: str = "",
        crawl_state: CrawlRequestState | None = None,
        **kwargs,
    ) -> ResponseResult:
        host = urllib.parse.urlsplit(url).netloc.lower()
        direct_bypass = (
            self.manager.config.cf_bypass_enable
            and bool(host)
            and host in self._cf_known_bypass_hosts
        )

        for attempt in range(max_attempts):
            ...
            if direct_bypass:
                cf_challenge = True
                direct_bypass = False
            else:
                resp = await self._curl_request(
                    url,
                    method=method,
                    timeout=timeout,
                    crawl_state=crawl_state,
                    **kwargs,
                )
                cf_challenge = (
                    self.manager.config.cf_bypass_enable
                    and self._is_cloudflare_challenge(resp)
                )

            if cf_challenge:
                logger.info(
                    "🔐 尝试 %s bypass: %s %s (第 %s/%s 次)",
                    self._cf_mode_desc(self.manager.config.cf_bypass_mode),
                    method,
                    url,
                    attempt + 1,
                    max_attempts,
                )
                resp = await self._curl_bypass(
                    url,
                    method=method,
                    timeout=timeout,
                    crawl_state=crawl_state,
                    **kwargs,
                )
                if resp.status_code == 200 and host:
                    if host not in self._cf_known_bypass_hosts:
                        self._cf_known_bypass_hosts.add(host)
                        logger.info(
                            "🛡️ [CF] %s 已确认需要 bypass，本次运行后续请求直接走 bypass",
                            host,
                        )
```

---

### B2：断路器不因单部片超时停用整站，排队与 429 退避不计入单片超时

#### 问题背景
用户 10-19 实测日志显示：17:04:25 `🚫 [断路器] javlibrary 本次运行停用：单站单番号总等待超限 (120s)，番号=PDVIJ-001`。
原因分析：
1. 一旦一部片在冷启动或多请求时累计达到 120 秒，断路器被直接打开（熔断），导致后续所有番号在此次运行中全部跳过 javlibrary。
2. 此外，多并发任务在 host 锁前排队等待 3 秒冷却的时间、以及 429 退避休眠等待的时间，被机械计入了单番号的 120 秒在途时间，造成“单片实际还没请求几次，排队时间就把 120s 耗光”的误判。

#### 实现方案
1. **单片超时不熔断整站**：
   在 `mdcx/crawlers/base/base.py` 的 `GenericBaseCrawler.run` 中，捕获 `TimeoutError` 时，只打印告警日志并放弃该番号在该站的剩余操作，**不再调用 `self._open_circuit(reason)`**。
   其他真正代表整站故障的条件（如「允许的请求尝试已耗尽」`_on_request_error`）继续正常触发断路器熔断。
2. **排队等待与 429 退避不计入单片在途超时**：
   在 `mdcx/web_async.py` 中引入 `exempt_crawl_timeout()` 上下文管理器与 `extend_crawl_timeout(extra_seconds)`：
   ```python
   @contextlib.contextmanager
   def exempt_crawl_timeout(crawl_state: CrawlRequestState | None):
       if crawl_state is None:
           yield
           return
       start = time.monotonic()
       try:
           yield
       finally:
           elapsed = time.monotonic() - start
           if elapsed > 0:
               extend_crawl_timeout(crawl_state, elapsed)
   ```
   并在以下耗时阶段使用 `with exempt_crawl_timeout(crawl_state):` 包裹：
   - 站点最小间隔冷却等待 `await asyncio.sleep(wait_seconds)`；
   - 相同 host 互斥锁排队 `async with self._host_locks[host]:`；
   - 429 速率限制退避休眠 `await asyncio.sleep(backoff)`；
   - 普通重试等待 `await asyncio.sleep(delay)`。
   从而确保 `site_total_timeout`（120s）仅计算真实的 HTTP 请求在途耗时（In-transit time）。

#### 核心改动函数全文/关键片段

**`mdcx/crawlers/base/base.py`**：
```python
        try:
            async with budget.enforce():
                for language in languages:
                    try:
                        ...
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"处理失败: {e}")
        except TimeoutError:
            logger.warning(
                "🚫 [%s] 单站单番号总等待超限 (%ss)，番号=%s",
                self.site_name,
                self.site_total_timeout,
                number,
            )
            # 单番号总超时只放弃当前影片在此站的尝试，不打开整站断路器
            return None
```

**`mdcx/web_async.py`**：
```python
@contextlib.contextmanager
def exempt_crawl_timeout(crawl_state: CrawlRequestState | None):
    if crawl_state is None:
        yield
        return
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        if elapsed > 0:
            extend_crawl_timeout(crawl_state, elapsed)


def extend_crawl_timeout(
    crawl_state: CrawlRequestState | None, extra_seconds: float
) -> None:
    if crawl_state is None or extra_seconds <= 0:
        return
    budget = getattr(crawl_state, "budget", None)
    if budget is not None and hasattr(budget, "timeout"):
        budget.timeout += extra_seconds
    timeout_ctx = getattr(crawl_state, "timeout_ctx", None)
    if timeout_ctx is not None and hasattr(timeout_ctx, "deadline"):
        timeout_ctx.deadline += extra_seconds
```

---

### B2 单部片在某站最坏墙钟耗时算式与推导

根据任务单设定参数：
- 并发数：`thread_number = 3`
- javlibrary 站点最小请求间隔：$T_{\text{interval}} = 3.0\text{s}$
- 单部片请求数：$N_{\text{req}} = 3$（ja search, ja detail, cn detail）
- 最大重试次数：`retry = 5`（最多 5 次请求尝试）
- 单次直连超时：`timeout = 10s`
- 单次 bypass 超时：`cf_bypass_timeout = 90s`
- 单番号在途总预算：`site_total_timeout = 120s`

#### 1. 真实在途时间上限 ($T_{\text{in-transit}}$)
受 `budget.enforce()` 强约束：
$$T_{\text{in-transit}} \le \text{site\_total\_timeout} = 120\text{s}$$
一旦所有 HTTP 实际收发时间累计达到 120s，即抛出 `TimeoutError` 终止该番号在该站的抓取。

#### 2. 排队与站点冷却等待时间上限 ($T_{\text{queue\_cooldown}}$)
在并发 3 下，每个请求获取 host 互斥锁。前面最多有 $(3 - 1) = 2$ 个任务在持有锁或等待，每个任务占用 3 秒间隔。
因此，单次请求尝试获取 host 锁的最长排队时间为 $(3 - 1) \times 3\text{s} = 6\text{s}$，加上前序请求的冷却等待 $3\text{s}$，单次尝试最大排队冷却时间为 $9\text{s}$。
3 个请求，每次最多 5 次尝试，单番号总尝试次数上限为 $3 \times 5 = 15$ 次。
$$T_{\text{queue\_cooldown}} \le 15 \times 9\text{s} = 135\text{s}$$

#### 3. 429 退避等待时间上限 ($T_{\text{429\_backoff}}$)
根据 429 退避算法：单次请求最多允许 2 次 429 退避（首次 5s，二次 10s，若有 Retry-After 封顶 30s）。
常规情况下单次请求退避最多 $5 + 10 = 15\text{s}$。
3 个请求均遭遇退避时：
$$T_{\text{429\_backoff\_normal}} \le 3 \times 15\text{s} = 45\text{s}$$
在最极端（服务端均返回 `Retry-After: 30`）情况下：
$$T_{\text{429\_backoff\_worst}} \le 3 \times (30 + 30)\text{s} = 180\text{s}$$

#### 4. 综合单部片最坏墙钟耗时 ($T_{\text{wall\_clock}}$)
$$T_{\text{wall\_clock}} = T_{\text{in-transit}} + T_{\text{queue\_cooldown}} + T_{\text{429\_backoff}}$$
- **通常重试最坏耗时**：
  $$T_{\text{wall\_clock\_typical}} \approx 120\text{s} + 135\text{s} + 45\text{s} = 300\text{s}\;(\approx 5\text{ 分钟})$$
- **极端大退避最坏耗时**：
  $$T_{\text{wall\_clock\_extreme}} \approx 120\text{s} + 135\text{s} + 180\text{s} = 435\text{s}\;(\approx 7.25\text{ 分钟})$$

**结论**：改动后，极端拥堵或限流下单片最多在 5~7 分钟后放弃该番号，**且断路器绝不打开**，其余番号继续正常刮削。

---

## 第三节 (Task D)：离线测试（T1–T6）验证结果

针对 B1、B2 及回归场景，在 `tests/crawlers/test_anti_ban_step1.py` 中编写了覆盖 T1–T6 的离线自动化测试，并在 `tests/test_crawl_circuit.py` 中同步更新断路器断言。

| # | 场景 | 期望 | 测试用例名 | 实测结果 |
|---|---|---|---|---|
| T1 | 同一 host 第 1 个请求遇挑战页、bypass 成功；第 2 个请求 | 第 2 个请求不发直连，直接走 bypass；提示日志只出现一次 | `test_t1_subsequent_request_skips_direct_and_logs_once` | **通过**【已实测】 |
| T2 | 另一个从未遇挑战的 host | 仍按原逻辑先直连 | `test_t2_unseen_host_attempts_direct_first` | **通过**【已实测】 |
| T3 | 一部片在某站累计超 `site_total_timeout` | 该片该站放弃；断路器未打开；同站下一部片仍会请求 | `test_t3_single_movie_timeout_does_not_open_circuit` | **通过**【已实测】 |
| T4 | 排队等冷却 + 429 退避合计超过 120 秒，但在途时间不超 | 不判超时，请求成功 | `test_t4_cooldown_and_backoff_exempt_from_total_timeout` | **通过**【已实测】 |
| T5 | 回归：「允许的请求尝试已耗尽」 | 仍打开断路器（与 master 一致） | `test_t5_exhausted_attempts_still_opens_circuit` | **通过**【已实测】 |
| T6 | 回归：v2.6 的 T1–T6 | 全部仍通过 | `tests/crawlers/test_javlibrary_429_backoff.py` 全部 6 项 | **通过**【已实测】 |

### 针对性测试执行日志【已实测】

```bash
$ pytest tests/crawlers/test_anti_ban_step1.py tests/test_crawl_circuit.py tests/crawlers/test_javlibrary_429_backoff.py
============================== 31 passed in 12.30s ==============================
```
全部 31 个相关测试用例 100% 通过。

---

## 第四节：全量测试前后对比

- **改动前（master baseline: `5dbac8fa8306c2514b149f2ab85fe7fbdd2dd522`）**：
  ```text
  811 passed, 14 skipped, 2 warnings in 122.05s
  ```
- **改动后（`fix/anti-ban-step1`: `6d2233e427a1d68e9e2a14a17190d89733c8d3f9`）**：
  ```text
  823 passed, 14 skipped, 2 warnings
  ```
  新增 12 个专项测试，0 失败，失败数未增加。代码风格通过 `ruff check .` 与 `ruff format --check .` 校验。

---

## 第五节：Windows 测试包信息

为避免污染 master，测试包构建通过专用测试分支 `ci/test-build-windows` 触发 GitHub Actions。

- **测试包文件名**：`MDCx-v1.1.1-TEST-6d2233e-windows-x86_64.exe`
- **Artifact 名称**：`windows-x86_64-test-6d2233e`
- **下载链接**：`https://github.com/Marcus515J/mdcx/actions/runs/39248041961/artifacts/12183853553`
- **GitHub Actions Run ID**：`39248041961`（Run URL: `https://github.com/Marcus515J/mdcx/actions/runs/39248041961`）
- **构建分支与签出提交**：
  - 分支：`ci/test-build-windows` 提交 `162f7693f79b8b4bb169b8142092bad074532ba0`（基于 `v1.1.1`，仅含临时构建工作流）
  - 工作流实际签出提交：`6d2233e427a1d68e9e2a14a17190d89733c8d3f9`（即 `fix/anti-ban-step1` 最终提交）
- **校验和（SHA256）**：
  - `.exe` 文件（`SHA256SUMS.txt` 原样输出）：
    `01058e2fbea6ff90ba01c063f2e597fd7e29bfbb987aa95a1dd7988b8a4eb8dd *MDCx-v1.1.1-TEST-6d2233e-windows-x86_64.exe`
  - Artifact 压缩包 Digest：
    `sha256:18553786ce373e336fd7965b022394ab585761b845bb901b992798aa4733723a`
- **分支状态**：`fix/anti-ban-step1` 仅推送到远端作为功能分支，**未合并入 master**。

---

## 第六节 (Task C)：各站请求节奏、配置项与 missav 重定向调查（Q1–Q6，只查不改）

### Q1：按站点列表：一部片在每个站发几个请求、走直连还是 bypass、目前有没有任何节奏限制（冷却、间隔、并发上限）？

| 站点 | 单番号请求数 | 直连 / Bypass | 当前节奏限制（冷却、间隔、并发） | 源码行号与证据 |
|---|---|---|---|---|
| **official** | 2 次（搜索 1 次 + 详情 1 次） | 直连 | 无单独限制，仅全局默认限流器（8 req/s） | `mdcx/crawlers/official.py:137, 148`；Prestige: `mdcx/crawlers/prestige.py:81, 91`；全局 limiter: `mdcx/web_async.py:90` |
| **dmm** | 2~5+ 次（主页 GraphQL、视频 GraphQL、litevideo/mono 及多尺寸封面探测） | 直连 | 无单独限制，全局默认限流器（8 req/s） | 主接口 GraphQL: `mdcx/crawlers/dmm_new/__init__.py:1140`；TV GraphQL: `1008, 1101`；litevideo: `892, 902`；mono: `1268, 1277` |
| **avbase** | 2 次（搜索 `works?q=` 1 次 + 详情 `works/...` 1 次） | 直连 | 无单独限制，全局默认限流器（8 req/s） | 搜索: `mdcx/crawlers/avbase_new.py:41`；详情: `47, 55`（继承自 `mdcx/crawlers/base/base.py:258, 271`） |
| **javbus** | 1~3 次（优先尝试直连 `/number`，404 时再搜 `search/...` + 详情页） | 直连（带用户配置 Cookie） | 无单独限制，全局默认限流器（8 req/s） | 直连详情: `mdcx/crawlers/javbus.py:176, 184`；回退搜索: `189, 191`；Cookie 注入: `167` |
| **missav** | 1~2 次（优先尝试 `/number/cn`，未命中或无码时搜 `search/...` + 详情页） | Cloudflare 保护，走 mirror bypass | 站点最小间隔 `_cf_bypass_min_interval = 2.0s`（所有 bypass 站点默认值） | 详情: `mdcx/crawlers/missav.py:549`；搜索: `545`；2.0s 冷却: `mdcx/web_async.py:393` |
| **javlibrary** | 3 次（ja 搜索 1 次 + ja 详情 1 次 + cn/tw 详情 1 次） | Cloudflare 保护，走 mirror bypass（本期 B1 改后直通 bypass） | ① host 排队锁 `_host_locks`；② 站点最小请求间隔 **3.0s**；③ 429 退避（5s/10s） | ja 搜索: `mdcx/crawlers/javlibrary.py:204`；ja 详情: `216`；cn/tw 详情: `187, 216`；3.0s 冷却: `mdcx/web_async.py:395, 821`；锁: `1315` |
| **javdb** | 2 次（搜索 `/search?q=...&locale=zh` 1 次 + 详情 `/v/...` 1 次） | 直连（带用户配置 `_jdb_session` Cookie） | ① 类内互斥锁 `_page_request_lock`（**并发上限 1**）；② 每次请求强制休眠 **1.0~2.0 秒随机延迟** | 搜索: `mdcx/crawlers/javdb_new.py:191`；详情: `173`；互斥锁: `130, 166, 172`；节流函数 `_throttle_page_request`: `154-162`；Cookie: `144` |

---

### Q2：一个 URL 在最坏情况下会被发多少次？按当前配置值算出 javlibrary、javdb 各自的最坏次数与算式

#### 最坏次数通用公式
$$\text{Max URL Attempts} = \text{retry} \times \text{bypass\_rounds} \times \text{bypass\_attempts} \times \text{container\_attempts}$$

- 外层 `retry`：用户配置（默认 3，用户日常配置为 5），`mdcx/web_async.py:1550`。
- bypass 轮次：`_cf_bypass_max_rounds = 1`（`mdcx/web_async.py:400`）。
- bypass 内部尝试：`_cf_bypass_max_attempts = 2`（`mdcx/web_async.py:398`）。
- 429 限流退避尝试：针对 429 状态码，单轮最多允许 2 次退避重试（`mdcx/web_async.py:1660-1675`）。
- 容器内部：`cf_bypasser.py` 每次调用最多重试 3 次（`attempt 1/3 ~ 3/3`）。

#### 1. javlibrary 最坏次数计算
在 v2.7 B1 改动后，已知 host 跳过直连，直接进入 bypass：
- **单次外层尝试内**：
  1. 调用 mirror bypass：若遭遇 429，最多退避重试 2 次（共 3 次 mirror 请求）；
  2. 若 mirror 遭遇 5xx/408/超时（非 429/400），回退调用 `/html` 接口 1 次；
  3. 容器内每次调用最多执行 3 次 browser attempt。
- **最坏情况算式**：
  - 对容器 HTTP 调用次数：
    $$N_{\text{container\_calls}} \le \text{retry}\,(5) \times (3_{\text{mirror (含 429)}} + 1_{\text{/html 回退}}) = 5 \times 4 = 20\text{ 次}$$
  - 容器向目标站发起的真实浏览器渲染尝试：
    $$N_{\text{target\_attempts}} \le 20 \times 3_{\text{container attempt}} = 60\text{ 次}$$
  - 注：若为 429 终态或 400 终态，v2.6 已实现直接终止不再回退 `/html`，实际调用数会减半（最多 $5 \times 3 = 15$ 次）。

#### 2. javdb 最坏次数计算
javdb 为纯直连站点（无 bypass 逻辑）：
- 单次请求由 `_curl_request()` 发出，若遇网络错误或 5xx 错误，外层循环重试最多 `retry` 次。
- **最坏情况算式**：
  $$N_{\text{javdb\_attempts}} = \text{retry} = 5\text{ 次}$$
  每次尝试之间强制间隔 $1.0 \sim 2.0\text{s}$（`mdcx/crawlers/javdb_new.py:158`）。

---

### Q3：列出所有影响请求速率的配置项

| 配置键名 | 默认值 | GUI 位置 | 作用域 | 对应代码与模型定义行号 |
|---|---|---|---|---|
| `thread_number` | 50 | 基本设置 -> 并发数（滑块） | 全局并发任务数 | `models.py:330`, `load_config.py:422`, `save_config.py:318` |
| `thread_time` | 0 | 基本设置 -> 线程延时（滑块，秒） | 全局每部片启动延时 | `models.py:331`, `load_config.py:425`, `save_config.py:319` |
| `rest_count` | 20 | 其他设置 -> 间歇刮削文件数量（输入框） | 全局累计处理 N 部片后休息 | `models.py:716`, `load_config.py:911`, `save_config.py:635` |
| `rest_time` | 0 | 其他设置 -> 间歇刮削休息时间（输入框，秒） | 全局间歇休息时长 | `models.py:717`, `load_config.py:919`, `save_config.py:640` |
| `retry` | 3 | 网络设置 -> 重试（滑块） | 全局单 URL 最大重试次数 | `models.py:675`, `load_config.py:884`, `save_config.py:614` |
| `timeout` | 10 | 网络设置 -> 超时（滑块，秒） | 全局单次直接 HTTP 超时 | `models.py:674`, `load_config.py:881`, `save_config.py:613` |
| `cf_bypass_timeout` | 90 | 无（仅 JSON 配置项） | 全局单次 Bypass 容器调用超时 | `models.py:672` |
| `site_total_timeout` | 120 | 无（仅 JSON 配置项） | 单站单番号在途总预算上限 | `models.py:673`, `crawlers/base/base.py:86` |
| `javdb_time` | 10 | 无（代码硬编码/隐藏键） | 仅 javdb 相关操作内部参数 | `models.py:332` |

---

### Q4：直连路径遇到 403、503、Cloudflare 1015 时分别怎么处理？会不会被当成可重试而反复请求？

1. **403 与 503 处理**：
   - 源码位置：`mdcx/web_async.py:853-862`（`_is_retryable_status_code`）明确将 `403`、`500`、`502`、`503`、`504` 列为可重试状态码：
     ```python
     def _is_retryable_status_code(status_code: int) -> bool:
         return status_code in {403, 408, 429, 500, 502, 503, 504}
     ```
   - 若开启了 Cloudflare bypass（`cf_bypass_enable = True`）：
     通过 `_is_cloudflare_challenge(resp)`（`web_async.py:864-874`）检查响应体是否含有 `cf-turnstile`、`challenge-running`、`just a moment...` 等挑战特征。
     - 若命中特征：转入 bypass 流程；
     - 若未命中特征（纯 403 权限拒绝或非 CF 503）：**会被判定为可重试**，外层循环会按 `retry`（如 5 次）反复请求并打印重试日志（`web_async.py:1575`）。
2. **Cloudflare 1015（Rate Limited 速率封禁页）处理**：
   - Cloudflare 1015 错误通常返回 HTTP 429 或 403，页面标题为 `Error 1015: You are being rate limited`。
   - 该页面不包含 Turnstile 挑战脚本（属于封禁页而非可解的挑战页），因此 `_is_cloudflare_challenge` 返回 `False`。
   - 若返回 429：命中 429 退避逻辑，退避 2 次后以 429 终止（`web_async.py:1660`）；
   - 若返回 403：因为 403 属于 `_is_retryable_status_code`，**会被当成可重试错误反复重试直至耗尽 `retry` 次数**，对目标站造成连续击打。

---

### Q5：代码里有没有针对 javdb 的特殊限速或登录 Cookie 相关的频率处理？

**有，javdb 是目前唯一拥有独立严格频率限制与并发锁的爬虫类**：
1. **全局串行并发锁**：
   `mdcx/crawlers/javdb_new.py:130` 定义了类级别锁 `_page_request_lock = asyncio.Lock()`。
   在搜索（`javdb_new.py:191`）和详情（`javdb_new.py:173`）发起前，必须获取此锁（`javdb_new.py:166, 172`），**确保同一时刻全局只有一个协程在访问 javdb**。
2. **强制随机延时节流**：
   `mdcx/crawlers/javdb_new.py:154-162` 实现了 `_throttle_page_request()`：
   ```python
   async def _throttle_page_request(cls) -> None:
       now = time.monotonic()
       elapsed = now - cls._last_page_request_at
       interval = random.uniform(1.0, 2.0)  # 强制 1.0~2.0 秒随机间隔
       if elapsed < interval:
           await asyncio.sleep(interval - elapsed)
       cls._last_page_request_at = time.monotonic()
   ```
3. **Cookie 注入与防封逻辑**：
   `mdcx/crawlers/javdb_new.py:144` 自动读取配置中的 `manager.config.javdb` 并放入请求头的 `Cookie` 字段。若遇到反爬拦截或 Cookie 失效时，javdb 爬虫直接返回 None 并在页面解析时标记错误，不会盲目循环重试。

---

### Q6：missav mirror 跟随重定向时，发给容器的第二个请求到底是什么？与首个请求有何不同？

#### 源码调用链定位
当 mirror 返回 301/302 时，`mdcx/web_async.py:1054` 进入重定向分支：
```python
if redirect_resp.status_code in {301, 302, 303, 307, 308}:
    redirect_url = redirect_resp.headers.get("location") or redirect_resp.headers.get("Location")
    ...
    return await self._call_bypass_mirror(
        parsed_redirect.geturl(), # 重定向后新 URL
        method="GET",
        headers=headers,          # 沿用原请求头
        body=None,
        timeout=timeout,
        crawl_state=crawl_state,
        proxy=proxy,
        origin_url=url,
    )
```

#### 第 1 个请求 vs 第 2 个请求参数对比（以用户日志 `SSNI-126/cn` 为例）

| 请求属性 | 第 1 个请求（首个 mirror 请求） | 第 2 个请求（跟随重定向请求） | 差异比对 |
|---|---|---|---|
| **请求 URL** | `http://192.168.50.5:8000/SSNI-126/cn` | `http://192.168.50.5:8000/dm45/SSNI-126/cn` | **路径改变**：由 `/SSNI-126/cn` 变为 `/dm45/SSNI-126/cn` |
| **`x-hostname`** | `missav.ws` | `missav.ws` | **完全一致**（从 URL 提取 netloc） |
| **`x-proxy`** | `http://192.168.50.8:7897` | `http://192.168.50.8:7897` | **完全一致** |
| **HTTP Headers** | 仅标准 UA 与 Accept 等常规头（`web_async.py:1055`） | 原样传入原 `headers`（`web_async.py:1189`） | **完全一致** |
| **Cookie 处理** | 无 | **无**（未携带 301/302 返回的 `Set-Cookie`） | **Cookie 丢失** |

#### 对照分析与 400 原因
- 用户 10-19 17:17 手测命令：
  `curl.exe -i "http://192.168.50.5:8000/dm45/SSNI-126/cn" -H "x-hostname: missav.ws" -H "x-proxy: http://192.168.50.8:7897"` 成功返回 200。
- MDCx 内部跟随重定向时：
  1. 第一个请求耗时 33 秒拿到重定向，在此期间容器内的 Playwright 上下文或 session 状态可能已发生变化；
  2. MDCx 是通过 `allow_redirects=False` 手动处理重定向的，在发第二个请求时，没有将第一个请求响应头中的 `Set-Cookie`（如 cf_clearance 或 session cookie）提取并放入第二个请求的 `Cookie` 头部；
  3. 传递给容器的路径若缺少必要的前导斜杠或重定向 URL 规范化存在偏差，可能导致容器转发错误。
  （注：本期严格遵守任务单要求，**只查不改 missav 代码**，留待后续专项决策。）

---

## 第七节：另见（未修改的遗留观察项）

1. **`cf_bypasser.py` 内部重试放大效应**：
   容器内部的 `cf_bypasser.py` 对每次浏览器页面导航内置了 3 次循环重试。配合外部重试，单次 URL 失败会被放大至多倍浏览器渲染尝试，后续可评估向容器传递 `max_attempts=1` 参数以降低开销。
2. **非 CF 站点的 403 盲目重试问题**：
   `_is_retryable_status_code` 将所有 403 一律视为可重试。若某些站点（如防爬虫封 IP 后返回 403 拒绝访问），MDCx 依然会重试满 `retry` 次，反而加速封禁，建议后续在防封单中细化 403 甄别机制。

---

## 第八节：v2.6 汇报更正

对照任务单要求，对 `handoff/reports/MDCx_执行汇报_v2.6.md` 中的 4 处事实错误进行正式更正：

1. **合并提交长哈希更正**：
   - v2.6 汇报中记录为：`ce03f173b22cfc1a0c8fc0280ebdbd52254e4df9`；
   - 实际 `git rev-parse HEAD` 完整哈希为：`ce03f17a131f0b3b5fbe3d0ae35f9b5ccb0225c5`。
2. **`ci/test-build-windows` 分支指向更正**：
   - v2.6 汇报中描述为「指向 `ecd7ab3`」；
   - 实际该分支基于 `v1.1.1` 发布提交创建，分支最新 commit 为 `4ff4e1bb9a86097e3b9e2613f106bf0ab45609e0`，其内部工作流中的 `actions/checkout` 步骤通过 `ref: ecd7ab3bcbb544e5cfbb5579cd68f0809d65cfbd` 签出测试目标代码。
3. **Q4 中 ja/cn 详情页行号更正**：
   - `mdcx/crawlers/javlibrary.py` 中实际行号为：
     - ja 搜索页：第 204 行；
     - ja 详情页：第 216 行；
     - cn 详情页：第 187 行与第 216 行。
4. **Task C missav 400 调查结论更正**：
   - v2.6 汇报中推测的「DNS 污染解析成私网 IP 导致容器 SSRF 拦截」判定为【推测，已被用户 10-19 实测否定】；
   - 用户在容器内实测 `getaddrinfo` 解析均为公网 IP，首个请求耗时 33 秒成功返回 301/302 重定向，400 实际发生在 MDCx 跟随重定向发出的第二个请求之后。
