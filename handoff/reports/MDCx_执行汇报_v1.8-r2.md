# MDCx 执行汇报 v1.8-r2（PR #12 返工）

日期：2026-10-18（北京时间）。依据：`handoff/MDCx任务单_v1.8-r2.md`，遵循 `handoff/README.md`。
标记：【已查证】= 源码/代码库严格核对；【已实测】= 本轮测试/CI 实际运行验证。

---

## 摘要与交付总览

- **结论**：本轮针对审核指出的 R1（使用说明事实错误与编造界面名）、R2（Cookie 教程复制建议与按钮名称）、R3（翻译开关机制与 `checkBox_llm` 移除）完成全部整改，全量测试 100% 通过（含新增的机械核对测试），重新构建 Windows 测试版并生成独立 artifact。
- **功能分支**：`feat/llm-only-and-resources`
  - **功能提交**【PR #12 内容】：[`9986eb3e423b533b6b8da0a7988780e498002d2b`](https://github.com/Marcus515J/mdcx/commit/9986eb3e423b533b6b8da0a7988780e498002d2b) (`fix: 修正使用说明与Cookie教程的事实错误、移除失效checkBox_llm并增加机械核对测试`)
  - **临时工作流提交**【合并前删除】：[`d92109a96b015a76d91a2be9bc42bff4832d100e`](https://github.com/Marcus515J/mdcx/commit/d92109a96b015a76d91a2be9bc42bff4832d100e) (`ci: 添加临时 Windows 测试构建工作流 (合并前删除)`)
- **草稿 PR**：[PR #12](https://github.com/Marcus515J/mdcx/pull/12)（保持 Draft，未合并，CI/CD Checks 全部通过）。
- **Windows 测试构建 Artifact**【已实测】：
  - 构件名称：`windows-x86_64-test-9986eb3` (Artifact ID: `12116699991`)
  - 包含文件：`MDCx-v1.1.0-TEST-9986eb3-windows-x86_64.exe` (约 145.78 MB)、`SHA256SUMS.txt`
  - 运行记录：[GitHub Actions Run 39077754701](https://github.com/Marcus515J/mdcx/actions/runs/39077754701)
  - 下载地址：`https://github.com/Marcus515J/mdcx/actions/runs/39077754701/artifacts/12116699991`
- **全量测试结果**【已实测】：**783 passed, 14 skipped**（无失败，耗时约 92 秒）。
- **规则遵守**：未合并 PR #12、未打版本标签、未发布正式 Release、未改动资源仓库 `Marcus515J/mdcx-resources`，handoff 分支仅提交本汇报文档。

---

## R1：软件内「使用说明」改正与机械核对

### 1. 审核发现的 10 项问题改正对照表【已查证】

| # | 说明原写法 / 审核发现 | 查证情况与代码依据 | 本轮修改结果 |
|---|---|---|---|
| 1 | 主温度默认 0.2，备用温度默认 1.0 | `models.py:80` 声明 `llm_temperature: float = 0.9`；`default_config.json` 中两者均为 `0.9`；备用温度默认等于主温度 | 说明中更正为：「主接口温度与备用接口温度（默认均为 <code>0.9</code>）各自独立保存与发送」 |
| 2 | 「使用备用模型」开关 | 界面上不存在独立开关；`llm_settings.py:50` 明确规则为「备用地址留空可停用」 | 说明中删除「使用备用模型」字样，更正为：「备用接口地址填写后即可启用（留空即停用）」 |
| 3 | 「查找模型」「验证配置」「启动本机模型」「停止本机模型」 | `local_model_settings.py:60-65` 真实控件为：`查找 / 验证路径`、`重新查找`、`启动备用模型`、`停止`、`打开日志`，以及 `llm_settings.py:24` 的 `将所选本机模型设为备用` | 说明中全部替换为真实控件文字：「查找 / 验证路径」（或「重新查找」）、「将所选本机模型设为备用」、「启动备用模型」、「停止」、「打开日志」 |
| 4 | 「使用演员数据库」 | 界面上无此文字；`MDCx.ui` 演员页对应控件为 `checkBox_actor_db`，显示文字为「使用数据库补全演员信息」 | 说明更正为：在「设置」的「演员」标签页选择该 <code>.db</code> 文件并勾选「使用数据库补全演员信息」 |
| 5 | 「保存配置」，以及「或勾选自动保存配置」 | 设置页底部按钮文字为「保存」（`pushButton_save_config`）；代码中不存在「自动保存配置」 | 步骤标题改为「保存设置」，操作描述更正为点击界面右下角「保存」，删除「或勾选自动保存配置」半句 |
| 6 | 「设置 → 分集」 | 设置页不存在「分集」标签页；实际位于「设置」-「命名」标签页的「分集命名规则」（`groupBox_32`） | 描述更正为：在「设置」-「命名」的「分集命名规则」中配置是否将字母结尾（如 <code>-C.mp4</code>）识别为分集 |
| 7 | 「可配置 FlareSolverr / CF Bypass」 | 代码里无 FlareSolverr，接口不兼容；仅支持 CF Bypass | 彻底移除 FlareSolverr 提及，仅写「可配置 CF Bypass 服务地址（CloudflareBypassForScraping）」 |
| 8 | 配置损坏「原文件会备份为 *_failed.json」 | `load_config.py:72` 的实际代码行为是 `manager.path = manager.data_folder / "_failed.json"`，自动切换为使用数据目录下的 `_failed.json` | 更正描述为：「若因手动修改导致配置读取或校验出错，程序会自动切换为使用数据目录下的 <code>_failed.json</code>，避免破坏原有配置文件」 |
| 9 | 「点击主界面左下角版本号亦可检查更新」 | `init.py:266` 绑定 `label_version_clicked`，仅调用 `webbrowser.open(GITHUB_RELEASES_URL)` 打开网页，无法在软件内检查更新 | 按任务单要求直接删除该句，避免误导用户 |
| 10 | 字幕标记「-UC、-U」 | `mdcx/models/flags.py` 中默认字幕标记仅为 `-C`、`-c`、`_C`、`_c`，无 `-UC` 和 `-U` | 删除 `-UC`、`-U`，只保留默认支持的 `-C`、`_C` |

### 2. 机械核对测试（`tests/test_ui_terms.py`）【已实测】

为彻底杜绝界面名词编造，新增自动化测试 `test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`：
1. **测试逻辑**：
   - 使用 `xml.etree.ElementTree` 解析 `mdcx/views/MDCx.ui`；
   - 提取 `textBrowser_about` 中所有由中文括号 `「...」` 括起的词汇；
   - 将 `textBrowser_about` 文本从 DOM 中清空，遍历 `MDCx.ui` 剩余全部 UI 字符串及 `mdcx/controllers/**` 下所有源码构建检索语料库；
   - 逐一断言提取的每一个中文括号词汇在语料库中存在完全相同的文字；
   - 只要有任意一个词汇在 UI 控件或控制器中找不到对应，测试即抛出 AssertionError。
2. **测试结果**：
   - 说明中共提取 **60 处** `「...」` 引用，去重后为 **42 个** 独立控件/标签页/按钮/分组名称；
   - 42 个名称全部在 `MDCx.ui` 或 `mdcx/controllers/**` 中精确匹配，**0 缺失、100% 通过**。
3. **核对词汇明细清单（42 项）**：
   - **导航与标签页**：`「设置」`、`「主界面」`、`「日志」`、`「工具」`、`「刮削目录」`、`「刮削网站」`、`「命名」`、`「字幕」`、`「翻译」`、`「演员」`、`「网络」`
   - **分组与功能区**：`「分集命名规则」`、`「文件清理设置」`、`「Cookie设置」`、`「标题」`、`「简介」`
   - **主操作与按钮**：`「开始」`、`「保存」`、`「重新刮削」`、`「输入网址重新刮削」`、`「查找 / 验证路径」`、`「重新查找」`、`「将所选本机模型设为备用」`、`「启动备用模型」`、`「停止」`、`「打开日志」`、`「检查cookie」`
   - **下载入口**：`「点击下载头像包」`、`「点击下载字幕包」`、`「点击下载水印图片包」`、`「点击下载演员数据库」`、`「如何获取 Cookie？点击查看教程」`
   - **配置字段与勾选框**：`「待刮削目录」`、`「成功输出目录」`、`「失败输出目录」`、`「排除目录」`、`「过滤文件名多余字符」`、`「保存日志」`、`「使用翻译引擎翻译标题」`、`「使用翻译引擎翻译简介」`、`「使用数据库补全演员信息」`、`「开发者模式」`

---

## R2：Cookie 教程（`resources/html/cookie_help.html`）改动

1. **保存按钮更正**【已查证】：
   - 教程第二节提醒文字中的 `「保存配置」` 全部改为 `「保存」`，与 MDCx 界面右下角真实按钮完全一致。
2. **复制 Cookie 建议优化**【已查证】：
   - 第一节第 5 条修改为：优先在 `Cookie`（或 `cookie`）行上点击鼠标右键，选择 **“复制值 / Copy value”**；若右键菜单中没有该项，再手动框选该行对应的值文本并复制；
   - 增加注明：「不同浏览器或语言版本的右键菜单名称可能略有差异，请以你的浏览器实际界面为准。长 Cookie 容易在手动框选时光标截断或漏选字符，建议优先使用右键菜单复制完整值」。
3. **纳入机械核对测试**【已实测】：
   - 教程第一节中的浏览器原生菜单项采用加粗标注（如 `检查（Inspect）`、`Network（网络）`、`Headers（标头）`），避免与 MDCx 控件标记混淆；
   - 教程第二节所有涉及 MDCx 控件名称均使用 `「...」` 标注：`「设置」`、`「网络」`、`「Cookie设置」`、`「检查cookie」`、`「保存」`；
   - 在 `tests/test_ui_terms.py` 中增加 `test_cookie_help_bracketed_terms_exist_in_ui_or_controllers` 与 `test_cookie_help_content_requirements`，断言教程中所有括号词汇在 MDCx 代码中精确存在，且不包含“保存配置”字样；测试 100% 通过。

---

## R3：翻译开关机制排查与路线选择

### 1. 字段级翻译开关查证情况【已查证】

经仔细查阅 `mdcx/views/MDCx.ui` 与控制器逻辑，**界面上完整具备按字段开启/关闭翻译的入口**：
- **位置**：位于「设置」-「翻译」标签页（`tab_6`）下部；
- **具体开关**：
  - **标题**（`groupBox_82`）：勾选框 `checkBox_title_translate`，文字为「使用翻译引擎翻译标题」；
  - **简介**（`groupBox_83`）：勾选框 `checkBox_outline_translate`，文字为「使用翻译引擎翻译简介」；
  - **演员/标签/系列/片商/发行商/导演**：分别有独立的映射表翻译开关（`checkBox_actor_translate`、`checkBox_tag_translate` 等）；
- **核心执行逻辑**（`mdcx/core/translate.py:translate_title_outline`）：
  ```python
  title_translate = manager.config.get_field_config(CrawlerResultFields.TITLE).translate
  outline_translate = manager.config.get_field_config(CrawlerResultFields.OUTLINE).translate
  # 只有当 title_translate 或 outline_translate 为 True 时，程序才会调用大模型翻译
  if manager.config.translate_config.translate_by and (
      (trans_title and title_translate) or (trans_outline and outline_translate)
  ):
      ...
  ```
  当用户取消勾选「使用翻译引擎翻译标题」时，标题不走 LLM 翻译；取消勾选「使用翻译引擎翻译简介」时，简介不走 LLM 翻译；两者均取消时，刮削过程完全不发起 LLM 请求。

### 2. 路线选择及实现依据【已查证 & 已实测】

根据任务单 R3 处理规则：
> “如果有字段级翻译开关：删除 `checkBox_llm` 这个勾选框（只有一种引擎，不需要选）。在说明里写清楚：要关闭翻译，就到某处关闭对应字段的翻译开关。”

本轮严格选择并执行**第 2 条路线**：
1. **删除 `checkBox_llm` 控件与无用的引擎外框**：
   - 在 `mdcx/views/MDCx.ui` 中，彻底移除已无多引擎选择意义的 `checkBox_llm`，并移除原本用于容纳多引擎复选框的 `groupBox_trans`（“翻译引擎”分组）；
   - 平移调整翻译页后续所有分组的纵坐标（`groupBox_llm` 移至 `y=20`，后续 `groupBox_82`～`groupBox_89` 向上紧凑对齐，页面高度收敛为 2400）；重新运行 `scripts/pyuic.sh` 编译 `MDCx.py`；
2. **控制器清理**：
   - `load_config.py`：移除 `self.Ui.checkBox_llm` 的状态绑定代码，清理未使用的 `Translator` 导入；
   - `save_config.py`：移除通过 `checkBox_llm` 构造列表的逻辑，统一维护 `manager.config.translate_config.translate_by = [Translator.LLM]`；
3. **使用说明指引**：
   - 在说明第八节明确指引：“要启用或关闭特定内容的翻译，直接在下方各字段设置中勾选或取消即可（例如在「标题」中勾选或取消「使用翻译引擎翻译标题」，在「简介」中勾选或取消「使用翻译引擎翻译简介」；演员名、标签、系列、片商、发行商、导演等字段则由各字段的映射表开关独立控制）”；
4. **测试覆盖**：
   - 在 `tests/test_ui_terms.py` 中增加 `test_r3_checkbox_llm_removed_and_field_switches_present` 与 `test_field_level_translation_switches_control_translation`，严格验证 `checkBox_llm` 已从 UI 彻底消除，且字段级开关真实存在有效。

---

## 验证与测试汇总

1. **自动化测试集**【已实测】：
   - 执行命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`
   - 结果：**783 passed, 14 skipped, 2 warnings**（原 776 项全部保持通过，新增 7 项 R1/R2/R3 专项测试全部通过）。
2. **代码风格与规范**【已实测】：
   - 执行命令：`.venv/bin/ruff check mdcx tests && .venv/bin/ruff format --check mdcx tests`
   - 结果：**All checks passed! 218 files already formatted.**
3. **Windows 交叉测试构建**【已实测】：
   - 执行工作流：`.github/workflows/test-build-windows.yml`（在临时提交 `d92109a` 中触发，基于功能提交 `9986eb3` 构建）；
   - 构建耗时：2 分 11 秒，所有 Windows 端验证步骤（含 pytest 与版本校验）100% 成功；
   - 产生 Artifact：`windows-x86_64-test-9986eb3` (ID `12116699991`)。
