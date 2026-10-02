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
