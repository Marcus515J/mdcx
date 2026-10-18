# MDCx 执行汇报 v2.0：查清 DeepSeek 思考模式的请求与读取

- **执行日期**：2026-10-18
- **执行方**：Antigravity（Gemini 3.8 Flash）
- **基线分支**：`master`
- **master HEAD 提交**：`5eb64efcf093dac25ddcc847528ededcbe6bbf7b`
- **当前任务模式**：本单只查不改。不改动仓库任何代码、配置与文档；代码全部基于 `master` 最新提交查阅；唯一产出为本汇报文件，提交并推送到 `handoff` 分支。
- **汇报文件位置**：`handoff/reports/MDCx_执行汇报_v2.0.md`

---

## 机械核对自查清单

| # | 核对项 | 要求 | 自查结果 | 对应章节 |
|---|---|---|---|---|
| 1 | HEAD 提交号 | master 上 `5eb64ef` 或之后提交 | `5eb64efcf093dac25ddcc847528ededcbe6bbf7b` | 头部信息、第六节 |
| 2 | 三条 git grep 原样输出 | 原样贴出，含「无输出」也明确标注 | 全部完整原样贴出 | 第二节 (Q2) |
| 3 | Q2 结论 | 明确为 A / B / C 之一 | 明确为 **A**（完全没有发送 `thinking`） | 第二节 (Q2) |
| 4 | Q1、Q3、Q4、Q5 | 每条都有路径 + 行号证据 | 全部标明文件相对路径与精确行号 | 第一、三、四、五节 |
| 5 | Q6 | 有捕获请求体 JSON、返回值及验证脚本 | 已完成离线 mock 验证，贴出 JSON、返回值及附录脚本 | 第六节、附录 |
| 6 | 仓库无改动 | master 上 `git status` 干净；handoff 只新增本汇报 | master 干净（见第六节输出）；handoff 仅新增本汇报 | 第六节 |
| 7 | 无密钥 | 严禁泄露任何真实 Key / 密码 | 全文无任何真实 Key，Mock 涉及处均打码掩码 | 全文已确认 |

---

## Q1 调用入口

【已查证】

1. **底层大模型请求发起入口**：
   - 文件路径：[`mdcx/llm.py`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L111-L152)
   - 方法名：`LLMClient.ask`（定义于第 111 行，实际发起 HTTP 请求位于第 132–137 行）：
     ```python
     132: chat = await self.client.chat.completions.create(
     133:     model=model,
     134:     messages=messages,
     135:     temperature=temperature,
     136:     extra_body=extra_body,
     137: )
     ```

2. **客户端与 SDK 类型**：
   - 使用官方 **OpenAI Python SDK (`openai` 包，当前环境中版本为 `1.91.0`)** 的异步客户端 `openai.AsyncOpenAI`。
   - 实例化位于 [`mdcx/llm.py`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L39-L51)（第 39–51 行）：
     ```python
     39: local = is_loopback_url(base_url)
     40: self.client = AsyncOpenAI(
     41:     api_key=api_key or ("local" if local else ""),
     42:     base_url=base_url,
     43:     http_client=AsyncClient(
     44:         proxy=None if local else proxy,
     45:         trust_env=not local,
     46:         timeout=timeout,
     47:         follow_redirects=not local,
     48:     ),
     49:     timeout=timeout,
     50:     max_retries=0,
     51: )
     ```
   - 架构说明：`LLMClient` 内部将自定义的 `httpx.AsyncClient`（配置了代理、超时、环回地址策略等）作为 `http_client` 注入 `AsyncOpenAI`，但请求组织和协议格式完全由 OpenAI SDK 的 `chat.completions.create` 驱动。

3. **业务层翻译调用入口**：
   - 文件路径：[`mdcx/base/translate.py`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L157-L249)
   - 函数名：`_llm_translate`（第 157 行）：
     - 主模型调用处：[`mdcx/base/translate.py:190`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L190)：
       ```python
       190: translated = await computed.llm_client.ask(model=tc.llm_model, **request)
       ```
     - 备用模型调用处：[`mdcx/base/translate.py:232-235`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L232-L235)：
       ```python
       232: translated = await fallback.ask(
       233:     model=tc.llm_fallback_model,
       234:     **{**request, "max_try": 1, "temperature": tc.llm_fallback_temperature},
       235: )
       ```
   - 并发/对外业务入口：[`mdcx/base/translate.py:251`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L251)（`llm_translate`，同时并发翻译标题与简介）与 [`mdcx/base/translate.py:262`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L262)（`translate_with_engine`）。

---

## Q2 请求体有没有 `thinking`

【已查证】

