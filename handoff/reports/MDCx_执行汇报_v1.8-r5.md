# MDCx 执行汇报 v1.8-r5：配图重叠修复、撤回越界改动、翻译来源按字段显示与独立性验证

**执行日期**：2026-10-18  
**执行分支**：功能分支 `feat/llm-only-and-resources`（PR #12 保持 Draft 草稿，未合并）  
**功能提交 SHA**：`3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e`  
**临时工作流更新提交 SHA**：`e53f52bfc5852dc7633dded984e9e07bc72e7b24`  
**测试构建产物**：`windows-x86_64-test-3984e3a`（MDCx-v1.1.0-TEST-3984e3a-windows-x86_64.exe）  
**汇报目标文件**：`handoff/reports/MDCx_执行汇报_v1.8-r5.md` 与 `handoff/reports/cookie_help_render_r5.png`

---

## 一、自查表

| 条目编号 | 任务要求描述 | 状态 | 证据所在位置 |
|---|---|---|---|
| **G1.1** | 第 4 步「请求列表」：说明文字「（或对应站点主页面请求）」不再压住「状态」列的 `200` | **完成** | `resources/html/cookie_help.html:202-225`，列坐标重排；`cookie_help_render_r5.png` 图 3 |
| **G1.2** | 「粘贴到 MDCx」：两个红色标注不压在下一行 javbus 输入框和按钮上；左侧站点名 `fc2ppvdb` 不被截断 | **完成** | `resources/html/cookie_help.html:321-344`，容器高度由 230 扩展至 255，输入框右移至 x=215；`cookie_help_render_r5.png` 图 5 |
| **G1.3** | 文字内容不改，图数保持 6 张；不联网，不用 `<img>`，免责声明齐备，控件名与 `MDCx.ui` 一致 | **完成** | `cookie_help.html` 机械检查 3、4、5 条，全部吻合 |
| **G1.4** | 交付不截断的整页渲染图（宽 900px，全高），完整可见第 6 张图（「保存」） | **完成** | `handoff/reports/cookie_help_render_r5.png`（900 × 2823 像素，涵盖全部 6 张 SVG 示意图及保存说明） |
| **G2** | 撤回越界改动：`mdcx/base/translate.py` 备用 `LLMClient` 改回 `tc.llm_fallback_url.unicode_string()` | **完成** | `mdcx/base/translate.py:226`；机械检查第 1 项通过 |
| **G3.1** | 先写测试验证：mock 主备接口测试情况 A、B、C、D 独立性，断言备用调用次数与结果来源 | **完成** | `tests/test_translate_llm.py:529-762`；**注：情况 A、B、C、D 测试在修改翻译逻辑前即全部通过**（详见下文二） |
| **G3.2** | 切换提示写明字段名（`标题：主模型失败，转本机备用` 等）；查清日志流并在同流去重；处理 wiki 单字段 | **完成** | `mdcx/base/translate.py:210-218`、`mdcx/core/translate.py:299-304`、`mdcx/tools/wiki.py:541-576`；每个流每个字段至多输出一次 |
| **G3.3** | 汇总行：来源相同时保持原样；不同时按 `标题 ...；简介 ...` 格式；字段为空未发请求时不显示 | **完成** | `mdcx/base/translate.py:50-73`（`TranslateResult.label` 组合逻辑）；`tests/test_translate_llm.py:765-879` |
| **G3.4** | 每个字段来源和模型名均取自实际请求那一路，不互相替代，不输出地址和 Key | **完成** | `TranslateResult` 拆分独立记录 `title_interface/model/fallback` 与 `outline_interface/model/fallback` |
| **G3.5** | 为第 2、3 条补测：情况 A 日志出现标题切换而不出现简介切换；汇总行包含两来源；单字段测试 | **完成** | `tests/test_translate_llm.py::test_translate_llm_situation_a_logs_and_summary_with_different_sources` 与 `test_translate_llm_single_field_summary_does_not_show_empty_field` 全部通过 |

---

## 二、G3.1 字段独立性验证结果（改代码前）

按照任务单「**先写测试验证，再改日志**」要求，在向 `mdcx/base/translate.py` 和 `mdcx/core/translate.py` 引入字段日志及组合汇总行之前，先在 `tests/test_translate_llm.py` 中编写并运行了情况 A、B、C、D 四个基准用例：

