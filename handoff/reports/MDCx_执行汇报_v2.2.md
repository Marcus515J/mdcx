# MDCx 执行汇报 v2.2：查清 ① NFO 标签里的演员名为什么变成简体 ② 各刮削站默认域名

- **执行日期**：2026-10-18
- **执行方**：Antigravity（Gemini 3.8 Flash）
- **基线分支**：`master`
- **master HEAD 提交**：`5eb64efcf093dac25ddcc847528ededcbe6bbf7b`
- **当前任务模式**：本单只查不改。不改动仓库任何代码、配置与文档；不新建分支；不发版；代码全部在 `master` 上阅读；唯一产出为本汇报文件，提交并推送到 `handoff` 分支。
- **汇报文件位置**：`handoff/reports/MDCx_执行汇报_v2.2.md`

---

## 机械核对自查清单

| # | 核对项 | 通过标准 | 自查结果 | 对应章节 |
|---|---|---|---|---|
| 1 | HEAD 提交号 | 是 master 上 `5eb64ef` 或之后提交 | `5eb64efcf093dac25ddcc847528ededcbe6bbf7b` | 头部信息、第七节 |
| 2 | Q1 标签演员名来源 | 有路径 + 行号，贴出把演员名加进标签的那一行 | 已查证，贴出 `mdcx/core/translate.py:102-108` 核心行并解析变量归属 | 第一节 (Q1) |
| 3 | Q2 繁转简发生处 | 有转换所在的函数和行号；配置项表完整；有「无条件」或条件原文 | 已查证，明确为 `translate_info` 中的 `zhconv.convert`，配置表完整，说明无条件执行 | 第二节 (Q2) |
| 4 | Q3 字段处理分叉点 | `actors` 与标签的分叉点有路径 + 行号 | 已查证，写出 `scraper.py:753-754` 与 `translate.py:107` 及 `nfo.py` 写入链路 | 第三节 (Q3) |
| 5 | Q4 明确结论 | 明确为 A / B / C 之一 | 明确为 **B**（标签来源就是 `actors` 字段，但事后被转换） | 第四节 (Q4) |
| 6 | Q5 来源追溯 | 有提交号和日期，查明 upstream / fork 来源 | 已查证，确认为 upstream `sqzw-x` 早在 2023–2025 年的提交引入，非本仓库改动 | 第五节 (Q5) |
| 7 | Q6 机械验证 | 基线 + 组 1 + 组 2 都有输出；附录贴完整验证脚本 | 全部离线完成，输出完整矩阵表格，附录贴出可独立运行的验证源码 | 第六节 (Q6)、附录 |
| 8 | Q7 默认域名清单 | 22 个站每站一行无遗漏；javlibrary 附加问题均有答案 | 22 个站逐一排查填表，javlibrary 两个问题均详细查证回答，引用相关原文 | 第七节 (Q7) |
| 9 | 仓库无改动 | master 上 `git status` 干净贴输出；handoff 只新增本汇报 | master 干净（贴出原样输出）；handoff 仅新增本汇报 | 第八节 |
| 10 | 无密钥 | 汇报中无任何 Key、Cookie | 全文已确认无任何真实 Key、Token、Cookie 或密码 | 全文已确认 |

---

## 问题 A：NFO 标签里的演员名繁简问题（Q1–Q6）

### Q1 标签里的演员名从哪来

【已查证】

