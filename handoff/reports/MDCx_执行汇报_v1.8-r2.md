# MDCx 执行汇报 v1.8-r2：PR #12 返工（使用说明事实错误、Cookie 教程优化、翻译开关清理）

日期：2026-10-18  
执行分支：`feat/llm-only-and-resources`（PR #12 保持草稿、未合并）  
交付构建：Windows x86_64 测试版（Artifact ID: `12118181873`）  
对应任务单：`handoff/MDCx任务单_v1.8-r2.md`（以提交 `4ef2bbb` 为准）

---

## 任务自查表

| 序号 | 任务项 | 状态 | 证据所在位置（测试名 / 命令输出 / 提交号） |
|---|---|---|---|
| **R1.1** | 主温度默认 0.9，备用温度默认 0.9（`models.py:80`、`default_config.json:659`） | **完成** | `test_temperature_defaults_and_default_config_json`、`test_r1_facts_in_about_text`（提交 `9986eb3`） |
| **R1.2** | 移除编造的「使用备用模型」开关，改为说明备用地址留空即停用（`llm_settings.py:16`、`models.py:121`） | **完成** | `test_r1_facts_in_about_text`（提交 `9986eb3`） |
| **R1.3** | 本机模型按钮真实名称核正（「查找 / 验证路径」「重新查找」「启动备用模型」「停止」「打开日志」） | **完成** | `test_r1_facts_in_about_text`、`test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`（提交 `9986eb3`） |
| **R1.4** | 演员数据库控件文字更正为「使用数据库补全演员信息」（`MDCx.ui:14930`） | **完成** | `test_r1_facts_in_about_text`、`test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`（提交 `9986eb3`） |
| **R1.5** | 设置保存按钮更正为「保存」（`pushButton_save_config`），删除无依据的「自动保存配置」半句 | **完成** | `test_r1_facts_in_about_text`、`test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`（提交 `9986eb3`） |
| **R1.6** | 分集设置标签页核正为「设置」-「命名」的「分集命名规则」（`MDCx.ui:7588`） | **完成** | `test_r1_facts_in_about_text`、`test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`（提交 `9986eb3`） |
| **R1.7** | 移除非法提及的 FlareSolverr，仅保留兼容并实测的 CF Bypass（CloudflareBypassForScraping） | **完成** | `test_r1_facts_in_about_text`（提交 `9986eb3`） |
| **R1.8** | 配置异常机制准确描述为“自动切换为使用数据目录下的 `_failed.json`”（`load_config.py:30`） | **完成** | `test_legacy_translate_config_migration_and_save_reload`、`test_r1_facts_in_about_text`（提交 `9986eb3`） |
| **R1.9** | 移除无对应点击事件的“点击左下角版本号检查更新”，字幕标记去除非默认标记 `-UC`、`-U` | **完成** | `test_r1_facts_in_about_text`（提交 `9986eb3`） |
| **R1-核对** | 对整份说明做机械核对：提取所有「」词汇并在 UI/控制器中精确匹配；核对默认值、路径、文件名 | **完成** | `test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`（42 处词汇 100% 匹配；提交 `9986eb3`） |
| **R2.1** | Cookie 教程中「保存配置」全部改为真实按钮名「保存」 | **完成** | `test_cookie_help_content_requirements`（提交 `9986eb3`） |
| **R2.2** | 优先右键选择“复制值 / Copy value”，无则手动框选；注明菜单名以浏览器实际界面为准，提示长 Cookie 避免漏选 | **完成** | `test_cookie_help_content_requirements`（提交 `9986eb3`） |
| **R2.3** | Cookie 教程中涉及 MDCx 界面名称纳入机械核对测试（`tests/test_ui_terms.py`） | **完成** | `test_cookie_help_bracketed_terms_exist_in_ui_or_controllers`（提交 `9986eb3`） |
| **R3.1** | 先查关闭翻译入口：查到所在标签页、分组名、控件 objectName、界面文字及 `MDCx.ui` 行号 | **完成** | 汇报第 R3 节详述；行号 13357–13398 与 13505–13646；测试 `test_r3_engine_selection_checkbox_removed_and_field_switches_present` |
| **R3.2** | 彻底删除 `checkBox_llm` 这一行（`.ui`、`pyuic.sh`、`save_config.py`、`load_config.py` 等所有引用代码） | **完成** | 提交 `9986eb3`、`a2ded91`；机械核对 `git grep -n checkBox_llm` 原样输出为空 |
| **R3.3** | 步骤 1 查到了入口：不新增控件。在说明中指引到「标题」「简介」分组关闭对应字段翻译开关，所用名称纳入机械核对 | **完成** | 说明第八节明确指引；测试 `test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`（提交 `9986eb3`） |
| **R3.4** | 删除「空列表强制改为 `[LLM]`」的处理（`save_config.py`、`models.py`、`migrations.py`），`translate_by = []` 恢复不翻译含义；旧配置仅含被删除引擎时迁移为 `[LLM]` | **完成** | 提交 `a2ded91`；机械核对 `git grep -n "or \[Translator.LLM\]"` 原样输出为空 |
| **R3.5** | 补充专项测试：旧配置只含 google 迁移为 `[LLM]`；旧配置 `[]` 保持 `[]` 且保存再载入仍为 `[]`；`[]` 时翻译函数不被调用（mock 调用 0 次） | **完成** | `test_r3_legacy_config_only_google_migrates_to_llm`、`test_r3_config_empty_translate_by_remains_empty_on_load_and_save_reload`、`test_r3_empty_translate_by_does_not_call_translate_engine`（提交 `a2ded91`） |

