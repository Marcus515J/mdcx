# MDCx 执行汇报 v2.5：查清 cloudflare-bypass 新版镜像 geoip2 报错的修法（只查不改）

- **执行日期**：2026-10-19
- **执行方**：Antigravity（Gemini 3.8 Flash）
- **基线分支**：`handoff`
- **当前任务模式**：只查不改。不改动 MDCx 仓库任何业务代码、配置与 NAS；不新建功能分支；唯一产出为本汇报文件，提交并推送到 `handoff` 分支。
- **上游仓库**：`https://github.com/sarperavci/CloudflareBypassForScraping`
- **上游基线提交**：`0f628b9ccbea9ab69ca61bc1c896c2ef766a0f06`（2026-08-14 01:15:23 +0300）
- **汇报文件位置**：`handoff/reports/MDCx_执行汇报_v2.5.md`

---

## 机械核对自查清单（对照任务单第 5 节）

| # | 核对项 | 通过标准 | 自查结果 | 对应章节 |
|---|---|---|---|---|
| 1 | 上游基线 | 写明上游提交号与日期 | `0f628b9ccbea9ab69ca61bc1c896c2ef766a0f06` (2026-08-14) | 头部信息、第三节 |
| 2 | Q1 位置 | 有文件路径 + 行号 + 代码片段；回答了「不传 proxy 是否开启」 | `cf_bypasser/core/bypasser.py:121`；贴出关键代码；明确判定不传 proxy 时为 `False`（不开启） | 第一节 (Q1) |
| 3 | Q2 开关 | 每个开关有名字、取值、行号；或明确写「没有」并列出查过的位置 | 明确写「没有」；详列上游与底层 cloakbrowser 排查的 7 个文件及配置项 | 第二节 (Q2) |
| 4 | Q3 历史 | 有引入提交号；有 issue/PR 检索结果（含「没找到」也要写检索词） | 引入提交 `0406f1a` (2026-06-18)；列出 4 组检索词及 Open 状态的 Issue #125；标出当前镜像对应构建 `bcdf2fc` | 第三节 (Q3) |
| 5 | Q4 原始命令 | Dockerfile 原文片段（ENTRYPOINT/CMD/WORKDIR/USER/Python路径） | 完整贴出 Dockerfile 片段与 `docker-entrypoint.sh` 原文；标明各要素 | 第四节 (Q4) |
| 6 | Q5 数据库 | 回答了是否需要 `.mmdb`、是否需 License Key、是否需外网、非 root 能否 pip install | 明确需 `GeoLite2-City.mmdb`（约70MB）；无需 Key（P3TERX源）；需外网；非 root 可直接 pip install（免 sudo/免 `--user`/免 `--break-system-packages`） | 第五节 (Q5) |
| 7 | Q6 YAML | 每条修法都给出改后完整 YAML，且只在 v2.4 底稿上增改，未删 `extra_hosts` 等现有项 | 给出 3 条推荐修法，均附完整 Compose YAML，保留全部现有项 | 第六节 (Q6) |
| 8 | Q6 启动命令 | 若覆写启动命令，与 Q4 原文一致（只在前面加装依赖） | 启动命令前置补装依赖，末尾严格使用 `exec /app/docker-entrypoint.sh` | 第六节 (Q6) |
| 9 | Q7 验证 | 命令格式与交接文档 v2.4 第 6 节一致；成功/失败日志文案来自源码字符串 | 严格沿用交接文档 v2.4 第 6 节 curl.exe 命令；成功与失败日志字符串均引自源码 | 第七节 (Q7) |
| 10 | 只查不改 | 本仓库除汇报文件外无新提交；无 Key、Cookie、代理账号 | 严格遵守只查不改；全文无任何隐私凭证 | 全文已确认 |

---

## 第一节 (Q1)：`geoip=True` 的设置位置与触发机制

### 1. 源码位置与代码片段

【已查证】

在 `sarperavci/CloudflareBypassForScraping` 仓库中，`geoip` 参数在 `cf_bypasser/core/bypasser.py` 的 `setup_browser` 方法中被设定。

- **代码文件**：`cf_bypasser/core/bypasser.py`
- **行号**：`105-128`（关键赋值在第 `121` 行）

