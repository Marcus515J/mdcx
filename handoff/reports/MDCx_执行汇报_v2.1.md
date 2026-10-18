# MDCx 执行汇报 v2.1：查清主界面「成功」列表分辨率后缀的来源与配置关系

- **执行日期**：2026-10-18
- **执行方**：Antigravity（Gemini 3.8 Flash）
- **基线分支**：`master`
- **master HEAD 提交**：`5eb64efcf093dac25ddcc847528ededcbe6bbf7b`
- **当前任务模式**：本单只查不改。不改动仓库任何代码、配置与文档；代码全部基于 `master` 最新提交查阅；唯一产出为本汇报文件，提交并推送到 `handoff` 分支。
- **汇报文件位置**：`handoff/reports/MDCx_执行汇报_v2.1.md`

---

## 机械核对自查清单

| # | 核对项 | 要求 | 自查结果 | 对应章节 |
|---|---|---|---|---|
| 1 | HEAD 提交号 | master 上 `5eb64ef` 或之后提交 | `5eb64efcf093dac25ddcc847528ededcbe6bbf7b` | 头部信息、第六节 |
| 2 | Q1 列表文字生成 | 有完整路径 + 行号，贴出最终拼接文字的那一行 | 完整调用链路已查清，包含信号触发与 UI 节点注入，贴出最终拼接代码 | 第一节 (Q1) |
| 3 | Q2 配置表 | §1 里的每一项都有「有影响 / 无影响」结论和代码位置 | 11 个配置项全部逐项分析并给出路径、行号与机制解释 | 第二节 (Q2) |
| 4 | Q3、Q4 结论 | 各自明确为 A / B / C 之一 | Q3 明确为 **B**；Q4 明确为 **A** | 第三节 (Q3)、第四节 (Q4) |
| 5 | Q5 来源追溯 | 有提交号和日期，查明 upstream / fork 来源 | 查清由 upstream `sqzw-x` 提交 `28c4f83` 与 `d59ab45` 引入（2025-07-22），非本仓库改动 | 第五节 (Q5) |
| 6 | Q6 机械验证 | 基线 + 5 组 + 附加组均有输出，附录附完整验证脚本 | 全部完成离线执行，贴出输出矩阵表格与附录源码 | 第六节 (Q6)、附录 |
| 7 | 仓库无改动 | master 上 `git status` 干净；handoff 只新增本汇报 | master 干净（贴出原样输出）；handoff 仅新增本汇报 | 第七节 |
| 8 | 无密钥 | 严禁泄露任何真实 Key / Cookie | 全文无任何真实 Key、密码或 Cookie | 全文已确认 |

---

## Q1 列表文字是哪里生成的

【已查证】

主界面右侧「成功」列表展示的每一条文本，从刮削流程到最终呈现在 UI 树状列表（`self.Ui.treeWidget_number`）中，调用链路如下：

### 1. 完整执行链路（文件路径与行号）

1. **分辨率解析与写入 `FileInfo`**：
   - 文件路径：[`mdcx/core/scraper.py:758-759`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L758-L759)
   - 代码：
     ```python
     758: definition, codec = await get_video_size(file_path, file_info.number)
     759: file_info.definition, file_info.codec = definition, codec
     ```
   - 说明：在异步单任务刮削核心函数 `_process_one_file` 中，通过 `get_video_size` 读取文件或路径分辨率（如 1080P、4K 等），并写入 `file_info.definition`。

2. **列表条目字符串（`show_name`）格式化拼接**：
   - 文件路径：[`mdcx/core/scraper.py:451-459`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L451-L459)
   - 代码：
     ```python
     451: show_data.show_name = (
     452:     str(Flags.count_claw)
     453:     + "-"
     454:     + str(Flags.succ_count)
     455:     + "."
     456:     + file_show_name.replace(number, file_info.number)
     457:     + ("-" if file_info.definition else "")
     458:     + file_info.definition
     459: )
     ```
   - 说明：刮削完成后进入展示数据构造，将总抓取批次编号、成功计数、基础文件名与分辨率后缀拼接为 `show_data.show_name`。

