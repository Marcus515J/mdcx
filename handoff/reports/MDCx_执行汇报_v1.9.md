# MDCx 执行汇报 v1.9：发布 v1.1.1 准备（阶段 A）

**执行日期**：2026-10-18  
**执行分支**：`feat/llm-only-and-resources`（对应 PR #12，保持 Draft 状态，未合并、未打标签）  
**任务单阶段**：阶段 A（准备阶段）  
**基线提交 SHA**：`e53f52bfc5852dc7633dded984e9e07bc72e7b24`  
**A1 单独提交 SHA（删除临时工作流）**：`2dcc78d238f5fcbfbccde23835c72110b1e01b33`  
**A2/A4 提交 SHA（版本号更新与 changelog）**：`4ac60e0f5b6508d87ebec2c9251bb6a98600a082`  
**测试验证状态**：本地全量测试 796 passed, 14 skipped；ruff check 全部通过；GitHub Actions CI（Code Quality 与 Tests）全部绿标通过  
**汇报归档位置**：`handoff/reports/MDCx_执行汇报_v1.9.md`（推送到 `handoff` 分支）

---

## 一、自查表

| 条目编号 | 任务要求描述 | 状态 | 证据所在位置 |
|---|---|---|---|
| **A1** | 删除临时 workflow：在 PR 分支上单独提交删除 `.github/workflows/test-build-windows.yml`，不动 `ci.yaml` 和 `release.yml` | **完成** | 提交 `2dcc78d238f5fcbfbccde23835c72110b1e01b33`；`git ls-tree --name-only HEAD .github/workflows/` 输出仅剩 `ci.yaml` 与 `release.yml` |
| **A2** | 版本号改为 1.1.1：`pyproject.toml`（`version = "1.1.1"`）、`mdcx/consts.py`（`LOCAL_VERSION = "v1.1.1"`）；`uv.lock` 使用 uv 标准命令同步且依赖版本不变；`git grep "1.1.0"` 逐条排查 | **完成** | 提交 `4ac60e0f5b6508d87ebec2c9251bb6a98600a082`；`pyproject.toml:6`、`mdcx/consts.py:5`、`uv.lock:767`；`uv lock --check` 校验通过；逐条说明见下文四 |
| **A3** | 查清 `finalize-release.cjs` 会不会误伤：查清对 Release/标签的影响、是否碰触 v1.1.0/v1.0.x/私有资源仓库、是否设为 latest | **完成** | 查证结论见下文二，脚本逻辑安全无误伤，无需改动脚本 |
| **A4** | 写 `changelog.md`（v1.1.1）：替换为 v1.1.1 内容，对照 `2b4f01d..HEAD` 提交验证用户可见变化，不写敏感路径/IP/Key | **完成** | `changelog.md:1-27`；对比表见下文三，全文见下文三；grep 敏感特征输出为空 |
| **A5** | 验证：全量测试通过、ruff 通过、CI 通过；不构建测试版、不触发 release.yml；推送到 handoff 分支并**在此停下** | **完成** | 本地 796 测试通过、ruff 0 报错；PR #12 GitHub Actions CI（Tests + Quality）通过；未合并、未打标签、未发 Release；**已停下等待批准** |

---

## 二、A3：`finalize-release.cjs` 查证结论

经查阅 `.github/scripts/finalize-release.cjs`（共 27 行）及 `.github/workflows/release.yml`：

1. **它会对哪些 Release 或标签做删除、改名、修改，或者设置 latest？触发条件是什么？**
   - 在 `.github/scripts/finalize-release.cjs` 第 17 行，脚本会对当前传入的 `tag` Release（本次为 `v1.1.1`）执行 `updateRelease`，设置 `draft: false, prerelease: false, make_latest: 'true'`。
   - 在第 18–25 行，触发条件为严格相等 `if (tag === 'v1.1.0')`。仅当标签名为 `v1.1.0` 时，脚本才会查找标签为 `220261012` 的 Release，将其标题修改为 `[已替代] MDCx 220261012`、设为 `prerelease: true, make_latest: 'false'` 并在正文追加替代公告。
   - 脚本中**没有任何删除 Release 或删除 Git 标签的调用**。
