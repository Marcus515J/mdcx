# MDCx 本周完整复盘与下一阶段交接

日期：2026-10-11（北京时间）。仓库：`Marcus515J/mdcx`。
当前分支：`feat/local-hy-mt2-translation`。本文件是下一次对话的首读入口。

## 先读：已经决定和验收的事

用户最新确认：**“可以，当前这一轮的结果保留。”** 第一阶段垃圾清理已验收；
第二阶段翻译调用及故障回退也已通过 Windows 实测。下一阶段只接续：

1. 将本地模型的查找、启动、停止和状态展示直接做进软件界面，简化使用。
2. 先读取软件原有窗口和控件的设计逻辑，再统一本周新增的清理、翻译控件。

最终日常方案固定为 **DeepSeek 云端主接口 → 同模型重试一次 → 本机 Hy-MT2 备用 → 对应字段原文**。
用户的私有标题/简介 Prompt 保持原样，温度为 **0.90**，不要再次索取 Prompt、Key、Cookie 或完整配置。
不要按旧交接恢复“本机主力、云端备用”，不要重做已验收的垃圾清理，不要重新进行相同人工故障测试。

本轮交接只审计和保存资料，不实现下一阶段界面或模型管理，不重建 EXE、不合并 PR。
本文件综合本周全部分支增量提交、当前代码、已有交接/验证资料和本对话测试记录；
原私人附件不进入 Git，下一次对话不一定能读取本对话上传文件，应先使用本文件及所链接的分析记录。
原《MDCx优化需求清单_v1.1.md》当前不在仓库；其当时核对结果保留在旧交接，本轮没有重新读取原附件。

## 一、版本、分支和可恢复位置

| 用途 | 固定位置 | 状态 |
| --- | --- | --- |
| 本周开始时的主分支基线 | `f3650ef300eeea38593833d1a052ec96b3c72ba8` | 10 月 4 日演员别名映射 PR #3；属于原有基线 |
| 第一阶段验收源码 | `fe491f7a9fde48fc754c49dba13781c2b64b1647` | 标签 `test-20261009-unified-cleanup`，已验收 |
| 第一阶段旧交接 | `7581fdbb784b72c9eab80e5ab0726603c9c70fb9` | `feat/garbage-cleanup-llm-refusal` 分支；仅供历史追溯 |
| 当前 Windows EXE 的构建源码 | `7734622d7f5f1c828e97a7493c82543cb06a3a1d` | 标签 `test-20261011-local-hymt2-reviewfix` |
| 本次整理前的验收记录源码 | `1469dd34a451c369e2ef6811cc693a5a451e0360` | 已收口全部实际翻译故障路径 |
| 后续开发应从哪里开始 | 当前分支包含本交接的最新提交 | 建议从这里另建新分支，不能从第一阶段旧分支重新开始 |

