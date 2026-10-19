# MDCx 交接文档 v2.4（2026-10-19）

替代 v2.3。冲突时以本文档为准。下一阶段只认这份，不带前面的试错。
标注：【已查证】= 源码/日志/截图为证；【已实测】= 注明谁、在哪跑；【推测】= 未验证。

---

## 1. 一句话现状

javlibrary 两条路并行：
- **镜像 c99i**：多结果番号固定匹配失败，根因已查清，**任务单 v2.4 执行方正在修**（等汇报）。
- **官网**：用户明确要能用官网。NAS 上 cloudflare-bypass 容器已修好 DNS 一关，卡在容器 `/html` 模式缺 geoip 依赖；**下一步测 mirror 模式**（第 6 节）。

## 2. 环境（沿用 v2.3 第 2 节，更正/补充）

- `192.168.50.8` = 用户 **Windows**（Clash Verge，端口 7897，局域网连接开，**DNS 覆写关**）【已实测，用户截图】。`cf_bypass_proxy` 指向它，所以 Windows 关机时 bypass 也会断。
- NAS `192.168.50.5`；Container Station「应用程序」里 `cloudflare-bypass` 是 Compose 应用，改 YAML 入口：应用程序页 → 齿轮/编辑 →「重新创建」【已实测】。
- 容器内进命令行：容器页该行齿轮 →「执行」→「执行控制台」→ `/bin/bash`，提示符 `ubuntu@…:/app$`【已实测】。
- 用户当前配置：javlibrary `custom_url` **已清空**（官网）。测 v2.4 测试包前要改回 `https://www.c99i.com/`。

## 3. 镜像路线：根因（全部已结）

- 10-18 镜像基线：PRED-110、PDVIJ-001 命中，SSNI-126 `未匹配到番号`，两次运行都不中【已实测】。
- 镜像搜 SSNI-126 停在列表页，两条（蓝光 + 普通），普通版链接 `https://www.c99i.com/ja/javli4yg4i.html`【已实测，用户浏览器】。
- `mdcx/crawlers/javlibrary.py:12-36` `get_real_url` 分支 2 只认 `href` 含 `/?v=jav`（官网格式）→ 镜像 `jav*.html` 一条都匹配不到【已查证】。凡多结果番号都会失败。
- **任务单 v2.4**（handoff `6a41385`）：两种格式都认，蓝光规则不变，离线测试 T1–T7，测试包，不合并。审核按其第 5 节 10 项。

## 4. 官网路线：已查清的链路

| 关卡 | 结果 | 来源 |
|---|---|---|
| MDCx 直连官网（经 7897 → JMS） | CF 挑战页 | 【已实测】10-19 10:36 日志 |
| 容器安全检查 | 原先拒：`Invalid or unsafe URL - localhost and private IPs are not allowed` | 【已实测】curl |
| 拒的原因 | 容器内 DNS 污染，javlibrary 每次解析都带一个 `2001::`（Teredo，判为私有）+ 随机境外 IPv4 | 【已实测】容器内 python 解析 |
| 污染范围 | 路由器 192.168.50.1、223.5.5.5、8.8.8.8 全部返回同类假地址 → 上游投毒，全网一样 | 【已实测】Windows nslookup |
| 真实 IP | `172.67.130.174`、`104.21.8.210`（经 Clash 代理查 Cloudflare DoH） | 【已实测】 |
| **修复已做** | 容器 YAML 加 `extra_hosts: - "www.javlibrary.com:172.67.130.174"`，重建成功 | 【已实测】 |
| 修后 `/html` | `HTTP 500`，`Failed to bypass Cloudflare protection`；日志：`geoip2 is required for geoip=True. Install it with: pip install cloakbrowser[geoip]` | 【已实测】curl + 容器日志 03:27 |
| mirror 模式 | missav 03:09 经同一代理成功点掉 Turnstile（`Clicked Turnstile checkbox`）；javlibrary 修 DNS 后**未测** | 【已实测】容器日志 |

