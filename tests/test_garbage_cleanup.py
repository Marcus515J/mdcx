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
