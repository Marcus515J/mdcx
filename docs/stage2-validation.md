# 第二阶段实现与验证记录

日期：2026-10-09（北京时间）。第二阶段分支：`feat/local-hy-mt2-translation`。
草稿 PR：[第二阶段增量 #4](https://github.com/Marcus515J/mdcx/pull/4)，基于第一阶段分支，未合并主分支。

## 成品及源码

- [Windows 测试版与启动脚本](https://github.com/Marcus515J/mdcx/releases/tag/test-20261009-local-hymt2)
- [EXE 直接下载](https://github.com/Marcus515J/mdcx/releases/download/test-20261009-local-hymt2/MDCx-test-20261009-local-hymt2-windows-x86_64.exe)
- [启动脚本直接下载](https://github.com/Marcus515J/mdcx/releases/download/test-20261009-local-hymt2/start-local-hymt2.ps1)
- 构建源码：`6c25252cbc5f96b487b5abf7828a7e07b54ac7c7`，标签：`test-20261009-local-hymt2`。
- EXE：153234693 字节；SHA256：`1be6ee9ab1cfccb786c5adc8c601b743b120464057c6038dc6ce962407ceebf7`。
- 脚本：1632 字节；SHA256：`fae808e075723977a30528459c54fbc31f48a7ccdabcb6f029f5dd07941a26d4`。
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

## 未覆盖及本机验证

真实 Hy-MT2/GPU、真实备用 API、用户 Windows 安装路径、启动文件选择对话框、实际私人配置迁移、真实旧 NFO 拒绝语仍未验证。
Linux 主题/缩放截图和 Windows 无显示测试不等于用户 Windows 桌面人工验收。

请从 Release 下载 EXE 与脚本。运行脚本选择海南鸡已有的 llama-server.exe 和 Hy-MT2 GGUF，等待服务加载完成并保持窗口打开；
在翻译页点击本机预设，填写自己的备用配置，再点击底部“保存”。完成后在服务窗口按 Ctrl+C 释放显存。
停止本机服务可验证异常转备用；清空备用地址保存可验证最终保留原文。拒绝路径使用既有检测，不改写提示词强迫模型拒绝。
详细启动、配置与请求次数说明见 [llm-refusal.md](llm-refusal.md)；私人 JSON、Key、Cookie 无需上传。
