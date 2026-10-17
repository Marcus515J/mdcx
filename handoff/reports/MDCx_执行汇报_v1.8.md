# MDCx 执行汇报 v1.8

日期：2026-10-17（北京时间）。对应 `handoff/MDCx任务单_v1.8.md`，遵循 `handoff/README.md`。标记：【已查证】= 当前源码、GitHub API 或官方文档；【已实测】= 本轮实际运行；【推断】= 基于现有证据的合理推断。

## 摘要与待确认事项

- **结论**：第 0 节（合并 PR #11、删除孤立标签 `220261012`）、A1（移除旧翻译引擎仅保留大模型 LLM）、A2（新建私有资源仓库 `Marcus515J/mdcx-resources` 并托管四类资源 Release）、A3（内置本地 Cookie 获取教程替换贴吧链接）、B1（重写 13 节软件内使用说明）、B2（清理文档与一次性工作流）已全部完成，并已创建草稿 PR #12 及构建 Windows 测试版 artifact。
- **待用户确认 / 自助处理事项（共 2 项）**：
  1. **Dropbox 历史目录中的旧版安装包（`release/` 子目录）是否需要额外存档**：
     - 【已查证】原 Dropbox 共享目录除 `水印样式包/watermark_0.4.zip` 和 `字幕包（来源网络34000字幕，更新至2023年3月）/34000字幕-202303.rar` 外，还包含一个 `release/` 子目录（内含 `MDCx-py-20231014.rar`、`MDCx-win-20231014.rar`、`MDCx-mac-20231014.dmg` 三份 2023 年旧版程序包）。
     - 按任务单规则，这三份旧程序包既非字幕也非水印，本轮**未放入** `subtitles` 或 `watermarks`。如需作为历史归档保留，可告知后再上传至资源仓库 `archive` 标签；若无需保留则无需操作。
  2. **百度贴吧 Cookie 原帖（`p/5492736764`）离线存档**：
     - 【已实测】本轮环境通过浏览器指纹模拟访问桌面端与移动端链接均被百度安全验证拦截（HTTP 403，返回 2,434 字节拦截页），按任务单跳过 `archive` 标签上传。若希望保留原帖纪念，可在常用浏览器打开该帖按 `Ctrl+S` 保存为单文件网页（`.mhtml` 或 `.html`），手动上传至 `Marcus515J/mdcx-resources` 的 `archive` Release。

---

## 第 0 节：合并上轮 PR #11 与删除孤立标签

**结论**：PR #11 已去掉临时构建工作流并 squash 合并入 `master`，孤立标签 `220261012` 已从远程删除，新功能分支 `feat/llm-only-and-resources` 已基于最新 `master` 切出。

- **移除临时工作流**【已实测】：在 `feat/llm-settings-and-cleanup` 提交 `30a9356`，删除 `.github/workflows/test-build-windows.yml`，等待 CI（`Code Quality`、`Tests`）全部通过。
- **Squash 合并 PR #11**【已查证】：合并提交号为 [`3b9df591efdc0edfb18f7db3574f3acaa9b81ef5`](https://github.com/Marcus515J/mdcx/commit/3b9df591efdc0edfb18f7db3574f3acaa9b81ef5)（提交说明：`feat: 翻译设置去厂商固定文案、Key 明文显示、独立备用温度与反馈渠道清理 (#11)`），远程与本地分支 `feat/llm-settings-and-cleanup` 已删除。
- **删除远程孤立标签 `220261012`**【已实测】：执行 `git push origin --delete refs/tags/220261012` 删除成功；`git ls-remote --tags origin` 复核现仅存 `v1.0.1`、`v1.0.2`、`v1.1.0`，对应历史提交 `ff8ac68` 仍在 `master` 历史中。

---

## A1：移除旧翻译引擎（只留大模型 LLM）

**结论**：谷歌、百度、DeepL、DeepLX 四个翻译引擎的代码、配置项、界面控件已全部移除；旧配置自动收敛为 `[Translator.LLM]` 且不触发 `_failed.json`，无专属外部依赖需移除。