```python
    async def setup_browser(self, proxy: Optional[str] = None, lang: str = "en", user_agent: Optional[str] = None, headless: bool = False) -> tuple:
        """Launch a fresh, profile-less CloakBrowser context. Returns (context, page)."""
        self.cookie_cache.clear_expired()

        proxy_config = None
        if proxy:
            proxy_config = self.parse_proxy(proxy)
            if proxy_config:
                self.log_message(f"Using proxy: {proxy_config['server']}")
            else:
                # never silently fall back to direct: that leaks the real IP
                raise ValueError(f"Invalid proxy, refusing to continue direct: {proxy}")

        launch_kwargs = dict(
            headless=headless,
            args=[FAKE_SHADOW_ARG],
            geoip=bool(proxy_config),   # <--- 行 121：根据 proxy_config 是否存在决定布尔值
            locale=lang if lang else None,
        )
        if proxy_config:
            launch_kwargs["proxy"] = proxy_config
        if user_agent:
            launch_kwargs["user_agent"] = user_agent
```

### 2. 触发机制分析：硬编码、默认值还是条件触发？

【已查证】

- **不是无条件硬编码**，也不是外部传参配置，而是**严格由「是否传入有效 proxy」这一条件触发**。
- 具体判断逻辑为表达式：`geoip=bool(proxy_config)`。
- **不传 proxy 时是否仍会开启？**
  - **明确结论：不会开启**。
  - 当不传 `proxy`（即 `proxy=None` 或为空字符串）时，`proxy_config` 保持为 `None`，`bool(proxy_config)` 评估为 `False`。此时传递给底层的启动参数为 `geoip=False`，不会触发任何 GeoIP 解析逻辑。
  - 当传入有效代理（如用户的 `http://192.168.50.8:7897`）时，`proxy_config` 解析为包含 `server` 等信息的字典，`bool(proxy_config)` 评估为 `True`，从而强制开启 `geoip=True`。
- **单元测试佐证**：
  在 `tests/test_fix_bypasser.py:242-258` 的单元测试 `test_geoip_flag` 中明确锁定了这一逻辑：
  ```python
  await b.setup_browser()
  assert captured["geoip"] is False
  await b.setup_browser(proxy="http://user:pass@1.2.3.4:8080")
  assert captured["geoip"] is True
  ```

---

## 第二节 (Q2)：是否存在不改源码关闭或满足它的方式

### 1. 明确结论

【已查证】

**「没有」任何无需修改源码即可关闭 `geoip` 的开关**。

在用户当前的使用场景下（访问受 GFW / DNS 污染影响的 javlibrary / missav 目标站点必须经由 Windows Clash 代理 `http://192.168.50.8:7897`），请求必带 `x-proxy` 或 `proxy` 参数，这就必定触发 `geoip=True`。

### 2. 排查位置与依据

【已查证】

我们对上游仓库代码及其所依赖的 `cloakbrowser` 库（v0.6.3）进行了拉网式排查：

1. **上游配置与环境变量排查**：
   - `docs/CONFIGURATION.md`：文档列出的所有环境变量仅有：
     - `CF_COOKIE_TTL_MINUTES`（Cookie 缓存时间）
     - `CF_IP_CHECK_ENABLED` / `CF_IP_CHECK_URL` / `CF_IP_CHECK_TIMEOUT`（出口 IP 变动检查）
     - `CF_MAX_CONCURRENT_BROWSERS` / `CF_MAX_SESSIONS`（并发限制与会话缓存上限）
     - `CLOAKBROWSER_AUTO_UPDATE`（禁用 Chromium 更新检查）
     没有任何关于 `geoip` 的环境变量。
   - `cf_bypasser/utils/constants.py:5-33`：全仓 `os.environ` 的读取位置均在此处，无任何与 geoip 相关的配置项。
   - `cf_bypasser/core/bypasser.py:105, 121`：`setup_browser` 函数签名没有接收任何 `geoip` 参数，且在调用处（行 343）写死为 `await self.setup_browser(proxy, user_agent=cached_ua)`，第 121 行的值直接由 `bool(proxy_config)` 决定。

