import plistlib
import struct
import tomllib

import pytest

from mdcx.consts import LOCAL_VERSION
from scripts import build, bump
from scripts import check_release_version as release


@pytest.fixture
def source(tmp_path):
    (tmp_path / "mdcx").mkdir()
    (tmp_path / "mdcx/consts.py").write_text('LOCAL_VERSION = "v1.1.0"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mdcx"\nversion = "1.1.0"\n', encoding="utf-8")
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "mdcx"\nversion = "1.1.0"\n\n[[package]]\nname = "cffi"\nversion = "2.0.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "changelog.md").write_text("# MDCx v1.1.0\n", encoding="utf-8")
    return tmp_path


def test_source_and_locked_project_have_one_release_version():
    assert release.validate_source(LOCAL_VERSION) == LOCAL_VERSION
    assert build.get_version_from_config() == LOCAL_VERSION


@pytest.mark.parametrize("tag", ["220261012", "v1.0.3", "1.1.0", "v1.1.0-rc.1"])
def test_release_rejects_invalid_or_mismatched_tag(source, tag):
    with pytest.raises(ValueError):
        release.validate_source(tag, source)


@pytest.mark.parametrize("file", ["mdcx/consts.py", "pyproject.toml", "uv.lock", "changelog.md"])
def test_release_rejects_any_source_version_drift(source, file):
    path = source / file
    path.write_text(path.read_text(encoding="utf-8").replace("1.1.0", "1.0.2"), encoding="utf-8")
    with pytest.raises(ValueError):
        release.validate_source("v1.1.0", source)


@pytest.mark.parametrize("part,expected", [("major", "v2.0.0"), ("minor", "v1.2.0"), ("patch", "v1.1.1")])
def test_bump_resets_lower_components(part, expected):
    assert bump.bumped_version("v1.1.0", part) == expected


def test_bump_synchronizes_sources_without_changing_dependencies(source, monkeypatch):
    monkeypatch.setattr(bump, "get_consts_file", lambda: source / "mdcx/consts.py")
    bump.update_version("v1.2.0")
    assert bump.get_current_version() == "v1.2.0"
    assert tomllib.loads((source / "pyproject.toml").read_text())["project"]["version"] == "1.2.0"
    packages = tomllib.loads((source / "uv.lock").read_text())["package"]
    assert {p["name"]: p["version"] for p in packages} == {"mdcx": "1.2.0", "cffi": "2.0.0"}


def test_bump_invalid_metadata_does_not_partially_change_sources(source, monkeypatch):
    monkeypatch.setattr(bump, "get_consts_file", lambda: source / "mdcx/consts.py")
    (source / "uv.lock").write_text("invalid layout", encoding="utf-8")
    with pytest.raises(ValueError):
        bump.update_version("v1.2.0")
    assert bump.get_current_version() == "v1.1.0"
    assert 'version = "1.1.0"' in (source / "pyproject.toml").read_text()


def test_build_rejects_display_version_mismatch_before_running_tools(source, monkeypatch):
    monkeypatch.chdir(source)
    builder = build.BuildManager("MDCx", "v1.0.2", False, True)
    calls = []
    monkeypatch.setattr(builder, "_check_environment", lambda: calls.append("tools"))
    with pytest.raises(SystemExit) as caught:
        builder.run()
    assert caught.value.code == 1 and calls == []


def test_windows_spec_embeds_file_and_product_versions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    builder = build.BuildManager("MDCx", "v1.1.0", False, True)
    builder.is_windows, builder.is_mac = True, False
    calls = []
    monkeypatch.setattr(builder, "_run_command", lambda args, *_args: calls.append(args))
    builder._generate_spec()
    assert "--version-file" in calls[0]
    content = (tmp_path / "build-version.txt").read_text(encoding="utf-8")
    assert "filevers=(1, 1, 0, 0)" in content and "prodvers=(1, 1, 0, 0)" in content
    assert "StringStruct('FileVersion', '1.1.0')" in content
    assert "StringStruct('ProductVersion', '1.1.0')" in content
    compile(content, "build-version.txt", "eval")


def test_mac_spec_uses_valid_numeric_bundle_versions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = tmp_path / "MDCx.spec"
    spec.write_text("app = BUNDLE(\n    bundle_identifier='com.mdcuniverse.mdcx',\n)\n", encoding="utf-8")
    build.BuildManager("MDCx", "v1.1.0", True, True)._modify_spec()
    content = spec.read_text(encoding="utf-8")
    assert "'CFBundleShortVersionString': '1.1.0'" in content
    assert "'CFBundleVersion': '1.1.0'" in content
    compile(content, "MDCx.spec", "exec")


def test_bundle_check_rejects_old_embedded_windows_version(tmp_path, monkeypatch):
    path = tmp_path / "MDCx.exe"
    data = bytearray(128)
    data[:2] = b"MZ"
    data[0x3C:0x40] = struct.pack("<I", 64)
    data[64:70] = b"PE\0\0\x64\x86"
    path.write_bytes(data)
    monkeypatch.setattr(release, "bundled_version", lambda _path: "220261012")
    monkeypatch.setattr(release, "validate_windows_metadata", lambda *_args: None)
    with pytest.raises(ValueError, match="显示版本"):
        release.validate_bundle(path, "v1.1.0")


def test_bundle_check_rejects_mac_version_drift(tmp_path):
    bundle = tmp_path / "MDCx.app"
    (bundle / "Contents").mkdir(parents=True)
    with (bundle / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump({"CFBundleShortVersionString": "v1.1.0", "CFBundleVersion": "220261012"}, stream)
    with pytest.raises(ValueError, match="macOS 成品版本"):
        release.validate_bundle(bundle, "v1.1.0")