1. **生成 NFO `<tag>` 的代码位置**：
   - 文件路径：[`mdcx/core/nfo.py:330-334`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/nfo.py#L330-L334)
   - 代码：
     ```python
     330:         # 输出 tag
     331:         if NfoInclude.TAG in nfo_include_new:
     332:             for t in tags:
     333:                 if t:
     334:                     write_text_element(code, "tag", t)
     ```
   - 说明：写入 NFO 的 `tags` 列表来自 [`mdcx/core/nfo.py:146-147`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/nfo.py#L146-L147)：
     ```python
     146:     series_tag = manager.config.nfo_tag_series.replace("series", series) if series else ""
     147:     tags = prioritize_nfo_tags(data.tags, series_tag=series_tag, series_template=manager.config.nfo_tag_series)
     ```
     这里的 `data.tags` 直接取自刮削结果数据模型 `CrawlersResult` 的 `tags` 属性（或向后兼容属性 `tag`）。

2. **`nfo_tag_include` 里的 `"actor"` 对应哪一行把演员名加进标签**：
   - 文件路径：[`mdcx/core/translate.py:102-108`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L102-L108)
   - 代码：
     ```python
     102:     # 添加演员
     103:     if TagInclude.ACTOR in tag_include:
     104:         whitelist = manager.config.nfo_tag_actor_contains
     105:         for actor in json_data.actors:
     106:             if not whitelist or actor in whitelist:
     107:                 nfo_tag_actor = manager.config.nfo_tag_actor.replace("actor", actor)
     108:                 tag = nfo_tag_actor + "," + tag
     ```
   - 核心拼接行：**第 107–108 行**：
     - 第 107 行：`nfo_tag_actor = manager.config.nfo_tag_actor.replace("actor", actor)`（默认模板为 `"actor"`，即取演员原名）；
     - 第 108 行：`tag = nfo_tag_actor + "," + tag`（将演员名作为元素拼接进 `tag` 逗号分隔字符串的最前面）。

3. **它取的是哪个变量——和 `actors` 字段是同一个变量，还是另一份拷贝/另一个来源**：
   - 取的是 **`json_data.actors`**（遍历中的每个 `actor` 元素）；
   - **与 `actors` 字段来自同一个数据源**：在 [`mdcx/core/scraper.py:753-754`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L753-L754) 中：
     ```python
     753:             await translate_actor(res)  # 映射输出演员名/信息
     754:             translate_info(res, file_info.has_sub)  # 映射输出标签等信息
     ```
     第 753 行执行后，`res.actors` 已经确定（此时为 `['麻倉憂']`）；第 754 行调用 `translate_info(res, ...)`，直接读取传入对象 `res` 的 `json_data.actors` 列表，因此标签中加入的演员字符串就是 `actors` 字段中的原始元素值。

---

### Q2 繁转简发生在哪

【已查证】

1. **函数名、路径 + 行号，转换工具库**：
   - **函数名**：`translate_info`
   - **路径与行号**：[`mdcx/core/translate.py:175-179`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L175-L179)
   - **代码**：
     ```python
     175:     if tag_language == Language.ZH_CN:
     176:         tag = zhconv.convert(tag, "zh-cn")
     177:     elif tag_language == Language.ZH_TW:
     178:         tag = zhconv.convert(tag, "zh-hant")
     ```
   - **转换使用的库或映射表**：**`zhconv`**（调用 `zhconv.convert(tag, "zh-cn")`）。
     - **不是** `mapping_actor.xml`；
     - **不是** `mapping_info.xml`；
     - **不是** LLM 翻译。
     - 说明：在第 108 行演员名被拼入 `tag` 字符串之后，第 176 行对整个已拼入演员名的 `tag` 文本整体执行了 `zhconv.convert(tag, "zh-cn")`。因 `麻倉憂` 中「倉」对应简体「仓」、「憂」对应简体「忧」，`zhconv` 在简体转换时将其转为了 `麻仓忧`。

2. **控制这一步的所有配置项**：

| 配置项（JSON 键名） | 作用 | 代码位置 | 用户是否可在界面上关闭/修改 |
|---|---|---|---|
| `field_configs.tags.language` | 决定标签转换的目标语言。若为 `"zh_cn"` 则执行 `zhconv.convert(tag, "zh-cn")`；若为 `"zh_tw"` 则转繁体；若为 `"jp"` 则跳过 `zhconv` 转换 | [`mdcx/core/translate.py:53, 175`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L53) | **可以**。主界面「设置」-「标签」字段语言单选框（`radioButton_tag_zh_cn`、`radioButton_tag_zh_tw`、`radioButton_tag_jp`，[`load_config.py:274-280`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/main_window/load_config.py#L274-L280)） |
| `nfo_tag_include` | 控制哪些信息写入标签。若包含 `"actor"`，则执行第 102–108 行将演员名拼入 `tag` | [`mdcx/core/translate.py:60, 102`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L60) | **可以**。主界面「标签」勾选框中的「演员」（`checkBox_tag_actor`，[`load_config.py:289`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/controllers/main_window/load_config.py#L289)） |
| `field_configs.tags.translate` | 控制是否启用 `mapping_info.xml` 映射初始标签（第 87–96 行） | [`mdcx/core/translate.py:48, 87`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L48) | **可以**。主界面「标签」映射勾选框（`checkBox_tag_translate`），但**无法关闭**第 176 行的 `zhconv` 繁简转换 |
| `nfo_tag_actor` | 写入标签时的演员格式模板，默认为 `"actor"` | [`mdcx/core/translate.py:106`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L106) | 配置文件项（默认 `"actor"`） |
| `nfo_tag_actor_contains` | 允许写入标签的演员白名单，默认为空列表（表示不限制） | [`mdcx/core/translate.py:103, 105`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L103) | 配置文件项（默认为空 `[]`） |

3. **这一步有没有「配置没开就不做」的判断？**
   - **条件原文**：
     ```python
     if tag_language == Language.ZH_CN:
         tag = zhconv.convert(tag, "zh-cn")
     elif tag_language == Language.ZH_TW:
         tag = zhconv.convert(tag, "zh-hant")
     ```
   - **机制说明**：
     - **对 `tag_translate`（界面「标签映射」开关）而言是无条件的**：即使用户取消勾选了标签翻译/映射（`translate=False`），只要标签语言设置为简体中文（`tag_language == Language.ZH_CN`），该段代码依然**无条件执行**。
     - **唯一的限制条件是 `tag_language`**：仅当用户将标签语言选为 `jp` 时，才不会进入 `zh-cn` 或 `zh-hant` 分支。

---

### Q3 `actors` 字段自己为什么没被转

【已查证】

1. **`actors` 字段的处理路径**：
   - 在 [`mdcx/core/scraper.py:753`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L753) 调用 `await translate_actor(res)`；
   - 在 [`mdcx/core/translate.py:191-249`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L191-L249) 中，演员处理通过 `map_actor_names(res)` 查阅本地演员映射表 `mapping_actor.xml`；
   - `translate_actor` **整个函数内完全没有任何调用 `zhconv` 的代码**！它仅仅通过 `actor_data.get(lang)` 尝试从 `mapping_actor.xml` 获取对应语言的名称；
   - 在落盘写入 NFO 时，[`mdcx/core/nfo.py:254-266`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/nfo.py#L254-L266) 中：
     ```python
     254:         if NfoInclude.ACTOR_ALL in nfo_include_new:
     255:             actors = data.all_actors
     256:         else:
     257:             actors = data.actors
     ...
     262:             for name in actors:
     263:                 print("  <actor>", file=code)
     264:                 write_text_element(code, "name", name, indent="    ")
     265:                 write_text_element(code, "type", "Actor", indent="    ")
     266:                 print("  </actor>", file=code)
     ```
     直接将 `data.actors` 列表里的元素原样写为 `<actor><name>麻倉憂</name></actor>`，不经过任何繁简转换。

2. **`actors` 字段与标签路径的分叉点**：
   - **第一分叉点（执行时序）**：[`mdcx/core/scraper.py:753-754`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/scraper.py#L753-L754)
     - 第 753 行处理 `actors`，第 754 行处理 `tag`；
   - **第二分叉点（数据流与转换分歧）**：[`mdcx/core/translate.py:104-108`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L104-L108) 与 [`:175-179`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L175-L179)
     - 在第 107–108 行，代码把 `json_data.actors` 的元素拷贝并拼接入单一的扁平字符串 `tag`；
     - 在第 176 行，`zhconv.convert(tag, "zh-cn")` 仅对变量 `tag` 生效，**完全没有触碰 `json_data.actors`**；
     - 第 183 行将转换后的 `tag` 写回 `json_data.tag`，而 `json_data.actors` 始终保持原始 Japanese 字符串 `['麻倉憂']`；
   - **第三分叉点（NFO 生成）**：[`mdcx/core/nfo.py:262-264`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/nfo.py#L262-L264) 与 [`:330-334`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/nfo.py#L330-L334)
     - `<actor><name>` 消费未被转换的 `data.actors`；
     - `<tag>` 消费被 `zhconv` 转换过的 `data.tags`。

3. **`field_configs.actors.language = "jp"` 在其中起什么作用**：
   - 在 [`mdcx/core/translate.py:234`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/core/translate.py#L234) 中：`lang = manager.config.get_field_config(field_name).language`；
   - 因为配置了 `"jp"`，所以 `actor_data.get(lang)` 从映射表中查询的是日文名（若查不到则原样保留 `麻倉憂`）；
   - 即使映射表生效，取的也是日文字符 `麻倉憂`，确保了 `actors` 字段不会被映射为中文简体；
   - 但它**完全管不到 `tag` 字段**，因为 `tag` 字段读取的是独立的 `field_configs.tags.language`（用户配置未显式改动该项，默认为 `"zh_cn"`）。

---

### Q4 结论明确判定

【已查证】

明确判定为：**B**

> **B 标签来源就是 `actors` 字段，但事后被转换**。
>
> 查证依据：在 `mdcx/core/translate.py:105-108` 中，标签中的演员名完全来源于 `for actor in json_data.actors:` 并直接拼入 `tag`；但在随后的第 176 行，整个 `tag` 串因 `tag_language == "zh_cn"` 而被 `zhconv.convert(tag, "zh-cn")` 全量转成了简体，导致其中的 `麻倉憂` 变成了 `麻仓忧`。

---

### Q5 来源追溯

【已查证】

使用 `git blame` 与 `git log -S` 追溯造成该行为的关键代码行：

1. **将 `actors` 加入 `tag` 的代码（`translate.py:102-108`）**：
   - 提交号：`bbcc9877eea13398b5d5fb9e24245a54ed6b3285`
   - 作者：`sqzw-x`（upstream 上游）
   - 日期：`2025-09-01 20:57:29 +0800`
   - Commit Message：`fix: 未向 tag 中添加演员 (fix #661)`
   - 说明：该次提交前代码取自 `json_data.actor.split(',')`，该次提交重构成遍历 `json_data.actors` 并拼入 `tag`。

2. **对 `tag` 全局执行 `zhconv.convert` 的代码（`translate.py:175-179`）**：
   - 提交号：`573189883f3d80b5f2d4c4c2e41b625e9cc413ca`
   - 作者：`sqzw-x`（upstream 上游）
   - 日期：`2023-11-12 01:10:28 +0800`
   - Commit Message：`Initial commit`
   - 演进记录：后续在 `540b35be`（2025-01-02，ruff 格式化）和 `9838a894`（2025-08-23，迁移 pydantic config）中保持原样。

**结论**：
该行为**完全是 fork 前上游 sqzw-x/mdcx 既有的历史代码行为**，并非本仓库 Marcus515J/mdcx v1.7 及之后的改动所引入。

---

### Q6 机械验证（本地离线）

【已实测】

在仓库外部创建了纯离线无网络测试脚本 `/Users/gameong/.gemini/antigravity/scratch/verify_actor_tag_q6.py`。
使用假数据（`number="PRED-110"`, `letters="PRED"`, `actors=['麻倉憂']`, `tag="痴女,美乳"`），调用 Q1 确认的核心函数 `translate_info(data, has_sub=False)`。

#### 1. 验证结果矩阵表格

| 测试组别 | 输入配置改动 | 演员名判定 | 输出标签列表 (`data.tags`) | 机制验证说明 |
|---|---|---|---|---|
| **基线** | 代码默认值（`nfo_tag_include` 含 `actor`，`tags.language="zh_cn"`） | **麻仓忧 (简体)** | `['PRED', '麻仓忧', '痴女', '美乳']` | 重现用户 Windows 实测问题：标签中演员被转为简体 |
| **组 1** | 仅从 `nfo_tag_include` 中去掉 `actor` | **未包含演员** | `['PRED', '痴女', '美乳']` | `TagInclude.ACTOR in tag_include` 为 False，不向标签添加演员 |
| **组 2-1** | Q2 开关：`field_configs.tags.language = "jp"` | **麻倉憂 (繁体/原样)** | `['PRED', '麻倉憂', '癡女', '美乳']` | 不进入 `zh-cn` 转换分支，保留原始日文汉字 `麻倉憂` |
| **组 2-2** | Q2 开关：`field_configs.tags.language = "zh_tw"` | **麻倉憂 (繁体/原样)** | `['PRED', '麻倉憂', '癡女', '美乳']` | 走 `zh-hant` 转换，`麻倉憂` 本身即为繁体，转换后保持原样 |
| **组 2-3** | Q2 开关：`field_configs.tags.translate = False` | **麻仓忧 (简体)** | `['PRED', '麻仓忧', '痴女', '美乳']` | **实测证明：关闭标签映射表依然无法阻止繁转简**，`zhconv.convert` 依然执行 |
| **组 2-4** | Q2 模板：`nfo_tag_actor = "【actor】"` | **麻仓忧 (简体)** | `['PRED', '【麻仓忧】', '痴女', '美乳']` | 模板成功替换并整体被转为简体 |
| **组 2-5** | Q2 白名单：`nfo_tag_actor_contains = ["麻倉憂"]` | **麻仓忧 (简体)** | `['PRED', '麻仓忧', '痴女', '美乳']` | 白名单命中，添加后被转为简体 |
| **组 2-6** | Q2 白名单：`nfo_tag_actor_contains = ["波多野結衣"]` | **未包含演员** | `['PRED', '痴女', '美乳']` | 白名单未命中，演员不被加入标签 |

---

## 问题 B：各站默认访问域名清单（Q7）

### Q7 各站默认域名清单

【已查证】

针对任务单指定的 22 个站点，查证其在代码中的默认域名、代码位置、是否支持 `custom_url`，以及是否经过 CF Bypass：

| # | 站点 | 默认访问的域名（代码里写死的值） | 代码位置（路径 + 行号） | 是否支持 `custom_url`（是/否，配置键名） | 是否经过 CF Bypass 的代码路径（是/否/有条件，写条件） |
|---|---|---|---|---|---|
| 1 | `official` | 无固定域名（根据番号前缀动态查 `ManualConfig.OFFICIAL` 字典路由到对应厂商官网；Prestige 则路由至 `https://www.prestige-av.com`；`base_url_` 为空字符串 `""`） | [`mdcx/crawlers/official.py:117-118, 123-127`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/official.py#L117-L118) | **否**（重写了 `_run`，完全忽略 `self.base_url` 与 `site_configs.official.custom_url`） | **有条件**（请求走 `AsyncWebClient.get_text`，开启 `enable_cf_bypass`；触发 CF 且配置 `cf_bypass_url` 时生效） |
| 2 | `dmm` | `https://www.dmm.co.jp` 与 `https://www.dmm.com`（`base_url_` 写死返回 `""`，代码明确注释 `# DMM 不支持自定义 URL`） | [`mdcx/crawlers/dmm_new/__init__.py:464-466, 495-497`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/dmm_new/__init__.py#L464-L466) | **否**（代码写死不支持自定义 URL，`base_url_` 固定为 `""`） | **有条件**（请求走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 3 | `mgstage` | `https://www.mgstage.com` | [`mdcx/crawlers/mgstage.py:166-167`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/mgstage.py#L166-L167) | **是**（`site_configs.mgstage.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 4 | `missav` | `https://missav.ws` | [`mdcx/crawlers/missav.py:321-322`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/missav.py#L321-L322) | **是**（`site_configs.missav.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 5 | `javlibrary` | `https://www.javlibrary.com` | [`mdcx/crawlers/javlibrary.py:134-135`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javlibrary.py#L134-L135) | **是**（`site_configs.javlibrary.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效；注意代码内另有关键词主动拦截抛错，见下文） |
| 6 | `javbus` | `https://www.javbus.com` | [`mdcx/crawlers/javbus.py:157-158`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javbus.py#L157-L158) | **是**（`site_configs.javbus.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 7 | `javdbapi` | `https://api.thejavdb.net/v1` | [`mdcx/crawlers/javdbapi.py:51-52`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javdbapi.py#L51-L52) | **是**（`site_configs.javdbapi.custom_url`） | **有条件**（走 `AsyncWebClient.get_json`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 8 | `javdb` | `https://javdb.com` | [`mdcx/crawlers/javdb_new.py:139-140`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javdb_new.py#L139-L140) | **是**（`site_configs.javdb.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 9 | `avbase` | `https://www.avbase.net` | [`mdcx/crawlers/avbase_new.py:33-34`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/avbase_new.py#L33-L34) | **是**（`site_configs.avbase.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 10 | `7mmtv` | `https://www.7mmtv.sx`（类名 `MmtvCrawler`） | [`mdcx/crawlers/mmtv.py:174-175`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/mmtv.py#L174-L175) | **是**（`site_configs.7mmtv.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 11 | `avsox` | 动态从发布页 `https://tellme.pw/avsox` 获取；兜底写死域名为 `https://avsox.click`；`base_url_` 返回 `""` | [`mdcx/crawlers/avsox.py:101-102, 110`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/avsox.py#L101-L102)、[`mdcx/base/web.py:465-475`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/web.py#L465-L475) | **否**（`base_url_` 写死为空，强制使用 `get_avsox_domain()` 解析的地址，忽略 `custom_url`） | **有条件**（发布页及详情页均走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 12 | `airav` | **未找到**（旧代码已废弃下线，无对应爬虫类实现） | 未找到（[`mdcx/manual.py:7`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/manual.py#L7) 显式排除 `Website.AIRAV`，已被 `airav_cc` 取代） | **否**（未找到代码） | **否**（无对应代码路径） |
| 13 | `airav_cc` | `https://airav.io` | [`mdcx/crawlers/airav_cc.py:144-145`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/airav_cc.py#L144-L145) | **是**（`site_configs.airav_cc.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 14 | `fc2` | `https://adult.contents.fc2.com` | [`mdcx/crawlers/fc2.py:192-193`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/fc2.py#L192-L193) | **是**（`site_configs.fc2.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 15 | `fc2hub` | `https://javten.com` | [`mdcx/crawlers/fc2hub.py:123-124`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/fc2hub.py#L123-L124) | **是**（`site_configs.fc2hub.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 16 | `fc2club` | `https://fc2club.top` | [`mdcx/crawlers/fc2club.py:101-102`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/fc2club.py#L101-L102) | **是**（`site_configs.fc2club.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 17 | `theporndb` | `https://api.theporndb.net` | [`mdcx/crawlers/theporndb.py:209-210`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/theporndb.py#L209-L210) | **是**（`site_configs.theporndb.custom_url`） | **有条件**（走 `AsyncWebClient.get_json`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 18 | `cnmdb` | `https://cnmdb.net` | [`mdcx/crawlers/cnmdb.py:91-92`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/cnmdb.py#L91-L92) | **是**（`site_configs.cnmdb.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 19 | `hdouban` | 前端页面及 ID 详情链接为 `https://ormtgu.com`；底层 API 请求写死为 `https://api.6dccbca.com` | [`mdcx/crawlers/hdouban.py:182-183, 205, 222, 225`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/hdouban.py#L182-L183) | **是**（部分支持，`site_configs.hdouban.custom_url`；仅控制前端页面与 external_id，后台 API 域名写死不受控） | **有条件**（走 `AsyncWebClient.get_json`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 20 | `madouqu` | `https://madouqu.com` | [`mdcx/crawlers/madouqu.py:117-118`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/madouqu.py#L117-L118) | **是**（`site_configs.madouqu.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 21 | `javday` | `https://javday.tv` | [`mdcx/crawlers/javday.py:143-144`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javday.py#L143-L144) | **是**（`site_configs.javday.custom_url`） | **有条件**（走 `GenericBaseCrawler._fetch` -> `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |
| 22 | `mdtv` | `https://www.mdpjzip.xyz` | [`mdcx/crawlers/mdtv.py:183-184`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/mdtv.py#L183-L184) | **是**（`site_configs.mdtv.custom_url`） | **有条件**（走 `AsyncWebClient`，触发 CF 且配置 `cf_bypass_url` 时生效） |

---

### Q7 附加问题回答

#### 1. `javlibrary` 在 `custom_url` 留空时访问哪个域名？代码里有没有对 Cloudflare 挑战的特殊处理？

【已查证】

1. **`custom_url` 留空时的访问域名**：
   - 访问 **`https://www.javlibrary.com`**（见 [`mdcx/crawlers/javlibrary.py:134-135`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javlibrary.py#L134-L135)：`return manager.config.get_site_url(Website.JAVLIBRARY, "https://www.javlibrary.com")`）。

2. **代码里对 Cloudflare 挑战的特殊处理**：
   - **特殊代理行为**：在 [`mdcx/crawlers/javlibrary.py:137-139`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javlibrary.py#L137-L139)：
     ```python
     137:     @property
     138:     def use_proxy(self) -> bool:
     139:         return not manager.config.get_site_config(Website.JAVLIBRARY).custom_url
     ```
     - 当用户**手填了 `custom_url`**（如镜像）时，`use_proxy` 判定为 `False`（**不走代理**）；
     - 当 `custom_url` **留空**（访问官方域名）时，`use_proxy` 判定为 `True`（**强制走代理**）。
   - **显式关键词拦截与抛错**：在 [`mdcx/crawlers/javlibrary.py:195-196`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javlibrary.py#L195-L196) 及 [`:207-208`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/javlibrary.py#L207-L208)：
     ```python
     195:             if "Cloudflare" in html_search:
     196:                 raise CralwerException("搜索结果: 被 Cloudflare 5 秒盾拦截！")
     ...
     207:         if "Cloudflare" in html_info:
     208:             raise CralwerException("搜索结果: 被 Cloudflare 5 秒盾拦截！")
     ```
     `javlibrary` 代码在拿到搜索页与详情页 HTML 后，主动检查文本中是否包含 `"Cloudflare"` 关键字，若包含则立刻抛出业务异常 `被 Cloudflare 5 秒盾拦截！` 终止该任务。

---

#### 2. 代码注释、变量名或提交信息中是否有说明某个默认域名是「镜像」或「备用域名」？

【已查证】

检索代码库与历史提交记录，发现以下明确提及：

1. **代码注释中的「镜像」说明（madouqu）**：
   - 文件：[`mdcx/crawlers/madouqu.py:39`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/madouqu.py#L39)
   - 原文引用：
     ```python
     # madouqu 详情页会混入旧镜像域名，统一回站点当前可访问的 WordPress CDN 地址。
     ```
2. **代码注释中的「不支持自定义 URL」说明（dmm）**：
   - 文件：[`mdcx/crawlers/dmm_new/__init__.py:465`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/crawlers/dmm_new/__init__.py#L465)
   - 原文引用：
     ```python
     # DMM 不支持自定义 URL
     ```
3. **提交信息中的站点下线与废弃说明（airav）**：
   - 提交号：`8459eb471850ecf34c1b0d7bc1c83c2b74a01b3d`（Hazard804，2026-04-29）
   - 原文引用：
     ```
     删除已废弃的 airav、javlibrary_new、theporndb_movies 旧入口，并移除旧版 CRAWLER_FUNCS 注册路径；airav 配置兼容迁移到 airav_cc。
     ```
4. **动态发布页机制（avsox）**：
   - 文件：[`mdcx/base/web.py:466`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/web.py#L466)
   - 机制：不使用单一固定域名，硬编码发布页 `https://tellme.pw/avsox` 在线动态获取当前可用域名，兜底域名写为 `https://avsox.click`。

---

## 另见

在本次只读排查中顺带发现的细节与现象（不影响当前任务，供后续决策参考）：
1. **`tag_translate` 与 `zhconv` 逻辑解耦**：
   在 `mdcx/core/translate.py` 中，用户界面上的「标签-使用信息映射表」（`checkBox_tag_translate`）只控制 `mapping_info.xml` 的匹配替换，而末尾的 `zhconv.convert(tag, "zh-cn")` 仅受语言选择 `field_configs.tags.language` 控制。这导致即便用户不想翻译标签，只要语言选择了简体中文，所有被拼进标签的演员名都会无条件被繁转简。
2. **`javlibrary` 的 `use_proxy` 属性设计**：
   `javlibrary` 默认留空时会强制走代理（`use_proxy=True`），只要填了 `custom_url`（哪怕填的是带端口的本地代理或境外镜像）就会自动变成直连（`use_proxy=False`）。如果后续用户要去掉 `custom_url` 换回官网，请求就会自动转为走全局代理配置。

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

### 2. handoff 分支提交状态

在 `handoff` 分支上仅包含交接文档与汇报文件，本单新增产出仅为本汇报文件。

---

## 附录：Q6 机械验证独立脚本源码

脚本路径（存放于仓库目录之外）：
`/Users/gameong/.gemini/antigravity/scratch/verify_actor_tag_q6.py`

```python
#!/usr/bin/env python3
"""
MDCx v2.2 Q6 机械验证脚本
验证 NFO 标签中演员名称繁简转换机制与各项配置的关系
"""

import sys
from pathlib import Path

# 将仓库根目录加入 sys.path
REPO_ROOT = Path(__file__).resolve().parent / "mdcx"
sys.path.insert(0, str(REPO_ROOT))

from mdcx.config.enums import Language, TagInclude
from mdcx.config.manager import manager
from mdcx.config.models import Config
from mdcx.config.resources import resources
from mdcx.core.translate import translate_info
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.types import CrawlersResult


def reset_config():
    """重置为代码默认配置"""
    manager.config = Config()


def make_sample_data():
    """构造一条假数据，actors=['麻倉憂']，附带少量常规标签"""
    res = CrawlersResult.empty()
    res.number = "PRED-110"
    res.letters = "PRED"
    res.actors = ["麻倉憂"]
    res.all_actors = ["麻倉憂"]
    res.tag = "痴女,美乳"
    return res


def run_case(name: str, config_modifier=None):
    reset_config()
    if config_modifier:
        config_modifier()

    data = make_sample_data()
    # 调用 Q1 找到的生成标签核心函数
    translate_info(data, has_sub=False)

    tags = data.tags
    actor_status = "未包含演员"
    for t in tags:
        if "麻仓忧" in t:
            actor_status = "麻仓忧 (简体)"
            break
        elif "麻倉憂" in t:
            actor_status = "麻倉憂 (繁体/原样)"
            break

    return {
        "case": name,
        "tags": tags,
        "actor_status": actor_status,
        "tag_language": manager.config.get_field_config(CrawlerResultFields.TAGS).language.value,
        "tag_translate": manager.config.get_field_config(CrawlerResultFields.TAGS).translate,
        "actor_in_tag_include": TagInclude.ACTOR in manager.config.nfo_tag_include,
        "nfo_tag_actor": manager.config.nfo_tag_actor,
        "whitelist": manager.config.nfo_tag_actor_contains,
    }


def main():
    print("=" * 100)
    print("MDCx v2.2 Q6 机械验证：标签演员名繁简转换与配置矩阵测试")
    print("=" * 100)

    results = []

    # 基线：nfo_tag_include 含 actor，其余用代码默认值 (field_configs.tags.language="zh_cn", translate=True)
    results.append(run_case("基线（代码默认值，含 actor）"))

    # 组 1：只把 nfo_tag_include 里去掉 actor
    def mod_group1():
        manager.config.nfo_tag_include = [
            t for t in manager.config.nfo_tag_include if t != TagInclude.ACTOR
        ]

    results.append(run_case("组 1: nfo_tag_include 去掉 actor", mod_group1))

    # 组 2-1: Q2 开关 - tags.language 改为 "jp"
    def mod_group2_lang_jp():
        manager.config.get_field_config(CrawlerResultFields.TAGS).language = Language.JP

    results.append(run_case("组 2-1: field_configs.tags.language='jp'", mod_group2_lang_jp))

    # 组 2-2: Q2 开关 - tags.language 改为 "zh_tw"
    def mod_group2_lang_tw():
        manager.config.get_field_config(CrawlerResultFields.TAGS).language = Language.ZH_TW

    results.append(run_case("组 2-2: field_configs.tags.language='zh_tw'", mod_group2_lang_tw))

    # 组 2-3: Q2 开关 - tags.translate 改为 False (关闭标签映射表)
    def mod_group2_translate_false():
        manager.config.get_field_config(CrawlerResultFields.TAGS).translate = False

    results.append(run_case("组 2-3: field_configs.tags.translate=False", mod_group2_translate_false))

    # 组 2-4: Q2 开关 - nfo_tag_actor 模板修改为 "【actor】"
    def mod_group2_actor_template():
        manager.config.nfo_tag_actor = "【actor】"

    results.append(run_case("组 2-4: nfo_tag_actor='【actor】'", mod_group2_actor_template))

    # 组 2-5: Q2 开关 - 白名单匹配命中 nfo_tag_actor_contains=['麻倉憂']
    def mod_group2_whitelist_hit():
        manager.config.nfo_tag_actor_contains = ["麻倉憂"]

    results.append(run_case("组 2-5: nfo_tag_actor_contains=['麻倉憂'] (命中)", mod_group2_whitelist_hit))

    # 组 2-6: Q2 开关 - 白名单未命中 nfo_tag_actor_contains=['波多野結衣']
    def mod_group2_whitelist_miss():
        manager.config.nfo_tag_actor_contains = ["波多野結衣"]

    results.append(run_case("组 2-6: nfo_tag_actor_contains=['波多野結衣'] (未命中)", mod_group2_whitelist_miss))

    # 打印测试结果矩阵
    print(f"{'测试组别':<42} | {'演员名判定':<18} | {'输出标签列表 (data.tags)'}")
    print("-" * 100)
    for r in results:
        print(f"{r['case']:<42} | {r['actor_status']:<18} | {r['tags']}")
    print("=" * 100)


if __name__ == "__main__":
    main()
```