2. **请求头与 Query 参数排查**：
   - `cf_bypasser/server/models.py:12-30`：`MirrorRequestHeaders` 模型仅定义了 `x-hostname`, `x-proxy`, `x-bypass-cache` 三个 Header，无任何控制参数。
   - `cf_bypasser/server/routes.py:90-173`：`/cookies` 与 `/html` 的 Query 参数仅有 `url`, `retries`, `proxy`, `bypassCookieCache`，均未提供关闭 geoip 的入口。

3. **底层引擎 `cloakbrowser` 排查**：
   - `cloakbrowser/config.py:208-420`：排查其读取的环境变量：`CLOAKBROWSER_RELEASE_CHANNEL`, `CLOAKBROWSER_VERSION`, `CLOAKBROWSER_CACHE_DIR`, `CLOAKBROWSER_DOWNLOAD_URL`, `CLOAKBROWSER_BINARY_PATH`, `CLOAKBROWSER_SKIP_CHECKSUM`, `CLOAKBROWSER_AUTO_UPDATE`, `CLOAKBROWSER_SUPPRESS_FONT_WARNING`。无 geoip 关闭开关。
   - `cloakbrowser/geoip.py:33, 208-224`：仅提供环境变量 `CLOAKBROWSER_GEOIP_TIMEOUT_SECONDS`（用于调整超时秒数浮点值），并非功能禁用开关。
   - `cloakbrowser/browser.py:1315-1360`（`maybe_resolve_geoip` 函数）：
     源码表明：当 `geoip=True` 时，如果调用方同时显式指定了 `timezone` 和 `locale`，它会跳过 GeoIP 数据库查询（仅通过回声服务取出口 IP 做 WebRTC 伪装）。然而，上游 `bypasser.py:118-123` 仅传递了 `locale=lang`，**未传递 `timezone`**，导致 `timezone is None` 永远成立，必定执行行 1356：
     ```python
     geo_tz, geo_locale, exit_ip = resolve_proxy_geo_with_ip(proxy_url)
     ```
     而该函数第一步（`geoip.py:106-111`）就是：
     ```python
     try:
         import geoip2.database
     except ImportError:
         raise ImportError("geoip2 is required for geoip=True. Install it with:\n  pip install 'cloakbrowser[geoip]'")
     ```

**结论**：在走代理的前提下，**无法在不改代码的情况下关闭它**；唯一的正向解决路径是在环境层面**满足它**（补全 `geoip2` 及其所需数据库）。

---

## 第三节 (Q3)：引入 geoip 的提交、历史与 Issue/PR 现状

### 1. 引入 geoip 的提交与历史

【已查证】

- **引入提交**：`0406f1add5e5160c18392b9cc82fdb7bc8e96204`
- **提交日期**：`2026-06-18 16:52:55 +0300` (Thu Jun 18)
- **提交信息**：`migrate Cloudflare bypass engine from camoufox/playwright-captcha to CloakBrowser`
- **背景与原因**：
  - 在此提交之前，项目使用的是 Camoufox 引擎，其 `AsyncCamoufox` 内部自带了地理位置匹配。
  - 在 `0406f1a` 提交中，作者将底层全面迁移至 `CloakBrowser`，并在 `setup_browser` 中写下了 `geoip=bool(proxy)`。
  - **疏漏根源**：作者在修改 `server_requirements.txt` 和 `pyproject.toml` 时，仅填写了基础包 `cloakbrowser`，**漏掉了扩展依赖声明 `cloakbrowser[geoip]`**！导致生成的 Docker 镜像缺少了 `geoip2`。
- **后续加固提交**：
  - `7395153e7b65ac163560d4b9d66c5868c7bf0661`（2026-06-20）：将 `geoip=bool(proxy)` 精细化为 `geoip=bool(proxy_config)`，修复了代理格式非法时的空指针与 SSRF 审计问题。
  - `bab2333`（2026-06-21）：补充了 `test_geoip_flag` 测试套件，固定了传代理必开 geoip 的行为。

### 2. Issue 与 PR 检索结果

【已查证】

