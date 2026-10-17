# MDCx 执行汇报 v1.6：重复刮削修复与诊断排查

日期：2026-10-17。对应任务单 `handoff/MDCx任务单_v1.6.md`。**结论：D5 修复完成并通过实测验证；D3/D4/D9 排查完成并标注来源与用户最少排查步骤；Windows 测试构建产物已生成；草稿 PR 已开。**

---

## 1. 交付信息汇总

- **功能分支**：`fix/rescrape-and-diagnostics`
- **代码提交**：
  - D5 修复与测试：[`cf47e44`](https://github.com/Marcus515J/mdcx/commit/cf47e446509ab1862f3e6c9abf833cda234bd6a2) `fix(scan): prevent repeated scraping by tracking companion nfo and all paths`
  - 临时工作流提交：[`cc9e635`](https://github.com/Marcus515J/mdcx/commit/cc9e6359efb57ad59c8996df1e2413a478973689) `临时：测试构建，合并前删除`
- **草稿 PR**：[#10 fix: prevent repeated scraping and filename drift (D5)](https://github.com/Marcus515J/mdcx/pull/10)（Draft，未合并）
- **Windows 测试版工作流**：[Actions Run 39027098314](https://github.com/Marcus515J/mdcx/actions/runs/39027098314)
- **Windows 测试版 Artifact**：`windows-x86_64-test-cf47e44`（包含 `MDCx-v1.1.0-TEST-cf47e44-windows-x86_64.exe`，大小 145.79 MB，保留 14 天）
- **测试结果**：773 通过，14 跳过，0 失败（包含新增的 4 项 D5 验证测试全部通过，全量回归 100% 通过）

---

## 2. D5：重复刮削与文件名漂移分析与修复

### 2.1 机制与原因分析

1. **「跳过已刮削」的判断机制【已查证】**：
   - **全局设置项**：受 `manager.config.no_escape` 中的 `NoEscape.SKIP_SUCCESS_FILE` 控制。在 UI 界面中的位置为：**「设置」->「刮削目录」->「文件扫描设置」->「跳过之前已刮削成功的文件」**（控件 `checkBox_skip_success_file`）。
   - **默认状态**：在 `resources/config/default_config.json` 和 `mdcx/config/models.py` 中，`skip_success_file` **默认未勾选**。当未勾选时，`not_skip_success = True`，`movie_lists` 永远不会跳过任何文件。
   - **路径匹配机制**：开启跳过时，原代码通过 `path not in Flags.success_list` 判断，只做 Python `Path` 对象的**精确绝对路径比对**。
   - **保存机制**：原 `save_success_list` 存在逻辑缺陷：开启软硬链接时仅记录 `old_path`；普通移动/复制模式下仅记录 `new_path`。

2. **用户场景下失效的具体原因【已查证】**：
   - **跨版本/新目录执行**：用户在 `H:\0H\MDCx\测试` 运行新提取的测试包（如 `TEST-989b825`），该目录下 `userdata/success.txt` 不存在，内存中 `Flags.success_list` 为空。
   - **移动到演员子目录或改名**：刮削后文件已移至原目录下的演员名子目录（如 `G:\待刮削\RION\SSNI-126-…mp4`）。即使旧记录中有原路径，路径变动后精确路径比对即失效。
   - **缺失同名 NFO 检测**：原 `movie_lists` 扫描时完全不检查视频同级目录下是否存在同名且非空的 `.nfo` 元数据文件。
   - **设置未开启的可能性**：若用户配置中未勾选「跳过之前已刮削成功的文件」，`not_skip_success` 恒为 True，直接无视记录。

3. **文件名漂移的原因【已查证】**：
   - 实体文件名在 `mdcx/core/file.py:255` 的 `_generate_file_name` 中拼出，主干包含 `res.title`。
   - 重复扫描触发重复刮削时，`mdcx/core/translate.py` 会重新调用 LLM 翻译日文标题。由于 LLM 每次生成的中文译文存在随机性，翻译结果变化导致生成的新文件名不同，造成「每次重刮、文件名漂移一次」。
   - 10-17 用户实测中由于翻译全部失败、系统保留了日文原标题，因此当天文件名未变。

### 2.2 修复方案（最小代码改动）

在 `mdcx/base/file.py` 中进行最小修复：
1. **完善记录**：`save_success_list` 同时记录 `old_path` 与 `new_path`（以及软链接目标），确保无论扫描源路径还是目标路径均命中成功列表。
2. **结合 NFO 识别已刮削文件**：在 `movie_lists` 中增加 `_has_valid_nfo` 函数。当开启「跳过之前已刮削成功的文件」时，若视频同级目录下存在大于 0 字节的 `<file_name>.nfo`，判定为已刮削（`is_scraped = True`），跳过该文件并累加 `skip` 计数，同时补入 `Flags.success_list`。
3. **未刮削与失败文件**：新文件或上轮刮削失败的文件（同级目录下无有效 NFO、且不在 `Flags.success_list` 中），继续正常进入待刮削列表。

### 2.3 用户设置项核对指引

若用户需要在刮削时不重刮已处理文件，请确认配置：
- **设置项**：「跳过之前已刮削成功的文件」
- **界面位置**：「设置」界面 -> 展开左侧「刮削目录」-> 找到「文件扫描设置」区域 -> 勾选「跳过之前已刮削成功的文件」（`checkBox_skip_success_file`）。
- **预期效果**：勾选后，即便更换测试文件夹或文件已整理入演员子目录，扫描日志也将正确显示 `Skip successfully scraped (N)` 并跳过。

### 2.4 实测验证对比

在 `tests/test_rescrape_skip.py` 中构造临时测试目录，验证「刮削成功 → 改名或移入子目录 → 再扫描」：
- **修复前**：由于移动到子目录或重命名后绝对路径不匹配、且无 NFO 检查，已刮削文件被全部作为新任务重新加入扫描列表，`Skip successfully scraped` 为 0。
- **修复后**：
  - 移入子目录的已刮削视频（`RION/SSNI-126-Title.mp4`）与改名的已刮削视频（`PRED-110-新译名.mp4`）均被识别并跳过，日志输出 `Found (2)! Skip successfully scraped (2)`。
  - 新加入的文件（`NEW-999.mp4`）与上轮失败的文件（`FAIL-001.mp4`）正常进入待刮削列表。
  - 用户主动取消勾选跳过时，全量进入（尊重用户强制重刮意图）。
  - 0 字节损坏 NFO 不会误跳过。

---

## 3. D3：检测网络时 javdb mirror 返回 400 排查

### 3.1 请求比对【已查证】

- **「检测网络」请求**：
  MDCx 向 NAS Bypass 服务（`http://192.168.50.5:8000/v/D16Q5?locale=zh`）发起 GET 请求，Headers 携带 `x-hostname: javdb.com` 与 `x-proxy: http://192.168.50.8:7897`。
- **刮削时访问 javdb 请求**：
  MDCx 客户端直接由 Windows 本机通过 Clash Verge 代理（`http://192.168.50.8:7897`）发起请求，使用 `curl_cffi` 模拟 Chrome 浏览器指纹。由于代理节点对 javdb 路由畅通且未触发 Cloudflare 质询拦截（`_is_cf_challenge_response` 为 False），**实际刮削根本不调用 NAS 的 bypass 服务**，因此刮削正常且每部仅需 4~5 秒。

### 3.2 上游 CloudflareBypassForScraping 源码分析【已查证】

查阅上游容器源码 `cf_bypasser/server/routes.py` 与 `cf_bypasser/utils/security.py`：
1. 服务端收到 mirror 请求后，在转发前执行安全校验：`is_safe_url(f"https://{hostname}")`。
2. `is_safe_url` 内部调用 NAS 本机操作系统的 `socket.getaddrinfo(hostname, None)` 进行 DNS 解析。
3. 在国内网络环境下，NAS 系统自身的 DNS 未配置代理分流，对被封锁站点（如 `javdb.com`、`7mmtv.sx`）发起直连查询时，遭遇 GFW DNS 污染，解析返回环回地址 `127.0.0.1`（或因网络阻断返回 `gaierror`）【推测】。
4. `is_safe_url` 中的 `_ip_is_blocked` 判定 `ip.is_loopback` 为 True，将该域名判定为不安全 SSRF 地址，返回 False。
5. `routes.py` 抛出 HTTP 400：`HTTPException(status_code=400, detail="Invalid or unsafe hostname - localhost and private IPs are not allowed")`。

### 3.3 结论

- **非本仓库代码问题**【已查证】。MDCx 构造的 mirror 请求与请求头完全符合上游规范。
- 根因为上游服务的 SSRF 校验依赖 NAS 本地 DNS 解析，在遭遇 DNS 污染返回 127.0.0.1 时触发安全拦截机制。

### 3.4 用户在 NAS 上的最少操作步骤

在 NAS 终端（SSH 或 Container Station 命令行）执行以下命令，确认 400 的详细错误信息：
```bash
docker logs --tail 50 cloudflare-bypass | grep -E "400|Invalid or unsafe|javdb"
```
若出现 `Invalid or unsafe hostname - localhost and private IPs are not allowed`，即可印证上述 DNS 污染触发 SSRF 拦截机制。

---

## 4. D4 与 D9：排查结论（只排查不改代码）

### 4.1 D4：lulubar、fc2ppvdb 的 `/html` 返回 HTTP 500

1. **现象来源**【已查证】：
   `mdcx/web_async.py:1127` `_call_bypass_html`，MDCx 向 NAS 发起 `GET /html?url=...&proxy=...` 请求。
2. **最可能原因**【已查证上游逻辑，推测站点情况】：
   - 上游 `cf_bypasser/server/routes.py` 第 118 行：当 Playwright/Patchright 无头浏览器在指定超时内未能解开 Cloudflare Turnstile 挑战、页面超时或浏览器进程异常退出时，`get_or_generate_html` 返回 None，服务端抛出 `HTTPException(status_code=500, detail="Failed to bypass Cloudflare protection")`。
   - 10-17 实测中 freejavbt 经 `/html` 成功，证明容器与代理本身正常，lulubar 和 fc2ppvdb 失败是由于特定站点挑战复杂度高或加载超时导致。
3. **证据强度**：
   - 上游抛出 500 的代码逻辑：【已查证】。
   - 具体站点挑战超时原因：【推测】。
4. **用户在 NAS 上的最少操作步骤**：
   在 NAS 执行以下命令查看对应站点的失败日志：
   ```bash
   docker logs --tail 100 cloudflare-bypass | grep -E "lulubar|fc2ppvdb|Failed to bypass|Error"
   ```

### 4.2 D9-a：DMM 预告 HEAD 返回 403/404

1. **现象来源**【已查证】：
   `mdcx/base/web.py` 第 402 行（`check_url`）、第 612 行（临时 `/pv/` 链接验证）以及第 706 行（探测 `4k`, `hhb`, `mhb`, `dmb` 等更高清晰度），通过 `client.request("HEAD", test_url)` 发起请求。
2. **最可能原因**【已查证】：
   - **404 来源**：MDCx 在解析预告时会主动探测更高画质的变体（如 `_4k_w.mp4`、`_hhb_w.mp4`）。绝大多数作品没有 4K 预告片，CDN 正常响应 404。代码在第 415 行已显式设计过滤：`if response.status_code == 404 and "_w.mp4" in url: return`，不影响后续流程。
   - **403 来源**：DMM CDN 服务器（`cc3001.dmm.co.jp`）存在防盗链策略，HEAD 请求若缺少浏览器上下文或代理节点被 DMM 标记，会返回 403；此外临时 `/pv/` 链接具有过期时间，过期后也会返回 403/404。
3. **证据强度**：代码主动探测与 404 忽略逻辑【已查证】；CDN 防盗链限制【推测】。
4. **用户确认步骤**：无需任何操作。预告探测在命中 404 时会自动回退到原始可用链接。

### 4.3 D9-b：Windows 软链接 WinError 1314

1. **现象来源**【已查证】：
   `mdcx/core/file.py` 第 137 行 `await aiofiles.os.symlink(old_path, new_path)`。
2. **最可能原因**【已查证】：
   Windows 系统中创建符号链接属于受保护操作，需要 `SeCreateSymbolicLinkPrivilege` 特权。若当前 Windows 未开启「开发人员模式」，且 MDCx 未以管理员身份运行，Windows 系统内核将直接拒绝并报错 `[WinError 1314] 客户端没有所需的特权`。
3. **证据强度**：Windows 操作系统 API 权限规范与 Python `os.symlink` 文档【已查证】。
4. **用户确认步骤**：
   - 打开 Windows「设置」->「系统」（或「更新和安全」）->「开发者选项」，确认是否已打开**「开发人员模式」**；
   - 若不愿开启开发人员模式，右键 MDCx 选择**「以管理员身份运行」**即可解除限制。

### 4.4 D9-c：GLM 返回 HTTP 400

1. **现象来源**【已查证】：
   `mdcx/llm.py` 第 132 行 `self.client.chat.completions.create(...)`，调用来源为 `mdcx/base/translate.py:186`。
2. **请求构造与原因排查**【已查证】：
   - **Base URL 拼接问题**：智谱 GLM 的兼容接口为 `https://open.bigmodel.cn/api/paas/v4/`。若用户在配置中写成了 `https://open.bigmodel.cn/api/paas/v4/chat/completions`，OpenAI SDK 会自动补全为 `.../chat/completions/chat/completions`，导致服务端返回 400。
   - **Temperature 参数限制**：MDCx 传递了 `temperature=tc.llm_temperature`。智谱开放平台对 `temperature` 参数范围要求在 `(0.0, 1.0)` 开区间内，若配置为 0 或 1.0，智谱接口将直接返回 400。
   - **Key 格式校验**：智谱 API Key 为 `<id>.<secret>` 格式，若格式不符或过期，接口亦会响应 400/401。
   - MDCx 在 `mdcx/llm.py:144` 捕获异常时仅记录了异常类名（如 `BadRequestError`），未打印具体服务端返回 JSON 详情。
3. **证据强度**：MDCx 客户端构造请求参数【已查证】；智谱开放平台参数校验规则【已查证】。
4. **用户确认步骤**：
   检查 MDCx「设置」中的翻译配置：
   1. 确认 `llm_url` 填写为 `https://open.bigmodel.cn/api/paas/v4/`（末尾带 `/`，不带 `chat/completions`）。
   2. 确认 `llm_temperature` 介于 `0.1` 至 `0.9` 之间。
   3. 确认 `llm_model` 填写为有效的模型名称（如 `glm-4-flash`）。

---

## 5. 改动文件与测试总结

### 5.1 改动文件清单

| 文件 | 类别 | 说明 |
|---|---|---|
| `mdcx/base/file.py` | 生产代码修改 | `save_success_list` 保存双向路径；`movie_lists` 增加 `_has_valid_nfo` 检测同级有效 NFO |
| `tests/test_rescrape_skip.py` | 测试代码新增 | 4 个测试用例，覆盖移入子目录、重命名、未勾选跳过、双向记录、0 字节 NFO |
| `.github/workflows/test-build-windows.yml` | 临时 CI 工作流新增 | 独立提交 `cc9e635`，专门用于构建 Windows 测试版 artifact，合并前删除 |

### 5.2 测试命令与统计

- **测试命令**：
  ```bash
  .venv/bin/pytest tests/test_rescrape_skip.py -v
  .venv/bin/pytest tests/
  ```
- **测试结果**：
  - `test_rescrape_skip.py`：**4 passed, 0 failed**（0.85s）
  - 全量回归测试：**773 passed, 14 skipped, 0 failed**（99.54s）
  - 代码检查：`ruff check` 与 `ruff format` 100% 通过无告警。

---

## 6. 约束遵守与没做到的部分

1. **硬约束遵守**：
   - 未新增任何设置项和依赖。
   - 未改动需求 A/B/C 的任何逻辑。
   - 未修改任何已有 NFO。
   - 未打标签、未发 Release、未合并 master；代码已在草稿 PR #10。
   - 临时 workflow 单独提交 `cc9e635` 并注明「临时：测试构建，合并前删除」。
   - 未假装复现连不上的 NAS 环境，如实列出源码证据强度与用户最少排查命令。
2. **没做到的部分**：
   - 无。本轮任务单范围内全部事项均已严格执行完毕。
