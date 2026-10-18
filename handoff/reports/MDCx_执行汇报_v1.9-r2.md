# MDCx 执行汇报 v1.9-r2：阶段 A 返工（uv.lock 回退多余改动、界面版本号与 changelog 措辞调整）

**执行日期**：2026-10-18  
**执行分支**：`feat/llm-only-and-resources`（对应 PR #12，保持 Draft 状态，未合并、未打标签）  
**任务单阶段**：阶段 A 返工（r2）  
**基线提交 SHA**：`e53f52bfc5852dc7633dded984e9e07bc72e7b24`  
**v1.9 原提交 SHA**：`4ac60e0f5b6508d87ebec2c9251bb6a98600a082`  
**v1.9-r2 返工提交 SHA**：`261394af28aba3b384448b618b6d4a1e581e8e82`  
**测试验证状态**：本地全量测试 796 passed, 14 skipped；ruff check 与 format 全部通过；GitHub Actions CI（Code Quality 与 Tests）全部绿标通过  
**汇报归档位置**：`handoff/reports/MDCx_执行汇报_v1.9-r2.md`（推送到 `handoff` 分支）

---

## 一、自查表

| 条目编号 | 任务要求描述 | 状态 | 证据所在位置 |
|---|---|---|---|
| **R1** | `uv.lock` 只能改本项目版本号：恢复 `altgraph` 和 `ptyprocess` 两处平台标记，相对于 `e53f52b` 仅改版本号一行；`uv lock --check` 通过 | **完成** | `git diff e53f52b..HEAD -- uv.lock` 原样输出仅剩版本号变更；`uv lock --check` 校验通过，退出码 0 |
| **R2** | 两处给用户看的「当前版本」过期：`README.md` 改为 v1.1.1 / 1.1.1 / 下载最新版；`MDCx.ui` 删掉「当前版本 `v1.1.0`，」，用 `pyuic6` 重新生成 `MDCx.py` | **完成** | `README.md:28-30`；`mdcx/views/MDCx.ui:22864`；`pyuic6` 重新生成 `mdcx/views/MDCx.py:11191`，两处同步且无多余改动 |
| **R3** | changelog 措辞调整：合并翻译中按字段日志的两条为一条，消除旧版既有行为误写为新功能的表述 | **完成** | `changelog.md:12`；全文见下文二 |
| **A5** | 验证与停下：全量测试通过、ruff 通过、CI 通过；未合并、未打标签、未发 Release；**在此停下** | **完成** | 796 passed, 14 skipped；CI 全绿；等待用户明确指令「批准发布 v1.1.1」 |

---

## 二、返工改动说明

### 1. R1：`uv.lock` 平台标记恢复与一致性校验
从 `e53f52bfc5852dc7633dded984e9e07bc72e7b24` 检出原始锁文件，仅将 `[[package]] name = "mdcx"` 块下的 `version = "1.1.0"` 调整为 `"1.1.1"`。恢复后的锁文件与 `e53f52b` 对比，完全保留了 `altgraph` 与 `ptyprocess` 的 `marker = "sys_platform != 'win32'"` 平台标记，未产生任何依赖项及标记的漂移。运行 `uv lock --check` 一次性校验通过，确认锁文件格式规范、依赖解析完全一致。

### 2. R2：更新 README 与软件内「使用说明」版本表述
- **`README.md`**：第 28 行更新为「当前为 **v1.1.1**」；第 29 行数字版本更新为 `1.1.1`；第 30 行指引文案更新为「下载最新版并沿用原配置即可」。
- **`mdcx/views/MDCx.ui`**：第 22864 行删去「当前版本 `v1.1.0`，」半句，保留「提供 Windows（`x86_64`）与 macOS（`arm64`）桌面版。」，避免后续版本维护时的重复修改。
- **`mdcx/views/MDCx.py`**：依据项目规范，使用虚拟环境中的 `pyuic6 mdcx/views/MDCx.ui -o mdcx/views/MDCx.py` 命令重新编译生成。生成的 Python 代码 diff 仅且仅有第 11191 行对应的富文本字符串变动，无任何多余差异。

