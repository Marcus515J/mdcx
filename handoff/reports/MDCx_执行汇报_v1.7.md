# MDCx 执行汇报 v1.7

日期：2026-10-17（北京时间）。对应 `handoff/MDCx任务单_v1.7.md`，遵循 `handoff/README.md`。标记：【已查证】= 当前源码、GitHub API 或官方文档；【已实测】= 本轮实际运行；【推测/待核实】= 尚无实际环境或授权证据。

## 交付与边界

- 基线【已查证】：开工前联网 fetch 并通过 GitHub API 二次确认 `master = 2b4f01d63da395a446ba42859945b0f8ca670f40`，满足任务前提。
- 功能分支：`feat/llm-settings-and-cleanup`。代码提交：`57eea90352f555093acdcde4017764a9e1c98f71`。临时构建工作流提交：`7b295e5c2aa8c4d2685bae7e7ba21936d24d67d4`（独立提交，合并前删除）。
- 草稿 PR：https://github.com/Marcus515J/mdcx/pull/11，目标 `master`，未合并。
- Windows 测试构建：https://github.com/Marcus515J/mdcx/actions/runs/39034104912；artifact：[windows-x86_64-test-57eea90](https://github.com/Marcus515J/mdcx/actions/runs/39034104912/artifacts/12101278461)。
- handoff 分支只新增本报告；未改任务单或交接文档。未打标签，未创建/修改 Release，未修改 master。
- 未改变网站优先级、原有温度取值、Prompt、重试链路、D5/D10/D8、NFO 或用户配置。唯一新增设置是备用温度；无新增依赖。

## D11–D14c 实现及搜索结果

|任务|实际变化|文件|搜索结论|
|---|---|---|---|
|D11|固定帮助/状态文案的 DeepSeek 替换为“云端主模型”或“主接口”|`mdcx/controllers/main_window/llm_settings.py`、`local_model_settings.py`、`mdcx/local_model.py`|原列出的 5 处全部替换。全仓（含 `.ui`、生成 `.py`、docs）大小写不敏感搜索后，无其他固定界面厂商文案。`docs/llm-refusal.md:3` 保留并列入 D15；配置模型/模板中的默认 API URL 和模型 ID 以及合成测试数据继续保留，它们是可编辑配置值，不改用户配置或默认厂商。|
|D12|主、备用 API Key 都为 `EchoMode.Normal`；无显示/隐藏按钮|`llm_settings.py`；调整已有 `tests/test_llm_settings_ui.py`|修改前整个仓库的 `EchoMode.Password` 仅这两处生产设置及一个测试断言；修改后搜索无结果。没有发现范围外的其他密码模式需要改动。|
|D13|新增 `llm_fallback_temperature`；备用超时下方新增“备用温度”，与主温度相同范围 0–2、步长 0.1、两位小数|`mdcx/config/models.py`、`resources/config/default_config.json`、`llm_settings.py`、`mdcx/base/translate.py`、新增 `tests/test_llm_temperature.py`、扩展设置 UI 测试|主请求始终用 `llm_temperature`；备用请求始终用新字段。缺少新字段时，Pydantic 默认工厂取同一份配置已解析的主温度（不是写死 0.9）。默认模板主/备均保持 0.9。|
|D14a|去掉反馈常量、启动反馈日志、配置错误中的提 Issue 链接、全部 Issue 模板和 stale workflow；错误详情及新版本下载入口保留|`mdcx/consts.py`、`main_window.py`、`load_config.py`、`.github/ISSUE_TEMPLATE/` 三文件、`.github/workflows/close-stale-issues.yml`、README；同步 `tests/test_version.py`|重搜 `issues`、`GITHUB_ISSUES_URL`、问题反馈/Bug 反馈：无产品反馈入口残留。保留技术出处：`scripts/build.py:275` runner-images #7522、`mdcx/crawlers/javdb_new.py:28` cssselect #138、`mdcx/crawlers/dmm_new/__init__.py:485` sqzw #393、`todo.md:13` 历史需求 #668。`changelog.md:26` 是历史发布描述，按 D15 只列建议。GitHub API 实查 `has_issues=false`，未改仓库设置。|
|D14b|只调查，详见下节|无生产代码/数据库/Release 改动|当前本仓库同名数据库 Release 404；可用附件来自 sqzw-x。|
|D14c|删除 Telegram/交流群整节和 Bug 反馈提示；来源链补为 sqzw-x → Hazard804 → Marcus515J|`README.md`|GitHub API 实查本仓库 parent 为 Hazard804/mdcx；历史来源、致谢、许可证正文均保留，LICENSE 未改。|

### D13 与实际验证

原备用请求【已查证】：`mdcx/base/translate.py` 从主请求字典展开参数，只覆盖 `max_try=1`，因此**原本确实发送 temperature，且与主温度相同**。本轮只在备用调用覆盖 temperature，不改变模型选择、Prompt、代理、超时或拒绝检测。

新增 6 项测试：2 项 HTTP MockTransport 请求体测试（主温度/备用温度分别 0.35/1.25 和 2/0，覆盖主重试及备用）、3 项旧配置文件加载及保存再载入（主温度 0/0.37/2）、1 项实际 Qt 控件范围/载入/保存/重载测试。MockTransport 在 HTTP 边界截获真实 OpenAI SDK 序列化后的 JSON，请求不出网、不调用任何真实模型 API。