---

## 机械核对命令与原样输出

### 1. `git grep -n checkBox_llm` 在分支上输出为空

- **运行命令**：
  ```bash
  git grep -n checkBox_llm
  ```
- **实际返回码**：`1`（grep 无匹配）
- **原样输出**：
  ```

  ```
  *(输出完全为空)*

### 2. `git grep -n "or \[Translator.LLM\]"` 输出为空

- **运行命令**：
  ```bash
  git grep -n "or \[Translator.LLM\]"
  ```
- **实际返回码**：`1`（grep 无匹配）
- **原样输出**：
  ```

  ```
  *(输出完全为空)*

> 注：针对 `or [Translator.LLM.value]` 模式同样进行了检索（`git grep -n "or \[Translator.LLM"`），返回码均为 `1`，输出完全为空。

---

## R1：使用说明（`textBrowser_about`）改动与机械核对

### 1. 9 项事实错误改正结果对照

1. **温度默认值**：
   - 错误表述：“主温度默认 0.2，备用温度默认 1.0”；
   - 代码核对：`mdcx/config/models.py:80` 主温度默认值为 `0.9`，第 103 行备用温度默认等于主温度（即 `0.9`），`resources/config/default_config.json:659` 中两者均为 `0.9`；
   - 改正结果：修改为“主接口温度与备用接口温度（默认均为 <code>0.9</code>）各自独立保存与发送”。
2. **备用模型启用/停用机制**：
   - 错误表述：“「使用备用模型」开关”；
   - 代码核对：界面无此控件，`llm_settings.py:16` 帮助文本与 `models.py:121` 规定：备用地址留空即停用；
   - 改正结果：修改为“备用接口地址填写后即可启用（留空即停用）”。
3. **本机模型按钮名称**：
   - 错误表述：“「查找模型」「验证配置」「启动本机模型」「停止本机模型」”；
   - 代码核对：`mdcx/controllers/main_window/local_model_settings.py` 与 `MDCx.ui` 真实按钮为：`pushButton_search_local_model`（「查找 / 验证路径」）、`pushButton_refresh_local_model`（「重新查找」）、`pushButton_start_local_model`（「启动备用模型」）、`pushButton_stop_local_model`（「停止」）、`pushButton_open_local_model_log`（「打开日志」）；
   - 改正结果：全部更正为真实控件名称。
4. **演员数据库控件名称**：
   - 错误表述：“「使用演员数据库」”；
   - 代码核对：`mdcx/views/MDCx.ui:14930` 控件 `checkBox_actor_db_enable` 的界面文字为“使用数据库补全演员信息”；
   - 改正结果：更正为「使用数据库补全演员信息」。
5. **保存按钮与自动保存配置**：
   - 错误表述：“「保存配置」，以及「或勾选自动保存配置」”；
   - 代码核对：`MDCx.ui:23788` 控件 `pushButton_save_config` 界面文字为「保存」；代码中不存在“自动保存配置”开关；
   - 改正结果：按钮名称更正为「保存」，删去“或勾选自动保存配置”半句。
6. **分集设置所在标签页**：
   - 错误表述：“「设置 → 分集」”；
   - 代码核对：设置页没有“分集”标签页，实际标签页为：刮削目录、刮削模式、刮削网站、下载、命名、翻译、字幕、水印、NFO、演员、网络、高级。分集设置实际位于「设置」-「命名」标签页下的「分集命名规则」分组（`MDCx.ui:7588`）；
   - 改正结果：指引更正为“在「设置」-「命名」的「分集命名规则」中”。