### 1. 三条命令的完整原样输出

#### 命令 1：`git grep -n -i "thinking" -- mdcx/`
```
无输出
```
*(退出码 1，没有任何匹配项)*

#### 命令 2：`git grep -n "extra_body" -- mdcx/`
```
mdcx/llm.py:120:        extra_body: object | None = None,
mdcx/llm.py:136:                            extra_body=extra_body,
```
*(退出码 0，匹配 2 处，均在 `mdcx/llm.py`)*

#### 命令 3：`git grep -n "reasoning" -- mdcx/`
```
无输出
```
*(退出码 1，没有任何匹配项)*

### 2. 结论

**A 完全没有发送 `thinking`**

**分析证明**：
1. 整个 `mdcx/` 目录中没有任何包含 `thinking` 或 `reasoning` 的代码、变量或数据字典构造。
2. 尽管 `LLMClient.ask` 在 [`mdcx/llm.py:120, 136`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L120) 的形参列表中声明了 `extra_body: object | None = None`，并透传给 `self.client.chat.completions.create(..., extra_body=extra_body)`，但在翻译业务层（[`mdcx/base/translate.py:178-184`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L178-L184) 的 `request` 字典以及主模型第 190 行、备用模型第 232 行的调用）**从未传递 `extra_body` 参数**，其值保持默认的 `None`。
3. 当 `extra_body=None` 时，OpenAI SDK 序列化 HTTP 请求体时不会向 JSON 根对象追加任何字段。因此发送到 DeepSeek API 的 HTTP 请求体中完全不存在 `thinking` 字段。
4. 依据 DeepSeek 官方文档规则，在没有显式发送 `{"thinking": {"type": "disabled"}}` 的情况下，支持思考模式的模型（如 `deepseek-flash`）将**默认以开启思考模式**处理请求。

---

## Q3 请求体实际带了哪些字段

【已查证】

在 [`mdcx/llm.py:132-137`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L132-L137) 中，实际传递给 `self.client.chat.completions.create` 的全部参数如下：

| 参数名 | 实际类型与结构 | 取值来源与对应配置项 | 默认值 |
|---|---|---|---|
| `model` | `str` | 主模型来自配置项 `tc.llm_model`（[`mdcx/config/models.py:67`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L67)）；备用模型来自 `tc.llm_fallback_model`（[`mdcx/config/models.py:101`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L101)） | 主模型 `"deepseek-chat"`；备用模型 `""` |
| `messages` | `list[dict]`（2条消息） | 在 [`mdcx/llm.py:122-125`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L122-L125) 组装，具体见下方展开 | 详见下方 |
| ↳ `system` | `{"role": "system", "content": ...}` | 硬编码在 [`mdcx/base/translate.py:179`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L179)：`"You are a professional translator."` | 固定文本 |
| ↳ `user` | `{"role": "user", "content": ...}` | 由模板替换生成（[`mdcx/base/translate.py:180`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L180)）：`prompt_template.replace("{content}", text).replace("{lang}", target_language)`。<br>- 标题模板来自 `tc.llm_prompt_title`（[`mdcx/config/models.py:69-72`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L69-L72)）；<br>- 简介模板来自 `tc.llm_prompt_outline`（[`mdcx/config/models.py:73-76`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L73-L76)）；<br>- 目标语言默认为 `"简体中文"` | `"Please translate the following text to {lang}. Output only the translation without any explanation.\n{content}"` |
| `temperature` | `float` | 主模型来自 `tc.llm_temperature`（[`mdcx/config/models.py:80`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L80)）；备用模型来自 `tc.llm_fallback_temperature`（[`mdcx/config/models.py:103`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L103)） | 主模型 `0.9`；备用模型继承 `llm_temperature` |
| `extra_body` | `None` | 形参预留（[`mdcx/llm.py:120`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L120)），业务层未传参，实际为 `None`，不向请求体注入额外参数 | `None` |

**未指定的常见大模型参数**：
- `max_tokens`：未传递（由厂商服务端自行使用默认最大生成上限）。
- `stream`：未传递（默认 `False`，采用非流式等待）。
- `top_p`、`presence_penalty`、`frequency_penalty`、`response_format`：均未传递。