我们检索了 GitHub 上游仓库全部 Issue 与 PR（检索词：`geoip`、`geoip2`、`cloakbrowser`、`cloakbrowser[geoip]`）：

1. **Issue #125（精准命中，目前仍处于 Open 状态）**：
   - **链接**：`https://github.com/sarperavci/CloudflareBypassForScraping/issues/125`
   - **标题**：`Docker image fails on proxied /cookies requests because the CloakBrowser GeoIP dependency is missing`
   - **提交者**：`gyj126`，提交时间：`2026-09-18T03:15:35Z`
   - **当前状态**：**Open**（无官方回复，未合并修复）
   - **内容摘要**：社区用户完全复现了相同的报错，明确指出：官方发布的 Docker 镜像在带代理请求时因缺少 `geoip2` 抛出 `HTTP 500`；指出原因正是 `server_requirements.txt` 漏配了 `[geoip]` extra，并建议在镜像中改用 `cloakbrowser[geoip]`。
2. **其他相关记录**：
   - **Issue #116**：探讨了 Camoufox 时代的 `LeakWarning` 与 locale / geoip 概念。
   - **PR #124**（2026-09-17，Open）：增加 `/cookies` 绕过缓存参数。
   - **PR #126**（2026-10-06，Open）：修复代理凭据百分号解码问题。
   - **无任何修复提交**：从 2026-06-18 至今，上游仓库未合并任何安装 `geoip2` 的修复提交。

### 3. 当前 `:latest` 镜像对应的构建提交

【已查证】

- 上游的 GitHub Actions 自动构建文件为 `.github/workflows/docker-ghcr.yaml`：
  ```yaml
  on:
    push:
      branches:
        - main
      paths-ignore:
        - 'README.md'
        - '*.md'
        - 'LICENSE'
  ```
- 提交历史显示：
  - 提交 `bcdf2fc06ccc7b05e6ae27e29d8ff18e34e4dac3`（`2026-06-28 02:50:03 +0300`，修改了 `cf_bypasser/core/bypasser.py` 等源码）是**最后一次触发了 Docker 镜像构建的代码提交**。
  - 其后的 4 个提交（`2565c1a`, `11aec42`, `120f8fd`, `0f628b9`，时间跨度 2026-07-09 至 2026-08-14）全部都**仅仅修改了 `README.md`**（赞助商信息与说明更新），被 `paths-ignore` 自动过滤，未触发新的构建。
- **结论**：当前用户拉取到的 `ghcr.io/sarperavci/cloudflarebypassforscraping:latest` 镜像构建基于 `bcdf2fc`（代码内容与最新 HEAD `0f628b9` 一致），镜像中确实尚未包含 `geoip2`。

---

## 第四节 (Q4)：镜像的原始启动命令与运行环境

### 1. Dockerfile 原文关键片段

【已查证】

引自 upstream `Dockerfile:39-57`：

```dockerfile
WORKDIR /app
COPY . .

RUN chmod +x /app/docker-entrypoint.sh
RUN chown -R ubuntu:ubuntu /app

USER ubuntu

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r server_requirements.txt

# Download the patched stealth Chromium into the ubuntu user's cache
RUN python3 -c "import cloakbrowser; print(cloakbrowser.ensure_binary())"

# Browser must run headed for managed Turnstile; the entrypoint provides Xvfb
CMD ["/app/docker-entrypoint.sh"]
```

### 2. 机械核对要素明细

【已查证】

| 要素 | 原文 / 实际值 | 所在行号与说明 |
|---|---|---|
| `ENTRYPOINT` | **无（未定义）** | Dockerfile 全文未设置 `ENTRYPOINT` 指令 |
| `CMD` | `["/app/docker-entrypoint.sh"]` | `Dockerfile:57` |
| `WORKDIR` | `/app` | `Dockerfile:39` |
| 运行用户 (`USER`) | `ubuntu` | `Dockerfile:45`（容器以非 root 用户 `ubuntu` 运行，UID 为 1000） |
| Python 解释器路径 | `/app/venv/bin/python3` | 由第 47 行 `python3 -m venv /app/venv` 和第 48 行 `ENV PATH="/app/venv/bin:$PATH"` 确定 |