- 环境：本机 macOS arm64，Python 3.13.14，`uv sync --locked --dev` 使用现有锁定依赖。
- 定向命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_llm_temperature.py tests/test_llm_settings_ui.py tests/test_llm_refusal.py tests/test_local_llm.py`：**82 passed, 1 skipped, 0 failed**（14.19 秒）。跳过项为 Windows 原生路径分隔符检查，本机是 Mac。
- 首次沙箱内跑定向测试：60 passed、1 skipped、22 errors，错误全部为既有本机 HTTP 测试服务绑定端口被拒（PermissionError）；未将其隐藏为通过。在允许绑定回环端口的环境重跑后得到上述 82/1/0。
- 第一次全量：773 passed、14 skipped、2 failed；两项旧版本日志测试以 `links[0]` 假定总有反馈链接，删除反馈后无新版本时本应无链接。已改成验证下载链接是否存在，并增加无反馈入口和无新版时不发送链接的断言。
- 最终全量命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`：**775 passed, 14 skipped, 0 failed**（95.63 秒）。
- `ruff check`、`ruff format --check`、`git diff --check`：全部通过。
- 额外实际运行 `_show_version_thread` 的三条模拟路径（无法获取版本、当前版、较新版）：均无反馈文字；仅较新版显示下载入口。实际创建并显示翻译 Qt 页面，检查明文模式和备用控件。截图只含合成/空配置，不含用户 Key。
- 既有警告：zhconv 的 pkg_resources 弃用、AsyncLimiter 跨事件循环复用；本轮未扩大范围修改。Mac 独立 UI 进程还出现 av/cv2 动态库重复类警告，进程正常退出。

## D14b 演员资料库调查（本轮没有发布）

### 上游、附件与兼容性

【已查证，GitHub API】

