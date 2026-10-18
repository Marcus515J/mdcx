# MDCx 任务单 v1.9：发布 v1.1.1

日期：2026-10-18。依据：v1.8 / r2 / r3 / r4 / r5 全部审核达标；用户用测试版 `windows-x86_64-test-3984e3a` 复测全部通过（【已实测】用户 Windows，10-18）。
本轮把 v1.7（PR #11，已 squash 合并进 master，`3b9df59`）和 v1.8（PR #12）的改动一起作为 **v1.1.1** 发布。

**本任务单分两个阶段，中间有一个硬停点：**
- **阶段 A（准备）**：只在 PR 分支上提交，不合并、不打标签。做完写汇报、推到 handoff，然后**停下**。
- **阶段 B（发布）**：只有用户在对话里明确说「批准发布 v1.1.1」之后才做。没有这句话，不管汇报写得多完整，都不进入阶段 B。

合并、打标签、发 Release 都无法简单撤回，所以这个停点不能省。

---

## 已知事实（【已查证】Claude 读 `origin/feat/llm-only-and-resources`，提交 `e53f52b`）

- 版本号写在两处：`pyproject.toml` 第 6 行 `version = "1.1.0"`，`mdcx/consts.py` 第 5 行 `LOCAL_VERSION = "v1.1.0"`。
- `.github/workflows/release.yml`：推送标签或手动触发后，构建 Windows 和 macOS 版，并用 `scripts/check_release_version.py` 核对版本号；然后以 `changelog.md` 为正文创建草稿 Release，最后调用 `.github/scripts/finalize-release.cjs` 正式发布。这一步的名字叫「Publish validated release and retire the date-numbered release」。
- `changelog.md` 目前是 v1.1.0 的内容，里面还提到「替代本轮曾发布的日期编号版 220261012」。
- 远端标签目前只有 v1.0.1、v1.0.2、v1.1.0。`220261012` 已经不存在，不用再删。
- 临时 workflow 是 `.github/workflows/test-build-windows.yml`，合并前要删除。
- PR #11 用的是 squash 合并（master 上只有单个父提交）。

## 阶段 A：准备

### A1. 删除临时 workflow
在 PR 分支上单独提交一次，删除 `.github/workflows/test-build-windows.yml`。不要动 `ci.yaml` 和 `release.yml`。

### A2. 版本号改为 1.1.1
1. `pyproject.toml` 改成 `version = "1.1.1"`，`mdcx/consts.py` 改成 `LOCAL_VERSION = "v1.1.1"`。
2. 如果 `uv.lock` 里记录了本项目自身的版本号，同步更新。更新方式用 uv 的标准命令，不要手改。只允许本项目这一条发生变化，依赖版本一个都不能变。
3. 运行 `git grep -n "1\.1\.0"`，逐条说明每一处是「需要改成 1.1.1」还是「与本项目版本号无关」（比如 `pytest-asyncio>=1.1.0`，或者 changelog 里的历史记录），把需要改的改掉。

### A3. 查清 `finalize-release.cjs` 会不会误伤
它的步骤名里有「retire the date-numbered release」，这是为 v1.1.0 替换 `220261012` 写的。查清楚：
1. 它会对哪些 Release 或标签做删除、改名、修改，或者设置 latest？触发条件是什么？
2. 发布 v1.1.1 时，它会不会碰到 v1.1.0、v1.0.x，或者私有资源仓库里的任何东西？
3. v1.1.1 发布后会不会被设为 latest（软件的检查更新读的是 `releases/latest`）？

在汇报里附文件名和行号，用两三句话回答以上三点。**如果它会误删或改动现有 Release，就停下来，不要改脚本，只在汇报里写清楚。** 怎么处理由 Claude 和用户决定。