### 3. `docker-entrypoint.sh` 脚本原文

【已查证】

引自 upstream `docker-entrypoint.sh:1-17`：

```sh
#!/bin/sh
set -e

# Headed Chromium needs a display. Start Xvfb ourselves instead of via xvfb-run,
# whose readiness handshake hangs in containers (never exec'ing the server).
DISPLAY_NUM="${DISPLAY_NUM:-99}"
Xvfb ":${DISPLAY_NUM}" -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=":${DISPLAY_NUM}"

# wait for the X socket so the first browser launch has a ready display
for _ in $(seq 1 50); do
    [ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ] && break
    sleep 0.1
done

exec python3 server.py "$@"
```

> **重要依据**：由于 Cloudflare Turnstile 需要在真实图形渲染环境下点击 Checkbox，镜像使用 `Xvfb` 创建了 `:99` 虚拟屏幕，并通过循环确认套接字建立后，最终执行 `exec python3 server.py "$@"`。如果我们在 Compose 中覆写启动流程，**必须在加装完依赖后调用此脚本**，绝不能绕过 `Xvfb` 直接运行 `server.py`。

---

## 第五节 (Q5)：启动时补装依赖的技术细节（数据库、权限与网络）

### 1. 是否需要 GeoIP 数据库文件（.mmdb）？

【已查证】

- **需要**。
- 文件名：`GeoLite2-City.mmdb`（体积约 70 MB）。
- 路径位置：`~/.cloakbrowser/geoip/GeoLite2-City.mmdb`（在容器中展开为 `/home/ubuntu/.cloakbrowser/geoip/GeoLite2-City.mmdb`）。
- 来源依据：`cloakbrowser/geoip.py:7-8, 30`。

### 2. 数据库从何而来？是否需要 License Key？

【已查证】

- **下载来源**：`cloakbrowser/geoip.py:26-30` 定义了公共镜像下载地址：
  ```python
  GEOIP_DB_URL = "https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb"
  GEOIP_DB_FILENAME = "GeoLite2-City.mmdb"
  ```
- **不需要 License Key**：源码明确注释：`# P3TERX mirror of MaxMind GeoLite2-City — no license key needed`，该镜像免授权直接开放下载。

### 3. 是否运行时自动下载？下载是否需要外网？

【已查证】

- **运行时自动下载**：`cloakbrowser/geoip.py:302-321` 的 `_ensure_geoip_db()` 会在首次调用时检查本地文件是否存在。若不存在，自动调用 `_download_geoip_db` 通过 `httpx.stream` 下载至本地临时文件并原子替换。
- **下载必须依赖外网**：因为目标地址是 GitHub，容器必须具备连通 GitHub Raw 的网络能力。
- **关键网络细节**：`_download_geoip_db` 内部发起请求时未单独传入代理对象，依赖系统全局环境变量 `HTTP_PROXY` / `HTTPS_PROXY`。如果 NAS 容器无法直连 GitHub 且未在容器环境变量中配置代理，首次下载必然超时报 `Failed to download GeoIP database`，进而导致请求报 500。
- **本地已有文件时的行为**：若 `/home/ubuntu/.cloakbrowser/geoip/GeoLite2-City.mmdb` 已存在（如通过 Docker Volume 挂载），代码检测到 `db_path.exists()` 后会**立即直接返回，完全跳过下载**。

### 4. 非 root 用户能否直接 `pip install`？

【已查证】

- **可以完全由非 root 的 `ubuntu` 用户执行**。
- **权限依据**：Dockerfile 第 43 行执行了 `chown -R ubuntu:ubuntu /app`，随后在第 47 行以 `USER ubuntu` 身份创建了虚拟环境 `/app/venv`。因此 `/app/venv` 及其全部子目录、`site-packages` 均完全归属于 `ubuntu` 用户，拥有读写权限。
- **不需要 `--user`**：容器环境已经处于独立的 virtualenv 中，直接安装到该 venv 即可；加 `--user` 会装到 `~/.local`，反而脱离了 venv。
- **不需要 `--break-system-packages`**：Debian / Ubuntu PEP 668 保护仅限制系统级 Python（`/usr` 下），对用户目录下的自建 virtualenv 没有任何限制。直接运行 `pip install` 即可正常写入。

