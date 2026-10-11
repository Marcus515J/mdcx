# 第二阶段实现与验证记录

> 下一阶段首读：[本周完整复盘与新交接](stage3-handoff.md)。本文保留按时间累积的验证历史，下方早期“尚未验收/下一步测试”已被后续实际验收覆盖。

更新日期：2026-10-11（北京时间）。第二阶段分支：`feat/local-hy-mt2-translation`。
草稿 PR：[第二阶段增量 #4](https://github.com/Marcus515J/mdcx/pull/4)，基于第一阶段分支，未合并主分支。

## 翻译链路实际验证完成

最后一轮用户实测（20:41:57–20:50:04）：云端每个字段失败两次后切换本机，
本机连接失败，六个字段均保留原文。三条汇总明确显示「未获得译文」，没有误报翻译成功。
结合此前云端正常、拒绝后重试、本机备用成功的记录，翻译调用/回退链路完成实际功能验证。
使用方案固定为 DeepSeek 云端主接口、本机 Hy-MT2 备用，沿用现有 EXE；
验收范围和测试后恢复步骤见 [翻译链路收口记录](stage2-translation-acceptance.md)。

## 最新决定：云端优先，本机备用

用户已实际验证本机模型加载和推理，MDCx 三条任务全部完成标题/简介翻译。
随后用户将优先级调整为 **云端 API → 同模型重试 → 本机 Hy-MT2 → 对应字段原文**。
现有测试版通过修改主/备用配置即可实现，不修改程序或第一阶段逻辑，不重建 EXE。
具体配置、旧启动器提示的处理及后续验收见 [云端优先使用说明](cloud-first-local-fallback.md)。
以下本机优先的实现和验证内容保留为历史记录；最新操作顺序以该说明为准。
用户随后提交两轮实际日志，故障切换到本机已确认走通：第一轮五个字段、第二轮六个字段进入本机，
两轮均三条全部完成翻译。第一轮也有主接口错误和拒绝，尚未证明云端正常翻译稳定；
译文存在角色关系和增写错误。用户确认主接口从 DeepSeek 换成 GLM，原提示词未改、温度 0.90，
且不提供提示词；下一步保持其私有提示词，通过恢复原供应商建立对照排查。
后续已恢复 DeepSeek，20:11:06–20:19:46 三条全部完成翻译，无 API 错误或备用切换；
一次拒绝经同模型重试成功。主宾关系明显改善，可见译文仍有增写/名字处理问题，
简介日志截断，未宣称完整准确性通过。当前云端主接口与已验证本机备用可以继续沿用。
语义错译不在请求错误/拒绝检测范围内，不会自动触发本机。
逐步证据及准确性问题见 [用户实际测试分析](cloud-first-real-test-20261011.md)。
本次 Linux 验证：翻译、拒绝回退、设置和 SDK/HTTP 测试 **77 项通过（22.29 秒）**，
其中新增云端优先/无 Key 本机备用的 9 条路径；ruff 和差异检查通过。
只新增验证及更新使用说明，沿用已发布 Windows EXE 和启动器，未宣称重新构建或执行新的 Windows 测试。

## 当前测试版：复盘问题修正

- [新版 Windows EXE](https://github.com/Marcus515J/mdcx/releases/download/test-20261011-local-hymt2-reviewfix/MDCx-test-20261011-local-hymt2-reviewfix-windows-x86_64.exe)；[双击启动包 ZIP](https://github.com/Marcus515J/mdcx/releases/download/test-20261011-local-hymt2-reviewfix/MDCx-HyMT2-launcher.zip)。
- [发布页面](https://github.com/Marcus515J/mdcx/releases/tag/test-20261011-local-hymt2-reviewfix)；源码 `7734622d7f5f1c828e97a7493c82543cb06a3a1d`，标签 `test-20261011-local-hymt2-reviewfix`。
- EXE：153234105 字节；SHA256 `bc89e82fb9ea405e6aaadf64ddb59fadc6ac5b9a4b80194d05d6c669c6e5bf7e`。
- 启动 ZIP：7487 字节；SHA256 `e7cbd79160993f92eace47e757bbfe0fa3ec8f48f08ad88b05aa299bab619bf1`。
- [Windows 验证、构建和上传](https://github.com/Marcus515J/mdcx/actions/runs/38111448545)：程序测试 **181 项通过（71.65 秒）**；Windows PowerShell 5.1 启动器 **22 项通过（81.099 秒）**，两个附件上传成功。
- Linux 本次翻译、回退和设置验证 **68 项通过（15.06 秒）**；ruff 和差异检查通过。已有 zhconv/pkg_resources 弃用警告未修改。
- 已重新下载两份 Release 附件，核对大小和完整 SHA256；EXE 为 Windows x86_64，ZIP 完整且三份文件与已测试启动器源码一致。

修正复用已有服务的操作顺序：先点本机预设，再填写实际模型名，最后保存，避免预设覆盖已填写名称。
汇总按标题/简介分别列出实际译文和保留原文；全部保留时显示“未获得译文”，部分成功显示“部分翻译完成”。
简介没有获得译文时保留原来源，避免在新输出中错误标记为 LLM 提供翻译；没有读取或改写用户已有 NFO。
新增验证覆盖全部/部分/完整译文、关闭标题翻译、简介来源及默认/不同服务模型名的启动说明。
已验收清理核心逻辑、配置迁移和依赖未改。草稿 PR 保留未合并。

下一步先验证用户本机能查找并加载模型，再使用少量媒体副本测试翻译和回退。
真实 Hy-MT2/GPU 与真实备用 API 尚未验收；“服务已就绪”表示加载/接口检查通过，翻译结果需要再验证。
启动器每次重新查找，多份安装可能需要选择序号；本次未加入路径缓存或自动修改用户配置。

## 初版成品及源码（历史记录）

- [Windows 测试版与启动脚本](https://github.com/Marcus515J/mdcx/releases/tag/test-20261009-local-hymt2)
- [EXE 直接下载](https://github.com/Marcus515J/mdcx/releases/download/test-20261009-local-hymt2/MDCx-test-20261009-local-hymt2-windows-x86_64.exe)
- [新版双击启动包](https://github.com/Marcus515J/mdcx/releases/tag/launcher-20261011-autofind)：解压后双击 `Start-HyMT2.cmd`，只需输入盘符。旧版单独 PS1 需要选择文件，已由新启动包替代。
- 构建源码：`6c25252cbc5f96b487b5abf7828a7e07b54ac7c7`，标签：`test-20261009-local-hymt2`。
- EXE：153234693 字节；SHA256：`1be6ee9ab1cfccb786c5adc8c601b743b120464057c6038dc6ce962407ceebf7`。
- 初版脚本（历史资产，勿再使用）：1632 字节；SHA256：`fae808e075723977a30528459c54fbc31f48a7ccdabcb6f029f5dd07941a26d4`。
- [Windows CI 测试、构建和上传](https://github.com/Marcus515J/mdcx/actions/runs/37939810767)：成功。

第一阶段已验收提交 `fe491f7` 和成品标签 `test-20261009-unified-cleanup` 保留。
第二阶段从交接提交 `7581fdb` 开始；文件清理判断、移动、删除、目录复制核对及配置迁移代码未改。
`pyproject.toml`、`uv.lock` 未改；没有新增依赖。没有读取或修改用户任何已有 NFO。

## 已完成

1. 读取账号下 [海南鸡 Fork](https://github.com/Marcus515J/Faster-Whisper-TransWithAI-ChickenRice) 的 README、Bridge 说明、job 示例和 Hy-MT2 翻译脚本，核实 llama.cpp OpenAI 兼容接口。
2. 新配置使用 `http://127.0.0.1:8080/v1` 和 `HY-MT2-7B-Q8_0`；已有显式配置保留，提供本机预设按钮。
3. 本机允许空 Key，隔离应用代理和环境代理，优先于其他已勾选翻译引擎。
4. 拒绝、API 错误、服务不可用、超时、空内容和空 choices 均进入同模型重试、备用、原文链路。
5. 默认每个字段最多两次本机请求、一次备用请求；关闭 SDK 隐式重试；同一提示词和温度用于全部步骤。
6. 标题与简介独立，空原文跳过；正常句中拒绝词不误命中；全失败保留对应字段原文。
7. 主/备用超时、备用地址/模型/隐藏 Key、重试次数接入原有加载和底部总保存。
8. 清理页去掉重复保存按钮，对齐字段、压缩说明、利用右侧空间；接续交接草稿，未扩大清理规则。
9. 提供复用已安装 llama-server 与 GGUF 的 Windows 启动脚本。MDCx 连接已启动服务，不自动管理 GPU 进程。

## 实际验证

Linux 在 `63c867c` 运行全量 `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`：
**661 passed, 13 skipped, 2 warnings in 159.03s**。警告为已有 zhconv/pkg_resources 弃用和已有 Web AsyncLimiter 跨循环提示；未顺手修改无关代码。

同一版本翻译、界面、第一阶段回归与网络生命周期选定测试：**192 passed, 1 warning in 20.04s**。
全仓 `ruff check .` 与 `ruff format --check .` 通过，`git diff --check` 通过。
深浅主题、两种窗口尺寸下的新增界面边界测试在 `QT_SCALE_FACTOR=1.5`、`2` 下分别 **12 项通过**，并检查 Linux 无显示模式截图。

随后只修正备用返回 `<br />` 这类纯换行内容的日志分类，避免将空返回记录为拒绝。
最终源码 `6c25252` 的翻译测试：**45 passed, 1 warning in 14.86s**。
Windows CI 在最终源码使用锁定依赖：**176 passed, 1 warning in 77.70s**；EXE 构建、启动脚本含空格路径传参检查及两个 Release 附件上传全部成功。

模拟服务实际使用标准库 ThreadingHTTPServer 和真实 OpenAI SDK，核验主模型与备用的路径、模型、提示词和请求数量。
没有使用私人 API、Key、Cookie 或真实刮削；API 错误日志不输出响应正文或凭据。

## 2026-10-11：修正本机启动包

用户不知道具体安装位置，初版 PS1 却要求手动选择程序/模型，且错误退出会关闭窗口。初版参数传递检查不足以验证实际使用流程。
新版提供 ZIP 和双击入口 `Start-HyMT2.cmd`，只需输入大概所在的盘；优先读取海南鸡的非敏感安装记录，缺失/损坏/失效时自动查找现有文件。
窗口显示查找、加载进度；健康接口确认模型加载完成才显示就绪；失败保留窗口、服务日志和日志路径。
脚本使用 UTF-8 BOM，CMD 使用 UTF-8/CRLF；通过 .NET 的完整路径启动程序，避免 Windows PowerShell 5.1 的方括号路径解析问题。

源码：`fb6ba96d449c26abb79a1481caa8f675f1d43dff`；发布标签：`launcher-20261011-autofind`。
[发布测试、打包与上传](https://github.com/Marcus515J/mdcx/actions/runs/38109272642)成功：21 项全部通过，81.832 秒。
已重新下载实际 Release 附件并检查 ZIP 完整性、三份文件与测试源码一致：7308 字节；SHA256 `15f14d9a8841376bf006327dc79f8ad55f2249c74675eea1443f08e79a59cd9e`。
[Windows PowerShell 5.1 实测与打包](https://github.com/Marcus515J/mdcx/actions/runs/38109143864)：**21 项全部通过，81.200 秒**。
测试实际运行独立编译的模拟服务 EXE，覆盖中文/空格/方括号/与号路径、盘符输入、安装记录及回退扫描、多模型选择、参数、真实 HTTP 就绪检查、服务退出、超时、端口冲突、已有服务复用、环境代理隔离、链接和待删目录排除、CMD 入口及解析失败/缺脚本时保留窗口。
测试只使用临时样本，不下载模型或访问私人配置。真实 GPU 加载仍由用户电脑完成。
启动 ZIP 可配合已有第二阶段 EXE 使用；本次没有修改应用和已验收清理逻辑，也没有重新构建 EXE。

## 未覆盖及本机验证

真实 Hy-MT2/GPU、真实备用 API、用户 Windows 实际安装和 GPU 加载、实际私人配置迁移、真实旧 NFO 拒绝语仍未验证。
Linux 主题/缩放截图和 Windows 无显示测试不等于用户 Windows 桌面人工验收。

请下载 EXE 与新版启动 ZIP。整个解压后双击 `Start-HyMT2.cmd`，输入大概安装在哪个盘，自动查找安装；等待显示“服务已就绪”并保持窗口打开；
在翻译页点击本机预设，填写自己的备用配置，再点击底部“保存”。完成后在服务窗口按回车停止本次启动的模型并释放显存。
停止本机服务可验证异常转备用；清空备用地址保存可验证最终保留原文。拒绝路径使用既有检测，不改写提示词强迫模型拒绝。
详细启动、配置与请求次数说明见 [llm-refusal.md](llm-refusal.md)；私人 JSON、Key、Cookie 无需上传。
