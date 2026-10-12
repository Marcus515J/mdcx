from pathlib import Path

import pytest

from mdcx.base import file as files
from mdcx.config.models import Config
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags
from mdcx.number import get_file_number


@pytest.fixture
def samples(monkeypatch, tmp_path):
    # Execute the real scan worker without the headless runtime thread wakeup issue.
    async def run_worker(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(files.asyncio, "to_thread", run_worker)
    cfg = Config(garbage_enabled=True, garbage_directory=str(tmp_path / "_待删"))
    monkeypatch.setattr(files.manager, "config", cfg)
    monkeypatch.setattr(files.manager.computed, "escape_string_list", [])
    monkeypatch.setattr(Flags, "success_list", set())
    monkeypatch.setattr(Flags, "file_mode", FileMode.Default)
    logs = []
    monkeypatch.setattr(files.signal, "show_log_text", lambda text: (logs.append(text), print(text)))
    paths = {}
    for name, size in {
        "FC2PPV-4057967.mp4": 1,
        "ABF-386-U 台湾uu.mp4": 1,
        "台湾uu美少女直播 20年信誉保证服务全球.mp4": 101 * 1024**2,
        "社 區 最 新 情 報.mp4": 101 * 1024**2,
        "x u u 6 2 . c o m.mp4": 101 * 1024**2,
        "未知小片.mp4": 1,
        "未知大片.mp4": 100 * 1024**2,
        "台湾uu.nfo": 1,
    }.items():
        path = tmp_path / "FC2PPV-4057967" / name
        path.parent.mkdir(exist_ok=True)
        with path.open("wb") as f:
            f.truncate(size)
        paths[name] = path
    return cfg, paths, logs


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_mixed_scan(samples, tmp_path, dry_run):
    cfg, paths, logs = samples
    cfg.garbage_dry_run = dry_run
    quarantine = Path(cfg.garbage_directory)
    quarantine.mkdir()
    collision = quarantine / "未知小片.mp4"
    collision.write_bytes(b"preserve")
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in paths.values()}
    result = await files.movie_lists([], [".mp4"], tmp_path)
    assert set(result) == {paths[n] for n in ["FC2PPV-4057967.mp4", "ABF-386-U 台湾uu.mp4", "未知大片.mp4"]}
    for name, path in paths.items():
        garbage = name in [
            "台湾uu美少女直播 20年信誉保证服务全球.mp4",
            "社 區 最 新 情 報.mp4",
            "x u u 6 2 . c o m.mp4",
            "未知小片.mp4",
        ]
        assert path.exists() == (dry_run or not garbage)
        if path.exists():
            assert (path.stat().st_size, path.stat().st_mtime_ns) == before[path]
    assert collision.read_bytes() == b"preserve"
    if not dry_run:
        assert (quarantine / "未知小片_1.mp4").exists()
    assert len([line for line in logs if "| " in line]) == 4
    assert await files.movie_lists([], [".mp4"], quarantine) == []
    assert set(await files.movie_lists([], [".mp4"], tmp_path)) == set(result)


@pytest.mark.asyncio
async def test_disabled(samples, tmp_path):
    cfg, paths, _ = samples
    cfg.garbage_enabled = False
    assert set(await files.movie_lists([], [".mp4"], tmp_path)) == {p for p in paths.values() if p.suffix == ".mp4"}
    assert all(p.exists() for p in paths.values())


def test_delete_and_symlink(samples, tmp_path):
    cfg, paths, logs = samples
    cfg.garbage_permanent_delete = True
    link = tmp_path / "台湾uu.mp4"
    link.symlink_to(paths["未知大片.mp4"])
    assert not files._process_garbage_file(link)
    assert link.exists()
    assert files._process_garbage_file(paths["未知小片.mp4"])
    assert not paths["未知小片.mp4"].exists()
    assert "永久删除" in logs[-1]


