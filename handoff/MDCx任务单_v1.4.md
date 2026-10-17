# MDCx 任务单 v1.4：给需求 C 出 Windows 测试版

日期：2026-10-17。上一轮：任务单 v1.3 → 汇报 `handoff/reports/MDCx_Codex汇报_v1.3.md`。
执行方：Antigravity（Codex 暂时没有额度）。规则同 `handoff/README.md`。

## 1. Claude 对 v1.3 的审核结论

- 任务单 §5 九条全部达标。Claude 抽查过三项【已查证】：CI 运行 39012765687 的结论是 success，对应提交 `989b825`；功能分支比 master 多 2 个提交、0 落后，改动只涉及汇报里列的 9 个文件；PR #9 仍是草稿，没有合并。
- 已知风险，**本轮不改代码**：检测和刮削共用唯一一个 `/html` 名额。如果刮削在检测还没跑完时开始，排在后面的 CF 站可能耗尽 120 秒，被断路器停掉一整轮。先用实测看真实影响，再决定改不改。

## 2. 本轮只做一件事：构建 Windows 测试版 EXE

基于功能分支 `codex/cf-bypass-run-budget` 的提交 `989b825`。

### 硬约束

- **不要推任何 `v*.*.*` 标签，也不要手动触发 `release.yml`。** 推 `v*.*.*` 标签会触发 `release.yml`，发出正式版。
- 不创建 GitHub Release，也不创建预发布。产物以 **Actions artifact** 交付。
- 不改 `mdcx/` 下的任何业务代码；不合并进 master；不改 PR #9 的草稿状态。
- 如果要新增一个临时构建 workflow，单独做一次提交，提交信息写明「临时：测试构建，合并前删除」。
- 版本号要能看出是测试版。参照 `scripts/build.py` 和 `scripts/check_release_version.py` 现有的做法，不为此改校验脚本；如果做不到，停下来在汇报里说明原因。

### 做法提示（可自行选择，但要满足上面的硬约束）

`release.yml` 已有 Windows 构建步骤（`uv sync --locked --dev` → `python scripts/build.py --version … --debug`），可以照它写一个只在推送到该功能分支时触发、只上传 artifact 的 workflow。

## 3. 验证（必须实际做）

1. Actions 运行成功，并给出运行链接。
2. artifact 里有 EXE，写明文件名、字节数、SHA256。
3. 确认没有新增标签，也没有新增 Release（附上标签列表和 Release 列表的前几项作为证据）。
4. 确认 master 仍是 `6da10c5`。

## 4. 交付

汇报写成 `handoff/reports/MDCx_执行汇报_v1.4.md`，推到 handoff 分支，只动 `handoff/reports/`。内容包括：

- Actions 运行链接
- artifact 下载链接
- EXE 的文件名、大小、SHA256
- 新增的提交号
- 第 3 节的四项证据
- 没做到的部分

## 5. 启动提示词（用户粘贴给 Antigravity）

见交接文档 v1.4 §8 下方，或 Claude 在对话里给出的版本。