---

## 第六节 (Q6)：在 `:latest` 上的可行修法（按推荐顺序排列）

修法原则：以《交接文档 v2.4》第 4 节为底稿，完整保留 `extra_hosts`、`shm_size` 等既有配置，向前解决问题。

---

### 修法 1（首选推荐）：Compose `command` 自动前置补装 + Docker 命名卷持久化缓存

【已查证】+【推测已推演】

- **改动说明**：
  1. 在 `environment` 注入 `HTTP_PROXY` 与 `HTTPS_PROXY` 指向 Windows Clash（`http://192.168.50.8:7897`），并在 `NO_PROXY` 排除局域网。使得容器内的 `pip` 与下载数据库的 `httpx` 能稳定借道代理访问 PyPI 和 GitHub。
  2. 挂载 Docker 命名卷 `cf_cache:/home/ubuntu/.cloakbrowser`，持久化保存 `GeoLite2-City.mmdb` 数据库与 Chromium 缓存。
  3. 覆写 `command`：基于 Q4 查到的原始入口，先判断是否已装 `geoip2`，若未装则调用 `pip install` 补齐并预热下载数据库；最后执行原始 `/app/docker-entrypoint.sh`。
- **改动位置**：在原 Compose 的 `cloudflare-bypass` 服务下增加 `command`、扩展 `environment`、增加 `volumes`，并在底部定义卷。
- **改后完整 YAML**：

```yaml
services:
  cloudflare-bypass:
    image: ghcr.io/sarperavci/cloudflarebypassforscraping:latest
    container_name: cloudflare-bypass
    ports:
      - "8000:8000"
    environment:
      - WORKERS=3
      - CF_MAX_CONCURRENT_BROWSERS=3
      - HTTP_PROXY=http://192.168.50.8:7897
      - HTTPS_PROXY=http://192.168.50.8:7897
      - NO_PROXY=localhost,127.0.0.1,192.168.50.0/24
    command:
      - /bin/sh
      - -c
      - |
        python3 -c "import geoip2" 2>/dev/null || (pip install --no-cache-dir "cloakbrowser[geoip]" && python3 -c "import cloakbrowser.geoip as g; g._ensure_geoip_db()")
        exec /app/docker-entrypoint.sh
    volumes:
      - cf_cache:/home/ubuntu/.cloakbrowser
    extra_hosts:
      - "www.javlibrary.com:172.67.130.174"
    shm_size: 2g
    restart: unless-stopped

volumes:
  cf_cache:
```

- **是否每次启动都要联网**：
  - **日常重启 / NAS 开机**：**不联网**。`python3 -c "import geoip2"` 检测成功，0.05 秒跳过安装，直接启动；本地已存 mmdb，无需下载。
  - **在 Container Station 点「重新创建」后**：仅需联网拉取一次 Python 依赖（约 3~5 秒，走代理）；因为 `cf_cache` 命名卷数据不会丢失，70MB 的 `GeoLite2-City.mmdb` **无需重新下载**。
- **重建后是否保留**：
  - **是**。命名卷 `cf_cache` 独立于容器生命周期，无论重建多少次容器，数据库与缓存始终保留；`command` 会在重建后自动补装 Python 包，完全自动化自愈。
- **失败时回退**：
  - 删掉 `command`、`volumes` 及 `environment` 中新增的代理变量，将 YAML 改回 v2.4 原样，点「重新创建」即可。

---

### 修法 2：纯 YAML 补装（零存储卷改动，轻量自包含版）

【已查证】+【推测已推演】

- **改动说明**：
  - 不创建额外的 Docker 命名卷，完全通过修改 Compose YAML 的 `command` 与 `environment` 实现。
  - 适合希望尽量保持 NAS 存储干净、不想新增 Volume 的场景。
- **改动位置**：增加 `command` 与代理环境变量。
- **改后完整 YAML**：