def test_recognition_is_explicit():
    assert get_file_number("未知大片.mp4", [])
    assert not get_file_number("未知大片.mp4", [], recognized_only=True)
    assert get_file_number("FC2PPV-4057967.mp4", [], recognized_only=True) == "FC2-4057967"


def test_move_failure_stays_out_of_search(samples, monkeypatch):
    _, paths, logs = samples

    def fail(*args, **kwargs):
        raise PermissionError("模拟无权限")

    monkeypatch.setattr(Path, "mkdir", fail)
    assert files._process_garbage_file(paths["未知小片.mp4"])
    assert paths["未知小片.mp4"].exists()
    assert "垃圾处理失败" in logs[-1]


@pytest.mark.asyncio
async def test_explicit_task_never_reaches_search(samples, monkeypatch):
    from mdcx.core import scraper

    _, paths, _ = samples
    path = paths["未知小片.mp4"]
    monkeypatch.setattr(Flags, "remain_list", [path])
    monkeypatch.setattr(Flags, "scrape_done", 0)

    def unexpected(*args, **kwargs):
        pytest.fail("命中文件不应读取元数据或搜索站点")

    monkeypatch.setattr(scraper, "get_file_info_v2", unexpected)
    await scraper.Scraper(object()).process_one_file((path, 1, 1))
    assert not path.exists()
    assert not Flags.remain_list
    assert Flags.scrape_done == 1


def test_prevent_char_and_appointed_number(samples, monkeypatch):
    cfg, paths, _ = samples
    cfg.prevent_char = "·"
    normal = paths["FC2PPV-4057967.mp4"].with_name("F·C·2·P·P·V·-·4·0·5·7·9·6·7.mp4")
    normal.write_bytes(b"normal")
    assert not files._process_garbage_file(normal)
    monkeypatch.setattr(Flags, "file_mode", FileMode.Again)
    monkeypatch.setattr(Flags, "new_again_dic", {paths["未知小片.mp4"]: ("ABC-123", "", "")})
    assert not files._process_garbage_file(paths["未知小片.mp4"])


def make_garbage_tree(tmp_path):
    folder = tmp_path / "只剩垃圾"
    folder.mkdir()
    (folder / "广告.mp4").write_bytes(b"garbage video")
    (folder / "推广.url").write_bytes(b"garbage link")
    return folder


@pytest.mark.parametrize("dry_run", [True, False])
def test_whole_folder_quarantine(samples, tmp_path, dry_run):
    cfg, _, logs = samples
    cfg.garbage_dry_run = dry_run
    folder = make_garbage_tree(tmp_path)
    quarantine = Path(cfg.garbage_directory)
    quarantine.mkdir()
    collision = quarantine / folder.name
    collision.mkdir()
    (collision / "正常文件.txt").write_bytes(b"preserve")
    before = {path.name: path.read_bytes() for path in folder.iterdir()}
    files._quarantine_garbage_folders(tmp_path, [])
    if dry_run:
        assert folder.exists()
        assert {path.name: path.read_bytes() for path in folder.iterdir()} == before
        assert not (quarantine / (folder.name + "_1")).exists()
        assert any("演练目录:" in line for line in logs)
    else:
        assert not folder.exists()
        destination = quarantine / (folder.name + "_1")
        assert {path.name: path.read_bytes() for path in destination.iterdir()} == before
        assert any("处理目录:" in line for line in logs)
    assert (collision / "正常文件.txt").read_bytes() == b"preserve"


@pytest.mark.parametrize(
    "protected", ["FC2PPV-4057967.mp4", "台湾uu.nfo", "poster.jpg", "movie.srt", "私人笔记.txt", "skip", "推广skip.url"]
)
def test_protected_file_prevents_directory_move(samples, tmp_path, protected):
    _, _, _ = samples
    folder = make_garbage_tree(tmp_path)
    protected_path = folder / protected
    protected_path.write_bytes(b"keep")
    files._quarantine_garbage_folders(tmp_path, [])
    assert folder.exists()
    assert protected_path.read_bytes() == b"keep"
    assert (folder / "广告.mp4").exists()