### A4. 写 `changelog.md`（v1.1.1）
1. 整个文件替换为 v1.1.1 的内容，标题写 `# MDCx v1.1.1`。v1.1.0 的旧内容不保留在这个文件里，Release 页面上还能看到。
2. 开头一句：本版延续 v1.1.0，可以直接沿用原来的配置。
3. 正文只写**用户看得到的变化**，按下面分组，每条一句话，不写实现细节：
   - **翻译**：
     - 只保留大模型翻译（云端或本机），删除谷歌、百度、DeepL、DeepLX。
     - 删除「LLM」勾选框，翻译开关在字段级设置里控制。
     - 界面不再写死 DeepSeek。
     - Key 改为明文显示。
     - 主模型和备用模型的温度分开设置。
     - 标题和简介各自判断：哪个字段在云端走不通，只有那个字段转本机备用。
     - 日志里写明每个字段实际走的是哪个接口、哪个模型。
   - **本机模型**：「重新查找」只按当前目录查找；新目录为空时清空路径并给出提示。
   - **资源与帮助**：
     - 演员资料库、字幕包、水印包、头像包的下载按钮改为指向作者的资源仓库。该仓库需要登录 GitHub 才能下载，未登录时显示 404 属正常。
     - 新增随程序附带的本地 Cookie 教程（含示意图）。
     - 使用说明已重写。
   - **其他**：删除反馈渠道。
4. 写之前，用 `git log --oneline 2b4f01d..HEAD`（或等价命令）对照 v1.7 和 v1.8 的实际提交，确认上面每一条都有对应的提交。没有对应提交的条目删掉，有提交但上面没列出的用户可见变化补上，并在汇报里列出增删了哪些。
5. 不写局域网 IP、本机路径、账号或 Key。

### A5. 验证
1. 全量测试通过，ruff 通过，CI 通过。
2. **本阶段不构建测试版**，也不触发 `release.yml`。
3. 汇报写成 `handoff/reports/MDCx_执行汇报_v1.9.md`，推到 handoff 分支。汇报里要有：
   - 自查表：A1–A4 每一项写「完成 / 未完成」以及证据位置。
   - A3 的结论。
   - `changelog.md` 全文。
   - 下面「阶段 A 机械核对」的原样输出。
4. 然后**停下**，等用户说「批准发布 v1.1.1」。

### 阶段 A 机械核对（命令和原样输出贴进汇报）
- `git ls-tree --name-only HEAD .github/workflows/`：输出里不能有 `test-build-windows.yml`。
- `git grep -n -E "^version|LOCAL_VERSION" pyproject.toml mdcx/consts.py`：两处都是 1.1.1。
- `git grep -n "1\.1\.0"`：贴原样输出，并逐条说明。
- `git diff origin/master..HEAD --stat`：贴原样输出。
- `git diff e53f52bfc5852dc7633dded984e9e07bc72e7b24..HEAD --stat`：只能出现 workflow 删除、`pyproject.toml`、`mdcx/consts.py`、`uv.lock`（如有）和 `changelog.md` 这几项。
- `git grep -n -E "192\.168|[A-Za-z]:\\\\|sk-" changelog.md`：输出为空。

## 阶段 B：发布（必须等用户说「批准发布 v1.1.1」）

1. 把 PR #12 从草稿改为可合并，用 **squash 合并**进 master（和 PR #11 的做法一致）。合并提交的标题写 `release: v1.1.1（LLM-only、资源仓库、Cookie 教程）(#12)`。
2. 用 `git rev-parse` 拿到合并后 master 的完整 40 位提交号，在这个提交上打带注释的标签 `v1.1.1`，然后推送标签，触发 `release.yml`。
3. 等工作流跑完。检查以下几点：
   - Release `v1.1.1` 已正式发布，不是草稿。
   - 附件里有 Windows exe、macOS dmg 和校验文件。
   - 正文就是 `changelog.md`。
   - 它被设为 latest。
   - v1.1.0、v1.0.2、v1.0.1 三个 Release 都还在，内容没有变。
4. 在汇报的「阶段 B」一节追加以下内容，然后推到 handoff 分支：
   - 合并提交号、标签提交号。
   - 工作流运行链接和结论。
   - 每个附件的文件名、大小和 SHA256。
   - 执行 `gh release list` 的原样输出。
5. 任何一步失败就停下，写清楚卡在哪一步、看到了什么。**不要删除标签再重打，不要手动上传附件补救。**
6. 删除 `feat/llm-only-and-resources` 分支前，先问用户。

## 执行方须知（Antigravity / Codex 通用）

- 只改本任务单列出的内容。有任何一步做不到，就停下来，在汇报里写明卡在哪一步、看到了什么；不要换一种做法绕过去。
- 每条机械核对都要贴实际运行的命令和原样输出，不要只写「已通过」。对照表和样例都必须从命令输出里原样复制。
- 写到提交号的地方，一律用 `git rev-parse` 得到的完整 40 位。
- 不要改动私有资源仓库 `Marcus515J/mdcx-resources`。