1. **情况 A（标题被拒，简介成功）**：主模型返回拒绝前缀「抱歉，我无法翻译该标题」，简介正常翻译。
   - 断言：备用模型被调用正好 1 次，Prompt 为标题 Prompt；`result.title` 来自备用模型，`result.outline` 来自主模型。
   - **改代码前运行结果**：**PASSED（通过）**。
2. **情况 B（标题成功，简介被拒）**：主模型正常翻译标题，简介返回拒绝前缀。
   - 断言：备用模型被调用正好 1 次，Prompt 为简介 Prompt；`result.title` 来自主模型，`result.outline` 来自备用模型。
   - **改代码前运行结果**：**PASSED（通过）**。
3. **情况 C（两者均被拒）**：
   - 断言：备用模型被调用 2 次；标题与简介均由备用模型提供。
   - **改代码前运行结果**：**PASSED（通过）**。
4. **情况 D（两者均正常）**：
   - 断言：备用模型被调用 0 次；标题与简介均由主模型提供。
   - **改代码前运行结果**：**PASSED（通过）**。

### 结论与代码原因分析
- **Claude 的分析判断得到证实**：代码在 `mdcx/base/translate.py` 的 `translate_with_engine` 中，早已通过 `asyncio.gather(_llm_translate(title, ...), _llm_translate(outline, ...))` 分别发起两次独立的协程调用。
- 每次 `_llm_translate` 拥有独立的局部变量、独立的重试计数器和独立创建的备用客户端连接，两者之间**不存在状态共享或联动切换**。
- **用户此前观察到的「标题被拒导致两者都转本机」的错觉，确系由于日志与标签未区分字段引起**：
  1. 旧版切换日志仅输出全局无前缀的 `主模型失败，转本机备用`，让人误以为整体切换；
  2. 旧版 `TranslateResult.label` 只要任一字段触发了 `fallback_used`，整条结果的 `interface` 和 `model` 就被覆写为备用模型，导致最后的单一行汇总日志打印成 `📝 翻译成功(LLM·本机备用 Hy-MT2)`，隐藏了简介实际上来自云端主模型的事实。

---

## 三、修改详情与日志流查证

### 1. G1：Cookie 教程配图（`resources/html/cookie_help.html`）

依据 r4 渲染图定位的三处问题进行了精确布局调整：
- **图 3（请求列表）**：
  - 将表格后半部分列标题及数据行的 X 坐标整体向右移位：`状态 / Status` 从 `x=210` 移至 `x=260`；`类型 / Type` 移至 `x=345`；`发起程序 / Initiator` 移至 `x=430`；`大小 / Size` 移至 `x=545`；`时间 / Time` 移至 `x=625`。
  - 第一行文档请求文字 `javdb.com （或对应站点主页面请求）`（起点 `x=18`）右侧至 `x=260` 留出超过 25px 安全间距，彻底消除对 `200` 的压迫。
- **图 5（粘贴到 MDCx 设置项）**：
  - 将 SVG 整体视口与外框高度由 `230` 增加至 `255`，`Cookie设置` 分组框高度由 `162` 增至 `195`。
  - 将三行输入框与按钮的起始 X 坐标由 `x=190` 后移至 `x=215`。`fc2ppvdb:` 文字区域（`x=140..205`）与输入框之间保持 10px 清晰留白，不再被截断。
  - 将针对 JavDB 的两个红色标注标签定位在 `y=115..133`，而第二行 javbus 的输入框顶端位于 `y=142`，二者之间有 9px 明确间距，绝无重叠。
- **整页截图**：
  - 使用无头浏览器以 900px 固定宽度对整页进行真实渲染，生成全高（2823px）图像 `handoff/reports/cookie_help_render_r5.png`，完整覆盖第 6 张「保存」示意图与底部说明。

### 2. G2：撤回越界改动（`mdcx/base/translate.py`）

- 将第 226 行创建备用 `LLMClient` 时的 `base_url=str(tc.llm_fallback_url)` 恢复为 `base_url=tc.llm_fallback_url.unicode_string()`。