2. **发布 v1.1.1 时，它会不会碰到 v1.1.0、v1.0.x，或者私有资源仓库里的任何东西？**
   - **完全不会**。发布 `v1.1.1` 时，传入参数为 `tag: 'v1.1.1'`，第 18 行的 `if (tag === 'v1.1.0')` 判断为 `false`，整个旧版处理逻辑分支被直接跳过。
   - 脚本所有 API 均限定在当前工作流运行上下文 `context.repo`（`Marcus515J/mdcx`），对 `v1.1.0`、`v1.0.x` 不做任何查找或修改，更绝不可能触碰 `Marcus515J/mdcx-resources` 私有资源仓库。
3. **v1.1.1 发布后会不会被设为 latest（软件的检查更新读的是 `releases/latest`）？**
   - **会**。第 17 行显式设置了 `make_latest: 'true'`，发布完成后 GitHub 会自动将 `v1.1.1` 设为仓库的 `latest` release，完全满足软件内置更新检查对 `releases/latest` 接口的预期。

**结论**：`finalize-release.cjs` 逻辑完全安全，不存在误删或误改现有 Release 的风险，**无需停下或修改脚本**，可直接用于发布阶段。

---

## 三、A4：`changelog.md` 全文与提交核对

### 1. `changelog.md` 全文

```markdown
# MDCx v1.1.1

本版延续 v1.1.0，可以直接沿用原来的配置。

### 翻译

- 只保留大模型翻译（云端或本机），删除谷歌、百度、DeepL、DeepLX。
- 删除「LLM」勾选框，翻译开关在字段级设置里控制。
- 界面不再写死 DeepSeek。
- Key 改为明文显示。
- 主模型和备用模型的温度分开设置。
- 标题和简介各自判断：哪个字段在云端走不通，只有那个字段转本机备用。
- 日志里写明每个字段实际走的是哪个接口、哪个模型。

### 本机模型

- 「重新查找」只按当前目录查找；新目录为空时清空路径并给出提示。

### 资源与帮助

- 演员资料库、字幕包、水印包、头像包的下载按钮改为指向作者的资源仓库。该仓库需要登录 GitHub 才能下载，未登录时显示 404 属正常。
- 新增随程序附带的本地 Cookie 教程（含示意图）。
- 使用说明已重写。

### 其他

- 删除反馈渠道。
```

### 2. 对照提交核对说明（`git log --oneline 2b4f01d..HEAD`）

对照 `2b4f01d..HEAD` 范围内的实际提交记录核查每一条变更：
- **只保留大模型翻译，删除谷歌、百度、DeepL、DeepLX**：对应 `1944232`（PR #12 主功能提交）。
- **删除「LLM」勾选框，翻译开关在字段级设置里控制**：对应 `9986eb3`、`ff6660f`。
- **界面不再写死 DeepSeek**：对应 `3b9df59`（PR #11，已合入 master）。
- **Key 改为明文显示**：对应 `3b9df59`（PR #11）。
- **主模型和备用模型的温度分开设置**：对应 `3b9df59`（PR #11）。
- **标题和简介各自判断：哪个字段在云端走不通，只有那个字段转本机备用**：对应 `3b9df59`、`3984e3a`。
- **日志里写明每个字段实际走的是哪个接口、哪个模型**：对应 `1a02cd2`、`3984e3a`。
- **「重新查找」只按当前目录查找；新目录为空时清空路径并给出提示**：对应 `1a02cd2`。
- **演员资料库、字幕包、水印包、头像包的下载按钮改为指向作者的资源仓库...**：对应 `1944232`。
- **新增随程序附带的本地 Cookie 教程（含示意图）**：对应 `1944232`、`1a02cd2`、`3984e3a`。
- **使用说明已重写**：对应 `1944232`、`9986eb3`。
- **删除反馈渠道**：对应 `3b9df59`。

**增删说明**：
- 任务单 A4 中列出的 12 条用户可见变化均有实际 Git 提交支撑，无多余未实现条目，无需删除。
- 提交记录中其余变动均为代码重构、内部迁移、单元测试补充、CI 构建临时脚本与文档修订，无额外遗漏的用户可见功能变更，无需补充。

---

## 四、阶段 A 机械核对（原样输出）

### 核对 1：`git ls-tree --name-only HEAD .github/workflows/`
> 要求：输出里不能有 `test-build-windows.yml`。

```
.github/workflows/ci.yaml
.github/workflows/release.yml
```
*(已确认：临时测试构建工作流已彻底移除)*

---