|仓库|同名 Release|发布日期（UTC；北京时间 +8）|说明文字|附件|
|---|---|---|---|---|
|`Hazard804/mdcx`|`GET /repos/Hazard804/mdcx/releases/tags/actor_info_database` 返回 404；分页列出现有公开 Releases 亦未找到此项|无|无|无|
|`sqzw-x/mdcx`|[actor_info_database](https://github.com/sqzw-x/mdcx/releases/tag/actor_info_database)，Release ID 128281322|2023-11-07 09:14:29 UTC（北京时间 17:14:29）|API `body=""`，无说明文字|下表两项；附件上传日期晚于 Release 发布日期，不能混用|

|附件|精确字节数|大小（MiB）|上传/更新时间（UTC）|
|---|---:|---:|---|
|`Actress-20231123.db`|10,977,280|10.47|2023-11-23 13:12:33 / 13:13:08|
|`Actress-20250220.db`|12,615,680|12.03|2025-02-20 09:50:08 / 09:50:28|

附件直链：[20231123](https://github.com/sqzw-x/mdcx/releases/download/actor_info_database/Actress-20231123.db)、[20250220](https://github.com/sqzw-x/mdcx/releases/download/actor_info_database/Actress-20250220.db)。推荐迁移较新的 20250220，但它并不代表资料更新至当前 2026 年。

【已实测】下载 20250220 附件到临时目录，精确大小 12,615,680 字节，SHA256：`251206ca729bb6fcdd55a88b228dfb1f6beb8d069dce947d90acb6750a50c9d8`。SQLite 以 `mode=ro` 打开，`PRAGMA quick_check` 返回 `ok`；包含 `Info`（21,860 行）、`Names`（42,185 行）、`Urls`。已核对当前读取的列全部存在，未更改数据库、未提交附件、未连用户媒体库。

【已查证】`init.py:281–283` 仅用浏览器打开本仓库的同名 Release；不会自动下载或安装。`ActressDB.init_db` 从配置 `info_database_path` 打开 SQLite；`use_database` 控制启动初始化及演员补全。实际读取 `Info` 和 `Names`（姓名/别名、三围、生日、出生地等），用于 Emby/Jellyfin 演员信息补全；不是刮削影片本身的必需库。因此同名 Release 挂原附件即可恢复现有入口，无需此轮改代码。

### 不干扰最新正式版的方案

【已查证】本仓库更新检查使用 `mdcx/consts.py` 的 `releases/latest`，由 `mdcx/base/web.py:760–808` 解析；当前 API 返回 `v1.1.0`。该代码还明确排除 draft/prerelease，并只接受语义版本。

【已查证，官方规则】GitHub 的创建 Release API 支持 `make_latest=false`，草稿和预发布不能设为 latest。依据：[GitHub Releases REST API](https://docs.github.com/en/rest/releases/releases#create-a-release)。

建议未来发布采用 **标签 `actor_info_database`、`prerelease=true`、`make_latest=false`** 两层约束；发布前后都核对 `releases/latest` 仍为当时的正式版本。标题注明“演员资料库（资源包，非程序升级）”。本标签不匹配 `release.yml` 的 `v*.*.*` 触发规则，不应触发正式程序发布；不得手动 dispatch 正式 release workflow。【推测/待实测】此方案按 API 及代码不会干扰更新，但本轮禁止发布，所以没有在本仓库创建后实证。

### 大小、许可与替代方案

【已查证】GitHub 单个 Release 附件必须小于 2 GiB，当前较新数据库仅 12.03 MiB，无需拆分或 Git LFS。依据：[GitHub Release 配额](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)。

【已查证】sqzw-x 仓库有 GPL-3.0 LICENSE；README 另有项目使用条款；数据库 Release 正文为空，没有单独的数据库授权说明。**【待核实】代码仓库的许可证是否覆盖采集的数据库内容和全部来源权利，不能仅凭公开下载断言可转载。** 本轮未获数据库维护者的单独转载说明，未来发布前需要核对来源/许可，保留作者和出处；若需要外部联系，另由用户授权。

若明确禁止转载或授权仍不清楚：本仓库只记录原始附件链接和来源说明，用户自行从上游下载，或获得许可后再托管；不擅自重新包装、转镜像。若未来文件超过附件上限：按许可提供分卷或由许可允许的存储托管并给校验值，不能直接把大数据库塞进 Git 历史。本轮没有实施这些替代方案。

### 发版那一轮的完整操作顺序（本轮均未执行）

1. 先由用户确认发布与转载授权，确定采用 20250220 及署名/许可证说明。复查上游附件是否变化和当时最新正式版，记录附件 ID、大小、SHA256 与来源。
2. 下载到临时目录，只读 `PRAGMA quick_check`，核对 `Info/Names` 字段与当前 reader；备份现有用户数据库（若用户本机已有），不覆盖它。
3. 在本仓库选定当时的正式 master 提交作为资源标签目标；确认 `actor_info_database` 尚未存在，且不会触发 `v*.*.*` 程序工作流。
4. 用 Releases API 建立 **draft=true、prerelease=true、make_latest=false** 的资源草稿；tag_name 为 `actor_info_database`。Release 正文写明上游链接、附件版本、原作者/许可、大小、SHA256 和“资源包、不是程序版本”。这一步会创建/使用资源标签，只能在获得未来那轮发布授权后做。
5. 向该草稿上传原始 `Actress-20250220.db` 和校验清单（以及许可要求的说明），核对服务端 size、下载后 SHA256；不得修改数据库内容或混入私人资料。
6. 再用 API 将 `draft=false`、继续保持 `prerelease=true`、`make_latest=false`，不启用讨论、不 dispatch 正式程序发布。
7. 复查本仓库 `releases/latest` 仍是第 1 步记录的正式版本；从现有“下载演员资料库”按钮打开新链接，下载附件后只读校验。
8. 用户在“设置 → 演员 → 补全信息”选择该文件，开启“使用数据库”，对一个已知演员验证，检查命中日志和 Emby/Jellyfin 更新。最后记录资源 Release 链接、校验和、许可依据及实际验证结果。

## D15 文档与无关内容清单（仅建议，未按此清单修改）

以下代码依据已对照当前功能分支；源码行号以本轮版本为准。D14a/D14c 已授权的反馈和 README 改动除外，其余文件未动。

### 1. 软件内“使用说明”逐条核对

【已查证】以下 `.ui` 是源，`.py` 是实际运行的生成副本；两处均已读取。

|位置|内容摘要|与当前版本是否相关（代码依据）|建议|理由|
|---|---|---|---|---|
|`MDCx.ui:23153-23157` / `MDCx.py:11336-11340`|上游地址：Movie_Data_Capture、AVDC、northsea4/mdcx-docker；说明内容来自 AVDC|README 与 `mdcx/` 仍保留上游来源；docker 不是本仓库 Windows/Mac 发行版|重写|保留来源署名；重写成当前上游链条，并将 docker 标为外部部署方案|
|`MDCx.ui:23159-23163` / `MDCx.py:11342-11346`|目录：功能简介、项目简介、番号命名、设置说明|对应后续条目|重写|保留，重排为可点击/可跳转的 HTML 目录|
|`MDCx.ui:23165-23166` / `MDCx.py:11348-11349`|日本电影元数据抓取，配合 EMBY/KODI/PLEX|当前仍写 NFO/封面/缩略图/背景图（`mdcx/core/nfo.py`, `core/web.py`, `scraper.py`）；UI 亦含 Emby/Jellyfin|重写|保留但重写：说明现支持多来源、Emby/Jellyfin 等，不只“日本电影”|
|`MDCx.ui:23168-23172` / `MDCx.py:11351-11355`|“Gui made by moyy996/Core made by yoshiko2”、旧 AVDC 项目与 AVDC releases|当前仓库代码与发行入口为 Marcus515J；README 上游链仍有这些署名|重写|保留致谢；旧 AVDC EXE 下载地址建议删除/改为历史来源，避免用户下载错误发行版|
|`MDCx.ui:23174-23178` / `MDCx.py:11357-11360`|标准有码：`SSNI-111`、`ssni00111`|`mdcx/number.py` 有 `[A-Z]{2,}-\d+`、`([A-Z]{2,})00\d{3}` 等提取规则|保留|保留；补充“示例、不区分大小写、实际以站点支持为准”|
|`MDCx.ui:23181-23182` / `MDCx.py:11364-11365`|无码：`111111-1111`、`111111_111`、`HEYZO-1111`、`n1111`|`number.py:UNCENSORED_DIGIT_NUMBER_PATTERN`、`is_uncensored`、HEYZO 分支均存在|保留|保留；明确 `111111-1111/…` 已归一化，避免误解为仅示例|
|`MDCx.ui:23185-23188` / `MDCx.py:11368-11371`|素人/Mgstage、LUXU、FC2 三种格式|`number.py` 的通用 `[A-Z]+-\d+`、`get_file_number` FC2 分支；`core/file.py` 与 `config` 仍有 FC2 网站|保留|保留；FC2 文字需注明 `FC2-PPV`/`FC2PPV` 会归一为 `FC2-数字`，不要承诺所有 FC2 变体|
|`MDCx.ui:23191-23192` / `MDCx.py:11374-11375`|欧美：`sexart.11.11.11`（系列.年.月.日）|`number.py:get_file_number` 日期正则与 `ManualConfig.OUMEI_NAME` 映射仍在，`config.models.py:441` 有欧美来源|重写|保留并改为“示例，日期可 2/4 位”；代码会输出规范化系列名与日期|
|`MDCx.ui:23195-23196` / `MDCx.py:11378-11379`|自带字幕：`-c/-C`、`-CD1-C`|相关，但取决于配置：`core/file.py:431–475` 按 `LETTER/ENDC` 判定 C 是否为分集；`560–660` 按 `cnword_char` 或字幕文件设置字幕。默认 JSON 未启用 ENDC，Config 类默认列表含 ENDC，不能泛称所有旧配置行为一致。|重写|说明 -C 的字幕与字母分集冲突如何按实际开关解释；区分用户配置和默认模板，不改本轮配置。|
|`MDCx.ui:23199-23200` / `MDCx.py:11382-11383`|多集仅写 `-CDn/-cdn`，并声称不支持 `-A -B -1 -2`，且原样 `**`|`core/file.py:423-475` 默认支持 `CD/PART/HD`、单数字、字母结尾、数字中间；`config.models.py:572-581` 默认 `CDChar` 含 LETTER/ENDC/DIGITAL/MIDDLE_NUMBER；UI `MDCx.ui:10684-10965` 明确 `-1`、`-A`、`-C` 可勾选|重写|**必须重写**：现文字与代码相反，不能说不支持 `-1/-A/-B`；按当前开关解释“默认识别”和 C 字幕冲突规则；把 Markdown 星号改 HTML `<b>` 或普通标点|
|`MDCx.ui:23203-23204` / `MDCx.py:11386-11387`|`CD1-C`：分集在前、字幕靠近扩展名|相关，但原顺序说明过于绝对：`core/file.py:255–288` 命名模板渲染完成后才追加 cd_part；`:666–676` 显示名也先字幕、后分集。|重写|重写为当前实际顺序与配置项，避免把单一示例当硬约束|
|`MDCx.ui:23207-23208` / `MDCx.py:11390-11391`|外挂字幕同名，支持 srt/ass/sub|`core/file.py:580-660`、`config.models.py:597-600` 从 `sub_type` 列表读取并复制；默认/用户列表可能扩展|重写|保留；改为“按设置中的字幕扩展名”，并说明 `.chs` 与字幕目录补全功能|
|`MDCx.ui:23210-23213` / `MDCx.py:11394-11396`|设置说明及旧 AVDC README 链接|当前设置已大幅扩展，README 的正式功能文档为本仓库 `docs/`|重写|重写：移除旧 AVDC README 主入口，指向本仓库 README/docs 和分节锚点|
|`MDCx.ui:23216-23218` / `MDCx.py:11399-11401`|刮削模式/整理模式|`save_config.py:732-741` 保留 `main_mode=1` 正常、`2` 整理；`scraper.py:821-823` 仍处理整理模式|保留|保留但补充更新/读取模式（`main_mode=3/4`）和当前“文件清理”入口|
|`MDCx.ui:23221-23223` / `MDCx.py:11404-11406`|软链接：需管理员；只展示不能播放|`core/file.py:129-172` 仍创建软/硬链接且有平台限制；`init.py:95-114` 说明 Windows/NAS/Emby；是否播放取决媒体库/路径|重写|重写：管理员要求是 Windows 权限条件，不应绝对说“不能播放”；补充 Mac 硬链接限制与硬链接模式|
|`MDCx.ui:23226-23227` / `MDCx.py:11409-11410`|调试模式输出元数据|`core/utils.py:135`、UI `调试模式（日志页面）` 仍存在|保留|保留；补充日志/诊断用途，避免暗示只输出番号元数据|
|`MDCx.ui:23230-23231` / `MDCx.py:11413-11414`|排除目录|`config`/文件遍历仍有排除目录与 `_待删` 清理目录|保留|保留；与文件清理文档合并说明优先级|
|`MDCx.ui:23234-23235` / `MDCx.py:11417-11418`|视频目录递归遍历|主流程文件爬取递归仍在 `core/file.py`/`file_crawler.py`|保留|保留；补充“待刮削目录”和清理排除目录语义|
|`MDCx.ui:23238-23242` / `MDCx.py:11421-11425`|命名模板：目录/媒体库标题/本地文件；字段 title/actor/studio/director/release/year/number/runtime/series/publisher|相关但语法过时：`core/naming/template.py` 使用 Jinja2；`fields.py:FIELD_DESCRIPTIONS` 有 24 项字段；`core/file.py:_generate_file_name` 与 NFO 标题分别渲染。|重写|原文仅用 title/actor 等裸字段描述模板，需写当前 {{ number }} 等 Jinja2 语法及字段表；区分目录、本地文件、NFO 标题。|
|`MDCx.ui:23245-23255` / `MDCx.py:11428-11438`|旧 `proxy=...`、timeout 3-10 秒、retry 2-5|当前代理/CF Bypass 是 UI 和 config 字段，网络重试在 `base/web.py`, `web_async.py`；设置项已不再以旧 INI 行为主|重写|重写，删除旧 INI 示例和“建议日本代理”；写当前 UI 的代理、CF Bypass、读取超时/重试含义|
|`MDCx.ui:23258-23259` / `MDCx.py:11441-11442`|PLEX 需装 XBMCnfoMoviesImporter|代码仍生成 NFO，但当前发行目标/文档覆盖 Emby/Jellyfin；无插件安装逻辑|保留|保留为 Plex 外部兼容提示，标注外部插件版本与链接需联网核验|
|`MDCx.ui:23262-23265` / `MDCx.py:11445-11448`|排除字符/目录/字符串|`config.models.py` 仍有 `prevent_char`、`exclude_folder`、`escape_string` 等并在 `number.py`/文件扫描使用|重写|保留但改名匹配现 UI 字段；补充文件清理的包含词/完整名/扩展名规则|
|`MDCx.ui:23268-23270` / `MDCx.py:11451-11453`|网站列表（avsox…missav），警告 JAVDB 约 30 次封 IP|当前 `ManualConfig.SUPPORTED_WEBSITES`、`mdcx/crawlers/` 站点远多于列表；JAVDB 限流属于随站点变化的经验|重写|重写为动态“来源网站选择”；删除硬编码旧列表与无依据“30 次”警告，改为遵守站点限制|
|`MDCx.ui:23273-23274` / `MDCx.py:11456-11457`|日志保存到程序目录 Log，每次运行 txt 可删除|相关，路径描述不准确：`main_window.py:_write_main_logs_to_file` 在 `manager.data_folder / "Log"` 写时间命名 txt；本机模型在配置目录 `logs/hymt2/<本次子目录>`，有应用数据目录降级。|重写|重写路径/文件名为当前平台实际日志目录，并链接到诊断说明|
|`MDCx.ui:23277-23278` / `MDCx.py:11460-11461`|刮削失败后不移动或移动到失败目录|`config.models.py:337`、`core/file.py:789-834` 仍有 `failed_file_move` 与失败目录；文件清理还新增演练/待删/永久删除|保留|保留基础语义，补充失败移动与垃圾清理是两套开关及安全行为|


排版与正确修改方式【已查证】：

- HTML 起于 `MDCx.ui:23138`，页面内容约 `23153–23279`；生成副本约 `MDCx.py:11336–11461`。大量空 `<p>`、`<br>` 以及 `margin-top/bottom:12px` 重复叠加产生大段空白；例如 `23179–23180`、`23189–23190`、`23193–23194`。建议用统一 HTML 段落边距，删除重复空段，仅列建议。
- `MDCx.ui:23200` 把 Markdown 的 `**` 放在 HTML span 文本中；`QTextBrowser.setHtml` 不会把它转换成加粗，所以显示字面星号。建议用 `<b>` 或普通文字；生成副本的 `setHtml` 含同样字符串。
- `MDCx.py` 文件头明确是 PyQt6 6.11.0 `pyuic6` 生成文件，手改会覆盖。正确顺序是编辑 `mdcx/views/MDCx.ui` → 在项目依赖环境执行 `sh scripts/pyuic.sh`（脚本含两条 pyuic6 生成命令，亦可仅运行主窗口对应那一条）→ 核查生成 diff、运行 Qt 页面。格式检查对生成文件有既有排除，不要借此全量格式化生成文件。
- 本轮没有修改 `.ui`、生成 `.py` 或这份说明正文。未来说明改版也应保留原作者致谢和许可，只把历史下载入口与当前下载入口区分清楚。

补充【已实测】：调用当前 `get_file_number`，上述标准有码、数字无码、HEYZO、n1111、LUXU、FC2-PPV/FC2PPV、欧美两位/四位年份示例均实际提取成功。使用说明 HTML 直接从 XML 解析，确认 `**不支持` 仍是字面文本；本轮未改说明。

### 2. README、开发说明、历史记录、docs 全部文件

|位置|内容摘要|与当前版本是否相关（代码依据）|建议|理由|
|---|---|---|---|---|
|`README.md:5–16`|来源链及致谢|相关；本仓库 API parent 是 Hazard804，README 的源项目链仍适用|保留|D14c 本轮已补 Hazard804；其他作者/历史来源保留。链接可达性另表。|
|`README.md:18–33`|当前版本、Windows/Mac 下载、功能文档、构建说明|相关；`consts.py/pyproject.toml/release.yml` 均是 v1.1.0 及 Windows x86_64/Mac arm64|保留|当前正式版本事实正确；后续发版再更新，文档入口有用。|
|`README.md:10–11`|anyabc 在 2023 年销号删库的历史断言|是来源历史，不是当前功能；本轮该 URL HTTP 200，不能据此证实同一原仓库/作者身份|重写|下一轮考虑改成可证实的历史分发说明；HTTP 200 不等于历史断言被推翻，保留出处和署名。|
|`README.md:35–43`、`LICENSE`|授权及上游条款|相关；现仓库继承 GPLv3 许可证文件和署名|保留|本轮任务明确不得删改 LICENSE 或上游署名。数据库转载权不由此自动认定。|
|`CONTRIBUTING.md:1–62`|uv/Python、运行测试、版本和构建发布流程|相关；pyproject 与 scripts/build.py、bump.py、check_release_version.py、release.yml 均存在|保留|当前开发与验证入口有效；正式发布说明不用于本轮 artifact。|
|`CONTRIBUTING.md:64–68`|新增配置的 manager 导入和控件绑定说明|部分过时；文中 `mdcx.models.config.manager` 实际不存在，当前是 `mdcx.config.manager`；已有 llm_settings 等独立控制器|重写|修正导入路径并说明配置可能在子模型中、动态控件有自己的 load/save，而非全放一个 Config 类/文件。|
|`CONTRIBUTING.md:70–75`|Qt Designer、pyuic 与事件处理|相关；`.ui`、scripts/pyuic.sh、init.py 与控制器仍在|保留|生成关系正确；可补充动态设置布局文件与只生成改动窗口的方法。|
|`CONTRIBUTING.md:77–97`|代码树、build.sh/changelog.sh|部分过时；脚本实际是 build.py/changelog.py；base/core 在 mdcx 顶层，不是 models 内|重写|按真实目录更新，避免新开发者找错路径；本轮未改。|
|`changelog.md:1–36`|v1.1.0 发布历史|相关；历史功能在 file cleanup、base/translate、local_model 和版本代码中均存在|保留|发布记录不应改写成现行设置说明。该文件未声明“主备共用温度”；独立备用温度应记入下一正式版变更，而非改写本版历史。|
|`changelog.md:26`|“更新、下载和反馈入口指向本仓库”|v1.1.0 的历史事实；本轮反馈入口已删除|保留|留历史条目；下一版注明移除反馈，避免当成当前使用说明。|
|`todo.md:1–3`|截至 10-02 的 v1.0.2 状态|已过时；当前源码和 Releases 均 v1.1.0|重写|加日期并更新现状，或把此段标为历史快照，不能继续称当前最新。|
|`todo.md:7`|PR #1 已关闭且不实施|历史决策；不是当前待开发任务|保留|防止重复提出已结束事项。|
|`todo.md:9–18`|#668、rjsf propertyNames、browser log、图片日志候选|混合；#668 是历史需求来源；当前桌面 Qt UI，不见 rjsf UI；browser.py、日志和图片下载代码仍在|重写|rjsf 若无具体当前入口建议删除该候选；其余按用户需求和现有代码复核，保留“未承诺实施”，本轮不实施。|
|`docs/garbage-cleanup.md:1–49`|清理入口、规则/排除、演练/移到待删/永久删除、安全与测试|相关；`base/file.py` 清理函数、`file_cleanup_settings.py`、测试均存在|保留|用户新增功能的现行说明，规则和安全行为应留。|
|`docs/garbage-cleanup.md:28`|“不新增配置项或依赖”|配置表实际列了多个 garbage_* 字段，源码也存在；可能是某轮增量改动的上下文|重写|改成明确的版本范围，避免读者误以为整个清理功能没有新增配置。|
|`docs/garbage-cleanup.md:30–31`|尚未收到实际旧 JSON、具体迁移待验证|是过去执行状态，不是长期用户说明；当前有合成迁移测试|重写|区分已自动验证的兼容承诺与当时未收到用户配置的事实，去掉过期会话口吻。|
|`docs/llm-refusal.md:3`|日常方案固定 DeepSeek|功能相关，固定厂商文案与本轮 D11 相冲突|重写|只在 D15 列项，本轮未改；未来改成云端主模型。|
|`docs/llm-refusal.md:15,27`|主备用共用温度及 Prompt|Prompt 仍共享；温度已在本轮独立|重写|新增备用温度行、解释旧配置继承主温度；不能把 Prompt 一并说成独立。|
|`docs/llm-refusal.md:5–34` 其余|字段独立翻译、拒绝/错误回退、本机隔离代理及边界|相关；`base/translate.py`、`llm.py`、local_model 控制器及测试保持|保留|用户新增翻译功能说明有效，无需整篇删除。|
|`docs/local-models.md:1–33`|模型发现/启动/停止、ID、Windows/Mac 范围、日志|相关；`local_model.py`、`local_model_settings.py` 有对应实现|保留|用户新增的现行文档，保留跨平台限制和不停止外部服务的说明；路径可细化到每次运行子目录。|
|`docs/pyqt6-migration.md:3–5`|“当前使用 PyQt5/Qt5”|过时的背景描述；依赖和 imports 现为 PyQt6|重写|加历史时点/迁移已完成，不能让读者误以为仍未迁移。|
|`docs/pyqt6-migration.md:7–58`|API 差异、第一阶段范围、后续建议、第二阶段进展、验证清单|多数相关；现有 style.py、init 与 Qt6 API 支持这些条目|保留|作为开发迁移记录有用；把已完成与建议项标明，避免把旧计划当当前任务。|
|`docs/crawler-migration.md:1–159`|新版框架、迁移步骤、字段兼容、测试、站点清单与 airav 下线|相关；`crawlers/base/*`、register_crawler 与文中列出站点可在注册表找到，airav_cc 保留|保留|开发文档有用；“迁移优先级”列出的一些站点后来已迁移，建议注明历史计划并以注册表为现状依据，不当成仍待实施。|

### 3. `.github/workflows/` 全部工作流

|位置|内容摘要|与当前版本是否相关（代码/触发条件依据）|建议|理由|
|---|---|---|---|---|
|`ci.yaml`|master/develop 的 push/PR 运行 ruff 与 pytest|相关；本 PR 实际触发并运行|保留|能阻止格式、静态、回归失败，不证明外站可达或用户本机 UI 体验。develop 属继承配置，未证实可删除，不擅改。|
|`release.yml`|v*.*.* 标签或手动输入标签，构建 Win/Mac、核验版本、发布成品|相关；当前正式发行入口|保留|本轮未触发；禁止用它交付临时测试版。|
|`finalize-v1.1.0.yml`|固定提交、run ID、SHA256 的一次性发布收尾|历史用途；源码固定 b2836534 / run 38244146018 / v1.1.0；仍可手动 dispatch 或特定 master 路径推送触发|删除|建议下一轮删除或移出 workflows 归档，防止误重跑历史发布；本轮 D15 不删不改。|
|`close-stale-issues.yml`（基线文件）|定期处理旧 Issues|无关；当前 has_issues=false 且本轮移除整个反馈渠道|删除|属于 D14a，本轮已删除，不是借 D15 扩大范围。|
|`test-build-windows.yml`（本轮临时）|固定代码提交的 Windows 测试与 artifact|与本轮测试交付相关，长期发行无关|删除|本轮按任务单单独提交并保留供下载；合并前删除，无标签/Release。|


### 4. 软件内其他外链与关于类内容

【已实测，2026-10-17】用只读 HTTP GET 跟随重定向记录下表状态；200 仅证明页面可达，不等于附件可下载、教程仍适用或该外部项目适用于本发行版。403 也不能认定帖子已删除。未登录任何第三方网站，没有上传资料。

|位置|内容摘要/链接|与当前版本是否相关（依据及访问结果）|建议|理由|
|---|---|---|---|---|
|`init.py:272` / 演员头像标签|[AVDC 头像包](https://github.com/moyy996/AVDC/releases/tag/%E5%A4%B4%E5%83%8F%E5%8C%85-2)|相关的可选资源；当前演员头像功能仍在 `tools/emby_actor_image.py`，非本仓库安装包；HTTP 200|保留|资源和 Win/Mac 功能可能相关；注明外部旧资源及版本，未批量下载头像附件验证。|
|`init.py:275–278` / 字幕包和标记包两个标签|[Dropbox 资源目录](https://www.dropbox.com/sh/vkbxawm6mwmwswr/AADqZiF8aUHmK6qIc7JSlURIa)|两个按钮共用该 URL；字幕/水印功能仍在，但未核实目录内具体资源是否匹配当前功能；HTTP 200；最终 https://www.dropbox.com/scl/fo/t2ornqip90wcaaxlgb1ai/AMxgPxN00ZkrguwaMttTrOQ?rlkey=i01dkl7fvxhpwxv264g3gb365|重写|跳转到新式共享目录且返回 200；应核对内容后分别命名或换有效资源，不能把 HTTP 200 当成资源已验证。|
|`init.py:280` / `MDCx.ui:20739`|[百度贴吧 Cookie 演示](https://tieba.baidu.com/p/5492736764)|Cookie 设置仍在；本站请求返回 403，无法从本轮环境读取教程；HTTP 403|重写|建议用当前界面的教程替代外站旧动画；不能宣称帖子已失效或用户浏览器一定打不开。|
|`init.py:281–283`|[本仓库演员数据库](https://github.com/Marcus515J/mdcx/releases/tag/actor_info_database)|`ActressDB` 仍读取，Win/Mac 都能用 SQLite；404 确认该资源入口当前不存在；HTTP 404|保留|功能保留；按 D14b 授权后托管附件再恢复入口，本轮不发布。|
|`MDCx.ui:12936–12938` / `.py:10812–10814`|[Emby 命名文档](https://support.emby.media/support/solutions/articles/44001159102-movie-naming)|多版本/分集命名与当前软件相关；200，跳转到 emby.media 新主机；HTTP 200；最终 https://emby.media/support/solutions/articles/44001159102-movie-naming/|保留|可更新为最终地址，仍为官方资料；不需随软件代码一起删除。|
|`MDCx.ui:21482–21484` / `.py:11223–11225`|[ThePornDB Token 入口](https://theporndb.net/)|当前 `crawlers/theporndb.py` 和 Token 设置仍在；200，跳转 /login；HTTP 200；最终 https://theporndb.net/login|保留|登录入口可达；未测试用户账号、Token 或真实 API。|
|`MDCx.ui:23153,23170` / 关于与正文|[Movie_Data_Capture 来源](https://github.com/yoshiko2/Movie_Data_Capture)|历史来源仍相关；200，跳转到 mvdctop/Movie_Data_Capture；HTTP 200；最终 https://github.com/mvdctop/Movie_Data_Capture|保留|保留原作者署名；链接可标注迁移后的项目，不能当本仓库成品下载入口。|
|`MDCx.ui:23154,23157,23171`|[AVDC 来源与旧说明出处](https://github.com/moyy996/AVDC)|源码继承来源相关，当前发行版不等于 AVDC；200；HTTP 200|保留|保留致谢；当前操作说明应针对本仓库重写。|
|`MDCx.ui:23155`|[northsea4/mdcx-docker](https://github.com/northsea4/mdcx-docker)|200；外部容器/Web/远程桌面方案，本仓库 release.yml 只构建 Windows/Mac；HTTP 200|重写|可放“其他部署/上游资源”，明确非本仓库 Windows/Mac 成品、不承诺本版本兼容。|
|`MDCx.ui:23172`|[旧 AVDC EXE 下载](https://github.com/moyy996/AVDC/releases)|200；下载的是旧 AVDC，非本仓库当前安装包；HTTP 200|重写|主下载入口换成本仓库 Releases，历史 AVDC 链接作为来源保留，避免混装。|
|`MDCx.ui:23213`|[旧 AVDC README 使用教程](https://github.com/moyy996/AVDC/blob/master/README.md)|200；历史教程与当前新增功能不完整对应；HTTP 200|重写|主教程改成本仓库 README/docs；署名和历史参考保留。|
|`README.md:10`|[anyabc 历史分发](https://github.com/anyabc/something/releases)|200；是 README 中的历史链条，不是本仓库当前发行入口；HTTP 200|保留|可达性不能证明当前该路径与历史账号身份一致，也不能证实历史删库说法；建议历史断言加来源。|
|`README.md:12`|[sqzw-x 上游](https://github.com/sqzw-x/mdcx)|200；当前代码来源链和数据库上游相关；HTTP 200|保留|上游署名必须保留。|
|`README.md:13`|[Hazard804 直接上游](https://github.com/Hazard804/mdcx)|200；GitHub API 确认本仓库 parent；HTTP 200|保留|D14c 本轮补齐。|
|README 下载及软件版本点击|[本仓库 Releases](https://github.com/Marcus515J/mdcx/releases)|200；当前 Win/Mac 发行入口，consts/init/main_window 仍使用；HTTP 200|保留|与当前成品直接相关。|
|`todo.md:13`|[上游 #668 历史需求](https://github.com/sqzw-x/mdcx/issues/668)|200；技术出处，不是本仓库反馈渠道；HTTP 200|保留|按 D14a 技术出处例外保留，不能因含 issues 字符就删掉。|


### 5. 新版“使用说明”大纲（仅标题，不写正文）

1. 适用版本与平台、首次设置和当前下载入口。
2. 快速开始：选择待刮削目录、保存配置、选择模式、开始与查看结果。
3. 番号和文件名：有码/无码/素人/FC2/欧美；字幕 `-C`、分集 `-CDn/-PARTn/-HDn/-1/-A` 及 C 冲突开关。
4. 模式与输出：正常/整理/更新/读取，成功与失败文件处理，软硬链接与平台条件。
5. 命名模板：Jinja2、可用字段、目录/本地文件/NFO 标题与后缀。
6. 来源和网络：站点/字段优先级、Cookie/Token、代理、CF Bypass 与限时含义。
7. 文件清理：扩展名/完整名/包含词、排除、演练、待删目录、永久删除及文件保护。
8. 云端翻译与本机备用：主接口、拒绝/错误重试、独立主备温度、共享 Prompt、失败保留原文。
9. 本机模型管理：查找/验证/选择、手动启停、模型 ID、日志、外部服务和 Windows/Mac 边界。
10. 字幕、水印、封面及其他资源下载的适用范围。
11. 演员资料：头像、SQLite 数据库、Emby/Jellyfin 补全与资源版本。
12. 日志与恢复：实际路径、失败目录、配置兼容和常见权限/网络问题。
13. 上游来源、外部参考、致谢和许可证。

## CI、Windows 测试交付与未验证部分

【已查证/已实测】

- [PR CI run 39034125344](https://github.com/Marcus515J/mdcx/actions/runs/39034125344)：Code Quality **success**；Ubuntu 全量测试 **775 passed, 14 skipped, 0 failed**（121.75 秒）。
- [Windows run 39034104912](https://github.com/Marcus515J/mdcx/actions/runs/39034104912)：**success**；原生 Windows 设置/温度/版本测试 **51 passed, 0 skipped, 0 failed**（8.27 秒），包含本机 Mac 跳过的 Windows 路径验证。构建前源码版本和构建后 EXE 内嵌版本检查均通过（v1.1.0）。
- [下载 Windows 测试 artifact](https://github.com/Marcus515J/mdcx/actions/runs/39034104912/artifacts/12101278461)：`windows-x86_64-test-57eea90`，ZIP 152,871,454 字节（145.79 MiB），含 `MDCx-v1.1.0-TEST-57eea90-windows-x86_64.exe` 及 `SHA256SUMS.txt`。需登录 GitHub 下载，保留至 **2026-10-31 20:52:13（北京时间）**。
- GitHub 返回的 **artifact ZIP** SHA256：`fea41bfb9a469405c8af96a31644bbd4bed88d4ba04568249512e163ed60d905`；EXE 自身校验值在随包 `SHA256SUMS.txt`，二者不可混用。
- 最终 PR API 状态：`isDraft=true`、`state=OPEN`、`mergedAt=null`、`mergeable=MERGEABLE`；3 项检查（Code Quality、Tests、build）均 SUCCESS。

- Windows artifact 固定代码提交 `57eea90`；工作流本身在 `7b295e5` 独立提交，合并前删除。成品仍使用源码正式版本 v1.1.0，文件名追加 TEST-57eea90；没有修改版本号或正式 Release。
- D15 的所有建议未实施（D14a/D14c 已明确授权部分除外）；数据库迁移方案未执行。这些是任务要求的边界，不将其写成已完成发布。
- 本机没有用户 Windows 桌面、实际 JSON、真实模型 API、NAS 或媒体库；未代替用户测试真实翻译质量/服务启动、演员信息写入或完整刮削。MockTransport 只验证请求参数和回退行为；Windows 构建结果及检查另外列出。
- 14 项本机跳过项主要是无本地 HTML 样本/未启用外站网络的既有测试，以及 Windows 专用路径检查，未用跳过标记掩盖本轮失败。
- 演员数据库转载授权仍待核实；本轮只下载只读检查，没有向外部维护者发消息。

用户复测可关注：主备 Key 明文、固定帮助文案不指定 DeepSeek、备用温度可单独保存、启动日志无反馈入口，并在自己的配置下分别验证主/备用翻译。临时测试程序以 TEST 文件名识别；保留原配置备份后使用。没有需要用户搬运的交接文件。

仓库最终状态：功能分支与远程一致且工作区干净，未删除未合并的分支；master 保持 `2b4f01d`（本地已快进到同一提交），报告单独提交到 handoff，handoff 无代码改动。其他既有本地目录/分支未清理。。
