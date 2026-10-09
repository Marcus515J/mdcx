# 本机 Hy-MT2 翻译与备用回退

第二阶段使用本机主模型 → 同模型重试 → 独立备用 LLM → 对应字段原文。
拒绝、请求失败、超时、空内容和空 choices 均走这条链路。标题与简介分别处理，空原文不请求。
只检查去掉开头空白和引号后的拒绝前缀；正常译文中间出现“抱歉”等词不会命中。
重试与备用沿用相同提示词与温度，不改写提示词绕过拒绝，不修复或改写已有 NFO。

## 已核实的海南鸡接口

已读取 `Marcus515J/Faster-Whisper-TransWithAI-ChickenRice` 的 README、
`tools/README_pipeline_bridge.md`、`tools/pipeline_job.example.json` 和 `tools/translate_srt_hymt2.ps1`。
该项目通过 llama.cpp `llama-server.exe` 调用 Hy-MT2 GGUF：

- OpenAI 兼容 `POST /v1/chat/completions`。
- 示例基址 `http://127.0.0.1:8080/v1`，模型名 `HY-MT2-7B-Q8_0`。
- 脚本默认 `ApiKey=local`，启动服务时不设置鉴权；MDCx 的回环地址允许空 Key。
- 海南鸡按需启动模型，任务结束关闭；MDCx 不能假设服务仍在运行。
- 路径由用户实际安装位置决定，未连接用户 Windows，也未核实其安装路径。

新配置采用以上本机地址与模型名；已有 JSON 的显式地址、模型、Key、提示词和其他配置保留。
在「设置 → 翻译 → LLM 翻译」点击“使用本机 Hy-MT2（海南鸡接口）”，可切换已有配置；
该按钮只修改主模型地址、模型、Key、同模型重试次数及 LLM 启用状态，保留备用配置。
本机 LLM 启用时优先于其他勾选引擎；最终保留原文后不再让其他引擎替换该字段。

## Windows 启动与设置

Release Assets 同时提供 EXE 和 `start-local-hymt2.ps1`。脚本不下载任何模型或依赖，复用海南鸡已装文件。
右键脚本“使用 PowerShell 运行”，依次选择已有 `llama-server.exe` 和 Hy-MT2 `.gguf`。
如果系统阻止脚本，可在脚本目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local-hymt2.ps1
```

这里的 PowerShell 参数只用于运行本地启动脚本。等待窗口显示模型加载完成，保持窗口打开，再开始 MDCx 刮削。
结束后在该窗口按 Ctrl+C 停止服务、释放显存。不要同时启动海南鸡的另一个 8080 服务。
已知路径时也可通过 `-LlamaServerPath` 和 `-ModelPath` 指定，路径含空格应加引号。
脚本固定监听回环地址 8080，使用与海南鸡一致的 `-ngl 999 -c 8192`，设置模型别名供 MDCx 使用。
MDCx 本身连接已启动服务，不自动管理 GPU 进程。

在同页填写备用地址、模型、Key 和读取超时，点击页面底部“保存”。例如 DeepSeek 的 OpenAI 兼容基址
`https://api.deepseek.com/v1`；模型 ID 以自己账号当前可用模型为准，Key 只在本机填写。
备用云端的地址、模型和 Key 必须全部填写；备用回环服务可留空 Key；清空备用地址即停用。
两个 Key 输入框隐藏内容，请勿上传私人 JSON、Key 或 Cookie。

## 请求次数与超时

`llm_refusal_retries` 默认 1，现在也用于请求失败与空返回后的同模型重试。
本机每一步只发送一次 HTTP 请求，备用只请求一次，SDK 隐式重试关闭：

| 情况 | 实际请求顺序 |
|---|---|
| 正常返回 | 主模型 1 次 |
| 重试成功 | 主模型 2 次 |
| 备用成功或所有步骤失败 | 主模型 2 次 → 备用 1 次 |
| 未配置备用 | 主模型最多 2 次 → 原文 |

`llm_read_timeout`、`llm_fallback_read_timeout` 分别控制主/备用读取超时；连接超时使用已有全局 `timeout`。
使用默认 60 秒读取超时时，两次主请求加一次备用可能累计约 180 秒读取等待，另加连接/速率等待。
云端主模型保留旧 `llm_max_try` 传输尝试设置；每次主模型调用最多该次数，拒绝/不可用外层再按
`llm_refusal_retries` 重试。默认最坏为云端主模型 10 次 HTTP 请求加备用 1 次；界面明确区分这两个设置。
本机忽略 `llm_max_try`，界面禁用该控件但保留旧值。最终失败后不再额外睡眠。
回环请求禁用应用代理、环境代理及重定向；云端仍使用现有代理设置。HTTPS 启用证书验证。
日志包含拒绝、重试、备用和原文步骤；API 错误只记录异常类型，不输出服务响应、Key 或 Cookie。

## 验证范围

`tests/test_local_llm.py` 使用标准库临时 HTTP 服务和真实 OpenAI SDK 检查请求顺序/数量、错误、超时、
空返回、空 choices、思考内容移除后的空返回、本机代理隔离和备用释放。
`tests/test_llm_refusal.py` 覆盖拒绝路径、字段独立及本机引擎优先；
`tests/test_llm_settings_ui.py` 覆盖设置加载、底部保存、备用停用、合成旧 JSON 保留及布局边界。
这些模拟验证不等于真实 Hy-MT2 或真实备用 API 联调；用户实际 Windows 启动、GPU、主题/字体效果仍需检查。