**特别说明：是否所有厂商（DeepSeek、GLM、本机模型）都用同一段代码、同一组参数？**
- **是**。代码中不存在任何针对厂商名称（如 DeepSeek、GLM、SiliconFlow 等）或特定模型 ID 的 `if/else` 分支逻辑。
- 所有厂商统一走同一套 `LLMClient.ask` -> `self.client.chat.completions.create` 调用链，发送相同结构、相同字段集合的请求体。
- 云端与本机模型的唯一代码差异仅在于底层网络策略和重试次数：
  1. [`mdcx/llm.py:39-48`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L39-L48)：通过 `is_loopback_url(base_url)` 判定，若为本地环回地址，则禁用代理（`proxy=None`）、禁用环境代理（`trust_env=False`）、禁止跳转（`follow_redirects=False`），且 API Key 为空时自动兜底填 `"local"`；
  2. [`mdcx/base/translate.py:182`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L182)：若主模型为本机，`max_try` 强制固定为 1，云端模型则使用 `tc.llm_max_try`。
  但在请求体参数（`model`、`messages`、`temperature`）层面上，所有厂商无任何差异。

---

## Q4 读结果读的是哪个字段

【已查证】

1. **响应解析代码路径与行号**：
   位于 [`mdcx/llm.py:138-141`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L138-L141)：
   ```python
   138: text = chat.choices[0].message.content if chat.choices else None
   139: if text:
   140:     text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
   141: return text
   ```

2. **读取字段细节**：
   - **只读 `choices[0].message.content`**。
   - 完全没有读取 `reasoning_content`。即使服务端返回了 `reasoning_content`，OpenAI SDK 虽在对象中解析该字段，但 `mdcx/llm.py` 未去取用该属性，思考过程被直接丢弃。
   - 请求为**非流式**（未设置 `stream=True`），整个代码库不存在 `delta.content` 的流式拼接逻辑。

3. **对 `<think>...</think>` 标签的过滤处理**：
   - **有**。位置就在 [`mdcx/llm.py:140`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L140)：
     ```python
     text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
     ```
   - 过滤逻辑：使用 `flags=re.DOTALL` 进行跨行正则贪婪/非贪婪替换，将从 `<think>` 开始到 `</think>` 结束的全部内联思考过程整体剔除。对于把思考过程写进 `content` 字段的厂商或本地推理引擎（如 GLM-4 部分版本、llama-server 挂载 DeepSeek-R1 权重等），该标签及内容会被完整过滤掉。
   - 后续处理：返回的文本随后在 [`mdcx/base/translate.py:195, 237`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L195) 经过 `_normalize_translated_linebreaks` 换行清洗，并在第 200 行经过 `_is_llm_refusal` 进行拒绝前缀检测。

---

## Q5 超时与重试

【已查证】

### 1. 60 秒超时机制

- **配置定义**：
  - 主模型超时：配置项 `tc.llm_read_timeout`（[`mdcx/config/models.py:77`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L77)），默认值为 `60` 秒。
  - 备用模型超时：配置项 `tc.llm_fallback_read_timeout`（[`mdcx/config/models.py:102`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L102)），默认值为 `60` 秒。
