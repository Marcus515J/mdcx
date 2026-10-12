import re
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from mdcx.version import normalize_version, parse_version, read_source_version

app = typer.Typer(
    name="bump",
    help="MDCx 版本号管理工具",
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def get_project_root() -> Path:
    """获取项目根目录"""
    current = Path(__file__).resolve()
    # 从 scripts/bump.py 往上找到项目根目录
    while current.parent != current:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise FileNotFoundError("无法找到项目根目录（包含 pyproject.toml 的目录）")


def get_consts_file() -> Path:
    """获取 consts.py 文件路径"""
    project_root = get_project_root()
    consts_file = project_root / "mdcx" / "consts.py"
    if not consts_file.exists():
        raise FileNotFoundError(f"找不到 consts.py 文件: {consts_file}")
    return consts_file


def get_current_version() -> str:
    """从 consts.py 中获取当前版本号"""
    return read_source_version(get_consts_file())


def update_version(new_version: str) -> None:
    """Keep application, Python metadata and the locked project version in sync."""
    new_version = normalize_version(new_version)
    consts_file = get_consts_file()
    content = consts_file.read_text(encoding="utf-8")

    # 替换版本号
    pattern = r'(LOCAL_VERSION\s*=\s*)([\'"])[^\'"]+\2'
    new_content, count = re.subn(pattern, lambda m: f'{m[1]}"{new_version}"', content)

    if count != 1:
        raise ValueError("版本号替换失败，请检查 consts.py 文件格式")

    root = consts_file.parent.parent
    numeric = new_version.removeprefix("v")
    updates = {consts_file: new_content}
    for name, pattern in (
        ("pyproject.toml", r'(\[project\]\nname = "mdcx"\nversion = ")[^"]+("\n)'),
        ("uv.lock", r'(\[\[package\]\]\nname = "mdcx"\nversion = ")[^"]+("\n)'),
    ):
        path = root / name
        updated, count = re.subn(pattern, lambda m: m[1] + numeric + m[2], path.read_text(encoding="utf-8"))
        if count != 1:
            raise ValueError(f"无法定位 {name} 中的项目版本，未写入任何文件")
        updates[path] = updated
    for path, text in updates.items():
        path.write_text(text, encoding="utf-8")


def bumped_version(current: str, part: str) -> str:
    major, minor, patch = parse_version(current)
    if part == "major":
        return f"v{major + 1}.0.0"
    if part == "minor":
        return f"v{major}.{minor + 1}.0"
    if part == "patch":
        return f"v{major}.{minor}.{patch + 1}"
    raise ValueError("--part 必须是 major、minor 或 patch")


@app.command()
def main(
    version: Annotated[str | None, typer.Option("--version", "-v", help="新版本号，如 v1.1.0")] = None,
    part: Annotated[str, typer.Option("--part", "-p", help="递增 major、minor 或 patch")] = "patch",
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="预览模式")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="强制执行")] = False,
) -> None:
    """
    更新 LOCAL_VERSION 版本号

    [bold green]示例:[/bold green]

    • [cyan]uv run bump[/cyan] - 修订号 +1
    • [cyan]uv run bump --part minor[/cyan] - 次版本 +1，修订号归零
    • [cyan]uv run bump --version v1.1.0[/cyan] - 设置指定版本号
    • [cyan]uv run bump --dry-run[/cyan] - 预览模式
    """
    try:
        # 获取当前版本号
        current_version = get_current_version()

        # 计算新版本号
        if version is not None:
            new_version = normalize_version(version)
        else:
            new_version = bumped_version(current_version, part)

        # 显示版本信息
        console.print(
            Panel.fit(
                f"[bold]当前版本:[/bold] [yellow]{current_version}[/yellow]\n"
                f"[bold]新版本:[/bold] [green]{new_version}[/green]",
                title="[bold blue]版本信息[/bold blue]",
                border_style="blue",
            )
        )

        if new_version == current_version:
            console.print("[yellow]版本号没有变化，无需更新[/yellow]")
            return

        if parse_version(new_version) < parse_version(current_version):
            raise ValueError("新版本不能小于当前版本")

        if dry_run:
            console.print("[cyan]预览模式：不会实际修改文件[/cyan]")
            return

        # 确认操作
        if not force:
            if not Confirm.ask(f"确认将版本号从 {current_version} 更新为 {new_version}？"):
                console.print("[yellow]操作已取消[/yellow]")
                return

        # 更新版本号
        update_version(new_version)
        subprocess.run(["uv", "lock", "--check", "--offline"], cwd=get_project_root(), check=True)

        console.print(
            Panel.fit(
                f"[bold green]✓[/bold green] 版本号已成功更新：[yellow]{current_version}[/yellow] → [green]{new_version}[/green]",
                title="[bold green]更新完成[/bold green]",
                border_style="green",
            )
        )

        # 显示文件路径
        consts_file = get_consts_file()
        console.print(f"[dim]已修改文件: {consts_file}[/dim]")

    except Exception as e:
        console.print(
            Panel.fit(f"[bold red]错误:[/bold red] {e}", title="[bold red]操作失败[/bold red]", border_style="red")
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
