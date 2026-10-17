# MDCx 执行汇报 v1.5：需求 C 合并进 master

日期：2026-10-17。对应任务单 `MDCx任务单_v1.5.md`。**结论：全部完成，CI 通过，已合并。**

## 1. 结果

- squash 提交号：`2b4f01d63da395a446ba42859945b0f8ca670f40`（短号 `2b4f01d`），现为 master 最新提交。
- PR 链接：https://github.com/Marcus515J/mdcx/pull/9
- CI 运行链接：https://github.com/Marcus515J/mdcx/actions/runs/39021444835
  - Code Quality：成功（https://github.com/Marcus515J/mdcx/actions/runs/39021444835/job/117363901680）
  - Tests：成功，2 分 36 秒（https://github.com/Marcus515J/mdcx/actions/runs/39021444835/job/117363901335）

## 2. 做了什么

1. 在功能分支新增提交 `9201701`「删除临时测试构建 workflow」，只删除 `.github/workflows/test-build-windows.yml`；普通推送，没有改写历史、没有强推。
2. 确认 PR 相对 `6da10c5` 的差异恰好是 v1.3 汇报 §4 的 9 个文件，workflow 文件不在其中。
3. CI 通过后把 PR #9 从草稿转为就绪，用 squash 合并，合并说明用中文面向非技术读者，写了改动内容、两个配置项（`cf_bypass_timeout` 默认 90、`site_total_timeout` 默认 120）和验证方式（自动测试 + 用户 10-17 实测 485 秒→96 秒）。
4. 合并后删除远程 `codex/cf-bypass-run-budget`。

## 3. 第 4 节四项证据

1. master 最新提交是本次 squash 合并：`git log origin/master` 首行为 `2b4f01d 让刮削在被 Cloudflare 拦截时少等、不死等 (#9)`，上一个是 `6da10c5`。
2. `git diff 6da10c5 origin/master --stat` 只列出 9 个文件（721 行新增、18 行删除）：
   - `mdcx/config/computed.py`
   - `mdcx/config/models.py`
   - `mdcx/crawlers/base/base.py`
   - `mdcx/web_async.py`
   - `resources/config/default_config.json`
   - `scripts/verify_cf_bypass.py`
   - `tests/cf_fake_server.py`
   - `tests/test_crawl_circuit.py`
   - `tests/test_web_async_cf_bypass.py`
3. 标签与 Release 与开工前一致。
   - 标签：`220261012`、`v1.0.1`、`v1.0.2`、`v1.1.0`。
   - Release：`MDCx v1.1.0`（Latest）、`v1.0.2`、`v1.0.1`。
4. 远程分支列表（`git ls-remote --heads`）只剩 `fix/release-draft-lookup`、`fix/semantic-release-version`、`handoff`、`master`，已没有 `codex/cf-bypass-run-budget`。

## 4. 没做到的部分

- 没有。没有打标签、发 Release、改版本号，也没有改 `mdcx/` 业务代码。
- 说明：合并后我只核对了标签、Release 和分支列表，没有去看合并后 master 上是否触发了新的 CI 或工作流运行。
- 说明：执行期间 handoff 分支有人新增了一个提交（`4634d90`→`4ab6349`），不是我推的，我只在其基础上新增本汇报。
