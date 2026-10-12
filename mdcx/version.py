"""The fork's stable release versions: vMAJOR.MINOR.PATCH."""

import ast
import re
from pathlib import Path

_VERSION = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def parse_version(version: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(version.strip())
    if not match:
        raise ValueError(f"无效版本号 {version!r}，应使用 v主版本.次版本.修订号")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def normalize_version(version: str) -> str:
    return "v" + ".".join(map(str, parse_version(version)))


def is_newer_version(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def read_source_version(path: Path) -> str:
    """Read the literal without importing application or configuration code."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "LOCAL_VERSION" for target in node.targets
        ):
            version = ast.literal_eval(node.value)
            if isinstance(version, str):
                return normalize_version(version)
            break
    raise ValueError("LOCAL_VERSION 必须是 v主版本.次版本.修订号格式的字符串")