### 3. G3：日志流查证、按字段去重与组合汇总行

#### （1）两个日志流的归属查证
任务单要求查清 `signal.add_log` 和 `LogBuffer.log().write` 是否属于同一个日志流：
- **UI 详细请求日志流**（`signal.add_log`）：
  - 绑定自 `Signals.detail_log_list`，信号连接至 `main_req_logs_show`，渲染在 MDCx 界面底部详细请求日志窗（`textBrowser_log_main_2`）。
  - 用于记录每次网络发包与实时事件。
- **影片主刮削日志流**（`LogBuffer.log().write`）：
  - 缓冲在 `LogBuffer` 单例中，由主刮削调度线程在每部影片处理完毕后调用 `show_log_text` 统一渲染至主界面中央刮削日志窗（`textBrowser_log_main`）。
- **结论**：二者**不是同一个日志流**，属于两个面向不同交互场景的独立显示区域。因此两处均需输出切换提示，但各自流内必须严格去重。

#### （2）日志去重与字段前缀实现
- 在 `mdcx/base/translate.py` 的 `_llm_translate` 中引入 `field_name` 形参。当发生主备切换时，组织格式为：
  `switch_msg = f"{field_prefix}主模型失败，{switch_dest}"`
  并通过 `signal.add_log(switch_msg)` 写入详细请求流。因为每个字段仅调用一次 `_llm_translate`，在详细请求日志流中每个字段的切换提示**至多出现一次**。
- 在 `mdcx/core/translate.py` 中，通过检查 `result.title_fallback` 和 `result.outline_fallback`，分别且至多写入一次：
  `LogBuffer.log().write(f"\n 标题：主模型失败，{title_dest}")`
  `LogBuffer.log().write(f"\n 简介：主模型失败，{outline_dest}")`
  在主刮削日志流中每个字段同样**至多出现一次**。
- 维基演员资料那一路（`mdcx/tools/wiki.py`）：
  - 当仅翻译单个字段（如 `_translate_english_tag`）时，`field_name` 传空，输出 `主模型失败，转本机备用`（不含冒号前缀）；
  - 当同时包含标签与简介时，分别传入 `标签` 与 `简介`。

#### （3）组合汇总行逻辑
扩展 `TranslateResult`，分别记录 `title_interface`、`title_model`、`title_fallback` 及 `outline_interface`、`outline_model`、`outline_fallback`，并由其 `.label` 属性根据发包情况合成：
- 两个字段来源相同时（例如同为主模型）：
  `📝 翻译成功(LLM·云端主模型 deepseek-flash)`
- 两个字段来源不同时：
  `📝 翻译成功(标题 LLM·本机备用 Hy-MT2；简介 LLM·云端主模型 deepseek-flash)`
- 某个字段为空未发请求时（如简介为空）：
  汇总行仅展示发请求的字段来源：`📝 翻译成功(LLM·云端主模型 deepseek-flash)`，不展示未请求字段。

---

## 四、机械核对（原样命令与输出）

### 1. `git grep -n "unicode_string\|base_url=str(" mdcx/base/translate.py`

**命令**：
```bash
git grep -n "unicode_string\|base_url=str(" mdcx/base/translate.py
```
**原样输出**：
```
mdcx/base/translate.py:226:                base_url=tc.llm_fallback_url.unicode_string(),
```
**说明**：备用客户端实例化恢复为 `.unicode_string()`，代码中无任何 `base_url=str(`。

---

### 2. `git grep -n "主模型失败" mdcx`

**命令**：
```bash
git grep -n "主模型失败" mdcx
```
**原样输出**：
```
mdcx/base/translate.py:215:            switch_msg = f"{field_prefix}主模型失败，{switch_dest}"
mdcx/core/translate.py:301:                LogBuffer.log().write(f"\n 标题：主模型失败，{title_dest}")
mdcx/core/translate.py:304:                LogBuffer.log().write(f"\n 简介：主模型失败，{outline_dest}")
```
**逐条写入日志流说明**：
- `mdcx/base/translate.py:215`：写入**UI 详细请求日志流**（通过 `signal.add_log` 发射到底部 `textBrowser_log_main_2` 面板）。带有 `field_prefix`（例如 `标题：`、`简介：`，单字段时为空）；
- `mdcx/core/translate.py:301`：写入**影片主刮削日志流**（通过 `LogBuffer.log().write` 缓冲至主界面中央 `textBrowser_log_main` 面板）。标题发生回退时记录；
- `mdcx/core/translate.py:304`：写入**影片主刮削日志流**（通过 `LogBuffer.log().write` 缓冲至主界面中央 `textBrowser_log_main` 面板）。简介发生回退时记录。

