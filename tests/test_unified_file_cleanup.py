import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mdcx.base import file as files
from mdcx.config.enums import CleanAction
from mdcx.config.manager import ConfigManager
from mdcx.config.models import Config
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags


@pytest.fixture
def cleanup(monkeypatch, tmp_path):
    cfg = Config(garbage_enabled=True, garbage_directory=str(tmp_path / "_待删"))
    monkeypatch.setattr(files.manager, "config", cfg)
    monkeypatch.setattr(files.manager.computed, "escape_string_list", [])
    monkeypatch.setattr(Flags, "file_mode", FileMode.Default)
    monkeypatch.setattr(Flags, "stop_requested", False)
    monkeypatch.setattr(files.signal, "stop", False)
    logs = []
    monkeypatch.setattr(files.signal, "show_log_text", lambda text: (logs.append(text), print(text)))
    return cfg, logs


def screenshot_files(media):
    media.mkdir()
    names = [
        "聚 合 全 網 H 直 播.html",
        "私人笔记.txt",
        "最 新 位 址 獲 取: 489155.com 收藏不迷路.txt",
        "明确指定的广告.txt",
        "明确指定的广告.txt.bak",
    ]
    # Windows cannot use ':' in a basename. Keep the spaces and use its fullwidth counterpart.
    names = [name.replace(":", "：") for name in names]
    paths = {name: media / name for name in names}
    for name, path in paths.items():
        path.write_bytes(b"" if name == "私人笔记.txt" else b"original content")
    return paths


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("delete", [False, True])
async def test_screenshot_files_during_real_scan(cleanup, tmp_path, dry_run, delete):
    cfg, logs = cleanup
    cfg.garbage_dry_run = dry_run
    cfg.garbage_permanent_delete = delete
    cfg.clean_name.append("明确指定的广告.txt")
    media = tmp_path / "media"
    paths = screenshot_files(media)
    nfo = media / "台湾uu.nfo"
    nfo.write_bytes(b"keep existing nfo")
    assert await files.movie_lists([], cfg.media_type, media) == []
    ads = [name for name in paths if name not in ("私人笔记.txt", "明确指定的广告.txt.bak")]
    for name, path in paths.items():
        assert path.exists() == (dry_run or name not in ads)
        if not dry_run and not delete and name in ads:
            assert (Path(cfg.garbage_directory) / name).read_bytes() == b"original content"
    assert paths["私人笔记.txt"].read_bytes() == b""
    assert paths["明确指定的广告.txt.bak"].read_bytes() == b"original content"
    assert nfo.read_bytes() == b"keep existing nfo"
    assert len([line for line in logs if "🗑" in line]) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_manual_cleanup_without_auto_or_scraping(cleanup, tmp_path, monkeypatch, dry_run):
    cfg, logs = cleanup
    cfg.garbage_enabled = False
    cfg.garbage_dry_run = dry_run
    cfg.clean_name = ["明确指定的广告.txt"]
    media = tmp_path / "media"
    paths = screenshot_files(media)
    pure = media / "纯垃圾"
    pure.mkdir()
    (pure / "推广.url").write_bytes(b"ad")
    quarantine = Path(cfg.garbage_directory)
    quarantine.mkdir()
    (quarantine / "聚 合 全 網 H 直 播.html").write_bytes(b"collision content")
    (quarantine / "推广.url").write_bytes(b"already quarantined")
    monkeypatch.setattr(
        files,
        "get_movie_path_setting",
        lambda **kwargs: SimpleNamespace(movie_paths=[media, quarantine], ignore_dirs=[]),
    )
    await files.check_and_clean_files()
    assert pure.exists() == dry_run
    assert paths["私人笔记.txt"].exists() and paths["明确指定的广告.txt.bak"].exists()
    assert paths["明确指定的广告.txt"].exists() == dry_run
    assert (quarantine / "聚 合 全 網 H 直 播.html").read_bytes() == b"collision content"
    assert (quarantine / "推广.url").read_bytes() == b"already quarantined"
    if not dry_run:
        assert (quarantine / "聚 合 全 網 H 直 播_1.html").read_bytes() == b"original content"
        assert (quarantine / "纯垃圾" / "推广.url").read_bytes() == b"ad"
    assert any("无需联网刮削" in line for line in logs)
    assert any("失败 0 个" in line for line in logs)


def test_full_filename_and_exclusions_are_shared(cleanup, tmp_path):
    cfg, _ = cleanup
    cfg.clean_name = ["广告.TXT"]
    cfg.clean_ext = []
    cfg.clean_contains = []
    cfg.clean_size = 1024
    for name, expected in [("广告.TXT", True), ("广告.txt", False), ("广告.TXT.bak", False), ("私人笔记.txt", False)]:
        path = tmp_path / name
        path.write_bytes(b"")
        assert bool(files._garbage_file_rules(path)) == expected
    cfg.clean_ignore_ext = [".txt"]
    assert not files._garbage_file_rules(tmp_path / "广告.TXT")
    cfg.clean_enable.remove(CleanAction.CLEAN_IGNORE_EXT)
    assert files._garbage_file_rules(tmp_path / "广告.TXT")
    cfg.clean_contains = ["新广告"]
    cfg.clean_ignore_contains = ["SKIP"]
    path = tmp_path / "新 广 告 s k i p.txt"
    path.write_bytes(b"ad")
    assert not files._process_garbage_file(path)
    assert path.exists()


