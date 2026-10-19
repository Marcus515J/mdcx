# MDCx 任务单 v2.5（2026-10-19）：查清 cloudflare-bypass 新版镜像 geoip2 报错的修法（只查不改）

> 背景只认 `handoff/MDCx交接文档_v2.4.md` 第 2、4 节加本单第 0 节。执行方可能是 Antigravity 或 Codex，按本单照做即可。
> 来源标注：【已查证】= 附仓库路径 + 行号（或提交号 / issue 链接）；【已实测】= 写明谁、在哪台机器、跑了什么；【推测】= 未验证。
> 本单**只查不改**：不改任何代码、不改用户配置、不改 NAS 容器、不推送到上游。与任务单 v2.4 互不相干，可并行。

---

## 0. 问题与证据

用户 NAS 上跑 cloudflare-bypass（上游 `sarperavci/CloudflareBypassForScraping`，镜像 `ghcr.io/sarperavci/cloudflarebypassforscraping:latest`，完整 Compose 见交接文档 v2.4 第 4 节）。

- 【已实测，用户 10-19 容器日志】03:09 missav 走 mirror 模式成功（日志有 `Clicked Turnstile checkbox`）。
- 【已实测】03:26 用户在 Container Station 对该应用点「重新创建」（加 `extra_hosts`），容器重新启动（日志 `Started server process [1]` 03:26:54）。
- 【已实测，用户 10-19 Windows curl + 容器日志】此后**所有请求**都 1 秒失败，`/html` 模式与 mirror 模式、javlibrary 与 missav 都一样。关键日志原文：
  ```
  Error running browser for https://missav.ws/: geoip2 is required for geoip=True. Install it with:
    pip install cloakbrowser[geoip]
  ...
  File "/app/cf_bypasser/core/mirror.py", line 179, in mirror_request
    raise Exception("Failed to get Cloudflare clearance cookies")
  ```
- 【推测】重新创建时 `:latest` 拉到了新版镜像，新版默认启用 geoip（大概率是根据代理出口 IP 设定浏览器时区/语言），但镜像里没装 `geoip2` 依赖。

**用户定的方向**：保持最新版，向前修；修不动才回退。所以本单要找的是「在最新版上怎么修」，不是「回到哪个旧版」。

## 1. 准备

1. 克隆上游 `https://github.com/sarperavci/CloudflareBypassForScraping` 的默认分支最新提交，汇报写出提交号和日期。
2. 只读代码、提交历史、issue/PR、Dockerfile、发布页；**不联网访问任何刮削目标站**，不构建、不运行镜像（除非 Q6 需要且你能在自己环境安全完成，跑了要写明在哪跑）。
3. 不把任何 Key、Cookie、代理账号写进汇报。

## 2. 要回答的问题

| # | 问题 | 要求 |
|---|---|---|
| Q1 | `geoip=True` 在哪里被设置？是硬编码、默认值、还是由某个条件（如传了 proxy）触发？ | 贴代码位置 + 行号 + 关键几行；说明不传 proxy 时是否仍会开启 |
| Q2 | 有没有**不改源码**就能关掉或满足它的方式：环境变量、请求头/参数、配置文件？ | 列出每个开关的名字、取值、生效位置（行号）；没有就写「没有」并说明查了哪些地方 |
| Q3 | 引入 geoip 的提交/版本是哪一个？之后有没有修复提交、新版镜像或 open/closed issue 讨论这个报错？ | 贴提交号、日期、issue/PR 链接；镜像 `:latest` 当前对应哪次构建（若能从 GitHub Actions / ghcr 页面查到） |
| Q4 | 镜像的原始启动命令是什么？ | 贴 Dockerfile 里的 `ENTRYPOINT` / `CMD` 原文、`WORKDIR`、运行用户（日志里提示符是 `ubuntu`，非 root）、Python 解释器路径 |
| Q5 | 若要在**启动时补装**依赖：`cloakbrowser[geoip]` 除了 Python 包，是否还需要 geoip 数据库文件（如 GeoLite2 `.mmdb`）？从哪来、需要 License Key 吗、是否运行时自动下载、下载需不需要外网？非 root 用户能否 `pip install`（需不需要 `--user` 或 `--break-system-packages`）？ | 每点标来源；查不到写【推测】 |
| Q6 | 基于 Q2–Q5，给出**在 `:latest` 上**的可行修法，按推荐顺序排列（最多 3 条）。每条写：要改 Compose 的哪几行（给出改后**完整** YAML，以交接文档 v2.4 第 4 节为底稿）、是否每次启动都要联网、重建后是否保留、失败时怎么回退 | 修法若需要覆写启动命令，命令必须基于 Q4 查到的原文，不得凭印象写 |
| Q7 | 修好后让用户在 Windows PowerShell 验证的命令 | 沿用交接文档 v2.4 第 6 节第 1 条那条 `curl.exe` 命令的格式；写明成功和失败时容器日志里各会出现什么文案（按源码里的实际字符串） |