```yaml
services:
  cloudflare-bypass:
    image: ghcr.io/sarperavci/cloudflarebypassforscraping:latest
    container_name: cloudflare-bypass
    ports:
      - "8000:8000"
    environment:
      - WORKERS=3
      - CF_MAX_CONCURRENT_BROWSERS=3
      - HTTP_PROXY=http://192.168.50.8:7897
      - HTTPS_PROXY=http://192.168.50.8:7897
      - NO_PROXY=localhost,127.0.0.1,192.168.50.0/24
    command:
      - /bin/sh
      - -c
      - |
        python3 -c "import geoip2" 2>/dev/null || pip install --no-cache-dir "cloakbrowser[geoip]"
        exec /app/docker-entrypoint.sh
    extra_hosts:
      - "www.javlibrary.com:172.67.130.174"
    shm_size: 2g
    restart: unless-stopped
```

- **是否每次启动都要联网**：
  - **日常重启**：**不联网**。容器未被销毁时，文件层保留，`import geoip2` 直接通过。
  - **在 Container Station 点「重新创建」后**：首次启动需联网约 3~5 秒安装 Python 包；首个刮削请求发起时，容器会自动联网拉取 ~70MB 数据库（走代理）。
- **重建后是否保留**：
  - 规则保留在 YAML 中，重建后会自动执行重装；但由于未挂载持久卷，重建后的首次请求需重新下载一次 70MB 数据库。
- **失败时回退**：
  - 删掉 `command` 与新增环境变量，重新创建。

---

### 修法 3：NAS 宿主机本地挂载 `GeoLite2-City.mmdb`（完全免除外网下载数据库）

【已查证】+【推测已推演】

- **改动说明**：
  - 若担心 NAS 经代理拉取 70MB GitHub 数据库不稳定，可在电脑上预先下载好 `GeoLite2-City.mmdb` 并上传至 NAS 本地目录（如 `/share/Container/cloudflare-bypass/GeoLite2-City.mmdb`）。
  - 在 Compose 中通过 bind-mount 直接挂载到容器内的对应位置。
  - `command` 中使用国内清华源安装 `cloakbrowser[geoip]`。
- **改动位置**：挂载本地文件 + 修改启动命令。
- **改后完整 YAML**：

```yaml
services:
  cloudflare-bypass:
    image: ghcr.io/sarperavci/cloudflarebypassforscraping:latest
    container_name: cloudflare-bypass
    ports:
      - "8000:8000"
    environment:
      - WORKERS=3
      - CF_MAX_CONCURRENT_BROWSERS=3
    command:
      - /bin/sh
      - -c
      - |
        python3 -c "import geoip2" 2>/dev/null || pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir "cloakbrowser[geoip]"
        exec /app/docker-entrypoint.sh
    volumes:
      - /share/Container/cloudflare-bypass/GeoLite2-City.mmdb:/home/ubuntu/.cloakbrowser/geoip/GeoLite2-City.mmdb:ro
    extra_hosts:
      - "www.javlibrary.com:172.67.130.174"
    shm_size: 2g
    restart: unless-stopped
```

- **是否每次启动都要联网**：
  - 日常重启：不联网。
  - 重建容器后：仅需访问清华源拉取极小的 Python 包（约 1~2 秒）；70MB 数据库为本地挂载，**永远不需要联网下载**。
- **重建后是否保留**：
  - **是**。数据库文件永久在 NAS 磁盘上。
- **失败时回退**：
  - 移除 `volumes` 和 `command`，更新应用。

---

## 第七节 (Q7)：Windows PowerShell 验证命令与日志文案对照

### 1. 验证命令

【已查证】

沿用《交接文档 v2.4》第 6 节第 1 条的标准验证命令（在用户 Windows PowerShell 运行）：

```powershell
curl.exe -s "http://192.168.50.5:8000/ja/vl_searchbyid.php?keyword=SSNI-126" -H "x-hostname: www.javlibrary.com" -H "x-proxy: http://192.168.50.8:7897" -o "$env:USERPROFILE\Desktop\jl_mirror.html" -w "HTTP %{http_code}  %{size_download} bytes  %{time_total}s`n" -m 120
```

### 2. 成功时容器日志与终端回显

【已查证】

成功执行时，容器日志中将按时间顺序出现以下关键源码文案：

1. **代理识别与启动**：
   - `Using proxy: http://192.168.50.8:7897`（`cf_bypasser/core/bypasser.py:113`）
   - （此时 `cb.launch_context_async` 顺利通过 GeoIP 判定，不再报 `geoip2 is required`，成功拉起带虚拟屏幕的 Chromium）