def test_zero_byte_note_can_be_explicitly_named_for_cleaning(cleanup, tmp_path):
    cfg, _ = cleanup
    cfg.clean_name = ["私人笔记.txt"]
    cfg.garbage_permanent_delete = True
    path = tmp_path / "私人笔记.txt"
    path.write_bytes(b"")
    assert files._garbage_file_rules(path) == ["清理文件名:私人笔记.txt"]
    assert files._process_garbage_file(path)
    assert not path.exists()


def test_nfo_images_subtitles_and_numbered_videos_always_protected(cleanup, tmp_path):
    cfg, _ = cleanup
    cfg.clean_size = 100000
    names = ["台湾uu.nfo", "台湾uu.jpg", "台湾uu.srt", "ABF-386-U 台湾uu.mp4"]
    cfg.clean_name = names
    cfg.clean_ext = [".nfo", ".jpg", ".srt", ".mp4"]
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"preserve")
        assert not files._process_garbage_file(path)
        assert path.read_bytes() == b"preserve"


def test_manual_clean_is_independent_of_previous_single_file_scrape(cleanup, tmp_path, monkeypatch):
    cfg, _ = cleanup
    cfg.garbage_enabled = False
    path = tmp_path / "台湾uu.mp4"
    path.write_bytes(b"ad")
    monkeypatch.setattr(Flags, "file_mode", FileMode.Single)
    monkeypatch.setattr(Flags, "appoint_url", "https://example.com/specified-film")
    assert not files._process_garbage_file(path)
    assert files._process_garbage_file(path, manual=True)
    assert not path.exists()


def test_old_string_rules_and_disabled_contains_are_preserved():
    data = {
        "clean_ext": ".html|.url",
        "clean_name": "一个广告.txt|另一个广告.txt",
        "clean_contains": "用户原有词",
        "clean_ignore_contains": "skip|私人",
        "clean_enable": ["clean_name", "clean_ignore_contains"],
        "garbage_enabled": True,
        "garbage_keywords": ["旧广告黑名单"],
    }
    Config.update(data)
    cfg = Config.model_validate(data)
    assert cfg.clean_name == ["一个广告.txt", "另一个广告.txt"]
    assert cfg.clean_contains == ["用户原有词", "旧广告黑名单"]
    assert cfg.clean_ignore_contains == ["skip", "私人"]
    assert CleanAction.CLEAN_CONTAINS not in cfg.clean_enable


@pytest.mark.parametrize("previous_test_build", [False, True])
def test_old_json_load_and_roundtrip_preserves_existing_choices(monkeypatch, tmp_path, previous_test_build):
    old = Config().model_dump(mode="json")
    for field in [
        "garbage_enabled",
        "garbage_domain_rule",
        "garbage_directory",
        "garbage_dry_run",
        "garbage_permanent_delete",
    ]:
        old.pop(field)
    old.update(
        media_path=r"G:\待刮削",
        soft_link=1,
        file_size=250.5,
        proxy="http://127.0.0.1:7890",
        use_proxy=True,
        clean_name=["准确的广告.txt"],
        clean_contains=["用户原有词"],
        clean_ignore_contains=["私人", "skip"],
    )
    old["translate_config"]["llm_model"] = "original-model"
    old["translate_config"]["llm_key"] = "test-key-preserved"
    old["site_configs"]["javbus"] = {"custom_url": "https://example.com"}
    old["javdb"] = "test-cookie-preserved"
    old["javbus"] = "test-cookie-also-preserved"
    if previous_test_build:
        old.update(garbage_enabled=True, garbage_keywords=["新增广告词", "用户原有词"], garbage_dry_run=True)
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    manager = ConfigManager.__new__(ConfigManager)
    manager._path = path
    monkeypatch.setattr(ConfigManager, "_replace_config", lambda self, config: setattr(self, "config", config))
    errors = manager.load()
    assert not any("验证失败" in error for error in errors)
    assert path.read_bytes() == before  # loading does not rewrite the user's original file
    manager.save()
    saved = json.loads(path.read_text(encoding="utf-8"))
    normalized = Config.model_validate(saved)
    baseline = Config.model_validate(old).model_dump(mode="json")
    for name in old:
        if name in baseline and name not in {"clean_contains", "clean_enable"} and not name.startswith("garbage_"):
            assert normalized.model_dump(mode="json")[name] == baseline[name], name
    assert normalized.clean_contains == (["用户原有词", "新增广告词"] if previous_test_build else ["用户原有词"])
    assert "garbage_keywords" not in saved
    assert normalized.garbage_enabled == previous_test_build
    again = json.loads(path.read_text(encoding="utf-8"))
    Config.update(again)
    assert Config.model_validate(again).model_dump(mode="json") == normalized.model_dump(mode="json")
