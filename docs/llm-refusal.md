# LLM 翻译拒绝检测与回退

退出程序后编辑当前 JSON 配置的 `translate_config`，再启动生效。
本次使用配置文件设置（原因见 `garbage-cleanup.md`），设置页保存现有配置时这些键仍保留。

| 键（均在 `translate_config` 内） | 默认值 |
|---|---|
| `llm_refusal_prefixes` | `["抱歉", "对不起", "很抱歉", "我不能", "我无法", "无法协助", "不能协助", "I'm sorry", "I am sorry", "I can't", "I cannot", "Sorry"]` |
| `llm_refusal_retries` | `1`（允许 0） |
| `llm_fallback_url` | `null`（也接受空字符串，表示未配置） |
| `llm_fallback_key` | `""` |
| `llm_fallback_model` | `""` |
| `llm_fallback_read_timeout` | `60` 秒 |

主 LLM 已有 `llm_url` 支持自定义 OpenAI 兼容 API 地址。备用配置示例：

```json
{
  "llm_fallback_url": "https://api.deepseek.com",
  "llm_fallback_key": "填入自己的 Key",
  "llm_fallback_model": "deepseek-flash",
  "llm_fallback_read_timeout": 60
}
```

备用地址、Key 和模型必须全部填写才启用；未完整配置时重试后直接保留原文。
标题和简介分别检测，仅检查去除开头空白及引号后的前缀（英文不区分大小写），中间出现不命中。
原文为空直接跳过。被拒后同模型重试，仍被拒则调用备用一次，备用拒绝/请求失败则保留该字段原文。
复用原 `llm_max_try` 处理 API 传输错误，它与拒绝重试次数不同。
重试和备用沿用同一提示词、温度，没有提示词改写或绕过拒绝的逻辑。
备用客户端使用已有 `LLMClient` 和现有代理设置，调用结束释放资源。
这不修复已存在的 NFO；新结果不会把命中的拒绝译文交给 NFO 写入流程。