## 3. 不要做的事

- 不改 MDCx 代码，不建功能分支（本单只产出汇报）。
- 不改上游代码、不提 PR、不 fork 后改代码给用户用（交接文档 v2.4 第 7 节已否决「改 cloudflare-bypass 源码」）。
- 不给「钉回旧版本」作为首选方案；只有 Q6 三条都走不通时，才在汇报末尾单列「回退方案」，写明对应 tag/digest 与理由。
- 不重新讨论交接文档已否决项（含：容器 DNS 指向 Windows Clash）。

## 4. 汇报

- 文件：`handoff/reports/MDCx_执行汇报_v2.5.md`，推到 `handoff` 分支。
- 结构：头部（上游提交号与日期、执行方、日期）→ Q1–Q7 逐条作答 → 推荐修法（含完整 YAML）→ 回退方案（仅在需要时）→ 另见。
- 每条结论标【已查证】/【已实测】/【推测】。代码位置写上游仓库相对路径加行号。

## 5. 机械核对清单（Claude 审核时逐项对照）

| # | 核对项 | 通过标准 |
|---|---|---|
| 1 | 上游基线 | 写明上游提交号与日期 |
| 2 | Q1 位置 | 有文件路径 + 行号 + 代码片段；回答了「不传 proxy 是否开启」 |
| 3 | Q2 开关 | 每个开关有名字、取值、行号；或明确写「没有」并列出查过的位置 |
| 4 | Q3 历史 | 有引入提交号；有 issue/PR 检索结果（含「没找到」也要写检索词） |
| 5 | Q4 原始命令 | Dockerfile 原文片段（ENTRYPOINT/CMD/WORKDIR/USER） |
| 6 | Q5 数据库 | 回答了是否需要 `.mmdb`、是否需 License Key、是否需外网 |
| 7 | Q6 YAML | 每条修法都给出改后完整 YAML，且只在 v2.4 底稿上增改，未删 `extra_hosts` 等现有项 |
| 8 | Q6 启动命令 | 若覆写启动命令，与 Q4 原文一致（只在前面加装依赖） |
| 9 | Q7 验证 | 命令格式与交接文档 v2.4 第 6 节一致；成功/失败日志文案来自源码字符串 |
| 10 | 只查不改 | 本仓库除汇报文件外无新提交；无 Key、Cookie、代理账号 |

## 6. 执行方启动提示词

```
仓库 Marcus515J/mdcx。切到 handoff 分支，阅读 handoff/README.md 和 handoff/MDCx任务单_v2.5.md，按任务单执行。这是只查不改的调查：去读上游 sarperavci/CloudflareBypassForScraping 的代码、Dockerfile、提交历史和 issue，回答 Q1–Q7；不改任何代码、不碰我的配置和 NAS；汇报写到 handoff/reports/MDCx_执行汇报_v2.5.md 并推到 handoff 分支。这是新开任务，与 v2.4 无关，可并行。
```
