# 开发

## 环境准备

### 依赖

* [uv](https://docs.astral.sh/uv/getting-started/installation/)

### clone

```bash
git clone https://github.com/Marcus515J/mdcx.git
cd mdcx
uv sync --locked --python 3.13 --dev
uv run pre-commit install
uv pip install -e .
```

## Run

启动 qt 版本

```bash
uv run main.py
```

## Test

Python 侧使用 pytest。先安装 FFmpeg（需包含 ffmpeg 和 ffprobe，并加入 PATH），视频测试会生成临时视频验证元数据读取。

```bash
QT_QPA_PLATFORM=offscreen uv run --locked pytest -q
```

CI 在主分支推送及 PR 新建、更新、重新打开和转为待评审时，运行代码格式、静态检查及完整 pytest 测试。测试使用 Python 3.13 和锁定依赖，Qt 使用无显示模式。

未提供本地 HTML 样本的解析器测试会按原有逻辑跳过；CI 不保证外部网站始终可用，也不代替 Windows/macOS 桌面交互和打包后应用的人工验证。

## 版本与正式发布

本 Fork 的正式版本为 `vMAJOR.MINOR.PATCH`：不兼容变更升第一位，兼容新增功能升第二位，修复升第三位。
v1.1.0 汇集兼容的清理、翻译与本机模型管理功能，延续 v1.0.2；不再用上游日期整数或独立的 2.0.0 元数据编号。

```bash
uv run bump --part patch --dry-run
uv run bump --part minor
uv run bump --version v1.2.0
```

递增工具同步 `mdcx/consts.py`、`pyproject.toml` 和 `uv.lock` 的项目版本；不修改依赖版本或用户配置。
再更新 `changelog.md` 的首行和内容，提交、完成 CI 后，在该提交上创建和推送一致的正式版本标签。

```bash
uv run --locked python scripts/check_release_version.py v1.1.0
uv run --locked python scripts/build.py --version v1.1.0 --debug
```

`--version` 必须与源码一致，标签也必须有 `v` 前缀。Windows FileVersion/ProductVersion 为对应三段数字，
固定 PE 版本为四段数字；macOS 两个 CFBundle 版本为三段数字，不带 `v`，遵循系统格式。
发布流程构建 Windows x86_64 和 macOS arm64，核验成品内嵌显示版本、架构和系统版本属性，
两份成品都完成后才公开 Release。成品文件名为 `MDCx-vX.Y.Z-平台.扩展名`，同时提供带版本号的 SHA256 清单。
版本不一致会阻止发布；日期标签不再触发正式构建。原 INI 中历史 `version` 与 JSON 的 `config_version` 是兼容/结构字段，不参与软件版本比较。

## 如何添加新配置项

1. 在 `mdcx/config/models.py` `Config` 类中添加配置字段及默认值
2. 通过 `from mdcx.models.config.manager import manager` 导入配置, 并通过 `manager.config.<key>` 访问配置项
3. 按下一节所述在设置界面中添加对应的控件, 修改 `mdcx/controllers/main_window/` 目录下 `load_config.py` 及 `save_config.py`, 以实现 UI 绑定

## 如何修改图形界面

* `mdcx/views/MDCx.ui` 定义了主窗口, `mdcx/views/posterCutTool.ui` 是图片裁剪窗口, 可使用 Qt Designer 或 Qt Creator 编辑
* 修改后运行 `./scripts/pyuic.sh` 生成对应的 Python 代码
* 如需设置控件事件等, 需修改 `mdcx.controllers.main_window.init.Init_Singal`
* 所有事件处理函数均在 `mdcx/controllers/main_window/main_window.py` 及 `mdcx/controllers/main_window/handlers.py`

## 代码结构说明

```bash
mdcx
├── mdcx # 源代码目录
│   ├── config # 配置管理
│   ├── controllers # Qt UI 控制器
│   │   └── main_window
│   ├── crawlers # 各网站爬虫
│   ├── models # 业务逻辑
│   │   ├── base
│   │   ├── core
│   │   └── tools
│   ├── utils
│   └── views # Qt UI 定义
├── scripts # 开发/构建脚本
│   ├── build.sh # 构建 Qt 版本
│   ├── changelog.sh # 生成变更日志模板
│   └── pyuic.sh # 从 Qt UI 生成 Python 代码
└── tests # 测试
```
