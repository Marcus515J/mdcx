# MDCx 任务单 v1.8-r5：配图重叠修复；撤回越界改动；翻译来源按字段显示并验证字段互不影响

日期：2026-10-18。依据：Claude 审核 r4（功能提交 `1a02cd21a1eca350f5a8aed0a6a8c5c89e5b96ba`）+ 用户复测测试版 `windows-x86_64-test-1a02cd2`。
r4 的 F1、F2、F3 用户复测全部通过，**不要改动它们已达成的行为**，只做下面列出的内容。
继续使用分支 `feat/llm-only-and-resources` 和 PR #12，保持草稿，不要合并。

---

## G1. Cookie 教程配图：修三处重叠

文件：`resources/html/cookie_help.html`。依据：r4 汇报所附 `handoff/reports/cookie_help_render.png`（【已实测】Claude 查看渲染图）。

要修的三处：
1. 第 4 步「请求列表」那张图：第一行的说明文字「（或对应站点主页面请求）」压住了右边「状态」列的 `200`。
2. 「粘贴到 MDCx」那张图：两个红色标注（「粘贴复制的 Cookie」「点击「检查cookie」」）压在下一行 javbus 的输入框和按钮上。
3. 同一张图：左侧站点名 `fc2ppvdb` 被截成了 `fc2ppvdt`。

要求：
1. 修改后，所有 SVG 里的文字不能互相遮挡，也不能被边框或其他元素截断。
2. 不改动图里的文字内容和图的数量（仍然是 6 张）。如果为了不重叠必须改文字，在汇报里逐条列出改前和改后。
3. r4 已有的约束继续有效：不联网，不用 `<img>`，控件名与 `MDCx.ui` 一致，每张图下面都有免责说明。
4. 交一张**不截断的整页渲染图**，宽度 900px，高度按页面实际高度，必须能看到第 6 张图（「保存」）。文件名为 `handoff/reports/cookie_help_render_r5.png`，只推到 handoff 分支。r4 那张图被截在 2400px，第 6 张没有拍到。

## G2. 撤回越界改动

r4 在 `mdcx/base/translate.py` 创建备用 `LLMClient` 时，把 `base_url=tc.llm_fallback_url.unicode_string()` 改成了 `base_url=str(tc.llm_fallback_url)`。任务单没有要求这项改动，用户决定改回原样。

要求：改回 `tc.llm_fallback_url.unicode_string()`，其他不动。

## G3. 翻译来源按字段显示，并验证字段之间互不影响

背景：
- 用户报告：看起来标题被拒以后，标题和简介都交给了本机模型。用户要求的行为是：**每个字段各自判断，云端能用就用云端，只有本字段云端用不了才转本机。优先级永远是云端优先。**
- Claude 读代码（【已查证】`mdcx/base/translate.py`，`translate_with_engine` 用 `asyncio.gather` 对标题和简介各调一次 `_llm_translate`，每次调用各自做重试和备用切换）认为逻辑已经按字段分开了。用户看到的现象，很可能是两处日志造成的误导：切换行没有写字段名；合并后的成功行只有一个标签，只要有一个字段用了备用，整行就显示为备用。这个判断**没有用用户的日志验证过**，属【推测】，要由下面第 1 条的测试来确认。

要求：
1. **先写测试验证，再改日志**。在 `tests/test_translate_llm.py` 里 mock 主接口和备用接口：
   - 情况 A：主接口对标题返回拒绝（命中 `llm_refusal_prefixes`），对简介正常返回译文。断言：备用接口**正好被调用 1 次**，调用的 prompt 是标题的 prompt；最终简介的结果来自主接口，标题的结果来自备用接口。
   - 情况 B：对调过来，标题正常，简介被拒。断言方式和情况 A 对称。
   - 情况 C：两个字段都被拒。断言：备用接口被调用 2 次。
   - 情况 D：两个字段都正常。断言：备用接口被调用 0 次。

   **如果情况 A 或 B 的测试失败**（也就是 Claude 判断错了，一个字段被拒确实会把另一个字段也带去备用），就修代码，让四种情况全部通过，并在汇报里说明原因，附文件名和行号。测试通过时不改这部分逻辑。