3. **跨线程 Qt 信号发射**：
   - 文件路径：[`mdcx/core/scraper.py:460`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L460) 与 [`mdcx/signals.py:71-72`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/signals.py#L71-L72)
   - 代码：
     ```python
     # mdcx/core/scraper.py
     460: signal.show_list_name("succ", show_data, number)

     # mdcx/signals.py
     71: def show_list_name(self, status: Literal["succ", "fail"], show_data: ShowData, real_number=""):
     72:     self.exec_show_list_name.emit(status, show_data, real_number)
     ```
   - 说明：刮削后台工作线程通过 Qt 信号 `exec_show_list_name` 将 `show_data` 投递给主界面主线程。

4. **信号槽分发接收**：
   - 文件路径：[`mdcx/controllers/main_window/init.py:167`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/main_window/init.py#L167) 与 [`mdcx/controllers/main_window/main_window.py:1084-1086`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/main_window/main_window.py#L1084-L1086)
   - 代码：
     ```python
     # init.py
     167: signal_qt.exec_show_list_name.connect(self.show_list_name)

     # main_window.py
     1084: def show_list_name(self, status: Literal["succ", "fail"], show_data: ShowData, real_number=""):
     1085:     # 添加树状节点
     1086:     self._addTreeChild(status, show_data.show_name)
     ```

5. **UI 树节点（`QTreeWidgetItem`）创建与挂载**：
   - 文件路径：[`mdcx/controllers/main_window/main_window.py:1051-1055`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/main_window/main_window.py#L1051-L1055)
   - 代码：
     ```python
     1051: def _addTreeChild(self, result, filename):
     1052:     node = QTreeWidgetItem()
     1053:     node.setText(0, filename)
     1054:     if result == "succ":
     1055:         self.item_succ.addChild(node)
     1056:     else:
     1057:         self.item_fail.addChild(node)
     ```
   - 说明：在主界面右侧树状控件（`self.Ui.treeWidget_number`）的「成功」父节点（`self.item_succ`）下添加子节点，节点的第 0 列文字即为 `filename`（即 `show_data.show_name`）。

### 2. 最终拼接该条文字的那一行代码

位于 [`mdcx/core/scraper.py:457-458`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L457-L458)：
```python
+ ("-" if file_info.definition else "")
+ file_info.definition
```
（在失败分支 [`mdcx/core/scraper.py:469-470`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L469-L470) 中也有完全相同的两行）。

---

## Q2 后缀的来源与条件

【已查证】

### 1. 变量与代码来源

- **来源变量**：`file_info.definition`（字符串类型，如 `"1080P"`、`"4K"`、`"720P"`、`"FHD"` 等）。
- **赋值位置**：[`mdcx/core/scraper.py:758-759`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L758-L759)：
  ```python
  definition, codec = await get_video_size(file_path, file_info.number)
  file_info.definition, file_info.codec = definition, codec
  ```
- **生成该变量的底层函数**：[`mdcx/core/utils.py:209-261`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/utils.py#L209-L261)（`get_video_size`）：
  - 当 `manager.config.hd_get == "video"` 时，调用 `get_video_metadata` 读取视频文件高度；
  - 当 `manager.config.hd_get == "path"` 时，调用 `_detect_height_from_path` 从文件名正则表达式匹配高度；
  - 根据高度数值（`height >= 1000`、`2000`、`700` 等）及 `manager.config.hd_name`（`"height"` 或 `"hd"`）映射出分辨率文本（如 1080P 或 FHD）。
- **拼接到文字的代码**：[`mdcx/core/scraper.py:457-458`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L457-L458)。

### 2. 对 §1 配置项逐项影响分析表

| # | 配置项 | 用户的当前值 | 对列表分辨率后缀的影响 | 代码位置（路径 + 行号） | 详细机制说明 |
|---|---|---|---|---|---|
| 1 | `hd_name` | `"height"` | **有影响**（影响显示文字风格） | [`mdcx/core/utils.py:237-260`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/utils.py#L237-L260) | 决定分辨率格式：为 `"height"` 时生成 720P、1080P、4K 等；为 `"hd"` 时生成 HD、FHD、QHD、UHD 等。对应 UI 单选框「720P、1080P、4K、8K」与「HD、FHD、QHD、UHD」。 |
| 2 | `hd_get` | `"video"` | **有影响**（决定是否提取分辨率） | [`mdcx/core/utils.py:222-236`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/utils.py#L222-L236) | 决定分辨率获取方式：`"video"` 为读取画面高度；`"path"` 为从文件名正则提取；若用户在界面勾选「不获取分辨率」（对应 `""`），则 `height=0`，`definition` 为空，列表不会追加分辨率后缀。 |
| 3 | `folder_hd` | `true` | **无影响** | [`mdcx/core/file.py:241`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L241)、[`mdcx/core/naming/fields.py:98`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/naming/fields.py#L98) | 对应 UI 复选框「添加 4K 字符：视频目录名」（`checkBox_foldername_4k`）。仅在重命名输出文件夹目录时，控制是否给模板里的 `number` 变量追加 4K/8K 后缀，与主界面列表文字完全无关。 |
| 4 | `file_hd` | `true` | **无影响** | [`mdcx/core/file.py:280`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L280)、[`mdcx/core/naming/fields.py:98`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/naming/fields.py#L98) | 对应 UI 复选框「添加 4K 字符：视频文件名」（`checkBox_filename_4k`）。仅在重命名磁盘视频文件时，控制是否给模板里的 `number` 变量追加 4K/8K 后缀，与主界面列表文字完全无关。 |
| 5 | `mark_type` | `["sub","umr","leak","uncensored","hd"]` | **无影响** | [`mdcx/core/image.py:40-44`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/image.py#L40-L44)、[`mdcx/controllers/cut_window.py:353`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/cut_window.py#L353) | 对应 UI「启用的水印类型」中的「HD」复选框（`checkBox_hd`）。仅控制在封面海报或截图角落打上海报画质角标/水印，与列表文字完全无关。 |
| 6 | `suffix_sort` | `["moword","definition","cnword"]` | **无影响** | [`mdcx/core/file.py:670-676`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L670-L676)、[`mdcx/core/scraper.py:456-458`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L456-L458) | 在 `get_file_info_v2`（第 670–676 行）中遍历 `suffix_sort` 构造 `file_show_name` 时，代码**只处理了 `moword` 和 `cnword`，根本没有写 `definition` 分支**；而在 `scraper.py:457-458` 中又直接无条件硬拼接了 `file_info.definition`，完全绕过了 `suffix_sort`。 |
| 7 | `folder_moword` / `file_moword` | `true` / `true` | **无影响** | [`mdcx/core/file.py:243, 282`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L243) | 仅控制输出目录名/文件名中是否包含马赛克破坏版字符，与列表显示及分辨率无关。 |
| 8 | `folder_cnword` / `file_cnword` | `true` / `true` | **无影响** | [`mdcx/core/file.py:242, 281`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L242) | 仅控制输出目录名/文件名中是否包含中文字幕字符，与列表显示及分辨率无关。 |
| 9 | `success_file_rename` | `true` | **无影响** | [`mdcx/core/file.py:261`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L261) | 仅控制刮削成功后是否执行文件重命名，不影响刮削过程中的列表展示构造。 |
| 10 | `naming_file` | `{{ number }} {{ title }}` | **无影响** | [`mdcx/core/file.py:269-275`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L269-L275) | 磁盘文件名的 Jinja2 渲染模板，仅用于落盘重命名，列表项文字不使用该模板。 |
| 11 | `naming_media` | `{% if number %}...` | **无影响** | [`mdcx/controllers/main_window/load_config.py:614`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/main_window/load_config.py#L614) | 媒体目录命名模板，不参与主刮削列表项命名。 |

### 3. 加后缀代码的判断条件

- **结论**：**【无条件】**。
- **依据**：代码在 [`mdcx/core/scraper.py:457-458`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L457-L458) 处原样为：
  ```python
  + ("-" if file_info.definition else "")
  + file_info.definition
  ```
  此处仅进行了一个简单的三元运算：`file_info.definition` 是否非空。只要字符串非空（即探测到了分辨率），就必定拼接 `"-"` 并追加该分辨率文本。**没有任何配置开关或开关变量参与判断**。

---

## Q3 结论

【已查证】

**结论：B 不受任何配置控制，永远加（代码行为，属设计缺陷与历史遗留）。**

### 依据分析：

1. **不存在对应的列表控制项**：整个 MDCx 项目中，没有任何一个配置项是用于控制「主界面右侧列表是否显示分辨率后缀」的。
2. **用户认知的偏差来源**：
   - 用户在 UI 上看到的开关是「命名」-「画质命名规则」中的「添加 4K 字符：视频文件名 / 视频目录名」（内部配置为 `file_hd` / `folder_hd`）。
   - 界面文字明确标注为：`指命名时在番号后添加 4K（仅4K）`。这两个开关**只作用于磁盘文件/文件夹重命名**，而且按其设计原本就只针对 4K/8K 生效，对列表文字完全不生效。
   - 用户关闭或以为关闭了分辨率后缀，但主界面列表依然每条必带，是因为列表文字根本不受这些开关控制。
3. **唯一的连带间接项**：只有当用户彻底将「分辨率获取方式」改为「不获取分辨率」（`hd_get = ""`）时，由于不获取视频高度，`file_info.definition` 成为空字符串，列表才不会带该后缀；但这会导致 NFO 标签、视频元数据等正常画质信息也一并不被采集，不是正常业务所期望的行为。

---

## Q4 显示 vs 落盘

【已查证】

**结论：A 只是列表显示，落盘名不受影响。**

### 1. 落盘重命名文件名与文件夹名的代码位置与逻辑

- **重命名文件名生成入口**：[`mdcx/core/file.py:255-301`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L255-L301)（`_generate_file_name`）：
  ```python
  274: result = render_name(
  275:     file_name_template,
  276:     file_info,
  277:     res,
  278:     NameRenderOptions(
  279:         target=NamingTarget.FILE,
  280:         show_definition_suffix=manager.config.file_hd,
  ...
  ```
- **重命名文件夹名生成入口**：[`mdcx/core/file.py:235-246`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L235-L246)（`_get_folder_path`）：
  ```python
  235: result = render_name(
  236:     folder_name,
  237:     file_info,
  238:     res,
  239:     NameRenderOptions(
  240:         target=NamingTarget.FOLDER,
  241:         show_definition_suffix=manager.config.folder_hd,
  ...
  ```
- **落盘命名上下文构造核心**：[`mdcx/core/naming/fields.py:97-107`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/naming/fields.py#L97-L107)（`build_naming_context`）：
  ```python
  97: definition_suffix = ""
  98: if show_definition_suffix and definition in {"8K", "UHD", "4K"}:
  99:     definition_suffix = f"-{definition}"
  100: 
  101: suffix_values = {
  102:     "moword": moword if show_moword_suffix else "",
  103:     "cnword": cnword if show_cnword_suffix else "",
  104:     "definition": definition_suffix,
  105: }
  106: for suffix in manager.config.suffix_sort:
  107:     number += suffix_values.get(getattr(suffix, "value", str(suffix)), "")
  ```

### 2. 差异对比：

1. **普通高清视频（如 1080P、720P）**：
   - **落盘名**：在 `fields.py:98` 中，条件 `definition in {"8K", "UHD", "4K"}` 判定为 `False`，因此 `definition_suffix` 为空字符串。在用户的 `naming_file = "{{ number }} {{ title }}"` 模板下，落盘文件名是 `ABC-123 标题.mp4`，**绝不会带 `-1080P` 或 `-720P` 后缀**。
   - **列表显示**：在 `scraper.py:458` 中无条件追加 `file_info.definition`，显示为 `1-1.ABC-123-1080P`。
2. **超高清视频（如 4K、8K）**：
   - **落盘名**：严格受 `file_hd` 控制。若 `file_hd == True`，落盘文件名带 `-4K`（如 `ABC-123-4K 标题.mp4`）；若 `file_hd == False`，落盘文件名**不带** `-4K`。
   - **列表显示**：无论 `file_hd` 是 `True` 还是 `False`，列表文字始终显示 `1-1.ABC-123-4K`。
3. **结论**：两处为完全独立的两套逻辑，列表上的分辨率后缀**纯粹是 UI 显示层的硬编码行为**，实际写到硬盘上的文件与文件夹名称完全不受其影响。

---

## Q5 来源追溯

【已查证】

通过 `git blame` 与 `git log -S` 追溯，加后缀的相关代码是 **fork 前（上游 sqzw-x/mdcx）就有的历史遗留缺陷**，并非本仓库 v1.7 或 v1.8 改动引入。

### 详细演变史：

1. **历史初期状态（上游 2025-07-22 之前）**：
   - 原始代码中存在一个内部字段 `json_data["_4K"]`；
   - 仅当分辨率为 4K/8K 时才赋值：
     ```python
     if definition in ["4K", "8K", "UHD", "UHD8"]:
         json_data["_4K"] = "-" + definition
     ```
   - 列表拼接时写入：`+ file_show_name.replace(...) + json_data["_4K"]`。
   - 在此阶段，1080P、720P 等文件在列表上是**不会**出现分辨率后缀的。

2. **缺陷引入提交（上游提交 `28c4f83`）**：
   - **Commit**：`28c4f83af1e1a858167994dcbfa31c2765620c52`
   - **Author**：sqzw `<mdcx.feedback@gmail.com>`
   - **Date**：Tue Jul 22 04:57:40 2025 +0800
   - **Subject**：`refactor!: 消除所有 typeddict 并使用 dataclass 替代`
   - **引入原因**：作者在重构消除 `typeddict` 时，移除了 `json_data["_4K"]`，并将列表拼接处的代码改为：
     ```python
     - + json_data["_4K"]
     + + "-"
     + + file_info.definition
     ```
   - 此处改动直接导致了两个问题：
     - 所有的分辨率（包括 1080P、720P）全部都被无条件拼接上了；
     - 当 `file_info.definition` 为空（未检测到分辨率）时，多出了一个末尾破折号 `-`（如 `1-1.ABC-123-`）。

3. **修补破折号提交（上游提交 `d59ab45`）**：
   - **Commit**：`d59ab4555dd7dbda9f0fad11a4e6af114bc325af`
   - **Author**：sqzw `<mdcx.feedback@gmail.com>`
   - **Date**：Tue Jul 22 11:34:03 2025 +0800（约 6.5 小时后）
   - **Subject**：`fix: 主界面右侧标题多余的横线`
   - **代码变更**：
     ```python
     - + "-"
     + + ("-" if file_info.definition else "")
       + file_info.definition
     ```
   - 上游作者当时只注意到了「为空时多出一条横线」，因此加了三元表达式判断 `file_info.definition` 是否为空；但**遗漏了最初只对 4K/8K 加后缀的前提条件**，从而使「所有非空分辨率均无条件追加到列表文字末尾」这一缺陷被固定留存至今。

4. **后续迁移**：
   - 上游在 `9838a8944bca85ee0c64a6e9849755e981da6006`（2025-08-23 20:23:08 +0800, `feat!: add browser & migrate to pydantic config`）重构时原样继承了该两行代码。
   - 本仓库 fork 之后至今，v1.7 与 v1.8 从未触碰过该处逻辑。

---

## Q6 机械验证

【已实测】

在仓库外部创建了独立的无网络纯离线验证脚本 `/Users/gameong/.gemini/antigravity/scratch/verify_resolution_suffix.py`，使用一条 mock 刮削数据（番号 `ABC-123`，标题 `测试视频标题`），加载 §1 的基线配置，逐项变动进行矩阵测试。

### 1. 验证结果矩阵表格

| 组别 | 输入配置改动 | 识别清晰度 | 列表文字（UI 显示） | 与基线是否不同 | 落盘文件名（实际写盘） |
|---|---|---|---|---|---|
| **基线** | §1 原样（1080P 视频） | `1080P` | `1-1.ABC-123-1080P` | **相同**（基准） | `ABC-123 测试视频标题.mp4` |
| **组 1** | 只把 `file_hd` 改为 `False` | `1080P` | `1-1.ABC-123-1080P` | **相同** | `ABC-123 测试视频标题.mp4` |
| **组 2** | 只把 `folder_hd` 改为 `False` | `1080P` | `1-1.ABC-123-1080P` | **相同** | `ABC-123 测试视频标题.mp4` |
| **组 3** | 只把 `mark_type` 去掉 `"hd"` | `1080P` | `1-1.ABC-123-1080P` | **相同** | `ABC-123 测试视频标题.mp4` |
| **组 4** | 只把 `suffix_sort` 去掉 `"definition"` | `1080P` | `1-1.ABC-123-1080P` | **相同** | `ABC-123 测试视频标题.mp4` |
| **组 5** | 只把 `hd_name` 改为另一个合法值 `"hd"` | `FHD` | `1-1.ABC-123-FHD` | **不同**（风格改变） | `ABC-123 测试视频标题.mp4` |
| **附加组 6** | `hd_get` 改为 `""`（界面「不获取分辨率」） | 空 | `1-1.ABC-123` | **不同**（后缀消除） | `ABC-123 测试视频标题.mp4` |
| **附加组 7** | 4K 视频（2160P，§1 原样） | `4K` | `1-1.ABC-123-4K` | - | `ABC-123-4K 测试视频标题.mp4` |
| **附加组 8** | 4K 视频 + `file_hd = False` | `4K` | `1-1.ABC-123-4K` | - | `ABC-123 测试视频标题.mp4` |

### 2. 实测关键发现

1. **组 1–4 的列表文字与基线 100% 一致**：
   无论如何开关 `file_hd`、`folder_hd`、`mark_type` 或修改 `suffix_sort`，主界面成功列表文字无任何波动，固定为 `1-1.ABC-123-1080P`。
2. **组 5 仅改变命名格式**：
   将 `hd_name` 由 `"height"` 改为 `"hd"` 后，列表文字由 `1-1.ABC-123-1080P` 变为 `1-1.ABC-123-FHD`，证明其确实受 `hd_name` 格式控制。
3. **附加组 6 彻底消除了后缀**：
   当把 `hd_get` 设为空（即界面选择「不获取分辨率」）时，`file_info.definition` 变为空，列表文字成功变为 `1-1.ABC-123`。
4. **附加组 7 与 8 证明了 Q4 的结论**：
   对于 4K 视频，当 `file_hd = False` 时，落盘文件名中的 `-4K` 成功被消除（变为 `ABC-123 测试视频标题.mp4`），但界面列表上依然固定显示 `1-1.ABC-123-4K`。

---

## 仓库状态核对

【已查证】

### 1. master 分支状态（干净，无改动）

在 `master` 分支执行 `git status` 的原样输出：
```
On branch master
Your branch is up to date with 'origin/master'.

nothing to commit, working tree clean
```
`master` HEAD 哈希值（`git rev-parse HEAD`）：
```
5eb64efcf093dac25ddcc847528ededcbe6bbf7b
```

### 2. handoff 分支状态

在 `handoff` 分支仅新增本汇报文件 `handoff/reports/MDCx_执行汇报_v2.1.md`，不改动任何其它文件。

---

## 另见

1. **失败列表存在完全相同的硬编码**：
   在 [`mdcx/core/scraper.py:469-470`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L469-L470)（失败分支）中，`show_data.show_name` 同样写死了 `+ ("-" if file_info.definition else "") + file_info.definition`。如果刮削在获取分辨率之后发生异常失败，失败列表中同样会展示该分辨率后缀。
2. **`suffix_sort` 对 `definition` 的空转**：
   在 [`mdcx/core/file.py:670-676`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/file.py#L670-L676) 中，代码遍历了 `manager.config.suffix_sort`，但只写了 `if each == "moword"` 和 `elif each == "cnword"`，完全忽略了 `definition`；随后在 `scraper.py` 中又强行将其追加到末尾。如果未来需要让列表后缀顺序受 `suffix_sort` 控制或受开关控制，这两处逻辑需要一并梳理。
3. **潜在修复建议（供 Claude 与用户后续评估，本单不改代码）**：
   若后续决定修改代码，使列表与落盘行为保持一致：
   - 方式一（恢复历史本意）：在 `scraper.py` 拼接时判断 `if file_info.definition in {"4K", "8K", "UHD", "UHD8"}` 且检查对应开关；
   - 方式二（完全遵循落盘名）：让列表直接展示已渲染完成的 `file_new_name`（即调用 Jinja 渲染后的文件名），彻底消除显示与落盘的不一致。

---

## 附录：Q6 机械验证脚本源码（未提交进仓库）

文件位于仓库外部路径：`/Users/gameong/.gemini/antigravity/scratch/verify_resolution_suffix.py`

```python
#!/usr/bin/env python3
"""
MDCx v2.1 Q6 机械验证脚本
验证主界面「成功」列表文字的拼接与各项配置的关系，以及显示 vs 落盘差异。
"""

import asyncio
from pathlib import Path
import sys
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent / "mdcx"
sys.path.insert(0, str(REPO_ROOT))

from mdcx.config.enums import MarkType, SuffixSort
from mdcx.config.manager import manager
from mdcx.core.file import _generate_file_name
from mdcx.core.utils import get_video_size
from mdcx.models.flags import Flags
from mdcx.models.types import CrawlersResult, FileInfo, ShowData


def compute_show_name(claw_count: int, succ_count: int, file_show_name: str, number: str, file_info: FileInfo) -> str:
    """mdcx/core/scraper.py:451-459 原样逻辑"""
    return (
        str(claw_count)
        + "-"
        + str(succ_count)
        + "."
        + file_show_name.replace(number, file_info.number)
        + ("-" if file_info.definition else "")
        + file_info.definition
    )


def apply_section_1_config():
    """应用 §1 给出的用户日常配置基线值"""
    manager.config.hd_name = "height"
    manager.config.hd_get = "video"
    manager.config.folder_hd = True
    manager.config.file_hd = True
    manager.config.mark_type = [
        MarkType.SUB,
        MarkType.UMR,
        MarkType.LEAK,
        MarkType.UNCENSORED,
        MarkType.HD,
    ]
    manager.config.suffix_sort = [
        SuffixSort.MOWORD,
        SuffixSort.DEFINITION,
        SuffixSort.CNWORD,
    ]
    manager.config.folder_moword = True
    manager.config.file_moword = True
    manager.config.folder_cnword = True
    manager.config.file_cnword = True
    manager.config.success_file_rename = True
    manager.config.naming_file = "{{ number }} {{ title }}"
    manager.config.naming_media = (
        "{% if number %}{{ number }}{% else %}[]{% endif %}"
        "{% if title and title != number %}{{ title }}{% endif %}"
    )


async def run_single_test(case_name: str, video_height: int = 1080):
    Flags.count_claw = 1
    Flags.succ_count = 1

    fake_file_path = Path("/movies/ABC-123.mp4")
    file_info = FileInfo(
        number="ABC-123",
        letters="ABC",
        has_sub=False,
        c_word="",
        cd_part="",
        destroyed="",
        leak="",
        wuma="",
        youma="",
        mosaic="",
        file_path=fake_file_path,
        folder_path=fake_file_path.parent,
        file_name="ABC-123",
        file_ex=".mp4",
        sub_list=[],
        file_show_name="ABC-123",
        file_show_path=fake_file_path,
        short_number="",
        appoint_number="",
        appoint_url="",
        website_name="",
        definition="",
        codec="",
    )

    res = CrawlersResult.empty()
    res.number = "ABC-123"
    res.title = "测试视频标题"

    with patch("mdcx.core.utils.get_video_metadata", return_value=(video_height, "AVC")):
        definition, codec = await get_video_size(fake_file_path, file_info.number)
        file_info.definition, file_info.codec = definition, codec

    list_text = compute_show_name(
        Flags.count_claw,
        Flags.succ_count,
        file_info.file_show_name,
        file_info.number,
        file_info,
    )
    disk_file_name = _generate_file_name(file_info.cd_part, file_info, res)

    return {
        "case": case_name,
        "definition": definition,
        "list_text": list_text,
        "disk_file_name": disk_file_name + ".mp4",
    }


async def main():
    print("=" * 80)
    print("MDCx v2.1 Q6 机械验证：成功列表分辨率后缀与配置关系矩阵测试")
    print("=" * 80)

    # 1. 基线
    apply_section_1_config()
    baseline = await run_single_test("基线 (§1 配置原样, 1080P 视频)")

    results = [baseline]

    # 组 1: 只把 file_hd 改为 False
    apply_section_1_config()
    manager.config.file_hd = False
    results.append(await run_single_test("组 1: file_hd=False"))

    # 组 2: 只把 folder_hd 改为 False
    apply_section_1_config()
    manager.config.folder_hd = False
    results.append(await run_single_test("组 2: folder_hd=False"))

    # 组 3: 只把 mark_type 去掉 'hd'
    apply_section_1_config()
    manager.config.mark_type = [
        MarkType.SUB,
        MarkType.UMR,
        MarkType.LEAK,
        MarkType.UNCENSORED,
    ]
    results.append(await run_single_test("组 3: mark_type 去掉 'hd'"))

    # 组 4: 只把 suffix_sort 去掉 'definition'
    apply_section_1_config()
    manager.config.suffix_sort = [
        SuffixSort.MOWORD,
        SuffixSort.CNWORD,
    ]
    results.append(await run_single_test("组 4: suffix_sort 去掉 'definition'"))

    # 组 5: 只把 hd_name 改为另一个合法值 ('hd')
    apply_section_1_config()
    manager.config.hd_name = "hd"
    results.append(await run_single_test("组 5: hd_name='hd'"))

    # 组 6: 附加项 - hd_get 改为 '' (对应界面「不获取分辨率」)
    apply_section_1_config()
    manager.config.hd_get = ""
    results.append(await run_single_test("附加组 6: hd_get='' (不获取分辨率)"))

    # 组 7: 4K 视频基线测试 (2160P, §1 原样)
    apply_section_1_config()
    results.append(await run_single_test("附加组 7: 4K 视频 (2160P, §1 原样)", video_height=2160))

    # 组 8: 4K 视频 + file_hd=False
    apply_section_1_config()
    manager.config.file_hd = False
    results.append(await run_single_test("附加组 8: 4K 视频 + file_hd=False", video_height=2160))

    # 输出表格与对比
    print(f"{'组别':<35} | {'识别清晰度':<10} | {'列表文字 (UI 显示)':<24} | {'与基线是否不同':<12} | {'落盘文件名 (实际写盘)':<25}")
    print("-" * 115)
    base_text = baseline["list_text"]
    for r in results:
        diff = "不同" if r["list_text"] != base_text else "相同"
        if r["case"].startswith("附加组 7") or r["case"].startswith("附加组 8"):
            diff = "-"
        print(f"{r['case']:<35} | {r['definition']:<10} | {r['list_text']:<24} | {diff:<12} | {r['disk_file_name']:<25}")

    print("=" * 115)


if __name__ == "__main__":
    asyncio.run(main())
```