### 1. 翻译调用点对照表【已查证】

| 翻译对象 | 代码位置（界面对应功能） | 原来用哪个引擎 | 现在走什么 |
| --- | --- | --- | --- |
| 影片标题（`title`）与简介（`outline`） | `mdcx/core/translate.py:translate_title_outline`（刮削时标题/简介翻译） | 从勾选的 `google` / `baidu` / `deepl` / `deeplx` / `llm` 中随机或按序调用 + 繁简转换 | 仅调用 `Translator.LLM`（云端主接口 + 本机备用接口）+ 繁简转换 |
| Emby / Jellyfin 演员维基补全（`taglines`、`overview`） | `mdcx/tools/wiki.py:_process_translation`（工具页演员信息补全） | 演员名走 `mapping_actor.xml`；标签与简介走 `translate_by` 配置的在线/LLM 引擎 | 演员名仍走 `mapping_actor.xml`；标签与简介仅走 `Translator.LLM` |
| 演员名（`actors`、`all_actors`） | `mdcx/core/translate.py:translate_actor`（刮削演员名映射） | `av-wiki` 日文真名查询（可选）+ 内置 `mapping_actor.xml` 映射表（原本就不调在线翻译引擎） | 保持不变（`av-wiki` + `mapping_actor.xml`） |
| 标签（`tags`）、系列（`series`）、片商（`studio`）、发行商（`publisher`）、导演（`director`） | `mdcx/core/translate.py:translate_info`、`mdcx/core/tag_priority.py`（刮削元数据字段映射） | 内置 `mapping_info.xml` 映射表 + `zhconv` 繁简转换（原本就不调在线翻译引擎） | 保持不变（`mapping_info.xml` + `zhconv`） |

### 2. 旧配置兼容与三份样本实测结果【已实测】

- **兼容机制**：在 `mdcx/config/migrations.py` 与 `TranslateConfig`（设置 `extra="ignore"` 及 `normalize_translate_by` 校验器）中，加载旧配置时自动剔除已废弃的引擎名（`google`、`baidu`、`deepl`、`deeplx`、`youdao`）及字段（`baidu_appid`、`baidu_key`、`deepl_key`、`deeplx_url`）；过滤后若 `translate_by` 为空，自动归一为 `[Translator.LLM]`。
- **3 份旧配置样本测试**（已固化到 `tests/test_translate_llm.py::test_legacy_translate_config_migration_and_save_reload`）：
  - 样本 1（仅含 `["google"]`）：加载无报错、未生成 `_failed.json`，加载后 `translate_by == [Translator.LLM]`，保存重读后一致。
  - 样本 2（含全部五项 `["google", "baidu", "deepl", "deeplx", "llm"]`）：加载无报错、未生成 `_failed.json`，加载后 `translate_by == [Translator.LLM]`，保存重读后一致。
  - 样本 3（含旧引擎及 `deepl_key`、`baidu_appid`、`baidu_key`、`deeplx_url`）：加载无报错、未生成 `_failed.json`，保存后 JSON 文件中已彻底移除上述 4 个旧字段，重读后 `translate_by == [Translator.LLM]`。

### 3. 依赖核查【已查证】

- 被删的四个引擎仅使用了 Python 标准库（`hashlib`、`random`、`time`、`urllib.parse.quote`）及项目共用的异步 HTTP 客户端 `computed.async_client`。`pyproject.toml` 与 `uv.lock` 中没有仅被这四个引擎独占使用的第三方依赖，因此本轮移除依赖数为 **0**。

---

## A2：私有资源仓库 `Marcus515J/mdcx-resources`

