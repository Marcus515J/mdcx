# MDCx 第一阶段收口 / 第二阶段交接

日期：2026-10-09（北京时间）。仓库：`Marcus515J/mdcx`。

## 先读这一段

用户已明确确认：**第一阶段垃圾文件清理通过实际测试，收口；停止继续实现，另开对话开展第二阶段。**
第一阶段固定在已发布、已验收的 `fe491f7a9fde48fc754c49dba13781c2b64b1647`。本次收口只保存交接资料和界面草稿，不改业务代码、不发布新程序。不要把尚未完成的本机模型接入说成已经完成。

第二阶段明确目标：**主力本机 Hy-MT2 → 同模型重试 → 备用 DeepSeek 或其他 LLM API → 保留该字段原文**。另有清理设置界面收尾需求，见下文。

## 一、第一阶段验收基线

- 工作分支：`feat/garbage-cleanup-llm-refusal`；尚未合并主分支。
- 已验收源码提交：`fe491f7a9fde48fc754c49dba13781c2b64b1647`。
- 程序版本标签：`test-20261009-unified-cleanup`。
- [Windows 测试版下载页面](https://github.com/Marcus515J/mdcx/releases/tag/test-20261009-unified-cleanup)。下载 Assets 中的 EXE，Source code 不是成品程序。
- [EXE 直接下载](https://github.com/Marcus515J/mdcx/releases/download/test-20261009-unified-cleanup/MDCx-test-20261009-unified-cleanup-windows-x86_64.exe)。大小：153227060 字节。
- SHA256：`faede502ac6081cbd374d20e38adab4f45f31496adf16fb3ccc15a9f69c20903`。
- [Windows 构建和测试记录](https://github.com/Marcus515J/mdcx/actions/runs/37928798612)：成功，**145 通过、0 失败**；Linux 同一组测试也为 **145 通过、0 失败**。
- 用户已经在自己的 Windows 环境确认清理功能通过。该确认不等于真实本机模型或云端翻译链路通过。

### 已完成的清理行为

1. 无番号垃圾视频在站点搜索前识别处理；复用已有番号识别和最小视频大小 `file_size`，N 默认 100 MB，不重复建立 N。
2. 清理设置统一在「设置 → 刮削目录 → 文件清理设置」，没有另一套独立垃圾规则编辑器。
3. 广告词编辑已有“文件名包含”；完整指定文件编辑已有“文件名等于”，多个项目用 `|` 分隔。
4. 完整文件名含扩展名、空格和大小写严格相等；包含词忽略空白和大小写。启用的排除规则优先。
5. 非视频文档必须命中扩展名、完整名称或包含词，不能仅因很小或 0 KB 清理。用户可明确指定一个 0 KB 文档的完整名称来清理它。
6. 正常番号视频、NFO、图片、字幕和符号链接受保护；媒体根目录不整体移动。
7. 默认移到源盘符/卷根的 `_待删`；允许自定义绝对目录。重名加序号，不覆盖已有文件。
8. 允许演练；演练只记录、不移动、不删除。永久删除开关默认关闭，只作用于匹配的单文件。
9. 仅含已确认垃圾的子目录整体移到 `_待删`，即使单文件方式选永久删除，纯垃圾目录仍整体移动。未知文件、保护文件、排除项、链接会阻止整体移动。
10. 手动清理不需要联网、成功刮削或打开自动清理。自动清理和手动清理使用同一套判断。
11. `_待删` 和自定义待删目录及其子目录排除在扫描之外；移动/删除记录原因、源路径、处理方式和目标路径。
12. 目录采用独占目标复制及源文件变化核对，失败保留源；复制中出现正常文件不会删除它。失败可能留下待删副本。

### 清理配置与迁移

| 项目 | 默认值 / 状态 |
|---|---|
| `garbage_enabled` | `false`，自动清理开关，与旧 `clean_enable` 的 `auto_clean` 同步 |
| `garbage_dry_run` | `false` |
| `garbage_permanent_delete` | `false` |
| `garbage_directory` | 空，采用源盘符/卷根 `_待删` |
| `garbage_domain_rule` | `true`；`.com` / `.net` / `.cc` / `www.` |
| `file_size`（已有） | `100.0` MB，共用 N |
| `clean_contains`（已有） | 原有 8 项加 `台湾uu`、`美少女直播`、`信誉保证`、`最新情報`；`最新情报` 原已存在 |
| `clean_name`（已有） | `uur76.mp4`、`uur93.com.mp4`；可自行编辑 |

上一测试版 `garbage_keywords` 自动合并到 `clean_contains` 并去重，新保存不输出重复黑名单。旧字符串规则和各规则启用状态保留。
原 JSON 加载不会覆盖文件，保存时才输出新版格式；合成旧配置的加载、保存、再加载及其他字段保留已测试。
**未收到用户真实旧 JSON，不能宣称已逐项验证其真实配置。用户不会上传包含个人 API Key/Cookie 的配置，不应索取这些敏感内容。**

### 待核实项目的实际结论

- 原有“忽略小于 N MB”及清理规则存在，已经复用；未新增另一套大小或关键词配置。
- 主 LLM 已支持自定义 OpenAI 兼容地址；原先没有独立备用模型概念，现已加入独立备用字段。
- 原附件提到的三个真实垃圾视频未提供本体，实际字节数仍未知；没有自行调大 N，超过 100 MB 的广告可依靠名称规则命中。
- 七个历史 NFO 未提供，未读取其中真实拒绝语；测试使用明确给出的模拟拒绝句。未修改任何已有 NFO。

### 测试命令和证据

Linux 已实际运行（仓库根目录，有现成 `.venv`）：

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q -s tests/test_garbage_settings_ui.py tests/test_unified_file_cleanup.py tests/test_garbage_cleanup.py tests/test_llm_refusal.py tests/test_translate_llm.py tests/test_config_conversion.py tests/test_config_network.py tests/test_number_definition.py tests/test_scraper_remain_list.py tests/test_media_paths.py
```

Windows CI 使用锁定依赖：

```powershell
uv sync --locked --dev
$env:QT_QPA_PLATFORM = "offscreen"
uv run --locked pytest -q tests/test_garbage_settings_ui.py tests/test_unified_file_cleanup.py tests/test_garbage_cleanup.py tests/test_llm_refusal.py tests/test_translate_llm.py tests/test_config_conversion.py tests/test_config_network.py tests/test_number_definition.py tests/test_scraper_remain_list.py tests/test_media_paths.py
uv run --locked scripts/build.py --debug
```

覆盖临时目录的演练、真实移动/删除、纯垃圾目录移动、手动清理、精确名称与近似名称、0 KB 笔记、排除项、重名、链接、复制失败及复制过程中新增正常文件。边界样本包含“小于 N 但有正常番号”和“大于等于 N、无番号且无垃圾规则命中”。
拒绝检测四条模拟路径已跑：重试成功、备用成功、全部拒绝保留原文、正常翻译直接返回；另测备用未配置、备用请求失败、标题/简介独立、空原文及拒绝词出现在句中。

Windows 日志：`145 passed, 1 warning in 68.73s (0:01:08)`。测试警告来自已有 `zhconv` 的 `pkg_resources` 弃用，没有顺手修改依赖。
拒绝路径实际日志含：`⚠️ 翻译被拒`、`🔁 翻译被拒：重试第 1 次`、`🔄 换备用模型`、`📝 保留原文`。
清理测试的实际日志摘录（只简写临时目录前缀）：

```text
🗑 演练: .../media/明确指定的广告.txt | 清理文件名:明确指定的广告.txt | 移到待删目录
🗑 处理: .../media/聚 合 全 網 H 直 播.html | 清理扩展名:.html | 移到待删目录 .../_待删/聚 合 全 網 H 直 播.html
🗑 演练目录: .../media/纯垃圾 | 仅含垃圾文件 | 整目录移到待删 .../_待删/纯垃圾
🗑 跳过清理目录: .../_待删
🎉 文件清理完成：匹配 4 个，已处理 0 个，失败 0 个 | 演练（不移动、不删除） | 0.0s
```

现成详细使用说明：`docs/garbage-cleanup.md`、`docs/windows-test-guide.md`、`docs/llm-refusal.md`。

### 可回退的提交

| 提交 | 内容 |
|---|---|
| `0911fd1` | 需求 A：刮削前垃圾视频处理 |
| `ebd60e0` | 需求 B：通用拒绝检测、重试、备用、原文 |
| `ff7c131` | 纯垃圾目录整体移动 |
| `9bedef1` | Windows 测试版构建工作流与说明 |
| `a87b170` | 可编辑垃圾规则与状态说明（后来统一界面替代独立弹窗） |
| `e848baa` | Windows 测试读取中文 JSON 使用 UTF-8 |
| `fe491f7` | 统一文件清理规则、界面及旧 JSON 迁移 |

主要代码入口：`mdcx/base/file.py`、`mdcx/number.py`、`mdcx/core/scraper.py`、`mdcx/config/models.py`、`mdcx/config/migrations.py`、`mdcx/config/extend.py`、`resources/config/default_config.json`、`mdcx/controllers/main_window/file_cleanup_settings.py` 及同目录 `init.py`、`load_config.py`、`save_config.py`、`main_window.py`。
翻译入口：`mdcx/base/translate.py`；现有客户端及构建位置：`mdcx/llm.py`、`mdcx/config/computed.py`。测试位于上述命令列出的文件。

## 二、第二阶段目标与当前真实状态

### 用户最新确认（优先于旧附件的范围）

用户要求本机 Hy-MT2 为主力，拒绝后同模型重试，仍拒绝转 DeepSeek 或其他 LLM API，最后保留原文。默认拒绝重试 1 次。
用户不清楚本机模型通过什么程序运行，只知道另一个仓库项目叫“海南鸡”，那里已配置好、使用该项目时可直接调用模型。
用户确认没有另一份交接记录，原附件没写本机模型也不再追溯，**按现在确认的方案实施**。

已重新核对《MDCx优化需求清单_v1.1.md》：它写的是通用主模型 → 重试 → 备用 → 原文，**没有 Hy-MT2、本机服务程序、地址或 model ID**。这只是已核实的文档事实，不能用它否定用户现在的方案。

### 已有实现与缺口

- 通用拒绝链已实现并模拟验证；仍使用用户当前填写的主模型，不会自动变成本机 Hy-MT2。
- 默认 `llm_url=https://api.llm.com/v1`、`llm_model=gpt-3.5-turbo`、`llm_key=""`，本机地址和模型 ID 尚未确定。
- `llm_refusal_retries=1`；拒绝前缀 12 项，见 `TranslateConfig` 和 `docs/llm-refusal.md`。
- 备用 `llm_fallback_url=null`、`llm_fallback_key=""`、`llm_fallback_model=""`、`llm_fallback_read_timeout=60`；目前只能编辑 JSON，没有备用模型的设置页控件。
- 备用只有地址、Key、模型全部完整时启用；提示词保持一致，不改写提示词以绕过拒绝。
- 标题和简介各自处理，不因一个字段拒绝覆盖另一个字段的正常译文；空原文跳过。
- `get_translator_skip_reason()` 当前要求主模型有 Key，无鉴权的本机服务会被跳过。是否应允许本机空 Key，须先查实际接入协议。
- `LLMClient` 当前使用 `AsyncOpenAI` 与 `httpx.AsyncClient`。本机请求仍可能受全局代理或环境代理影响，需要核对并合理处理本机地址。
- **首轮主模型 API 请求失败返回 `None`，保留旧翻译引擎错误处理；这条路径目前不会直接转独立备用 LLM。** 第二阶段须明确覆盖本机未启动、超时、错误和空返回，不能只测拒绝语。
- `llm_max_try=5` 是已有传输错误尝试数，与拒绝重试 1 次不同；OpenAI SDK 自身也可能重试。应核对总请求数和耗时，避免把多个重试层叠加误说成仅重试一次。

### “海南鸡”调查停在哪里

只获知项目名称；尚未确定 GitHub 仓库链接、运行程序、端口、协议、服务模型 ID或是否为进程内直接推理。**尚未读取该项目源代码，也未验证它的接口。**
下一位先通过已连接 GitHub 的仓库名称/描述搜索查找该项目，查看 README、部署说明和模型调用代码，优先复用其现有调用方式。找不到仓库时只向用户索取仓库链接，不要重复要求用户解释不会配置的技术细节，不要索取完整私人配置、Key 或 Cookie。
不能默认它一定是 Ollama 或 OpenAI 兼容服务，不能凭空指定端口或 model ID。云端工作环境不能据此宣称已连通用户 Windows 本机。

## 三、界面收尾需求与已保存草稿

用户指出“保存清理设置”与页面底部“保存”重复；经查底部保存已经包含清理设置。希望去掉重复按钮，将新增几格与原有输入框统一，压缩长说明并利用右侧空间。

现有发布版仍有单独“保存清理设置”。本轮曾修改两个文件，但用户随后要求停工；改动已导出为 **`docs/drafts/stage2-cleanup-ui.patch`**，业务代码恢复至验收版，草稿未提交为功能、未发布。

草稿内容：复用原 `gridLayout_52` 使标签/字段共享列；统一目录、处理方式、N 控件的边框/高度；去掉 N 的上下箭头；说明拆为左右两块；自动清理和手动按钮同一行；去掉单独保存按钮，测试改为点击底部总保存。
草稿曾跑清理界面 4 项测试通过，**没有完成真实主题、高 DPI、窗口缩放及 Windows 新构建验收**。这只是可接续草稿，不能直接宣称界面问题解决。

新对话另建第二阶段分支，再按需要查看或应用：

```bash
git switch feat/garbage-cleanup-llm-refusal
git switch -c feat/local-hy-mt2-translation
git apply --check docs/drafts/stage2-cleanup-ui.patch
git apply docs/drafts/stage2-cleanup-ui.patch
```

应用后再验证控件边界、主题与字体；修改相应使用说明中的“保存清理设置”。备用模型界面尚无草稿，应复用现有配置字段、接入原有加载和底部总保存，不增加第二套保存流程。

## 四、第二阶段建议执行及测试顺序

1. 阅读本交接、确认第一阶段标签及干净工作区；第一阶段功能保留，另建分支实施。
2. 查“海南鸡”的实际本机模型部署与调用方式，得出非敏感的接口类型、地址、模型 ID及启动要求；不假设服务协议。
3. 接上本机主力配置，让备用地址/模型/Key/超时与拒绝重试设置在界面可见、可保存；保留用户旧配置。若本机服务无需 Key，按真实协议支持，而非要求用户上传密钥。
4. 完成清理页外观收尾；总保存统一保存，禁止扩大清理规则或改动已经验收的文件处理逻辑。
5. 复用标准库/已装依赖构建可控模拟服务或客户端替身，无私人 API、Cookie、真实刮削即可跑翻译测试；若需离线测试入口，先检查已有工具，避免增加无关运行时配置。
6. 实际覆盖四条既定路径及备用空配置、标题/简介、空原文、正常句中拒绝词；增加本机服务不可用、超时、错误、空返回和本机代理隔离验证，校验每一步实际请求顺序和数量。
7. 全部拒绝只能返回对应字段原文，日志逐步可见；重试与备用保持相同翻译提示词。不得增加任何绕过模型拒绝的逻辑。
8. 先跑无秘密模拟测试，再让用户在 Windows 自行填非敏感连接信息和本地私有 Key，验证真实本机 → 备用 → 原文。若发布新 EXE，运行 Windows CI 测试、构建并核实资产上传成功后提供链接。

真实 Hy-MT2 及真实备用 API 调用、用户机器服务启动方式、真实用户配置迁移、真实旧 NFO拒绝语读取仍未覆盖。已有测试通过不能替代这些联调。

## 五、边界和无关问题

- 复用现有依赖和代码，不新增依赖、无关抽象或无关配置项；需求 A/B 保持可独立回退。
- 删除/移动必须有日志；正常文件不能误伤；待删目录排除；任何已有 NFO 不修改。
- 用户私人 JSON 不必上传；测试使用合成配置或本地自行填值，日志/截图不显示 Key、Cookie。
- 原附件末尾明确不做：MTES-003/004 重复刮削、文件名漂移、bypass 超时后浏览器重复启动。这些均未修改，不属于第二阶段当前目标，除非用户另行扩展范围。
- Windows 软链接 `WinError 1314` 属于权限问题，未混入清理或翻译修复。

## 新对话可直接使用的开场文字

> 请在 Marcus515J/mdcx 阅读分支 feat/garbage-cleanup-llm-refusal 的 docs/stage2-handoff.md。第一阶段垃圾清理已验收，固定标签 test-20261009-unified-cleanup，不重做。现在另建分支完成第二阶段：查另一个叫“海南鸡”的项目如何调用我的本机 Hy-MT2，实施“本机 Hy-MT2 → 同模型重试 → 备用 DeepSeek 或其他 API → 保留原文”，并完成交接里记录的界面收尾。不要索取我的私人 API Key/Cookie 或完整配置，不新增依赖，不改已有 NFO，不写绕过模型拒绝的提示词或逻辑。先读代码用不超过 15 行说明要改什么，再直接做；确实缺少仓库链接时再问我。模拟测试实际跑通，再提供 Windows 成品测试版和未覆盖项。