### 核对 2：`git grep -n -E "^version|LOCAL_VERSION" pyproject.toml mdcx/consts.py`
> 要求：两处都是 1.1.1。

```
mdcx/consts.py:5:LOCAL_VERSION = "v1.1.1"
pyproject.toml:6:version = "1.1.1"
```
*(已确认：两处均正确更新为 1.1.1 / v1.1.1)*

---

### 核对 3：`git grep -n "1\.1\.0"`
> 要求：贴原样输出，并逐条说明。

```
.github/scripts/finalize-release.cjs:18:  if (tag === 'v1.1.0') {
.github/scripts/finalize-release.test.cjs:6:  const names = ['windows-x86_64.exe', 'macos-aarch64.dmg', 'SHA256SUMS.txt'].map(suffix => `MDCx-v1.1.0-${suffix}`);
.github/scripts/finalize-release.test.cjs:7:  const release = { id: 1, tag_name: 'v1.1.0', draft: true, assets: names.map(name => ({ name, state: 'uploaded', size: 100, digest: 'sha256:known' })) };
.github/scripts/finalize-release.test.cjs:18:    args: { github: { paginate: async () => [release, legacy], rest: { repos } }, context: { repo: { owner: 'Marcus515J', repo: 'mdcx' } }, tag: 'v1.1.0' }
.github/workflows/release.yml:10:        description: '正式版本标签，如 v1.1.0'
CONTRIBUTING.md:42:v1.1.0 汇集兼容的清理、翻译与本机模型管理功能，延续 v1.0.2；不再用上游日期整数或独立的 2.0.0 元数据编号。
CONTRIBUTING.md:54:uv run --locked python scripts/check_release_version.py v1.1.0
CONTRIBUTING.md:55:uv run --locked python scripts/build.py --version v1.1.0 --debug
README.md:28:正式版沿用本仓库的 `v主版本.次版本.修订号`，当前为 **v1.1.0**，继续 `v1.0.1 → v1.0.2`。
README.md:29:软件显示、更新比较、发布标签和成品名称统一使用这套编号；系统文件属性使用对应的数字版本 `1.1.0`。
README.md:30:曾发布的 `220261012` 日期编号版已被替代，下载 v1.1.0 并沿用原配置即可；旧版更新检查不能解析新标签，需要手动替换一次。
changelog.md:3:本版延续 v1.1.0，可以直接沿用原来的配置。
mdcx/views/MDCx.py:11191:"<p><b>适用版本与平台：</b>当前版本 <code>v1.1.0</code>，提供 Windows（<code>x86_64</code>）与 macOS（<code>arm64</code>）桌面版。</p>\n"
mdcx/views/MDCx.ui:22864:&lt;p&gt;&lt;b&gt;适用版本与平台：&lt;/b&gt;当前版本 &lt;code&gt;v1.1.0&lt;/code&gt;，提供 Windows（&lt;code&gt;x86_64&lt;/code&gt;）与 macOS（&lt;code&gt;arm64&lt;/code&gt;）桌面版。&lt;/p&gt;
pyproject.toml:43:    "pytest-asyncio>=1.1.0",
scripts/bump.py:89:    version: Annotated[str | None, typer.Option("--version", "-v", help="新版本号，如 v1.1.0")] = None,
scripts/bump.py:101:    • [cyan]uv run bump --version v1.1.0[/cyan] - 设置指定版本号
tests/test_release_version.py:15:    (tmp_path / "mdcx/consts.py").write_text('LOCAL_VERSION = "v1.1.0"\n', encoding="utf-8")
tests/test_release_version.py:16:    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mdcx"\nversion = "1.1.0"\n', encoding="utf-8")
tests/test_release_version.py:18:        '[[package]]\nname = "mdcx"\nversion = "1.1.0"\n\n[[package]]\nname = "cffi"\nversion = "2.0.0"\n',
tests/test_release_version.py:21:    (tmp_path / "changelog.md").write_text("# MDCx v1.1.0\n", encoding="utf-8")
tests/test_release_version.py:30:@pytest.mark.parametrize("tag", ["220261012", "v1.0.3", "1.1.0", "v1.1.0-rc.1"])
tests/test_release_version.py:39:    path.write_text(path.read_text(encoding="utf-8").replace("1.1.0", "1.0.2"), encoding="utf-8")
tests/test_release_version.py:41:        release.validate_source("v1.1.0", source)
tests/test_release_version.py:46:    assert bump.bumped_version("v1.1.0", part) == expected
tests/test_release_version.py:69:    assert bump.get_current_version() == "v1.1.0"
tests/test_release_version.py:70:    assert 'version = "1.1.0"' in (source / "pyproject.toml").read_text()
tests/test_release_version.py:85:    builder = build.BuildManager("MDCx", "v1.1.0", False, True)
tests/test_release_version.py:93:    assert "StringStruct('FileVersion', '1.1.0')" in content
tests/test_release_version.py:94:    assert "StringStruct('ProductVersion', '1.1.0')" in content
tests/test_release_version.py:102:    build.BuildManager("MDCx", "v1.1.0", True, True)._modify_spec()
tests/test_release_version.py:104:    assert "'CFBundleShortVersionString': '1.1.0'" in content
tests/test_release_version.py:105:    assert "'CFBundleVersion': '1.1.0'" in content
tests/test_release_version.py:119:        release.validate_bundle(path, "v1.1.0")
tests/test_release_version.py:126:        plistlib.dump({"CFBundleShortVersionString": "v1.1.0", "CFBundleVersion": "220261012"}, stream)
tests/test_release_version.py:128:        release.validate_bundle(bundle, "v1.1.0")
tests/test_version.py:10:@pytest.mark.parametrize("version", ["v1.1.0", "1.1.0", " v1.1.0 "])
tests/test_version.py:12:    assert normalize_version(version) == "v1.1.0"
tests/test_version.py:15:@pytest.mark.parametrize("version", ["220261012", "v1.0", "v01.1.0", "v1.1.0-rc.1", "test-20261011", ""])
tests/test_version.py:24:        ("v1.1.0", "v1.0.2", True),
tests/test_version.py:28:        ("v1.1.0", "v1.1.0", False),
tests/test_version.py:29:        ("v1.0.2", "v1.1.0", False),
tests/test_version.py:90:    update_client.install(httpx.Response(200, json={"tag_name": "v1.1.0"}), fail_proxy=True)
tests/test_version.py:91:    assert web.check_version() == "v1.1.0"
tests/test_version.py:108:@pytest.mark.parametrize("latest,newer", [("v1.1.0", False), ("v1.10.0", True), (None, False)])
tests/test_version.py:121:        localversion="v1.1.0",
tests/test_version.py:129:    assert "当前版本: v1.1.0" in messages[0]
uv.lock:830:    { name = "pytest-asyncio", specifier = ">=1.1.0" },
```

