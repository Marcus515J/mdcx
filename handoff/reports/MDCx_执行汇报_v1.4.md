# MDCx 执行汇报 v1.4：Windows 测试版构建

执行方：Antigravity。日期：2026-10-17。对应任务单：`handoff/MDCx任务单_v1.4.md`。

## 结论

Windows 测试版 EXE 已由 GitHub Actions 构建成功并作为 artifact 上传。**但 EXE 的实际字节数和 SHA256 没有验证到**（见「没做到的部分」），任务单 §3 第 2 项只完成一半。

## 交付信息

- Actions 运行（成功）：https://github.com/Marcus515J/mdcx/actions/runs/39016236575
- artifact：`windows-x86_64-test-989b825`（id 12095111709），下载页：https://github.com/Marcus515J/mdcx/actions/runs/39016236575/artifacts/12095111709
  - zip 大小 152,870,080 字节（API 返回的 `size_in_bytes`）。
  - 保留 14 天，约 2026-10-31 过期。
- 构建源码：提交 `989b825`（workflow 里用 `ref` 固定检出该提交）。

## EXE 信息

- 预期文件名：`MDCx-v1.1.0-TEST-989b825-windows-x86_64.exe`（由 workflow 的命名步骤生成，**未亲眼在 artifact 内确认**）。
- EXE 字节数：**未验证**。
- EXE SHA256：**未验证**。zip 的哈希不等于 EXE 的哈希，不能代替。

## 新增提交

都在功能分支 `codex/cf-bypass-run-budget` 上，只改 `.github/workflows/test-build-windows.yml`，没有碰 `mdcx/`：

1. `20649ec` 临时：测试构建，合并前删除。对应运行 39016141179，**失败**：版本读取步骤的 shell 引号写错，27 秒退出。
2. `6569396` 临时：测试构建，合并前删除（修复版本读取步骤）。去掉该步骤，版本号写死为 `v1.1.0`（`scripts/build.py` 本来就会拒绝与源码版本不一致的值）。对应运行 39016236575，**成功**（构建 2 分 6 秒）。

任务单要求 workflow「单独一次提交」，实际是两个提交，原因是第一个有 bug；为避免强推改写功能分支，选择追加修复提交。合并前这两个提交涉及的文件都要删除。

## 任务单 §3 证据（取证时间约 2026-10-17 16:13 +08:00）

1. Actions 运行成功：见上，run 39016236575 结论 `success`。
2. artifact：存在、未过期、zip 152,870,080 字节；EXE 字节数和 SHA256 未验证。
3. 没有新增标签和 Release：
   - `git ls-remote --tags --sort=-v:refname` 前几项：`v1.1.0`、`v1.0.2`、`v1.0.1`、`220261012`，共 4 个标签，与开工时一致（`v1.1.0^{}` 是 v1.1.0 的解引用行）。没有新标签。
   - `gh release list` 前几项：`MDCx v1.1.0`（Latest，4 天前）、`v1.0.2`、`v1.0.1`。没有新 Release 或预发布。
4. master 仍是 `6da10c5464efcd39252ce12ce88ec9957d89d4e6`（`git ls-remote` 结果）。

另：PR #9 仍是 OPEN 草稿，head 因上述两个提交变为 `6569396`。`release.yml` 只由 `v*.*.*` 标签或手动触发，本轮都没有使用。

## 没做到的部分

1. **EXE 实际字节数、SHA256、artifact 内文件名未验证。** 原因：下载 artifact 时，`gh` 被重定向到 `productionresultssa1.blob.core.windows.net`；本机代理规则 `DomainSuffix(windows.net)` 走 DIRECT，直连只有约 33–55 KB/s，152 MB 需要约 1 小时。按用户指示中止下载，没有计算哈希。后续可在 `windows.net` 走代理或网络更快时下载上述 artifact，再补一份 `_v1.4-r2` 汇报。
2. **版本号无法在 EXE 内体现测试版。** `mdcx/version.py` 只接受 `vX.Y.Z`，`build.py` 要求构建版本等于 `mdcx/consts.py` 的 `LOCAL_VERSION`（`v1.1.0`）。按约束不改校验脚本和业务代码，所以 EXE 内部版本仍显示 `v1.1.0`，只在文件名里加了 `TEST-989b825`。与正式版 v1.1.0 容易混淆，测试时请认准文件名。
3. 没有运行 `check_release_version.py --bundle` 和 pytest：该校验要求标签、changelog 标题与源码版本全部一致，不适用于测试构建。