7. **Cloudflare 拦截工具**：
   - 错误表述：“可配置 FlareSolverr / CF Bypass”；
   - 代码核对：仓库无 FlareSolverr 实现且接口不兼容，已由用户实测否决；当前唯一支持的拦截服务为 CF Bypass（CloudflareBypassForScraping，见 `web_async.py`）；
   - 改正结果：删除 FlareSolverr，仅保留 CF Bypass。
8. **配置异常恢复机制**：
   - 错误表述：“原文件会备份为 *_failed.json”；
   - 代码核对：`mdcx/controllers/main_window/load_config.py:30` 的实际逻辑为：当配置载入校验失败时，自动切换为使用数据目录下的 `_failed.json` 作为后备配置，而不是将原文件重命名为 `_failed.json`；
   - 改正结果：修改为“若因手动修改导致配置读取或校验出错，程序会自动切换为使用数据目录下的 <code>_failed.json</code>，避免破坏原有配置文件”。
9. **版本号点击更新与非默认字幕标记**：
   - 错误表述：“点击主界面左下角版本号亦可检查更新”、字幕标记“-UC、-U”；
   - 代码核对：主界面左下角版本号无点击事件绑定；默认字幕标记为 `-C`（中文字幕）等，`-UC`/`-U` 非内置默认规则；
   - 改正结果：彻底删除左下角点击检查更新的表述，删除 `-UC`/`-U` 字幕标记。

### 2. 机械核对测试（`tests/test_ui_terms.py`）

新增自动化机械核对测试 `test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers`：
1. **测试逻辑**：
   - 使用 `xml.etree.ElementTree` 解析 `mdcx/views/MDCx.ui`；
   - 提取 `textBrowser_about` 中所有由中文括号 `「...」` 括起的词汇；
   - 清空 DOM 中 `textBrowser_about` 文本，遍历 `MDCx.ui` 剩余全部 UI 字符串及 `mdcx/controllers/**` 下所有源码构建检索语料库；
   - 逐一断言每一个中文括号词汇在语料库中存在完全相同的文字；任何一个不匹配即断言失败。
2. **测试结果**：说明中共提取 60 处 `「...」` 引用，去重后为 42 个独立控件/标签页/按钮/分组名称，全部精确匹配，**0 缺失、100% 通过**。
3. **42 项核对词汇明细**：
   - **导航与标签页（11 项）**：`「设置」`、`「主界面」`、`「日志」`、`「工具」`、`「刮削目录」`、`「刮削网站」`、`「命名」`、`「字幕」`、`「翻译」`、`「演员」`、`「网络」`
   - **分组与功能区（5 项）**：`「分集命名规则」`、`「文件清理设置」`、`「Cookie设置」`、`「标题」`、`「简介」`
   - **主操作与按钮（11 项）**：`「开始」`、`「保存」`、`「重新刮削」`、`「输入网址重新刮削」`、`「查找 / 验证路径」`、`「重新查找」`、`「将所选本机模型设为备用」`、`「启动备用模型」`、`「停止」`、`「打开日志」`、`「检查cookie」`
   - **下载入口（5 项）**：`「点击下载头像包」`、`「点击下载字幕包」`、`「点击下载水印图片包」`、`「点击下载演员数据库」`、`「如何获取 Cookie？点击查看教程」`
   - **配置字段与勾选框（10 项）**：`「待刮削目录」`、`「成功输出目录」`、`「失败输出目录」`、`「排除目录」`、`「过滤文件名多余字符」`、`「保存日志」`、`「使用翻译引擎翻译标题」`、`「使用翻译引擎翻译简介」`、`「使用数据库补全演员信息」`、`「开发者模式」`

### 3. 说明中的默认值、路径与文件名核对清单

- **默认值**：
  - 主接口温度默认值：`0.9`（对照 `models.py:80`）
  - 备用接口温度默认值：`0.9`（对照 `models.py:103`）
  - 全局默认配置：`resources/config/default_config.json` 中两者均为 `0.9`
- **路径与文件名**：
  - 本机模型日志路径：`logs/hymt2/<本次启动子目录>/llama-server.log`（对照 `local_model.py:44`）
  - 主程序日志路径：配置文件同级 `Log/` 目录按时间命名的 `.txt`（对照 `consts.py`）
  - 异常备份配置文件名：`_failed.json`（对照 `load_config.py:30`）
  - 排除待删目录默认名：`_pending_delete`（对照 `models.py:43`）
  - 水印图标目录：`userdata/watermark/`（对照 `resources.py`）
  - 演员 SQLite 数据库格式：`Actress-*.db`（对照资源仓库 Release 资源规范）

---

## R2：Cookie 教程（`resources/html/cookie_help.html`）改动