- MDCx 代码：mirror 返回终态状态码（如 400）时**跳过 /html**（`web_async.py:1239`、`:1454`），断路器 `crawlers/base/base.py:120/132`。执行汇报 v2.3 的日志字典漏了这三条，待并入下一张涉及 CF 的任务单。
- 回退：删掉 `extra_hosts` 两行，「重新创建」→「更新」。
- 维护提醒【推测】：`extra_hosts` 只用于过安全检查，实际请求经代理远端解析，IP 变化大概率无影响。

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
    extra_hosts:
      - "www.javlibrary.com:172.67.130.174"
    shm_size: 2g
    restart: unless-stopped
```

## 5. 未决 / 挂起

1. **全网 DNS 污染**：已挂起，见项目文档 `claude/挂起-全网DNS污染-v1.0.md`（补：8.8.8.8 也已实测被污染）。用户最终要解决，与反代一起考虑。
2. 评分刻度混用：`claude/挂起-评分刻度混用-v1.0.md`，先问用户「新软件设想」。
3. javlibrary：项目文档 `claude/挂起-javlibrary镜像与Cloudflare-v1.2.md`（本文档第 3、4 节更新于其上，以本文档为准）。
4. missav、javbus 保留与否：等大批量。
5. 功能分支 `feat/llm-only-and-resources` 是否删除：未决。

## 6. 新对话开场就做

1. **测 mirror 模式访问 javlibrary**（用户 Windows PowerShell，一次一个动作）：
   ```
   curl.exe -s "http://192.168.50.5:8000/ja/vl_searchbyid.php?keyword=SSNI-126" -H "x-hostname: www.javlibrary.com" -H "x-proxy: http://192.168.50.8:7897" -o "$env:USERPROFILE\Desktop\jl_mirror.html" -w "HTTP %{http_code}  %{size_download} bytes  %{time_total}s`n" -m 120
   ```
   【推测】命令据汇报 v2.3 Q6 命令 3 改写。成功 = 200 且上万字节，打开文件应见 SSNI-126 两条结果；同时看容器日志是否有 `Clicked Turnstile` / `challenge solved`。
2. mirror 通 → 让用户用 MDCx 实刮官网 3 部（配置保持官网）验证；不通 → 看容器日志定原因（geoip 问题是否也在 mirror 路径；是否要换镜像版本/在容器里补 geoip2，后者重建会丢失，需评估）。
3. 收到「汇报好了」→ 审核执行汇报 v2.4，然后用户改回镜像测测试包。

## 7. 已否决（沿用 v2.3 第 8 节，另补）

- 容器 DNS 指向 Windows Clash（会推翻「DNS 覆写保持关闭」的既定决定）。
- 改 cloudflare-bypass 源码（非本仓库，升级即覆盖）。

## 8. 新对话启动提示词

```
我在继续维护自己的 MDCx fork（GitHub 仓库 Marcus515J/mdcx）。交接文件在 handoff 分支的 handoff/ 目录，规则见 handoff/README.md。请先接入该仓库，只读 handoff/MDCx交接文档_v2.4.md，不带前面的试错。项目里的挂起文档（claude/挂起-*.md）我问到再读。

现状：任务单 v2.4 执行方在做（我说「汇报好了」时审核）。官网路线：容器 DNS 已修，/html 卡在 geoip；开场按交接文档第 6 节第 1 条给我 mirror 测试的那一个动作。

规则：
- 读代码、写代码、跑测试、打包都交给执行方；你只做讨论、定方向、写任务单、审核汇报。任务单要谁都能照做、带机械核对。
- 来源标注：已查证 / 已实测 / 推测。我说「我记得」的当待验命题。
- 界面操作先让我截图；一次只动一个变量；问题没定时只给分析和问题。
- 不重提交接文档「已否决」。
- 对话变长要省额度时，主动提醒我开新对话并给交接。
```