草稿 [PR #4](https://github.com/Marcus515J/mdcx/pull/4) 的 base 是第一阶段分支，
head 是当前分支，尚未合并主分支。第一阶段标签、当前测试版和历史发布保留。
`7734622` 之后到 `1469dd3` 只增加测试和文档，云端优先通过现有主/备用配置实现，没有重新构建程序。

目前使用的成品：[最新 Release](https://github.com/Marcus515J/mdcx/releases/tag/test-20261011-local-hymt2-reviewfix)。

| 资产 | 大小（字节） | SHA256 |
| --- | --- | --- |
| `MDCx-test-20261011-local-hymt2-reviewfix-windows-x86_64.exe` | 153234105 | `bc89e82fb9ea405e6aaadf64ddb59fadc6ac5b9a4b80194d05d6c669c6e5bf7e` |
| `MDCx-HyMT2-launcher.zip` | 7487 | `e7cbd79160993f92eace47e757bbfe0fa3ec8f48f08ad88b05aa299bab619bf1` |

两份成品已实际重新下载，核对完整大小、校验和、EXE x86_64 架构、ZIP 内容与测试源码。
当前已验收程序不需要因为这次写交接而替换。

## 二、本周垃圾文件识别、清理与规则的完整状态

### 入口与操作

唯一设置入口：**设置 → 刮削目录 → 文件清理设置**。
原先新增的独立垃圾规则弹窗已被统一页面替代；没有两套关键词、大小或保存入口。
“文件名等于”“文件名包含”等原有输入框继续使用，多项用 `|` 分隔。
页面底部“保存”统一保存配置；重复的“保存清理设置”已移除。
“点击检查待刮削目录并清理文件”手动按钮先保存页面，然后执行清理。
手动清理无需联网、无需成功刮削，也不要求打开“刮削时自动清理”。
自动和手动清理共用判断规则；自动模式保留指定 URL、Again 指定番号的保护，手动不继承之前的刮削模式。

### 判断顺序和边界

1. 已启用的排除扩展名、排除包含词优先；每条原有规则仍受 `clean_enable` 控制。
2. 识别出的正常番号视频、NFO、图片、字幕、符号链接受到保护。
   字幕包括配置 `sub_type` 及 srt/ass/ssa/sub/idx/vtt。没有识别出番号的普通文件名不能伪装成有效番号。
3. 完整文件名必须包含扩展名，**空格和大小写严格一致**；包含词忽略空白和大小写。
4. 无番号视频可以命中启用的扩展名、完整名称、包含词、域名规则，或大小规则；这些条件按“或”匹配。
5. 域名样式为 `.com`、`.net`、`.cc`、`www.`，检查前做大小写/空白归一化。
6. N 复用既有 `file_size`，默认 **100 MB**，视频要**严格小于 N**才命中；1 MB = 1024² 字节。
   原有 `clean_size` 是另一项已有 **KB** 规则，正数时 `<=` 门槛，0 关闭；不要把 KB 与 N 混为一谈。
7. 非视频文档只能命中名称、扩展名或包含词规则，不能因为很小或 0 KB 就清理未知笔记。
   明确指定完整名称的 0 KB 广告文档可以清理。
8. 刮削前识别出的垃圾视频不发起站点搜索，演练或处理失败也跳过该垃圾的搜索；
   刮削后扫描纯垃圾目录。媒体根目录不会整体移走。

### 文件与目录怎么处理

- 默认移到**源盘符/卷根 `_待删`**，可设置自定义绝对目录；不是统一搬到软件所在盘。
- `_待删`、自定义待删目录和其子目录排除在后续扫描/刮削之外。
- 同名目标加 `_1` 等序号，独占目标，不能覆盖旧文件。
- 永久删除默认关闭，只作用于已匹配的单文件。
- 只含已确认垃圾的**子目录整体移到待删**，保留内部结构；即使选了永久删除，纯垃圾目录仍整体移动。
- 保护文件、未知文件、排除文件或链接阻止整个目录移动，但其中已确认垃圾仍可单文件处理。
- 空目录不当作“纯垃圾目录”整体隔离；旧的空目录清理及 `.DS_Store`/`Thumbs.db` 处理属于原程序逻辑。
- 目录采用独占目标复制、源文件状态核对后删除源；复制失败或源变化保留源，可能留下待删副本。
  不宣称跨盘原子移动、自动回滚或失败时完全没有副本。
- 演练只记录，不移动、不删除，包括不执行空目录删除。日志包含模式、原因、源路径、动作、目标路径。

### 默认规则与旧配置迁移

| 配置 | 当前默认或含义 |
| --- | --- |
| `garbage_enabled` | `false`；自动清理，与旧 `clean_enable` 中的 `auto_clean` 同步 |
| `garbage_dry_run` | `false`；默认是真实处理，不能称为默认演练 |
| `garbage_permanent_delete` | `false`；默认移到待删 |
| `garbage_directory` | 空；采用源盘符/卷根 `_待删` |
| `garbage_domain_rule` | `true` |
| `file_size` | `100.0` MB；与原来的“忽略小于 N MB”共用 |
| `clean_size` | `0.0` KB；大小清理关闭 |
| `clean_ext` | `.html`、`.url` |
| `clean_name` | `uur76.mp4`、`uur93.com.mp4` |
| `clean_ignore_ext` | 空列表 |
| `clean_ignore_contains` | `skip`、`ignore` |

`clean_contains` 共 12 项：直播盒子、最新情报、最新位址、注册免费送、房间火爆、美女荷官、妹妹直播、精彩直播、
台湾uu、美少女直播、信誉保证、最新情報。前 8 项原已存在；后 4 项新增，`最新情报` 并非新增。
上述原有规则默认启用，但自动清理仍默认关闭。

旧 `garbage_keywords` 合并并去重到 `clean_contains`；代码兼容属性保留，新序列化不再输出第二份黑名单。
旧 `|` 分隔字符串迁移到规则列表，规则开关和排除项保留。加载只在内存迁移，点击保存才改 JSON。
合成旧配置加载/保存/再加载和无关字段保留已经验证；**没有收到真实私有 JSON，不能说已核验用户所有旧设置**。
原要求涉及的三个真实垃圾视频未上传本体，字节数未知；没有调大 N。
七个历史 NFO 未提供、未读取真实拒绝语，未实施批量回溯修复。

第一阶段核心判断、隔离、删除、目录核对和迁移已验收；第二阶段只收尾其界面，不重做核心。
详细规则说明：[garbage-cleanup.md](garbage-cleanup.md)。

## 三、翻译本周做过什么，最终保留什么

### 方案演变

最初加入通用“检测拒绝 → 同模型重试 → 独立备用 → 原文”。随后第二阶段按当时要求接本机为主、云端为备。
用户实际启动并验证本机后，明确改为**云端为主、本机为备**；这是最终方案，优先于旧文档和启动窗口提示。
恢复原 DeepSeek 后主接口、拒绝重试工作正常；最后一轮确认两端均失败也可保留原文，功能收口。

### 目前实际调用规则

- 标题、简介分别独立走主接口、同模型重试、备用、对应字段原文；一个字段失败不覆盖另一个字段的成功译文。
- 请求错误、超时、空返回以及检测到开头拒绝语均进入相同故障链。空原文不请求。
- 默认拒绝/不可用重试 1；云端内部 `llm_max_try` 是另一层请求错误尝试数，默认 5。
  最终配置将“云端主模型尝试”设为 **1**，因此每个失败字段是云端首次 + 重试一次 + 本机一次。
- 本机主接口和任何备用每一步只请求一次；OpenAI SDK `max_retries=0`，避免额外隐含重试。
- 无需改 Prompt 触发/绕过拒绝。主/备用共用用户标题/简介 Prompt 与温度；统一系统消息为通用翻译说明。
- 12 个默认拒绝前缀：抱歉、对不起、很抱歉、我不能、我无法、无法协助、不能协助、
  `I'm sorry`、`I am sorry`、`I can't`、`I cannot`、`Sorry`。
  忽略开头空白/引号与英文大小写；词出现在句中不因此判为拒绝。
- 备用必须有地址、模型；云端备用还需要 Key。本机回环地址可空 Key，不因缺 Key 跳过。
- 回环检测支持字面 localhost、127.*、::1，不做 DNS；本机隔离全局/环境代理，不跟随重定向。
  云端沿用现有代理。请求客户端有活跃请求/租约和关闭管理，备用客户端使用后释放。
- 正常返回只做换行等文本处理，未发现程序转换调换主宾关系。
- 全部保留时汇总“未获得译文”，部分成功显示“部分翻译完成”，分别列出标题/简介。
  简介未翻译时保留原 `outline_from` 来源，避免假标成 LLM。未读取或改写用户历史 NFO。
- 请求日志目前只写异常类型，成功摘要统一为 `Llm`，缺少每个影片/字段的成功后端标识。
  不能仅凭“翻译完成(Llm)”判定来自云端还是本机；需要结合切换日志和服务推理时间。
- **语义错误不会自动触发备用**：主宾颠倒、姓名不一致、增写等不属于现有错误/拒绝判断。
  不擅自增加自动语义评审、纠错模型或改写历史 NFO。

### 最终用户配置与默认值要分开

| 设置 | 当前日常使用应保持 |
| --- | --- |
| 主 URL / Model / Key | 用户已验证可用的 DeepSeek 私有配置，不能由本机预设覆盖 |
| 翻译服务 | 只勾选 LLM；多引擎会随机排列，云端主接口不会自动获得最高优先级 |
| 云端主模型尝试 | 1 |
| 拒绝 / 不可用重试 | 1 |
| 标题 / 简介 Prompt | 用户原有私有内容，不索取、不替换 |
| Temperature | 0.90；主/备用共用 |
| 备用 URL | `http://127.0.0.1:8080/v1` |
| 备用 Model | `HY-MT2-7B-Q8_0`；复用别的服务时以实际 ID 为准 |
| 备用 Key | 空 |
| 备用读取超时 | 默认 60 秒 |

主读取超时配置默认 60 秒；曾建议可先设 30 秒，但日志没有证明用户改了，不能把建议写成实际设置。
`TranslateConfig` 温度字段默认 0.20，仓库 `default_config.json` 则为 0.90；用户确认使用 0.90。
当前代码的新配置主 URL/Model 仍默认本机，备用为空。
“使用本机 Hy-MT2（海南鸡接口）”按钮会填**主** URL/Model 并清掉主 Key；它没有启动进程。
旧启动器/README 提示点本机主预设，已不适合最终云端优先方案。下一阶段必须统一这些提示和控件行为，
但不能自动迁移、猜测或清空已有云端私有配置。
操作说明：[cloud-first-local-fallback.md](cloud-first-local-fallback.md)。

## 四、今天用户实测与准确性结论

以下均为 2026-10-11 北京时间；每轮三条媒体、每条标题/简介两个字段。

| 时间 / 场景 | 证据 | 结论 |
| --- | --- | --- |
| 18:58:02–19:06:08 本机正常 | 6 个字段与 6 次本机推理时间对应；耗时 15.90/13.41/15.88 秒 | 本机加载、实际调用、翻译完成已验证 |
| 19:36:53–19:45:44 GLM 配置 | 8 次 BadRequestError、2 次拒绝、5 次重试、5 次转本机及对应推理 | 5/6 字段由本机备用完成；不能当作全部云端质量样本 |
| 19:47:54–19:56:03 故意无效云端模型 | 12 次 BadRequestError、6 次重试、6 次转本机及对应推理 | 主接口错误后本机承担全部 6 字段，三条翻译完成 |
| 20:11:06–20:19:46 恢复 DeepSeek | 无 API 错误、无备用切换；20:13:33 一次拒绝重试后成功 | 全部 6 字段由主接口完成，拒绝重试也通过 |
| 20:41:57–20:50:04 云端无效、本机已停止 | 12 次主错误、6 次重试、6 次切换、6 次 APIConnectionError、6 次备用不可用、6 次保留原文 | 两端失败正确回到对应原文，三条均显示未获得译文 |

最终轮启动器显示服务在 **20:40:45 停止**，早于测试；完整 stderr 没有本轮新增推理。
三条翻译阶段耗时 3.04、3.05、2.99 秒；标题与原题相同，简介可见部分与原简介相同。
日志三次 NFO 生成完成，但实际 NFO 没上传，不能说读取/核对过完整输出文件。
`Total 3 / Success 3 / Failed 0` 统计刮削完成，不等于取得译文；独立翻译汇总已明确原文回退。
早期 18:54:51 手动中止不算故障。第一阶段垃圾清理用户已于 10 月 9 日验收。

关于质量：GLM 测试时多数输出其实来自本机；PRED-110 有主宾/被动角色错误，简介有增写，名字有不同处理。
用户说明正常 GLM 轮使用 `https://open.bigmodel.cn/api/paas/v4` 和 `GLM-5.3-Flash`；
原供应商是 DeepSeek，旧模型由用户描述为 `V4.1Flash`。这些是用户描述，不是核实过的账户模型 ID。
Prompt 和温度与此前相同，不能归因于本次改过 Prompt/温度。
GLM 的 HTTP 400 仅记录异常类型，具体错误原因未定位；公开文档访问受环境代理限制，不能猜测无效模型名或权限。
DeepSeek 恢复后关键主宾关系改善，用户肉眼认为可用；可见片段仍有局部增写和姓名处理差异。
简介日志截断，未检查私有 Prompt，因此不宣称逐字忠实或所有译文完全正确，也不归责用户 Prompt。
已验收的是**调用及故障回退功能**，下一阶段不继续纠缠已通过路径。

原始证据文件名包括：`2026-10-11-18-52-33.txt`、`18-56-31.txt`、`19-34-47.txt`、
`20-10-10.txt`、`20-41-18.txt`（后三个短名同样有 `2026-10-11-` 前缀），各轮主/详细请求粘贴日志，
`launcher.log`、`server-stderr.log`。`server-stdout.log` 为 0 KB 属正常，不必补传。
服务日志运行中曾恰为 4 KB/16 KB 且在半行截断，应正常停止后等缓冲刷新，不能当成没有推理。
完整逐轮分析：[cloud-first-real-test-20261011.md](cloud-first-real-test-20261011.md)，
功能验收：[stage2-translation-acceptance.md](stage2-translation-acceptance.md)。

## 五、本地模型安装和启动：已经查清与尚未实现

用户不知道模型具体位置和安装方式，只大致知道在哪个盘；不要再次让用户解释部署技术或先找文件。
已查到“海南鸡”是 [Marcus515J/Faster-Whisper-TransWithAI-ChickenRice](https://github.com/Marcus515J/Faster-Whisper-TransWithAI-ChickenRice)。
其 `tools/setup_stage2_runtime.ps1`、桥接调用和部署说明使用 llama.cpp 的 OpenAI 兼容服务；
安装记录 `<baseRoot>\stage2_runtime.json` 的 `llama_server_path`、`model_path` 可辅助查找，
默认 runtime 位于 `<baseRoot>\stage2-runtime\llama.cpp\...`。海南鸡按任务启停不代表 MDCx 已有进程管理。

用户当前**已验证**的运行位置：

| 项目 | 值 |
| --- | --- |
| 选择的服务程序 | `H:\0AI\llama.cpp\llama-server.exe` |
| 找到的另一份程序 | `H:\MarvisData\InferenceFrame\llama.cpp-cuda-12.4-b9128\llama-server.exe`；未选择验证 |
| 模型文件 | `H:\0AI\models\HY-MT2-7B-Q8_0.gguf` |
| 服务地址 / ID | `http://127.0.0.1:8080/v1` / `HY-MT2-7B-Q8_0` |
| MDCx 测试目录 / JSON | `H:\0H\MDCx\测试` / `日常.json` |
| 待刮削目录 | `G:\待刮削` |

现在仍靠外部 ZIP：解压后双击 **`Start-HyMT2.cmd`**，不是直接打开 PS1。
旧单 PS1 会打开记事本、右键运行黑窗闪退，已被 CMD 入口的错误停留和日志替代。
CMD 用 Windows PowerShell 5.1、进程范围 ExecutionPolicy Bypass、UTF-8；PS1 用 BOM/CRLF。

当前启动器已实现：

- 输入盘符，广度查找现有程序/模型，优先使用安装记录；跳过系统/隔离目录和链接。
- PE 的 MZ 与 GGUF 头验证；优先 7B Q8，找到多个可选择。**每次重新查找，没有路径缓存**。
- 使用已安装程序与模型，不下载、不安装新模型，不读取私有 MDCx 配置或旧 NFO。
- 参数为 `-m <model> -ngl 999 -c 8192 --host 127.0.0.1 --port 8080 --alias HY-MT2-7B-Q8_0`。
- Windows 空格、中文、方括号等路径按字面传递；`/health` 就绪且 `/v1/models` 有 Hy-MT2 ID 才报告可用。
- 最多等待 180 秒，每 10 秒提示；端口占用报错，不杀未知进程。
- 已有兼容且就绪服务可复用，不归本次所有、不停止；新启动的服务由本窗口管理。
- 服务窗口必须保持打开，回车停止本次启动进程、释放显存。不会在云端失败时自动开模型。
- `logs` 记录启动器、stdout、stderr；目录不可写时回落到 `%LOCALAPPDATA%\MDCx-HyMT2\logs`。

**未实现：软件内启动/停止/加载状态、路径记忆、界面后台查找和服务进程生命周期管理。**
本机接入功能已通，下一阶段要改的是使用体验，而不是重新寻找一种协议或模型。

## 六、原有窗口/控件设计逻辑与本周界面改动

### 原有结构应先读哪些文件

- PyQt6。主设计源 [MDCx.ui](../mdcx/views/MDCx.ui)，生成文件 [MDCx.py](../mdcx/views/MDCx.py)。
  [scripts/pyuic.sh](../scripts/pyuic.sh) 会重新生成主窗和 posterCutTool；只改生成文件会被覆盖。
  延续现有 controller 动态控件模式，或同时维护 `.ui` 与生成文件，不能引入互相覆盖的两套布局。
- 主窗口 [main_window.py](../mdcx/controllers/main_window/main_window.py)：`setupUi`、绑定主题刷新、
  部分旧动态 UI、`Init_Singal`、`Init_Ui`、`load_config`；新动态控件需在配置加载前准备好。
- [init.py](../mdcx/controllers/main_window/init.py)：设置树/下拉列表/旧控件，最后添加站点优先级、清理和 LLM 控件。
  基础窗口约 1089×700，设置由堆叠页面、滚动区域、内部表格布局组成，外层不少固定坐标。
  **Windows 明确 `setFixedSize` 禁止主窗口调整大小**；Linux 离屏 resize 不能冒充真实 Windows 可缩放验收。
- [style.py](../mdcx/controllers/main_window/style.py)：统一 `LIGHT_TOKENS` / `DARK_TOKENS`、palette、
  全局 QSS、菜单/树样式。原输入控件约 14px 字体、1px 边框、输入框圆角 10、下拉圆角 8、
  4px/8px 内边距和统一焦点色；复用主题来源，不另造颜色/圆角体系。
- [load_config.py](../mdcx/controllers/main_window/load_config.py)、
  [save_config.py](../mdcx/controllers/main_window/save_config.py)：整个设置页的加载和底部总保存。
  现有站点优先级弹窗 `site_priority_dialog.py`、裁剪窗口 `CutWindow` / `posterCutTool.ui` 可作为原有窗口参照。

### 清理页已经怎么收尾

[file_cleanup_settings.py](../mdcx/controllers/main_window/file_cleanup_settings.py) 动态扩展原 `groupBox_61`，
高度 775；复用 `gridLayout_52`，标签最小宽度 130、输入控件最小高 30，并复制原输入框样式。
增加目录、处理方式、N 等行；N 用无箭头 `QDoubleSpinBox`，与原 `lineEdit_escape_size` 双向同步并阻止信号递归。
说明利用右侧空间分为两块；自动开关/手动按钮同排，状态另排，移动后续分组并增加滚动页高度。
旧确认项隐藏，重复保存按钮移除。`63c867c` 已实现原交接的界面草稿内容，**不要再应用旧 patch**。

### 翻译页已经增加哪些控件

[llm_settings.py](../mdcx/controllers/main_window/llm_settings.py) 扩展原 `groupBox_llm` 和滚动页 +365，
内部 grid 区域调整到 661×916，后续分组下移。新行 13–20 包括本机主预设、主超时、拒绝重试、
备用 URL/Model/Key/超时和帮助文字；控件最小高 30，复制主 URL 输入框样式，主/备用 Key 遮蔽显示。
加载/底部保存已接入，云端尝试数在主接口是本机时禁用。尚无进程管理控件。

### 下一次统一时必须检查的点

1. 标签列、控件高度、边框、间距、按钮状态、帮助文字和滚动区域统一到原页面；
   检查复制局部 style 是否覆盖全局深浅主题。用户说的“窗口/小格”首先指新增的这些界面元素。
2. `_setup_combo_boxes` 在新增清理下拉控件前执行；检查新下拉弹出列表是否缺原统一设置。
   这是代码顺序发现，未声称已经造成实际 Windows 显示故障。
3. 不用多层固定坐标不断加高页面解决全部新增控件；同时保证原有分组和底部保存可达。
   是否改整窗可调整大小属于下一阶段设计选择，不能假称原程序已支持。
4. 分清“保存配置”与“启动/停止服务”。不再新增第二套清理规则或独立保存，不把云端 Key 清空。
5. `exit_app()` 最后调用 `os._exit(0)`：普通析构、Qt 退出信号不能保证执行。
   新增模型进程清理必须发生在这里退出前；关闭确认取消、最小化和托盘隐藏不能当成退出。
6. 现有 `Computed` / `LLMClient` 有请求租约与关闭流程；配置变更或停服期间要协调在途翻译，
   后台查找/加载/健康轮询不得阻塞 Qt 主线程，UI 更新通过现有线程/信号方式。

## 七、下一阶段工作顺序和验收边界

先读上述 `.ui`、初始化、主题、清理/翻译 controller 及配置加载保存，把设计逻辑说明清楚，
然后从当前已验收分支另建开发分支。用户已授权下一阶段两项工作，常规可逆实施不用反复确认。

### 软件内本地模型使用

- 首次只需知道盘符：后台发现现有安装，列出多份程序/模型供选择，支持浏览兜底；
  记忆已选路径，下次优先验证缓存，缺失时重新查找。不要每次全盘扫描或让用户先掌握安装详情。
- 在翻译页提供启动、停止、加载进度/就绪/失败状态和日志入口，使用上述已验证协议/健康检查与模型 ID。
- 明确进程所有权：本软件启动的可停止，复用已有服务不擅自停止；占用端口、模型缺失、超时、
  异常退出给出可读原因，不能靠闪退黑窗；退出时清理自己启动的服务。
- 继续让 DeepSeek 保持主接口，本机作为备用；本机设置动作只更新本机备用相关字段。
  保留原云端地址/模型/Key、Prompt、0.90 温度及用户其他设置。
- 至少先完成界面内可启动/停止这一闭环；是否云端失败时再按需加载、是否软件启动时自动加载，
  在读取代码后选择最小可用方案，不能把这些尚未决定的策略当成既定验收要求。
- 复用现有程序和模型，不重新安装/下载，不重做清理核心或故障回退算法，不引入不必要依赖。

### 控件统一和验证

统一本周新增清理、翻译及新模型管理控件，遵循原主题/布局/总保存。
有意义的自动验证覆盖路径发现缓存、带中文/空格/方括号、加载健康、端口占用、服务所有权、
重复点击、异常退出、取消关闭与正常退出清理，以及配置保存再加载不覆盖云端私有字段。
适当跑受影响的清理/翻译回归；除非改动导致新风险，不要求用户重做已通过的全套人工故障测试。
实际 Windows 要核对深浅主题、常用 100%/150%/200% 缩放、固定窗大小下滚动/标签/按钮/输入框和保存可达。
离屏截图不能替代用户桌面外观验收。需要新 EXE 时先完成 Windows CI、构建、资产与下载校验再给测试链接。

## 八、已有验证、发布和边界记录

| 阶段 | 证据 |
| --- | --- |
| 第一阶段 | Linux / Windows 同组 145 项通过；[Windows CI 37928798612](https://github.com/Marcus515J/mdcx/actions/runs/37928798612)，68.73 秒；用户 Windows 清理实测通过 |
| 第二阶段早期全量 | Linux 661 通过、13 跳过、2 警告，159.03 秒；相关选测 192 通过，20.04 秒 |
| 早期主题/缩放 | Linux 离屏深浅主题、两尺寸、1.5/2 缩放各 12 项通过；不等于真实 Windows 桌面验收 |
| 初版第二阶段 EXE | `test-20261009-local-hymt2` / `6c25252`；[CI 37939810767](https://github.com/Marcus515J/mdcx/actions/runs/37939810767)，176 项通过 |
| 自动查找启动包 | `launcher-20261011-autofind` / `fb6ba96`；[CI 38109272642](https://github.com/Marcus515J/mdcx/actions/runs/38109272642)，PowerShell 5.1 共 21 项通过 |
| 当前 EXE / 启动包 | [CI 38111448545](https://github.com/Marcus515J/mdcx/actions/runs/38111448545)，181 程序测试通过，71.65 秒；启动器 22 通过，81.099 秒；构建和上传成功 |
| 同版独立启动器工作流 | [CI 38111448704](https://github.com/Marcus515J/mdcx/actions/runs/38111448704)，22 通过，83.850 秒 |
| 当前版 Linux 翻译选测 | 68 通过，15.06 秒；随后云端优先新增 9 个验证，总 77 通过，22.29 秒；ruff / 差异检查通过 |

Windows 程序测试使用锁定依赖、Qt offscreen；启动器用真实 PowerShell 5.1 测试。
已有 zhconv/pkg_resources 弃用警告没混入功能修复。`pyproject.toml`、`uv.lock` 本周未改，没有新增依赖。
本轮仅写交接，检查文档/链接/提交完整性，不把历史测试冒充本轮重跑。

历史资产便于回退，不应给用户替代当前版：

- 第一阶段 EXE：153227060 字节，SHA256 `faede502ac6081cbd374d20e38adab4f45f31496adf16fb3ccc15a9f69c20903`。
- 初版第二阶段 EXE：153234693 字节，SHA256 `1be6ee9ab1cfccb786c5adc8c601b743b120464057c6038dc6ce962407ceebf7`。
- 初版单 PS1 已淘汰；自动查找旧 ZIP：7308 字节，SHA256 `15f14d9a8841376bf006327dc79f8ad55f2249c74675eea1443f08e79a59cd9e`。
- 早期标签 `test-20261009-ab-folders`、`test-20261009-rule-editor`、`test-20261009-rule-editor-v2` 属清理迭代历史。

旧独立分支 `fix/translate-without-nfo` 的 `5b5f132228819cf5f6894e878057c18a0b114fee` 是 **9 月 4 日**
“不输出 NFO 也处理翻译元数据”的修复，已包含在主分支和当前分支；本周未重做，也不是待合并遗漏。

### 明确保留的范围外/未验证事项

- MTES-003/004 重复刮削、文件名漂移、bypass 超时后浏览器重复启动未修改，不属于当前下一阶段范围。
- `192.168.50.5:8000/html` bypass、jav321 等站点超时、DMM 预告 HEAD 403/404 会拖慢刮削，
  是独立网络问题，不是已验证 LLM 回退链故障；Windows 软链接 `WinError 1314` 是权限问题。
- GLM HTTP 400 的具体服务端原因尚未定位，完整语义质量未验收；目前已选可用 DeepSeek，不强行扩展。
- 真实私有 JSON 逐字段迁移、三个垃圾视频本体大小、七个历史 NFO、完整实际输出 NFO 未读取验证。
- 当前服务路径已验证，另一份 llama-server 未选择测试；软件内进程管理仍待实现。
- 本周 UI 有自动验证，但真实 Windows 深浅主题/高 DPI 外观仍留给下一阶段。

## 九、资料优先级与旧记录如何使用

发生冲突时按**用户最新要求 → 本交接 → 最新验收/云端优先记录 → 历史说明**读取。

| 文档 | 用途 / 注意 |
| --- | --- |
| 本文件 | 下一次对话首读，汇总本周工作和下一阶段边界 |
| [stage2-translation-acceptance.md](stage2-translation-acceptance.md) | 当前翻译功能验收和最后一轮故障计数 |
| [cloud-first-real-test-20261011.md](cloud-first-real-test-20261011.md) | 今天全部实际日志分析；前半旧“尚未验证”应结合末尾最终结果读取 |
| [cloud-first-local-fallback.md](cloud-first-local-fallback.md) | 当前云端主、本机备配置；故障测试步骤已执行，不必重复 |
| [stage2-validation.md](stage2-validation.md) | 发布/测试累积历史；下方“下一步未验收”只对应当时状态 |
| [garbage-cleanup.md](garbage-cleanup.md) | 当前统一清理规则 |
| [stage2-handoff.md](stage2-handoff.md) | 10 月 9 日第一阶段→第二阶段旧交接；本机主力、未接入等描述已过时 |
| [llm-refusal.md](llm-refusal.md)、[windows-test-guide.md](windows-test-guide.md) | 配置细节和历史测试指引；按云端优先新通知使用 |
| [drafts/stage2-cleanup-ui.patch](drafts/stage2-cleanup-ui.patch) | 当时停止开发留下的草稿；内容已由 `63c867c` 实施，禁止再套用 |
| [pyqt6-migration.md](pyqt6-migration.md)、[crawler-migration.md](crawler-migration.md) | 原有技术背景，非本周新增需求 |

## 十、新对话可直接粘贴

> 请读取 Marcus515J/mdcx 的 feat/local-hy-mt2-translation 分支 docs/stage3-handoff.md，并以当前最新提交另建下一阶段开发分支。第一阶段垃圾清理和第二阶段翻译调用/故障回退都已验收，保留现有结果，不重做。最终方案是 DeepSeek 云端主接口、同模型重试一次、本机 Hy-MT2 备用、最后对应字段原文。现在完成两件事：把本地模型查找、路径记忆、启动/停止与状态直接做进软件界面；先读取原有窗口/控件及主题设计，再统一本周新增的清理、翻译和模型管理界面。不要覆盖我的云端配置、私有 Prompt 和 0.90 温度，不再索取 Prompt、Key、Cookie 或完整配置，不改历史 NFO，不再次套用旧界面 patch。先读交接和代码，简要说明具体改动后继续实施；用相关验证和 Windows 成品完成下一阶段，不扩展到交接列出的无关问题。


## 附录 A：本周全部增量提交（北京时间）

以 10 月 4 日主分支基线至 `1469dd3` 的完整祖先链为准，共 24 条；文档、测试、启动器迭代都列出。
这次综合交接的提交另见本文件 Git 历史，不属于下面已经验收的功能改动。

| 提交 | 北京时间 | 内容 |
| --- | --- | --- |
| [`0911fd1`](https://github.com/Marcus515J/mdcx/commit/0911fd1) | 10-09 10:50 | feat: safely quarantine unidentified garbage videos before scraping |
| [`ebd60e0`](https://github.com/Marcus515J/mdcx/commit/ebd60e0) | 10-09 10:55 | feat: detect LLM translation refusals and fall back to original text |
| [`ff7c131`](https://github.com/Marcus515J/mdcx/commit/ff7c131) | 10-09 15:17 | feat: quarantine garbage-only folders after scraping |
| [`9bedef1`](https://github.com/Marcus515J/mdcx/commit/9bedef1) | 10-09 15:17 | ci: build Windows prereleases with a testing guide |
| [`a87b170`](https://github.com/Marcus515J/mdcx/commit/a87b170) | 10-09 19:37 | feat: edit garbage rules in settings and report processing mode |
| [`e848baa`](https://github.com/Marcus515J/mdcx/commit/e848baa) | 10-09 19:39 | test: read saved Chinese configuration as UTF-8 on Windows |
| [`fe491f7`](https://github.com/Marcus515J/mdcx/commit/fe491f7) | 10-09 20:14 | feat: unify file cleanup settings and explicit filename handling |
| [`7581fdb`](https://github.com/Marcus515J/mdcx/commit/7581fdb) | 10-09 21:23 | docs: close accepted cleanup stage and hand off local LLM integration |
| [`21ff6f9`](https://github.com/Marcus515J/mdcx/commit/21ff6f9) | 10-09 21:47 | feat: connect local Hy-MT2 and handle unavailable translations through fallback |
| [`63c867c`](https://github.com/Marcus515J/mdcx/commit/63c867c) | 10-09 21:48 | ui: finish cleanup settings layout and use the shared save button |
| [`6c25252`](https://github.com/Marcus515J/mdcx/commit/6c25252) | 10-09 21:50 | fix: distinguish empty backup translations from refusals in logs |
| [`c537f62`](https://github.com/Marcus515J/mdcx/commit/c537f62) | 10-09 21:58 | docs: record stage two validation and verified Windows release assets |
| [`8465177`](https://github.com/Marcus515J/mdcx/commit/8465177) | 10-11 11:35 | fix: make local Hy-MT2 launcher discover installs and retain errors |
| [`859a08b`](https://github.com/Marcus515J/mdcx/commit/859a08b) | 10-11 11:38 | fix: preserve literal Windows runtime paths and check loaded model health |
| [`fb6ba96`](https://github.com/Marcus515J/mdcx/commit/fb6ba96) | 10-11 11:40 | test: account for Windows canonical paths and replace outdated launcher guide |
| [`85a27dd`](https://github.com/Marcus515J/mdcx/commit/85a27dd) | 10-11 11:43 | docs: record Windows-tested automatic local model launcher |
| [`0202a64`](https://github.com/Marcus515J/mdcx/commit/0202a64) | 10-11 11:45 | docs: record verified downloadable launcher package |
| [`7734622`](https://github.com/Marcus515J/mdcx/commit/7734622) | 10-11 12:23 | fix: clarify reused model setup and report actual translation outcomes |
| [`70e3b8a`](https://github.com/Marcus515J/mdcx/commit/70e3b8a) | 10-11 12:30 | docs: record verified review-fix Windows release and launcher |
| [`e1765d0`](https://github.com/Marcus515J/mdcx/commit/e1765d0) | 10-11 19:29 | test: verify cloud-first local fallback and document minimal configuration |
| [`fff1f48`](https://github.com/Marcus515J/mdcx/commit/fff1f48) | 10-11 20:05 | docs: record verified cloud-to-local failover and translation quality findings |
| [`66076f7`](https://github.com/Marcus515J/mdcx/commit/66076f7) | 10-11 20:07 | docs: incorporate provider change and unchanged private prompts in quality diagnosis |
| [`c10d22e`](https://github.com/Marcus515J/mdcx/commit/c10d22e) | 10-11 20:23 | docs: record DeepSeek recovery and successful refusal retry |
| [`1469dd3`](https://github.com/Marcus515J/mdcx/commit/1469dd3) | 10-11 20:53 | docs: close real translation failover validation including source preservation |

关键历史归属：独立弹窗 `a87b170` 后由 `fe491f7` 统一；旧 UI 草稿由 `63c867c` 落实；
实际字段汇总与来源修复 `7734622`；云端优先配置与新增验证 `e1765d0`；
DeepSeek 恢复 `c10d22e`；两端失败最终验收 `1469dd3`。

## 附录 B：本周全部最终改动文件与定位

以下为 `f3650ef..1469dd3` 的最终净改动，完整列出，便于下一位逐项核对。
历史上新增后删除的 `garbage_settings_dialog.py` 不在净差异里，已由统一 controller 替代。
`mdcx/views/MDCx.ui`、生成文件、全局 `style.py`、`config/computed.py` 和 `config/manager.py` 是
应阅读的原有设计/生命周期来源，本周没有净修改；不要把相关源码阅读误认为已改造。

| 状态 | 文件 |
| --- | --- |
| 修改 | [.gitattributes](../.gitattributes) |
| 新增 | [.github/workflows/local-launcher.yml](../.github/workflows/local-launcher.yml) |
| 新增 | [.github/workflows/test-release.yml](../.github/workflows/test-release.yml) |
| 新增 | [docs/cloud-first-local-fallback.md](../docs/cloud-first-local-fallback.md) |
| 新增 | [docs/cloud-first-real-test-20261011.md](../docs/cloud-first-real-test-20261011.md) |
| 新增 | [docs/drafts/stage2-cleanup-ui.patch](../docs/drafts/stage2-cleanup-ui.patch) |
| 新增 | [docs/garbage-cleanup.md](../docs/garbage-cleanup.md) |
| 新增 | [docs/llm-refusal.md](../docs/llm-refusal.md) |
| 新增 | [docs/stage2-handoff.md](../docs/stage2-handoff.md) |
| 新增 | [docs/stage2-translation-acceptance.md](../docs/stage2-translation-acceptance.md) |
| 新增 | [docs/stage2-validation.md](../docs/stage2-validation.md) |
| 新增 | [docs/windows-test-guide.md](../docs/windows-test-guide.md) |
| 修改 | [mdcx/base/file.py](../mdcx/base/file.py) |
| 修改 | [mdcx/base/translate.py](../mdcx/base/translate.py) |
| 修改 | [mdcx/config/extend.py](../mdcx/config/extend.py) |
| 修改 | [mdcx/config/migrations.py](../mdcx/config/migrations.py) |
| 修改 | [mdcx/config/models.py](../mdcx/config/models.py) |
| 新增 | [mdcx/controllers/main_window/file_cleanup_settings.py](../mdcx/controllers/main_window/file_cleanup_settings.py) |
| 修改 | [mdcx/controllers/main_window/init.py](../mdcx/controllers/main_window/init.py) |
| 新增 | [mdcx/controllers/main_window/llm_settings.py](../mdcx/controllers/main_window/llm_settings.py) |
| 修改 | [mdcx/controllers/main_window/load_config.py](../mdcx/controllers/main_window/load_config.py) |
| 修改 | [mdcx/controllers/main_window/main_window.py](../mdcx/controllers/main_window/main_window.py) |
| 修改 | [mdcx/controllers/main_window/save_config.py](../mdcx/controllers/main_window/save_config.py) |
| 修改 | [mdcx/core/scraper.py](../mdcx/core/scraper.py) |
| 修改 | [mdcx/core/translate.py](../mdcx/core/translate.py) |
| 修改 | [mdcx/llm.py](../mdcx/llm.py) |
| 修改 | [mdcx/number.py](../mdcx/number.py) |
| 修改 | [resources/config/default_config.json](../resources/config/default_config.json) |
| 新增 | [scripts/Start-HyMT2.cmd](../scripts/Start-HyMT2.cmd) |
| 新增 | [scripts/local-hymt2-README.txt](../scripts/local-hymt2-README.txt) |
| 新增 | [scripts/package-local-hymt2.ps1](../scripts/package-local-hymt2.ps1) |
| 新增 | [scripts/start-local-hymt2.ps1](../scripts/start-local-hymt2.ps1) |
| 新增 | [scripts/test_local_hymt2_launcher.py](../scripts/test_local_hymt2_launcher.py) |
| 新增 | [tests/test_garbage_cleanup.py](../tests/test_garbage_cleanup.py) |
| 新增 | [tests/test_garbage_settings_ui.py](../tests/test_garbage_settings_ui.py) |
| 新增 | [tests/test_llm_refusal.py](../tests/test_llm_refusal.py) |
| 新增 | [tests/test_llm_settings_ui.py](../tests/test_llm_settings_ui.py) |
| 新增 | [tests/test_local_llm.py](../tests/test_local_llm.py) |
| 新增 | [tests/test_unified_file_cleanup.py](../tests/test_unified_file_cleanup.py) |

测试入口分工：`test_garbage_cleanup` / `test_unified_file_cleanup` 测清理行为与迁移，
`test_garbage_settings_ui` / `test_llm_settings_ui` 测设置交互，`test_llm_refusal` / `test_local_llm`
测拒绝、错误、本机/云端请求及 SDK 路径；`scripts/test_local_hymt2_launcher.py` 测 Windows 启动器。
CI 入口 `.github/workflows/test-release.yml`、`local-launcher.yml`；打包 `scripts/package-local-hymt2.ps1`。