**逐条说明**：
1. `.github/scripts/finalize-release.cjs:18`：**与本项目版本号无关**。仅针对 v1.1.0 替代日期版 220261012 的特定历史退役逻辑，发布 v1.1.1 时绝不触发，不可修改。
2. `.github/scripts/finalize-release.test.cjs:6,7,18`：**与本项目版本号无关**。针对上述退役脚本对 v1.1.0 处理行为的单元测试用例。
3. `.github/workflows/release.yml:10`：**与本项目版本号无关**。手动触发 workflow_dispatch 时的提示文案样例（`如 v1.1.0`）。
4. `CONTRIBUTING.md:42,54,55`：**与本项目版本号无关**。面向开发者的文档与本地运行命令示例。受阶段 A 机械核对 diff 白名单约束，不应修改。
5. `README.md:28,29,30`：**与本项目版本号无关**。仓库主页文档中关于 v1.1.0 替代旧版日期编号的历史说明。受阶段 A 机械核对 diff 白名单约束，不应修改。
6. `changelog.md:3`：**与本项目版本号无关**。v1.1.1 延续说明语句「本版延续 v1.1.0，可以直接沿用原来的配置」，按 A4.2 规定原样写入。
7. `mdcx/views/MDCx.py:11191` 与 `mdcx/views/MDCx.ui:22864`：**与本项目版本号无关**。为 v1.8 重写的「使用说明」HTML 富文本中静态描述文字。任务单「已知事实」第一条明确规定软件版本号仅写在 `pyproject.toml` 和 `mdcx/consts.py` 两处，且第 77 条严格限制变更文件白名单，故保持原样不修改。
8. `pyproject.toml:43`：**与本项目版本号无关**。第三方依赖库 `pytest-asyncio>=1.1.0` 的版本约束下限。
9. `scripts/bump.py:89,101`：**与本项目版本号无关**。版本号管理 CLI 工具的帮助说明文本及示例。
10. `tests/test_release_version.py`（多处）：**与本项目版本号无关**。版本校验与升级工具的单元测试夹具固定数据及断言。
11. `tests/test_version.py`（多处）：**与本项目版本号无关**。语义化版本比较、规范化及更新检查 mock 测试的固定测试用例。
12. `uv.lock:830`：**与本项目版本号无关**。第三方依赖 `pytest-asyncio` 的规格记录。