**结论**：已新建私有仓库 [`Marcus515J/mdcx-resources`](https://github.com/Marcus515J/mdcx-resources)，编写 `README.md` 维护指南，并将四类资源全部通过 Release 附件上传及完成回下 SHA256 比对；软件内四个下载按钮已全部指向该仓库对应标签页。

### 1. 资源 Release 清单与上传前后 SHA256 核验【已实测】

| Release 标签 | 附件文件名 | 原始来源与作者 | 精确大小（字节 / MiB） | 上传前 SHA256 | 上传后回下 SHA256 比对结果 |
| --- | --- | --- | --- | --- | --- |
| [`actor-info-db`](https://github.com/Marcus515J/mdcx-resources/releases/tag/actor-info-db) | `Actress-20250220.db` | `sqzw-x/mdcx` (`actor_info_database`)，作者 `sqzw-x` | `12,615,680` (12.03 MiB) | `251206ca729bb6fcdd55a88b228dfb1f6beb8d069dce947d90acb6750a50c9d8` | **一致** |
| [`actor-info-db`](https://github.com/Marcus515J/mdcx-resources/releases/tag/actor-info-db) | `Actress-20231123.db` | 同上 | `10,977,280` (10.47 MiB) | `c97520d0a7e6befd61e06fd3926fc2c185635ffad2485d80903fffa42dd690ab` | **一致** |
| [`watermarks`](https://github.com/Marcus515J/mdcx-resources/releases/tag/watermarks) | `watermark_0.4.zip` | Dropbox 共享目录 `水印样式包/`，作者 `Hermit / anyabc` | `4,016,397` (3.83 MiB) | `691df11ad404bcf8cefa0ac5746154ae719a42509f5c46c7dbd6189c040f0e05` | **一致** |
| [`subtitles`](https://github.com/Marcus515J/mdcx-resources/releases/tag/subtitles) | `34000.-202303.rar`（原名 `34000字幕-202303.rar`，GitHub 自动将中文转为 `.`） | Dropbox 共享目录 `字幕包（来源网络34000字幕，更新至2023年3月）/`，作者 `Hermit / anyabc` | `368,827,484` (351.74 MiB) | `6dd21e9bf9ca009762a7e9be61a6b25a3fe1aa7d8aa90f6efef71d3de163c5f4` | **一致** |
| [`actor-photos`](https://github.com/Marcus515J/mdcx-resources/releases/tag/actor-photos) | `Actor.zip` | `moyy996/AVDC` (`头像包-2`)，作者 `moyy996` | `202,907,836` (193.51 MiB) | `909e05f5fa90d9bf4f293d5f79922e91eb7eb397183e0576c7bb7dc32483f1eb` | **一致** |
| [`actor-photos`](https://github.com/Marcus515J/mdcx-resources/releases/tag/actor-photos) | `People.7z` | 同上 | `189,989,484` (181.19 MiB) | `2198ef0ce1fe924eccd1925aad673e2ffdd6078f890b2c2e3c5fb2377e70bbc6` | **一致** |

- **Dropbox 整包核查记录**【已实测】：原始 Dropbox 文件夹打包下载总大小 `630,940,737` 字节（601.71 MiB），SHA256 为 `c198dcf430a2cc97fb68b9e2eacc4e1fd1c1dd1e3918ccfc800293153748abbb`，包含 `水印样式包/watermark_0.4.zip`、`字幕包（来源网络34000字幕，更新至2023年3月）/34000字幕-202303.rar` 及 `release/` 下的 3 个 20231014 旧版安装包（见文首待确认事项 1）。
- **代码常量与按钮绑定**【已查证】：在 `mdcx/consts.py` 新增 `GITHUB_RESOURCES_REPO = "Marcus515J/mdcx-resources"` 与 `GITHUB_RESOURCES_RELEASES_URL`，`mdcx/controllers/main_window/init.py` 中 4 个资源按钮已分别指向 `actor-photos`、`subtitles`、`watermarks`、`actor-info-db`。无任何资源文件或 Token 写入公开代码仓库。

---

## A3：软件内 Cookie 教程页（替换贴吧链接）

**结论**：已新增内置离线教程 `resources/html/cookie_help.html`，替换原百度贴吧链接；Windows 与 Mac 开发态及 PyInstaller 打包态均通过 `resources.cookie_help_path` 正常定位打开。

- **界面归属与覆盖站点**【已查证】：该链接位于「设置 → 网络 → Cookie设置」底部（控件 `label_get_cookie_url`，原文字为贴吧 URL，现改为「如何获取 Cookie？点击查看教程」，左侧标签改为「配置教程：」），对应同一分组内的 `javdb`、`javbus`、`fc2ppvdb` 三个站点的 Cookie 填写框与「检查cookie」按钮。
- **教程页路径与验证**【已实测】：
  - 源码路径：`resources/html/cookie_help.html`；定位属性：`mdcx/config/resources.py` 中的 `resources.cookie_help_path`（打包态自动解析至 `sys._MEIPASS / "resources/html/cookie_help.html"`，`scripts/build.py` 已整目录打包 `resources`）。
  - 教程涵盖 Chrome / Edge 开发者工具（`F12` → `Network` / `网络` → 选中主请求 → `Headers` / `标头` → `Request Headers` → 手动框选复制 `Cookie`）及在 MDCx 中粘贴、点击「检查cookie」和点击右下角「保存配置」的完整流程。
  - 本机实测渲染截图已生成并核验排版正常（保存在本轮会话制品目录 `cookie_help_screenshot.png`，遵循公开代码仓库不提交二进制图片原则未入库）。
- **贴吧原帖存档结果**【已实测】：访问 `https://tieba.baidu.com/p/5492736764` 返回 HTTP 403（百度安全验证拦截），按任务单跳过 `archive` 标签上传，见文首待确认事项 2。

---

## B 段：使用说明重写与文档整理清单

**结论**：已按 v1.7 汇报 D15 第 5 节的 13 节大纲重写软件内「使用说明」（先改 `MDCx.ui` 再运行 `pyuic6` 生成 `MDCx.py`），并按任务单表格完成全部文档与工作流清理。

| 对象 | 本轮处理结果 |
| --- | --- |
| `mdcx/views/MDCx.ui` & `MDCx.py`（「使用说明」页） | 按 13 节大纲重写 `textBrowser_about` HTML 并开启 `openExternalLinks`；反映仅保留大模型翻译、独立主备温度、私有资源仓库入口与本地 Cookie 教程；修正「不支持 -1、-A、-B」的错误描述；清除多余空段落与字面 `**`；保留上游来源、旧 AVDC 链接与 `mdcx-docker` 说明于第 13 节 |
| `mdcx/views/MDCx.ui` & `MDCx.py`（Emby 命名文档外链） | 更新为跳转后的最终官方地址 `https://emby.media/support/solutions/articles/44001159102-movie-naming/` |
| `README.md` | 更新功能简介（仅保留 LLM 翻译、说明扩展资源托管于私有资源仓库且不贴需登录直链）；上游来源、致谢与许可证声明保持不动 |
| `CONTRIBUTING.md` | 修正配置管理器导入路径为 `from mdcx.config.manager import manager`，更新 UI 初始化函数名 `Init_Ui`、子模块说明及真实目录树与 `scripts/*.py` 脚本名 |
| `changelog.md` / `LICENSE` | 未做任何修改 |
| `todo.md` | 已删除（由 `handoff` 分支取代） |
| `docs/llm-refusal.md` | 去固定厂商名称（改为通用 OpenAI 兼容云端主模型）、写明主备温度独立配置、仅保留 LLM 翻译引擎 |
| `docs/garbage-cleanup.md` | 去掉过期的会话口吻，在表格中明确区分本功能新增的 5 个 `garbage_*` 配置字段与复用的既有字段 |
| `docs/local-models.md` | 保留并同步补充独立主/备用温度说明 |
| `docs/pyqt6-migration.md`、`docs/crawler-migration.md` | 保留正文，在开头添加「历史记录：迁移已完成或为当时计划，现状以代码为准。」 |
| `.github/workflows/finalize-v1.1.0.yml` | 已删除一次性发版工作流，消除误触发风险 |

---

## 验证、CI 与交付信息

### 1. 本地与 CI 测试结果【已实测】

- **本地定向测试**：
  - 命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_translate_llm.py tests/test_llm_refusal.py tests/test_config_conversion.py tests/test_llm_settings_ui.py tests/test_llm_temperature.py tests/test_local_llm.py tests/test_local_model.py -v`
  - 结果：**127 passed, 1 skipped, 0 failed**（22.52 秒）。
- **本地全量测试**：
  - 命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`
  - 结果：**776 passed, 14 skipped, 0 failed**（95.38 秒）。
- **本地静态检查**：`.venv/bin/ruff check` 与 `.venv/bin/ruff format --check` 全部通过。
- **GitHub Actions CI**（[Run 39042471427](https://github.com/Marcus515J/mdcx/actions/runs/39042471427)）：
  - `Code Quality`：**success**（8 秒）。
  - `Tests`（Ubuntu 全量测试）：**776 passed, 14 skipped, 0 failed**（121.24 秒）。
- **GitHub Actions Windows 测试构建**（[Run 39042467329](https://github.com/Marcus515J/mdcx/actions/runs/39042467329)）：
  - 原生 Windows 定向测试（含 `test_translate_llm.py`、`test_llm_refusal.py`、`test_llm_temperature.py`、`test_llm_settings_ui.py`、`test_version.py`）：**91 passed, 0 skipped, 0 failed**（11.31 秒）。
  - 源码版本与打包后 `dist/MDCx.exe` 版本校验（`v1.1.0`）全部通过。

### 2. 分支、提交、PR 与 Windows 测试包下载

- **`master` 分支基线**：`3b9df591efdc0edfb18f7db3574f3acaa9b81ef5`（PR #11 合并提交）。
- **功能分支**：`feat/llm-only-and-resources`
  - 功能与文档主提交：[`1944232e1212ce8d97792cbe0691b1f8319a4413`](https://github.com/Marcus515J/mdcx/commit/1944232e1212ce8d97792cbe0691b1f8319a4413)
  - 临时构建工作流提交（合并前删除）：[`a7ff025c5d11e7dc6c26fe26038a26e47387c7b3`](https://github.com/Marcus515J/mdcx/commit/a7ff025c5d11e7dc6c26fe26038a26e47387c7b3)
- **草稿 PR**：[PR #12](https://github.com/Marcus515J/mdcx/pull/12)（`isDraft=true`、`state=OPEN`、`mergeable=MERGEABLE`，未合并）。
- **Windows 测试版 Artifact**：
  - 下载链接：[windows-x86_64-test-1944232](https://github.com/Marcus515J/mdcx/actions/runs/39042467329/artifacts/12104616375)（需登录 GitHub 下载，保留至 **2026-10-31 22:52:39 北京时间**）。
  - Artifact ZIP 大小：`152,866,827` 字节（145.79 MiB），内含 `MDCx-v1.1.0-TEST-1944232-windows-x86_64.exe` 与 `SHA256SUMS.txt`。
  - Artifact ZIP SHA256：`77e6ce44baa0e390e86b6ccbcf0af21c7ce77477b3e195e39d94fd4832b58510`。

### 3. 未做到的部分与边界说明

- 百度贴吧原帖（`p/5492736764`）因返回 HTTP 403 未能自动抓取上传至 `archive` 标签（见待确认事项 2）。
- Dropbox 目录下的 `release/` 子目录（3 个 20231014 旧版程序包）因既非字幕也非水印，按任务单要求未混入 `subtitles` 或 `watermarks`，列于待确认事项 1 供用户决定。
- 本机无真实云端模型 API Key、Emby/Jellyfin 媒体库及 Windows 桌面环境，未代替用户进行真实影片刮削与在线翻译调用。