1. **按钮名称更正**：
   - 教程第二节中所有指导文字将原『保存配置』全部更正为『保存』，与 MDCx 界面右下角真实按钮文字完全一致。
2. **复制 Cookie 操作优化**：
   - 第一节第 5 条明确指引：优先在 `Cookie`（或 `cookie`）行上点击鼠标右键，选择 **“复制值 / Copy value”**；若右键菜单中没有该项，再手动框选该行对应的值文本并右键复制；
   - 补充说明：“优先使用右键菜单中的‘复制值 / Copy value’可避免长 Cookie 在手动框选时光标截断或漏选字符。不同浏览器或语言版本的右键菜单名称可能略有差异，请以你的浏览器实际界面为准”。
3. **纳入机械核对测试**：
   - 教程中涉及 MDCx 界面的名称全部使用 `「...」` 标注：`「设置」`、`「网络」`、`「Cookie设置」`、`「检查cookie」`、`「保存」`；
   - 在 `tests/test_ui_terms.py` 中编写 `test_cookie_help_bracketed_terms_exist_in_ui_or_controllers` 与 `test_cookie_help_content_requirements`，断言教程所有括号词汇在 MDCx 代码中真实存在，且教程不含“保存配置”字样；测试 100% 通过。

---

## R3：删除「LLM」勾选框，翻译开关由用户控制

### 1. 步骤 1：排查关闭翻译入口【已查证】

经排查 `mdcx/views/MDCx.ui` 与控制器逻辑，**界面上具备按字段开启/关闭翻译的完整入口**：
- **所在标签页**：左侧导航「设置」（`tab_settings`）中的「翻译」标签页（`tab_6`）；
- **分组 1**：`groupBox_82`，分组标题为「标题」，`MDCx.ui` 第 **13357–13379** 行；
  - 控件 objectName：`checkBox_title_translate`，`MDCx.ui` 第 **13394** 行；
  - 控件界面文字：「使用翻译引擎翻译标题」，`MDCx.ui` 第 **13396** 行；
- **分组 2**：`groupBox_83`，分组标题为「简介」，`MDCx.ui` 第 **13505–13528** 行；
  - 控件 objectName：`checkBox_outline_translate`，`MDCx.ui` 第 **13642** 行；
  - 控件界面文字：「使用翻译引擎翻译简介」，`MDCx.ui` 第 **13644** 行；
- **其他字段**：`groupBox_84`～`groupBox_89` 分别提供演员、标签、系列、片商、发行商、导演的映射表翻译独立开关（`checkBox_actor_translate`、`checkBox_tag_translate` 等）；
- **执行逻辑验证**（`mdcx/core/translate.py:281`）：
  ```python
  if manager.config.translate_config.translate_by and (
      (trans_title and title_translate) or (trans_outline and outline_translate)
  ):
      ...
  ```
  当取消勾选「使用翻译引擎翻译标题」时，标题不翻译；取消勾选「使用翻译引擎翻译简介」时，简介不翻译；两者均取消时不发起任何翻译调用。

### 2. 步骤 2：删除 `checkBox_llm` 这一行【已落实】

- 在 `mdcx/views/MDCx.ui` 中，彻底移除已无多引擎选择意义的 `checkBox_llm` 控件及其容纳外框 `groupBox_trans`；后续分组纵坐标平移对齐；
- 运行 `scripts/pyuic.sh` 重新编译生成 `mdcx/views/MDCx.py`；
- 在 `mdcx/controllers/main_window/load_config.py` 中移除对 `checkBox_llm` 的设置与绑定代码；
- 在 `mdcx/controllers/main_window/save_config.py` 中移除原先通过 `checkBox_llm` 赋值列表的逻辑以及强制覆盖语句；
- 机械核对 `git grep -n checkBox_llm` 输出完全为空。

### 3. 步骤 3：选路说明（依据步骤 1 查到的行号）

- **选路依据**：步骤 1 在 `MDCx.ui` 第 13357–13646 行查到了各字段翻译开关（`checkBox_title_translate`、`checkBox_outline_translate` 等），因此执行步骤 3 第一种情况：**不新增控件**。
- **说明指引**：在软件内使用说明（`textBrowser_about`）第八节写入明确指引：
  > “要启用或关闭特定内容的翻译，直接在下方各字段设置中勾选或取消即可（例如在「标题」中勾选或取消「使用翻译引擎翻译标题」，在「简介」中勾选或取消「使用翻译引擎翻译简介」；演员名、标签、系列、片商、发行商、导演等字段则由各字段的映射表开关独立控制）。”
  所用名称纳入机械核对测试并通过。

