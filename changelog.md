# MDCx v1.2.0

发布日期：2026-10-29

本版汇集 v1.1.1 之后的翻译、日志与来源策略改进；翻译使用大模型 API。

### 来源与请求

- 修复 JavBus 首次详情未找到后，回退搜索时的异常。
- JavLibrary 复用同片页面，去掉重复的双语言读取；搜索已返回精确详情时直接解析。
- CF 挑战、bypass 解题失败、mirror 超时和 /html 回退失败，在既有尝试耗尽后按片计数：本片放弃该站、暂停 60 秒，连续三部失败才停站，成功清零。
- FC2 官方简介中的“看更多”等占位文本不再作为正文，继续由后续来源补缺。
- 新增 DMM 搜索与传输诊断日志，便于区分页面未匹配和网络失败。外站及 bypass 的可用性仍受实际网络与服务状态影响。

### NFO 与评分汇总

- NFO rating 按来源满分统一换算为 10 分制，保留小数；没有可用评分时不写入。
- votes 只记录同一评分来源的真实评分人数，拿不到就不写；想看人数另存 wanted / wantedsource，不再冒充评分人数。
- 评分汇总覆盖本片已抓取的各站评分及可得人数，不为了人数额外请求站点。
- 旧 NFO 不迁移，重刮后才是新写法。
- 界面「影评人评分（criticrating）」勾选项已无效果，不再输出 criticrating。
- 命名模板如果用了 score，文件名里的分数会保留原始精度（如 4.34），不再提前截为一位小数。

### 翻译与日志

- 中文源标题也可交给大模型精简；片内标题与简介的人名尽量保持一致，失败时按字段回退并记录诊断。
- Windows 任务栏显示批次进度；保存日志时同时保存网络请求记录。

### 日常推荐配置 2.12

2.12 延续 2.11 的来源顺序，配置文件由使用者单独保留，不入库、不随发布包分发。以下为启用站点顺序；各字段只使用对应站点已实现的能力，不是每个字段都逐站请求。

| 分类 | 启用站点顺序 | 评分顺序 | 简介顺序 |
| --- | --- | --- | --- |
| 有码 | official → dmm → avbase → missav → javlibrary → javbus → javdb | javlibrary → javdb | official → dmm → avbase → missav |
| 素人 | mgstage → dmm → avbase → 7mmtv → javbus | mgstage → dmm | mgstage → dmm → avbase → 7mmtv |
| FC2 | fc2 → fc2hub → 7mmtv → javdb | fc2 → javdb | fc2 → fc2hub → 7mmtv |
| 无码 | 7mmtv → javbus → missav → avsox → javdb | javdb | 7mmtv → missav |

来源顺序依据 [PR #51](https://github.com/Marcus515J/mdcx/pull/51) 的配置 2.11 清单及 [PR #53](https://github.com/Marcus515J/mdcx/pull/53) 的 2.12 核对结果；本版不改默认配置或防封数值。
