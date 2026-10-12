"""Fail a release before publishing if its source or native bundle has mixed versions."""

import argparse
import dis
import plistlib
import struct
import sys
import tomllib
from pathlib import Path

from mdcx.version import normalize_version, parse_version, read_source_version


def validate_source(tag: str, root: Path = Path(".")) -> str:
    version = normalize_version(tag)
    if tag != version:
        raise ValueError("正式发布标签必须为 v主版本.次版本.修订号")
    if read_source_version(root / "mdcx/consts.py") != version:
        raise ValueError("标签与软件内版本不一致")
    numeric = version.removeprefix("v")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    locked = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    packages = [p for p in locked["package"] if p["name"] == "mdcx"]
    if project["project"]["version"] != numeric or len(packages) != 1 or packages[0]["version"] != numeric:
        raise ValueError("标签与项目/锁文件版本不一致")
    if (root / "changelog.md").read_text(encoding="utf-8").splitlines()[0] != f"# MDCx {version}":
        raise ValueError("发布说明标题与标签不一致")
    return version


def bundled_version(executable: Path) -> str:
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(executable))
    pyz_name = next(name for name, entry in archive.toc.items() if entry[-1] == "z")
    module = archive.open_embedded_archive(pyz_name).extract("mdcx.consts")
    previous = None
    for instruction in dis.get_instructions(module):
        if instruction.opname == "STORE_NAME" and instruction.argval == "LOCAL_VERSION":
            if previous and previous.opname == "LOAD_CONST" and isinstance(previous.argval, str):
                return previous.argval
            break
        previous = instruction
    raise ValueError("成品未包含字符串形式的软件版本")


def validate_windows_metadata(executable: Path, version: str) -> None:
    # Native CI verifies Windows Explorer's strings and the numeric file version.
    import ctypes
    from ctypes import wintypes

    library = ctypes.WinDLL("version", use_last_error=True)
    library.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    library.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    library.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    library.VerQueryValueW.argtypes = [
        wintypes.LPCVOID,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.UINT),
    ]
    size = library.GetFileVersionInfoSizeW(str(executable), None)
    if not size:
        raise ValueError("Windows 成品缺少版本资源")
    data = ctypes.create_string_buffer(size)
    if not library.GetFileVersionInfoW(str(executable), 0, size, data):
        raise ValueError("无法读取 Windows 版本资源")
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    for field in ("FileVersion", "ProductVersion"):
        key = f"\\StringFileInfo\\040904B0\\{field}"
        if not library.VerQueryValueW(data, key, ctypes.byref(pointer), ctypes.byref(length)):
            raise ValueError(f"Windows 成品缺少 {field}")
        if ctypes.wstring_at(pointer, length.value).rstrip("\0") != version.removeprefix("v"):
            raise ValueError(f"Windows 成品 {field} 不一致")
    if not library.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ValueError("Windows 成品缺少固定版本信息")
    values = struct.unpack("<13I", ctypes.string_at(pointer, length.value))
    expected = parse_version(version)
    for high, low in ((values[2], values[3]), (values[4], values[5])):
        if (high >> 16, high & 0xFFFF, low >> 16, low & 0xFFFF) != (*expected, 0):
            raise ValueError("Windows 成品数字版本不一致")


def validate_bundle(bundle: Path, version: str) -> None:
    if bundle.suffix == ".app":
        with (bundle / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        numeric = version.removeprefix("v")
        if info.get("CFBundleShortVersionString") != numeric or info.get("CFBundleVersion") != numeric:
            raise ValueError("macOS 成品版本不一致")
        executable = bundle / "Contents/MacOS" / info["CFBundleExecutable"]
        with executable.open("rb") as stream:
            magic, cpu = struct.unpack("<II", stream.read(8))
        if magic != 0xFEEDFACF or cpu != 0x0100000C:
            raise ValueError("macOS 成品应为 arm64 Mach-O")
    else:
        executable = bundle
        with executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ValueError("Windows 成品缺少 PE 头")
            stream.seek(0x3C)
            offset = struct.unpack("<I", stream.read(4))[0]
            stream.seek(offset)
            if stream.read(6) != b"PE\0\0\x64\x86":
                raise ValueError("Windows 成品应为 x86_64 PE")
        if sys.platform == "win32":
            validate_windows_metadata(executable.resolve(), version)
    if bundled_version(executable) != version:
        raise ValueError("成品中的软件显示版本与发布标签不一致")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    version = validate_source(args.tag)
    if args.bundle:
        validate_bundle(args.bundle, version)
    print(f"版本一致性检查通过：{version}")


if __name__ == "__main__":
    main()