2. 切换提示写明字段名：`标题：主模型失败，转本机备用`、`简介：主模型失败，转本机备用`（备用不是本机时写作「转备用接口」）。在同一个日志流里，每个字段的切换提示最多出现一次。r4 同时在 `mdcx/base/translate.py`（`signal.add_log`）和 `mdcx/core/translate.py`（`LogBuffer.log().write`）各写了一次，可能导致重复。请先查清这两个是不是同一个日志流，在汇报里写明，然后按「同一个流里每个字段只出现一次」的原则去重。演员资料那一路（`mdcx/tools/wiki.py`）也按同样规则处理；那一路如果只有一个字段，就不需要加字段名。
3. 成功、部分完成、失败的汇总行：
   - 两个字段来源相同时，保持 r4 的格式，例如 `📝 翻译成功(LLM·云端主模型 deepseek-flash)`。
   - 来源不同时写成 `📝 翻译成功(标题 LLM·本机备用 Hy-MT2；简介 LLM·云端主模型 deepseek-flash)`。「部分翻译完成」和失败行也用同样的规则。
   - 某个字段为空、没有发请求时，不显示这个字段。
4. 每个字段的来源和模型名，都必须取自这个字段实际发出请求的那一路，不能用另一个字段的来源代替。仍然不允许输出地址和 Key。
5. 给第 2、3 条补测试：情况 A 的日志里出现 `标题：主模型失败，转本机备用`，不出现 `简介：主模型失败`；汇总行包含两个不同的来源。

## 机械核对（命令和原样输出贴进汇报）

- `git grep -n "unicode_string\|base_url=str(" mdcx/base/translate.py`：备用 `LLMClient` 那一行必须是 `unicode_string()`，不能再出现 `base_url=str(`。
- `git grep -n "主模型失败" mdcx`：贴原样输出，逐条说明它写进哪个日志流。
- `git grep -n "Llm" mdcx resources`：输出为空（r4 的结果要保持住）。
- `git grep -n -E "<img|https?://" resources/html/cookie_help.html`：输出为空。
- `git show <新功能提交>:resources/html/cookie_help.html | grep -c "<svg"` 和 `grep -c "示意图，菜单名以你的浏览器实际界面为准"`：两个数都等于 6。
- `git diff 1a02cd21a1eca350f5a8aed0a6a8c5c89e5b96ba <新功能提交> --stat`（不计临时 workflow）：只出现与 G1、G2、G3 相关的文件和测试文件，逐个文件说明改动原因。
- 全量测试结果（通过数 / 跳过数），以及 G3 新增的每个测试函数名。

## 执行方须知（Antigravity / Codex 通用）

- 只改本任务单列出的内容。有任何一步做不到，就停下来，在汇报里写明卡在哪一步、看到了什么；不要换一种做法绕过去。
- 每条机械核对都要贴实际运行的命令和原样输出，不要只写「已通过」，也不要写「（空输出）」以外的概括。
- **对照表、日志样例必须从代码或测试输出里原样复制**。r4 汇报里 F2 的对照表与代码不一致：代码实际是英文的 `Translation skipped!` 和 `Translation failed!`，表里却写成了中文；「改前」也写错了。这类内容一律以 `git grep` 或测试输出为准，不能凭印象写。
- 汇报开头放自查表：G1 第 1–4 条、G2、G3 第 1–5 条，每条写「完成 / 未完成」以及证据所在位置。G3 第 1 条必须写明：情况 A、B 的测试在**改代码之前**是通过还是失败。
- 临时 workflow 里写提交号时，用 `git rev-parse` 得到的完整 40 位。

## 验证与交付

- 全量测试通过，CI 通过。
- 更新临时 workflow，重新构建 Windows 测试版，作为 artifact 交付，并在汇报里写明 exe 的 SHA256。临时 workflow 仍然单独提交，合并前删除。
- 汇报写成 `handoff/reports/MDCx_执行汇报_v1.8-r5.md`，和 `cookie_help_render_r5.png` 一起推到 handoff 分支，只改 `handoff/reports/` 目录。
- 不要合并，不要打标签，不要发 Release，不要改动资源仓库。