### 3. R3：`changelog.md` 调整后全文
```markdown
# MDCx v1.1.1

本版延续 v1.1.0，可以直接沿用原来的配置。

### 翻译

- 只保留大模型翻译（云端或本机），删除谷歌、百度、DeepL、DeepLX。
- 删除「LLM」勾选框，翻译开关在字段级设置里控制。
- 界面不再写死 DeepSeek。
- Key 改为明文显示。
- 主模型和备用模型的温度分开设置。
- 日志按字段写明实际用的接口和模型；某个字段在云端走不通转备用时，会单独标出是哪个字段，另一个字段不受影响。

### 本机模型

- 「重新查找」只按当前目录查找；新目录为空时清空路径并给出提示。

### 资源与帮助

- 演员资料库、字幕包、水印包、头像包的下载按钮改为指向作者的资源仓库。该仓库需要登录 GitHub 才能下载，未登录时显示 404 属正常。
- 新增随程序附带的本地 Cookie 教程（含示意图）。
- 使用说明已重写。

### 其他

- 删除反馈渠道。
```

---

## 三、机械核对（原样输出）

### 核对 1：`git diff e53f52bfc5852dc7633dded984e9e07bc72e7b24..HEAD -- uv.lock`
> 要求：只能有本项目版本号这一行的改动。

```
diff --git a/uv.lock b/uv.lock
index be56d53..e2903c1 100644
--- a/uv.lock
+++ b/uv.lock
@@ -764,7 +764,7 @@ wheels = [
 
 [[package]]
 name = "mdcx"
-version = "1.1.0"
+version = "1.1.1"
 source = { editable = "." }
 dependencies = [
     { name = "aiofiles" },
```
*(已确认：精确且仅包含 mdcx 版本号单行修改)*

---

### 核对 2：`uv lock --check` 及其原样输出，附 `uv --version`
> 要求：贴原样输出。

```
uv 0.11.29 (901092ee1 2026-07-15 aarch64-apple-darwin)
Resolved 106 packages in 26ms
```
*(已确认：校验通过，未报错，退出码 0)*

---

### 核对 3：`git grep -n "v1\.1\.0" README.md mdcx/views/MDCx.ui mdcx/views/MDCx.py`
> 要求：贴原样输出。不能再有「当前为 v1.1.0」「当前版本 v1.1.0」。

```
```
*(已确认：输出为空，原有的「当前为 v1.1.0」和「当前版本 v1.1.0」均已彻底消除)*

---

### 核对 4：`git grep -n "当前版本" mdcx/views/MDCx.ui mdcx/views/MDCx.py`
> 要求：贴原样输出。

```
```
*(已确认：输出为空，使用说明中已彻底移除硬编码版本文案)*

---

### 核对 5：`git diff 4ac60e0..HEAD --stat`
> 要求：只出现 `uv.lock`、`README.md`、`mdcx/views/MDCx.ui`、`mdcx/views/MDCx.py`、`changelog.md`。

```
 README.md          | 6 +++---
 changelog.md       | 3 +--
 mdcx/views/MDCx.py | 2 +-
 mdcx/views/MDCx.ui | 2 +-
 uv.lock            | 4 ++--
 5 files changed, 8 insertions(+), 9 deletions(-)
```
*(已确认：精确覆盖要求的 5 个文件，无任何越界变动)*

---

### 核对 6：全量测试结果、ruff、CI 结论

1. **本地全量测试**：
   - 运行命令：`pytest -q`
   - 结果：**796 passed, 14 skipped, 2 warnings in 103.10s**（全量通过）
2. **代码规范与格式检查**：
   - `ruff check .`：**All checks passed!**（0 错误，0 警告）
   - `ruff format --check .`：**230 files already formatted**（格式规范一致）
   - `scripts/check_release_version.py v1.1.1`：**版本一致性检查通过：v1.1.1**
3. **远端 GitHub Actions CI**：
   - PR 分支最新提交：`261394af28aba3b384448b618b6d4a1e581e8e82`
   - 工作流：`CI/CD Pipeline`（PR #12 Checks）
   - **Code Quality**：✓ 6s 通过
   - **Tests (push)**：✓ 2m35s 通过
   - 状态：**0 cancelled, 0 failing, 2 successful, 0 skipped, and 0 pending checks**

---

## 四、停下与等待指令

阶段 A 的全部返工要求（R1、R2、R3）已完全执行达标，机械核对与远端 CI 均已 100% 通过：
- `uv.lock` 平台标记已恢复，版本号独立升级；
- `README.md` 与界面使用说明中的过期版本号已更新/解耦；
- `changelog.md` 已校准措辞；
- PR #12 保持 Draft 状态，master 分支未变动，未打标签，未进入阶段 B。

**当前已按任务单要求在此停下。**  
**等待用户在对话中明确回复「批准发布 v1.1.1」后，方可进入阶段 B（合并 PR #12、打标签、推送并发布 Release）。**