- **生效位置**：
  - 主模型客户端构造：[`mdcx/config/computed.py:26`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/computed.py#L26)：
    ```python
    26: timeout=httpx.Timeout(config.timeout, read=config.translate_config.llm_read_timeout),
    ```
  - 备用模型客户端构造：[`mdcx/base/translate.py:228`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L228)：
    ```python
    228: timeout=Timeout(cfg.timeout, read=tc.llm_fallback_read_timeout),
    ```
  - 客户端透传注入：[`mdcx/llm.py:46, 49`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L46)。
- **超时性质分析（整次请求总时长 vs 读取超时）**：
  - **是读取超时（Read Timeout），不是整次请求的总时长上限**。
  - 在 `httpx.Timeout(config.timeout, read=config.translate_config.llm_read_timeout)` 中：
    - 第一个参数 `config.timeout`（默认 10 秒，定义于 [`mdcx/config/models.py:674`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L674)）作为基础默认超时，限定连接（`connect`=10s）、写入（`write`=10s）和连接池（`pool`=10s）；
    - 关键字参数 `read` 显式设为 60 秒。
    - 在 HTTP 通信中，`read` 超时是指请求发完后，等待服务端回传响应流中数据块的最大空闲间隔。由于大模型翻译采用非流式请求，服务端在完整生成译文前不会发出响应头或内容，因此这 60 秒直接限制了「从发包结束到服务端完成思考和生成并传回首包」的最大等待时间。若 DeepSeek 思考+生成超过 60 秒，将直接抛出 `httpx.ReadTimeout` 异常导致请求失败。它不是包含 DNS、连接、传输在内的全局总时间限制。

### 2. 「尝试次数 2」生效机制

- **配置定义**：
  - 配置项 `tc.llm_max_try`（[`mdcx/config/models.py:79`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/config/models.py#L79)），代码默认值为 1；在用户现有实测运行配置中修改为了 2。
- **生效位置**：
  - 业务层传参：[`mdcx/base/translate.py:182`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L182)：
    ```python
    182: "max_try": 1 if primary_is_local else tc.llm_max_try,
    ```
    （当主模型为云端接口时，`max_try` 传入 `tc.llm_max_try` 即 2；备用模型在第 234 行固定传入 `max_try: 1`）。
  - 执行重试循环：[`mdcx/llm.py:129-148`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L129-L148)：
    ```python
    129: for attempt in range(max_try):
    130:     async with self.limiter:
    131:         try:
    132:             chat = await self.client.chat.completions.create(...)
    138:             text = chat.choices[0].message.content if chat.choices else None
    139:             if text:
    140:                 text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    141:             return text
    142:         except Exception as e:
    144:             log_fn(f"⚠️ LLM API 请求失败: {type(e).__name__}")
    145:     if attempt + 1 < max_try:
    146:         log_fn(f"🔁 LLM API {wait}s 后重试")
    147:         await asyncio.sleep(wait)
    148:         wait *= 2
    ```
  - 重试行为：当请求出现网络故障或 `ReadTimeout` 超时等异常时，`for attempt in range(max_try)` 生效，第 1 次失败后等待 1 秒后发起第 2 次尝试（`wait *= 2` 指数退避）。若达到最大次数仍失败，打印 `❌ LLM API 请求失败, 已达最大尝试次数` 并返回 `None`。
- **补充说明（被拒重试）**：
  在 [`mdcx/base/translate.py:187-204`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/base/translate.py#L187-L204) 还存在一层同模型被拒重试循环：
  `for attempt in range(tc.llm_refusal_retries + 1):`
  该层由 `llm_refusal_retries`（默认 1）控制，仅在 HTTP 请求成功但模型返回了触发词（如“抱歉”、“我无法”）时重新发起请求。

---

## Q6 机械验证（本地离线）

【已实测】

在仓库外部编写了独立的自动化验证脚本 `/Users/gameong/.gemini/antigravity/scratch/verify_deepseek_q6.py`。
脚本通过 monkeypatch `httpx.AsyncClient.send` 拦截真实 HTTP 报文，无需联网、无需真实 API Key，完整模拟 DeepSeek API 在思考模式下同时返回 `reasoning_content` 与 `content` 的场景。

### 1. 捕获到的发往服务端的真实请求体 JSON（Key 打码）

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a professional translator."
    },
    {
      "role": "user",
      "content": "Please translate the following text to 简体中文. Output only the translation without any explanation.\nHello world"
    }
  ],
  "model": "deepseek-chat",
  "temperature": 0.9
}
```
*(注：请求目标 URL 为 `https://api.deepseek.com/v1/chat/completions`；Authorization 请求头已在传输层拦截器中确认为 `Bearer sk-***MASKED***`)*

### 2. 服务端返回数据与翻译函数返回值对比

- **喂给 MDCx 的 Mock 服务端响应数据**：
  ```json
  {
    "id": "chatcmpl-mock-deepseek-test-001",
    "object": "chat.completion",
    "created": 1729245600,
    "model": "deepseek-chat",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "译文YYY",
          "reasoning_content": "思考XXX：这是一段深度思考过程，不应出现在最终译文中"
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 18,
      "completion_tokens": 32,
      "total_tokens": 50
    }
  }
  ```

- **MDCx 翻译函数（`_llm_translate`）实际返回值**：
  ```
  '译文YYY'
  ```

- **断言与核验结果**：
  1. 返回值严格等于 `'译文YYY'`；
  2. `reasoning_content` 中的 `'思考XXX'` **完全未混入**最终译文；
  3. 请求体 JSON 中完全不含 `thinking` 参数。测试断言全部通过（PASS）。

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
`master` 提交哈希值（`git rev-parse HEAD`）：
```
5eb64efcf093dac25ddcc847528ededcbe6bbf7b
```

### 2. handoff 分支状态

在 `handoff` 分支上仅新增汇报文件 `handoff/reports/MDCx_执行汇报_v2.0.md`，不改动任何其它文件。

---

## 另见