### 4. 步骤 4：删除强制兜底为 `[LLM]`，恢复 `translate_by = []` 语义【已落实】

- **`models.py`**：在 `TranslateConfig.normalize_translate_by` 中删除 `kept or [Translator.LLM]`，改为：
  ```python
  if isinstance(value, list):
      if not value:
          return []
      kept = [Translator.LLM for item in value if item in (Translator.LLM, Translator.LLM.value)]
      if kept:
          return kept
      return [Translator.LLM]
  ```
  旧配置如果显式为 `[]`，解析后保持 `[]`；仅当旧配置包含且只包含已删除引擎（如 `["google"]`）时，保留 v1.8 规则迁移为 `[Translator.LLM]`。
- **`migrations.py`**：同步更新 `translate_by` 迁移逻辑，删除 `or [Translator.LLM.value]`，空列表保留为 `[]`，仅含已删除引擎时迁移为 `[Translator.LLM.value]`。
- **`save_config.py`**：删除在界面保存配置时硬编码覆盖 `manager.config.translate_config.translate_by = [Translator.LLM]` 的代码，保存操作不破坏已有 `translate_by` 配置。
- **机械核对**：`git grep -n "or \[Translator.LLM\]"` 输出完全为空。

### 5. 步骤 5：补充测试（测试名与验证结果）

在 `tests/test_translate_llm.py` 中新增并验证以下测试：
1. `test_r3_legacy_config_only_google_migrates_to_llm`：
   - 验证旧配置只含 `["google"]` 时，载入后自动迁移为 `[Translator.LLM]`，保存后写入 `["llm"]`，再次载入仍为 `[Translator.LLM]`。**PASSED**。
2. `test_r3_config_empty_translate_by_remains_empty_on_load_and_save_reload`：
   - 验证旧配置为 `[]` 时，载入后仍为 `[]`，调用 `save()` 保存后磁盘文件保持 `[]`，再次载入仍为 `[]`。**PASSED**。
3. `test_r3_empty_translate_by_does_not_call_translate_engine`：
   - 验证当 `translate_by = []` 时，调用 `translate_title_outline`，通过 `mock` 断言底层翻译函数 `translate_with_engine` 调用次数严格为 0（`mock_translate_with_engine.call_count == 0`），且原始内容完整保留。**PASSED**。

---

## 验证与交付汇总

### 1. 本地全量测试与代码质量

- **自动化测试执行**：
  - 执行命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`
  - 测试结果：**786 passed, 14 skipped, 2 warnings in 94.44s**（原 776 项保持通过，新增 10 项专项测试全部通过）。
- **静态检查与格式化**：
  - 执行命令：`.venv/bin/ruff check mdcx tests && .venv/bin/ruff format --check mdcx tests`
  - 检查结果：**All checks passed! 218 files already formatted.**

### 2. GitHub Actions CI/CD 与 Windows 交叉测试构建

- **功能提交**：`a2ded916211611b8660e20db1bd6f2bef4b3bdc3`（`fix(translate): 完善空列表 translate_by 保留逻辑与机械核对测试`）
- **工作流更新提交**：`f55f9396cde4304fa1abd838a7b1b9ee60113d81`（`ci: 更新临时 Windows 测试构建工作流以指向 a2ded91 (合并前删除)`）
- **CI/CD Pipeline**（Run ID: `39078771096`）：
  - 状态：**Success**（Tests in 2m26s、Code Quality in 7s 均通过）。
  - 链接：[GitHub Actions Run 39078771096](https://github.com/Marcus515J/mdcx/actions/runs/39078771096)
- **Windows 测试构建**（Run ID: `39078768986`）：
  - 耗时：2 分 11 秒，所有 Windows 端自动化步骤（依赖安装、全套专项测试、版本校验、PyInstaller 打包校验）100% 成功。
  - 产生 Artifact：`windows-x86_64-test-a2ded91`（Artifact ID: `12118181873`，大小: 145.8 MB）。
  - 下载链接：[下载 windows-x86_64-test-a2ded91.zip](https://github.com/Marcus515J/mdcx/actions/runs/39078768986/artifacts/12118181873)

### 3. 分支与交付规范遵循

- 功能代码与测试修改保持在 `feat/llm-only-and-resources` 分支；
- PR #12 保持 **Draft（草稿）** 状态，未合并；
- 本汇报位于 `handoff/reports/MDCx_执行汇报_v1.8-r2.md` 并推送到 `handoff` 分支；
- 未打标签（Git Tag）、未发布 GitHub Release、未改动资源仓库（`Marcus515J/mdcx-resources`）。