def test_source_root_and_empty_directory_never_move(samples, tmp_path):
    _, _, _ = samples
    folder = make_garbage_tree(tmp_path)
    files._quarantine_garbage_folders(folder, [])
    assert folder.exists()
    empty = tmp_path / "empty"
    empty.mkdir()
    files._quarantine_garbage_folders(tmp_path, [folder])
    assert empty.exists() and folder.exists()


def test_nested_and_symlink_directory(samples, tmp_path):
    cfg, _, _ = samples
    folder = make_garbage_tree(tmp_path)
    nested = folder / "nested"
    nested.mkdir()
    (nested / "广告.url").write_bytes(b"nested garbage")
    files._quarantine_garbage_folders(tmp_path, [])
    assert not folder.exists()
    assert (Path(cfg.garbage_directory) / folder.name / "nested" / "广告.url").exists()
    link_folder = make_garbage_tree(tmp_path)
    (link_folder / "link").symlink_to(tmp_path / "FC2PPV-4057967", target_is_directory=True)
    files._quarantine_garbage_folders(tmp_path, [])
    assert link_folder.exists()


@pytest.mark.asyncio
async def test_scan_defers_whole_garbage_directory(samples, tmp_path):
    cfg, _, _ = samples
    folder = make_garbage_tree(tmp_path)
    result = await files.movie_lists([], [".mp4"], tmp_path)
    assert folder.exists()
    assert (folder / "广告.mp4").exists()
    assert not any(path.is_relative_to(folder) for path in result)
    files._quarantine_garbage_folders(tmp_path, [])
    assert not folder.exists()
    assert await files.movie_lists([], [".mp4"], Path(cfg.garbage_directory)) == []


def test_copy_failure_keeps_original_directory(samples, tmp_path, monkeypatch):
    _, _, logs = samples
    folder = make_garbage_tree(tmp_path)

    def fail(*args, **kwargs):
        raise PermissionError("模拟复制失败")

    monkeypatch.setattr(files.shutil, "copytree", fail)
    files._quarantine_garbage_folders(tmp_path, [])
    assert (folder / "广告.mp4").read_bytes() == b"garbage video"
    assert any("垃圾目录移动失败" in line for line in logs)


def test_new_normal_file_during_copy_keeps_source(samples, tmp_path, monkeypatch):
    _, _, logs = samples
    folder = make_garbage_tree(tmp_path)
    copytree = files.shutil.copytree

    def copy_and_add(source, destination, **kwargs):
        result = copytree(source, destination, **kwargs)
        (source / "正常笔记.txt").write_bytes(b"new normal file")
        return result

    monkeypatch.setattr(files.shutil, "copytree", copy_and_add)
    files._quarantine_garbage_folders(tmp_path, [])
    assert folder.exists()
    assert (folder / "正常笔记.txt").read_bytes() == b"new normal file"
    assert (folder / "广告.mp4").exists()
    assert any("保留源目录" in line for line in logs)


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_run_finishes_with_directory_quarantine(samples, tmp_path, dry_run):
    from mdcx.core import scraper

    cfg, _, _ = samples
    media = tmp_path / "isolated_media"
    media.mkdir()
    folder = make_garbage_tree(media)
    cfg.media_path = str(media)
    cfg.garbage_dry_run = dry_run
    cfg.thread_time = 0
    cfg.switch_on = []
    cfg.emby_on = []
    cfg.actor_photo_kodi_auto = False
    files.signal.stop = False
    await scraper.Scraper(object())._run(FileMode.Default, None)
    assert folder.exists() == dry_run
    if not dry_run:
        assert (Path(cfg.garbage_directory) / folder.name / "广告.mp4").exists()