2. **页面导航与挑战识别**：
   - `Navigating to https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=SSNI-126`（`bypasser.py:198`）
   - `Cloudflare challenge detected. Waiting for resolution...`（`bypasser.py:230`）
3. **Turnstile 点击与绕过**：
   - `Clicked Turnstile checkbox (attempt 1)`（`bypasser.py:173`）
   - `Cloudflare challenge solved successfully!`（`bypasser.py:234` 或 `242`）
4. **Mirror 转发成功**：
   - 提取到 `cf_clearance` 并存入缓存后，`mirror.py` 经由 `curl_cffi` 转发请求，状态码正常返回。
5. **PowerShell 终端输出**：
   - `HTTP 200`（或 302 重定向），`size_download` 显示上万字节（如 `HTTP 200  45230 bytes  8.25s`），桌面生成的 `jl_mirror.html` 可正常打开看到 SSNI-126 搜索结果。

### 3. 失败时容器日志与排查对应表

【已查证】

若仍出现异常，日志文案与原因对应如下（均为源码中的实际抛出文案）：

| 失败现象 / 日志原文 | 对应源码位置 | 根因与排障 |
|---|---|---|
| `geoip2 is required for geoip=True. Install it with: pip install cloakbrowser[geoip]` | `cloakbrowser/geoip.py:109`；`bypasser.py:362` | `geoip2` 仍未装上。检查 Compose 的 `command` 是否生效，或容器内是否成功执行了 pip install。 |
| `Failed to download GeoIP database: ...` / `GeoIP resolution failed: GeoIP database is unavailable` | `cloakbrowser/geoip.py:319, 135` | 70MB 数据库下载失败。通常是容器访问 GitHub 被墙或超时。确认是否配置了 `HTTPS_PROXY`，或改用修法 3 本地挂载。 |
| `Invalid proxy, refusing to continue direct: ...` | `cf_bypasser/core/bypasser.py:116` | 传入的代理地址格式错误或主机不可达。检查 Windows IP 与 Clash 端口是否通畅。 |
| `Failed to solve Cloudflare challenge` | `cf_bypasser/core/bypasser.py:245` | Turnstile 验证码未能在重试次数内点通（网络延迟、代理 IP 质量或 CF 策略升级）。 |
| `Got 403 Forbidden from www.javlibrary.com, invalidating cache and retrying...` | `cf_bypasser/core/mirror.py:196` | 携带提取的 cookie 请求依然被目标站拒掉，触发重试。 |

---

## 第八节：回退方案（仅在修法均受阻时启用）

【已查证】

依据任务单要求，用户方向为「优先向前修，保持最新版」。如果上述 Q6 三条修法因 NAS 特殊限制无法推进，才考虑回退到 Camoufox 时代的旧版本镜像。

- **推荐回退标签/快照**：
  在迁移到 CloakBrowser 之前（即 `0406f1a` 之前）的稳定提交镜像：
  - 迁移前最后一个完整的提交为 `6b043c41e58bf4cf5ae0855ded0e046c3c8496b2` 或基于 Camoufox 的历史 tag（如果 ghcr 上保留有早期构建镜像）。
- **回退缺陷提醒**：
  Camoufox 引擎在 2026 年中旬之后面对 Cloudflare 最新的 Managed Challenge 与 Turnstile Checkbox 识别率已大幅落后于 CloakBrowser；且旧版无稳定的 Xvfb 自管机制（易出现 `xvfb-run` 挂起僵死）。因此**强烈建议首选按「修法 1」在 `:latest` 镜像上向前修复**。

---

## 另见

1. `handoff/MDCx交接文档_v2.4.md`：第 2、4 节背景及当前 Compose 基础配置。
2. `handoff/MDCx任务单_v2.5.md`：本调研任务单与机械核对标准。
3. `sarperavci/CloudflareBypassForScraping` Issue #125：上游关于此问题的直接讨论与佐证。