---

### 3. `git grep -n "Llm" mdcx resources`

**命令**：
```bash
git grep -n "Llm" mdcx resources
```
**原样输出**：
```
（空输出，退出码 1）
```
**说明**：源码与资源中完全杜绝「Llm」命名，全部保持大写「LLM」。

---

### 4. `git grep -n -E "<img|https?://" resources/html/cookie_help.html`

**命令**：
```bash
git grep -n -E "<img|https?://" resources/html/cookie_help.html
```
**原样输出**：
```
（空输出，退出码 1）
```
**说明**：教程 HTML 中未引入任何外链资源或 `<img>` 标签，离线脱机安全完备。

---

### 5. `git show 3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e:resources/html/cookie_help.html | grep -c "<svg"` 与免责声明计数

**命令**：
```bash
git show 3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e:resources/html/cookie_help.html | grep -c "<svg" && git show 3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e:resources/html/cookie_help.html | grep -c "示意图，菜单名以你的浏览器实际界面为准"
```
**原样输出**：
```
6
6
```
**说明**：SVG 图表数与说明文字数均精确为 6。

---

### 6. `git diff 1a02cd21a1eca350f5a8aed0a6a8c5c89e5b96ba 3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e --stat`（不计临时 workflow）

**命令**：
```bash
git diff 1a02cd21a1eca350f5a8aed0a6a8c5c89e5b96ba 3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e --stat
```
**原样输出**：
```
 .github/workflows/test-build-windows.yml |   8 +-
 mdcx/base/translate.py                   | 113 +++++++--
 mdcx/core/translate.py                   |   9 +-
 mdcx/tools/wiki.py                       |   5 +
 resources/html/cookie_help.html          |  78 +++----
 tests/test_llm_refusal.py                |   2 +-
 tests/test_translate_llm.py              | 381 ++++++++++++++++++++++++++++++-
 7 files changed, 523 insertions(+), 73 deletions(-)
```

**逐文件改动原因说明**（除临时 workflow 文件外）：
1. `mdcx/base/translate.py`：恢复备用客户端 base_url 为 `unicode_string()`；在 `TranslateResult` 中增加按字段的来源与回退标记并实现组合标签；在 `_llm_translate` 中支持按字段加前缀输出主备切换提示；
2. `mdcx/core/translate.py`：在主刮削日志中输出带字段名的切换提示；
3. `mdcx/tools/wiki.py`：维基演员资料翻译适配字段名透传规则（单字段不加前缀）；
4. `resources/html/cookie_help.html`：修复图 3 和图 5 的文字重叠与截断问题；
5. `tests/test_llm_refusal.py`：将 mock 中的备用地址更新为 `HttpUrl` 对象，满足 `unicode_string()` 属性调用；
6. `tests/test_translate_llm.py`：新增 G3.1 独立性验证用例（情况 A/B/C/D）、G3.5 详细日志与汇总行用例、单字段空输入用例。

---

### 7. 全量测试结果与 G3 新增测试函数

**命令**：
```bash
.venv/bin/pytest -q
```
**原样输出**：
```
........................................................................ [  8%]
........................................................................ [ 17%]
........................................................................ [ 26%]
.........................ssss........................................... [ 35%]
........................................................................ [ 44%]
.....................................................................s.. [ 53%]
........................................................................ [ 62%]
........................................................................ [ 71%]
......................................sssssssss......................... [ 80%]
........................................................................ [ 89%]
........................................................................ [ 98%]
............                                                             [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/zhconv/zhconv.py:33
  /Users/gameong/.gemini/antigravity/scratch/mdcx/.venv/lib/python3.13/site-packages/zhconv/zhconv.py:33: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
    from pkg_resources import resource_stream

tests/core/test_web_amazon.py::test_get_big_poster_keeps_low_res_amazon_match_without_google_fallback
  /Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/web_async.py:1359: RuntimeWarning: This AsyncLimiter instance is being re-used across loops. Please create a new limiter per event loop as re-use can lead to undefined behaviour.
    await limiter.acquire()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
796 passed, 14 skipped, 2 warnings in 110.18s (0:01:50)
```

