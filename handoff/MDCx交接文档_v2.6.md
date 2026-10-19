# MDCx 交接文档 v2.6（2026-10-19）

替代 v2.4（v2.5 只有任务单和汇报，无交接文档）。冲突时以本文档为准。下一阶段只认这份，不带前面的试错。
标注：【已查证】= 源码/日志/截图为证；【已实测】= 注明谁、在哪跑；【推测】= 未验证。

---

## 1. 一句话现状

**javlibrary 官网路线已打通**：NAS 的 cloudflare-bypass 容器修好（补装 geoip2），MDCx 经 mirror 模式过 Cloudflare；v2.4 的列表页匹配修复实测生效、用户已批准合并。**剩下的问题：javlibrary 站点自身限流（429）触发 MDCx 走错路径并熔断**——任务单 v2.6 执行方在做。镜像 c99i 路线搁置（官网可用即不再碰）。

## 2. 用户的版本习惯（定方向用）

保持所有软件最新；出问题就向前修；实在修不动才回退。容器镜像保持 `:latest`，不钉旧版本。

## 3. 环境

- Windows `192.168.50.8`：Clash Verge，端口 7897，局域网连接开，DNS 覆写关。MDCx 在这台跑；bypass 容器的代理也指向它，**Windows 关机则 bypass 断**。
- NAS `192.168.50.5`：Container Station。改 YAML：应用程序页 → `cloudflare-bypass` → 编辑 →「重新创建」→ 粘贴 →「验证」→「更新」【已实测】。看日志：容器页该行 → 日志。
- MDCx 测试包当前用 `MDCx-v1.1.1-TEST-09911e2`（v2.4）；配置 `日常_v2.3.json`，javlibrary `custom_url` **为空 = 官网**。

## 4. bypass 容器：根因与修复（已结）

- 根因【已查证，执行汇报 v2.5 + 上游 Issue #125 截图】：上游迁移到 CloakBrowser 后，只要请求带代理就强制 `geoip=True`（`cf_bypasser/core/bypasser.py:121` `geoip=bool(proxy_config)`），但镜像依赖漏写 `cloakbrowser[geoip]`。上游 Issue #125（2026-09-18，Open，无维护者回复）。没有开关可关。之前「重新创建」拉到新镜像后全站 1 秒 500 就是这个。
- 修复【已实测，用户 10-19】：Compose 加代理环境变量 + 启动时缺 geoip2 就补装。首次请求经代理下载约 70MB GeoLite2 数据库（约 70 秒），之后 javlibrary、missav 都能点掉 Turnstile。
- 未采用：汇报 v2.5 修法 1（命名卷挂整个 `~/.cloakbrowser`，会把镜像自带的 Chromium 冻在旧版，违背保持最新）；修法 3（手工维护 mmdb 文件）。
- 代价：每次「重新创建」后启动要联网装包、首个请求要重下数据库（都走 Windows 代理）。日常重启不受影响。
- 回退：把 YAML 换回去（删 `HTTP_PROXY/HTTPS_PROXY/NO_PROXY` 三行和 `command` 段），「重新创建」→「更新」。上游若修了 #125，`command` 段可删。

当前容器 YAML（完整）：

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

`extra_hosts` 用于过容器的私有 IP 安全检查（容器内 DNS 被污染）；全网 DNS 污染另有挂起文档。

## 5. javlibrary 官网实测（用户 10-19 15:37，测试包 09911e2，3 部并发）

- 3/3 刮削成功。javlibrary 只有 PDVIJ-001 拿到数据（评分 8.30、wanted 94）。
- v2.4 修复生效：SSNI-126 选中普通版 `javli4yg4i.html`，不是蓝光 `javli4yg4m`【已实测】。官网列表链接现在也是 `./jav*.html` 格式（用户拿到的官网搜索页 HTML），所以 v2.4 对官网同样必需。
- 429：javlibrary 自己返回（容器日志：带有效 cookie，0.7 秒回 429，7560 字节）。三次都发生在数秒内连发 6–8 个 javlibrary 请求之后【已实测】。之后 MDCx 回退 /html → 浏览器挑战失败 → 500 → 断路器停用 javlibrary【已实测】。
- 【推测】并发 3 × 每部片多页（ja 搜索、ja 详情、cn 详情）造成短时密集请求；把 429 当 CF 挑战处理是错路径。
- missav：本轮 `mirror 返回终态 HTTP 400` → 熔断，但容器日志里没有对应请求；15:29 那轮成功过。原因未知。
- 其余满屏 🔴 多为「该站没这条数据」或预告片高画质探测 404，属正常。
- 评分：SSNI-126 / PRED-110 的 score 回退到 javdb（4.5 / 4.4，看起来是 5 分制），与 javlibrary 的 8.3 混用——见挂起文档，未处理。

## 6. 进行中

- **任务单 v2.6**（handoff 分支）：A 用 PR 合并 v2.4 进 master（用户已批准，不打 tag）；B 先查后改——429 退避重试、不回退 /html、不计入断路器，javlibrary 最小请求间隔；C 只查 missav 的 400。审核按其第 5 节 13 项。
- 收到「汇报好了」→ 审核 → 用户用新测试包、同样 3 部片、同样配置复测，同时给 MDCx 日志和容器日志。

## 7. 未决 / 挂起（问到再读项目里的对应文档）

1. 全网 DNS 污染：`claude/挂起-全网DNS污染-v1.0.md`。
2. 评分刻度混用：`claude/挂起-评分刻度混用-v1.0.md`，先问用户「新软件设想」。
3. javlibrary 镜像与 Cloudflare：`claude/挂起-javlibrary镜像与Cloudflare-v1.2.md`（官网已通，本文件第 4–5 节为准）。
4. missav、javbus 保留与否：等大批量。
5. 功能分支 `feat/llm-only-and-resources` 是否删除：未决。
6. 容器启动依赖 Windows 代理：上游修 #125 后可简化。

## 8. 已否决（不要重提）

- 沿用 v2.4 第 7 节：容器 DNS 指向 Windows Clash；改 cloudflare-bypass 源码。
- 把 bypass 镜像钉回旧版本作为首选（用户方向：保持最新、向前修）。
- 汇报 v2.5 修法 1（命名卷挂整个 `~/.cloakbrowser`）。

## 9. 新对话启动提示词

```
我在继续维护自己的 MDCx fork（GitHub 仓库 Marcus515J/mdcx）。交接文件在 handoff 分支的 handoff/ 目录，规则见 handoff/README.md。请先接入该仓库，只读 handoff/MDCx交接文档_v2.6.md，不带前面的试错。项目里的挂起文档（claude/挂起-*.md）我问到再读。

现状：javlibrary 官网路线已通（bypass 容器已补 geoip2），v2.4 已验证并批准合并；任务单 v2.6（合并 v2.4 + 修 429 退避与 javlibrary 请求间隔 + 查 missav 的 400）执行方在做，我说「汇报好了」时审核。

规则：
- 读代码、写代码、跑测试、打包都交给执行方；你只做讨论、定方向、写任务单、审核汇报。任务单要谁都能照做、带机械核对。
- 来源标注：已查证 / 已实测 / 推测。我说「我记得」的当待验命题。
- 界面操作先让我截图；一次只动一个变量；问题没定时只给分析和问题。
- 软件保持最新，出问题向前修，修不动才回退。
- 不重提交接文档「已否决」。
- 对话变长要省额度时，主动提醒我开新对话并给交接。
```