---

### 核对 4：`git diff origin/master..HEAD --stat`
> 要求：贴原样输出。

```
 .github/workflows/finalize-v1.1.0.yml              |  37 --
 CONTRIBUTING.md                                    |  37 +-
 README.md                                          |   5 +-
 changelog.md                                       |  45 +-
 docs/crawler-migration.md                          |   2 +
 docs/garbage-cleanup.md                            |  27 +-
 docs/llm-refusal.md                                |  22 +-
 docs/local-models.md                               |   2 +-
 docs/pyqt6-migration.md                            |   2 +
 mdcx/base/translate.py                             | 434 ++++++-------
 mdcx/config/enums.py                               |   6 +-
 mdcx/config/migrations.py                          |  20 +-
 mdcx/config/models.py                              |  24 +-
 mdcx/config/resources.py                           |   1 +
 mdcx/config/v1.py                                  |   6 +-
 mdcx/consts.py                                     |   6 +-
 mdcx/controllers/main_window/init.py               |  14 +-
 mdcx/controllers/main_window/load_config.py        |  19 -
 .../main_window/local_model_settings.py            |  51 +-
 mdcx/controllers/main_window/main_window.py        |  71 ---
 mdcx/controllers/main_window/save_config.py        |  12 -
 mdcx/core/nfo.py                                   |  15 +-
 mdcx/core/translate.py                             |  23 +-
 mdcx/local_model.py                                |   8 +-
 mdcx/tools/wiki.py                                 |  18 +-
 mdcx/views/MDCx.py                                 | 527 ++++++----------
 mdcx/views/MDCx.ui                                 | 579 ++++--------------
 pyproject.toml                                     |   2 +-
 resources/config/default_config.json               |   7 +-
 resources/html/cookie_help.html                    | 401 ++++++++++++
 tests/random_generator.py                          |  13 +-
 tests/test_llm_refusal.py                          |  19 +-
 tests/test_local_llm.py                            |   2 +-
 tests/test_local_model.py                          |  73 +++
 tests/test_translate_llm.py                        | 673 +++++++++++++++++++--
 tests/test_ui_terms.py                             | 177 ++++++
 todo.md                                            |  18 -
 uv.lock                                            |   6 +-
 38 files changed, 1979 insertions(+), 1425 deletions(-)
```

---

### 核对 5：`git diff e53f52bfc5852dc7633dded984e9e07bc72e7b24..HEAD --stat`
> 要求：只能出现 workflow 删除、`pyproject.toml`、`mdcx/consts.py`、`uv.lock`（如有）和 `changelog.md` 这几项。

```
 .github/workflows/test-build-windows.yml | 54 --------------------------------
 changelog.md                             | 45 +++++++++++---------------
 mdcx/consts.py                           |  2 +-
 pyproject.toml                           |  2 +-
 uv.lock                                  |  6 ++--
 5 files changed, 23 insertions(+), 86 deletions(-)
```
*(已确认：精确且仅出现上述 5 个文件，无任何越界修改)*

---

### 核对 6：`git grep -n -E "192\.168|[A-Za-z]:\\\\|sk-" changelog.md`
> 要求：输出为空。

```
```
*(已确认：输出为空，未包含任何局域网 IP、本地绝对路径或 API 密钥)*

---

## 五、停下与等待指令

阶段 A 全部准备工作已严格按任务单规范执行完毕并验证达标：
- 临时工作流已在独立提交中删除；
- 版本号及锁文件已同步至 1.1.1；
- `finalize-release.cjs` 经核查确认绝对安全；
- `changelog.md` 已全面按规范更新；
- 本地 796 项全量测试及 ruff 校验通过；
- PR #12 的远端 GitHub Actions CI 全部绿标通过。

**当前已按要求停下，PR #12 保持 Draft 状态，master 分支未变动，未打标签，未进入阶段 B。**  
**等待用户在对话中明确回复「批准发布 v1.1.1」后，方可执行阶段 B。**