**G3 新增的测试函数列表**（位于 `tests/test_translate_llm.py`）：
1. `test_translate_llm_field_independence_case_a_title_refused`：情况 A（标题被拒转备用，简介成功留在主模型）；
2. `test_translate_llm_field_independence_case_b_outline_refused`：情况 B（标题成功留在主模型，简介被拒转备用）；
3. `test_translate_llm_field_independence_case_c_both_refused`：情况 C（两者均被拒，备用调用 2 次）；
4. `test_translate_llm_field_independence_case_d_neither_refused`：情况 D（两者均成功，备用调用 0 次）；
5. `test_translate_llm_situation_a_logs_and_summary_with_different_sources`：断言情况 A 日志中只出现标题切换行、不出现简介切换行，且汇总行显示不同来源；
6. `test_translate_llm_single_field_summary_does_not_show_empty_field`：断言单字段请求（另一字段为空）时汇总行不显示空字段。

---

## 五、验证与交付汇总

### 1. 本地检查
- **Ruff 代码风格与检查**：
  ```bash
  .venv/bin/ruff check mdcx tests && .venv/bin/ruff format --check mdcx tests
  ```
  结果：**All checks passed! 218 files already formatted.**
- **本地全量测试**：**796 passed, 14 skipped**，测试通过率 100%。

### 2. GitHub Actions CI 与 Windows 构建产物

- **功能代码提交 SHA**：`3984e3a5cfcb7e0b6aaf30f63a128b6a4c9dc76e`（`fix: 修复Cookie教程配图重叠、撤回unicode_string改动并细化按字段翻译来源与切换提示`）
- **临时工作流更新提交 SHA**：`e53f52bfc5852dc7633dded984e9e07bc72e7b24`（`ci: 更新临时 Windows 测试构建工作流以指向 3984e3a (合并前删除)`）
- **CI/CD Pipeline 检查**（Run ID: `39090726711`）：
  - 状态：**Success**（全部 Code Quality 与 Tests 运行通过）
  - 运行链接：[GitHub Actions Run 39090726711](https://github.com/Marcus515J/mdcx/actions/runs/39090726711)
- **Windows 测试构建**（Run ID: `39090724277`）：
  - 状态：**Success**（耗时 2m51s，通过 Windows 端全部测试并完成 PyInstaller 打包）
  - 运行链接：[GitHub Actions Run 39090724277](https://github.com/Marcus515J/mdcx/actions/runs/39090724277)
  - 产物（Artifact）名称：`windows-x86_64-test-3984e3a`
    - Artifact ID: `12122802082`
    - 文件大小: 152,870,975 字节 (~145.8 MB)
    - 可执行文件名称: `MDCx-v1.1.0-TEST-3984e3a-windows-x86_64.exe`
    - 可执行文件大小: 153,703,260 字节
    - 可执行文件 SHA256: `0348fda165e5629f17ee13af14b6065e1bdbd951bd0f658e7a745b0dbe8dbbd7`
    - 压缩包 SHA256 Digest: `sha256:14b35e0a26b49059685bde2e003322de30596a836f867443e631fe840c0504be`
    - 下载链接：[下载 windows-x86_64-test-3984e3a.zip](https://github.com/Marcus515J/mdcx/actions/runs/39090724277/artifacts/12122802082)

### 3. 分支与交付规范遵循

- 代码修改完全位于 `feat/llm-only-and-resources` 分支；
- PR #12 保持 **Draft（草稿）** 状态，未合并；
- `handoff` 分支仅新增汇报文件 `handoff/reports/MDCx_执行汇报_v1.8-r5.md` 与渲染图 `handoff/reports/cookie_help_render_r5.png`，严格限定在 `handoff/reports/` 目录下；
- 未打 Git Tag 标签、未发 Release、未对资源仓库（`Marcus515J/mdcx-resources`）作任何修改。