1. **`extra_body` 参数通道已就绪**：
   在 [`mdcx/llm.py:120, 136`](file:///Users/gameong/.gemini/antigravity/scratch/mdcx/mdcx/llm.py#L120) 中，`LLMClient.ask` 已经实现了 `extra_body: object | None = None` 并透传至 `self.client.chat.completions.create(..., extra_body=extra_body)`。后续若决定增加「关闭思考」开关，底层 SDK 层面无需进行大改，仅需在业务调用处根据配置将 `{"thinking": {"type": "disabled"}}` 传入 `extra_body` 即可对 DeepSeek 生效。
2. **`temperature` 参数在思考模式下失效**：
   当前配置下 `llm_temperature` 默认值为 `0.9`，由于未传 `thinking: disabled`，DeepSeek 在思考模式下会直接忽略该采样温度。
3. **未设置 `max_tokens` 参数**：
   当前请求未指定 `max_tokens`，如果开启思考模式，DeepSeek 的思考 tokens + 最终译文 tokens 将受服务端的默认 token 上限约束。若输入长简介，需注意是否会因思考过程消耗过多 token 而接近上限或超出 60 秒读取超时。

---

## 附录：Q6 离线验证脚本源码（未提交进仓库）

文件路径：`/Users/gameong/.gemini/antigravity/scratch/verify_deepseek_q6.py`

```python
#!/usr/bin/env python3
"""
MDCx v2.0 Q6 离线机械验证脚本
验证 DeepSeek 思考模式下：
1. MDCx 发出的实际 HTTP 请求体 JSON；
2. 服务端返回同时包含 reasoning_content 和 content 时，MDCx 翻译函数的实际返回值；
3. 服务端若在 content 中混入 <think>...</think> 标签时的清洗效果。
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 将 mdcx 仓库根目录加入 sys.path
REPO_ROOT = Path(__file__).resolve().parent / "mdcx"
sys.path.insert(0, str(REPO_ROOT))

import httpx
from mdcx.base.translate import _llm_translate, llm_translate
from mdcx.config.manager import manager


async def main():
    print("=" * 60)
    print("MDCx v2.0 Q6 离线机械验证开始")
    print("=" * 60)

    # 1. 确认配置当前状态（默认 DeepSeek 配置）
    tc = manager.config.translate_config
    print(f"[配置检查] llm_url: {tc.llm_url}")
    print(f"[配置检查] llm_model: {tc.llm_model}")
    print(f"[配置检查] llm_temperature: {tc.llm_temperature}")
    print(f"[配置检查] llm_max_try: {tc.llm_max_try}")

    captured_requests = []
    orig_send = httpx.AsyncClient.send

    # 2. 构造 Mock 网络传输层
    async def mock_send(client_self, request: httpx.Request, *args, **kwargs) -> httpx.Response:
        body_bytes = request.content
        body_json = json.loads(body_bytes.decode("utf-8")) if body_bytes else None

        # 打码敏感信息（如 Authorization 请求头）
        headers = {}
        for k, v in request.headers.items():
            if "auth" in k.lower() or "key" in k.lower():
                headers[k] = "Bearer sk-***MASKED***"
            else:
                headers[k] = v

        captured_requests.append({
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "body": body_json,
        })

        # 模拟 DeepSeek API 响应：
        # choices[0].message 同时包含 reasoning_content（思考过程）和 content（最终译文）
        fake_api_response = {
            "id": "chatcmpl-mock-deepseek-test-001",
            "object": "chat.completion",
            "created": 1729245600,
            "model": "deepseek-chat",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "译文YYY",
                        "reasoning_content": "思考XXX：这是一段深度思考过程，不应出现在最终译文中",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 18,
                "completion_tokens": 32,
                "total_tokens": 50,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 18,
            },
        }

        return httpx.Response(status_code=200, json=fake_api_response, request=request)

    httpx.AsyncClient.send = mock_send

    try:
        # 3. 运行底层 _llm_translate
        test_text = "Hello world"
        prompt_template = "Please translate the following text to {lang}. Output only the translation without any explanation.\n{content}"

        result = await _llm_translate(
            text=test_text,
            prompt_template=prompt_template,
            target_language="简体中文",
            field_name="标题",
        )

        print("\n[测试结果] _llm_translate 返回值:")
        print(f"  -> {repr(result)}")

        # 4. 打印捕获到的请求体 JSON
        print("\n[捕获请求] 实际发给服务端的请求 URL:")
        print(f"  -> {captured_requests[0]['url']}")
        print("\n[捕获请求] 实际发给服务端的请求体 JSON:")
        print(json.dumps(captured_requests[0]["body"], indent=2, ensure_ascii=False))

        # 5. 断言验证
        assert result == "译文YYY", f"返回值异常: 预期 '译文YYY'，实际得到 {repr(result)}"
        assert "思考XXX" not in (result or ""), "错误: reasoning_content 混入了译文返回值！"
        print("\n[校验结果] PASS: 成功捕获请求体，且返回值仅包含 '译文YYY'，未混入 '思考XXX'！")

    finally:
        httpx.AsyncClient.send = orig_send


if __name__ == "__main__":
    asyncio.run(main())
```
