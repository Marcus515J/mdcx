import pytest

from mdcx.base import file as files
from mdcx.config.enums import NoEscape
from mdcx.config.models import Config
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags


@pytest.fixture
def rescrape_env(monkeypatch, tmp_path):
    Flags.success_list = set()
    Flags.file_mode = FileMode.Default
    Flags.stop_requested = False
    files.signal.stop = False
    logs = []
    trace_logs = []
    monkeypatch.setattr(files.signal, "show_log_text", lambda text: logs.append(text))
    monkeypatch.setattr(files.signal, "show_traceback_log", lambda text: trace_logs.append(text))

    cfg = Config()
    cfg.no_escape = [NoEscape.SKIP_SUCCESS_FILE, NoEscape.RECORD_SUCCESS_FILE]
    cfg.media_type = [".mp4", ".mkv"]
    monkeypatch.setattr(files.manager, "config", cfg)
    return cfg, logs, trace_logs


@pytest.mark.asyncio
async def test_scraped_file_moved_or_renamed_is_skipped(rescrape_env, tmp_path):
    cfg, logs, trace_logs = rescrape_env
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # 1. 模拟刮削成功并移入演员子目录
    actor_dir = media_dir / "RION"
    actor_dir.mkdir()
    scraped_moved_video = actor_dir / "SSNI-126-中文标题.mp4"
    scraped_moved_video.write_bytes(b"dummy video content")
    scraped_moved_nfo = actor_dir / "SSNI-126-中文标题.nfo"
    scraped_moved_nfo.write_bytes(b"<movie><title>SSNI-126</title></movie>")

    # 2. 模拟刮削成功并改名
    scraped_renamed_video = media_dir / "PRED-110-新译名.mp4"
    scraped_renamed_video.write_bytes(b"dummy video content")
    scraped_renamed_nfo = media_dir / "PRED-110-新译名.nfo"
    scraped_renamed_nfo.write_bytes(b"<movie><title>PRED-110</title></movie>")

    # 3. 模拟新加入的文件（未刮削，无nfo）
    new_video = media_dir / "NEW-999.mp4"
    new_video.write_bytes(b"dummy video content")

    # 4. 模拟上一轮刮削失败的文件（无nfo）
    failed_video = media_dir / "FAIL-001.mp4"
    failed_video.write_bytes(b"dummy video content")

    # 确保 Flags.success_list 为空（模拟跨机器/新版测试包/移动后路径不匹配）
    Flags.success_list = set()

    # 执行扫描
    scan_result = await files.movie_lists([], cfg.media_type, media_dir)

    # 验证：已刮削（移入子目录或改名）的文件被跳过；新文件与失败文件进入刮削列表
    assert set(scan_result) == {new_video, failed_video}

    # 验证日志输出的跳过计数：2个已刮削文件被跳过，2个新/失败文件被找到
    expected_done_log = "Found (2)! Skip successfully scraped (2)"
    assert any(expected_done_log in log for log in logs or trace_logs)

    # 验证 Flags.success_list 自动补充了跳过项
    assert scraped_moved_video in Flags.success_list
    assert scraped_renamed_video in Flags.success_list


@pytest.mark.asyncio
async def test_not_skip_success_when_user_unchecks_setting(rescrape_env, tmp_path):
    cfg, logs, trace_logs = rescrape_env
    # 用户未勾选「跳过之前已刮削成功的文件」
    cfg.no_escape = [NoEscape.RECORD_SUCCESS_FILE]

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video = media_dir / "SSNI-126.mp4"
    video.write_bytes(b"video")
    nfo = media_dir / "SSNI-126.nfo"
    nfo.write_bytes(b"<movie></movie>")

    scan_result = await files.movie_lists([], cfg.media_type, media_dir)
    # 未勾选跳过时，即使存在 nfo 也会进入扫描
    assert scan_result == [video]
    assert any("Found (1)! Skip successfully scraped (0)" in log for log in logs or trace_logs)


@pytest.mark.asyncio
async def test_save_success_list_preserves_both_old_and_new_paths(rescrape_env, tmp_path):
    cfg, logs, _ = rescrape_env
    old_video = tmp_path / "incoming" / "SSNI-126.mp4"
    new_video = tmp_path / "media" / "RION" / "SSNI-126-Title.mp4"

    Flags.success_list = set()
    await files.save_success_list(old_video, new_video)

    assert old_video in Flags.success_list
    assert new_video in Flags.success_list


@pytest.mark.asyncio
async def test_empty_or_zero_byte_nfo_is_not_treated_as_scraped(rescrape_env, tmp_path):
    cfg, logs, trace_logs = rescrape_env
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    video = media_dir / "BROKEN-001.mp4"
    video.write_bytes(b"dummy")
    zero_nfo = media_dir / "BROKEN-001.nfo"
    zero_nfo.write_bytes(b"")  # 0 字节损坏或残留 NFO

    Flags.success_list = set()
    scan_result = await files.movie_lists([], cfg.media_type, media_dir)

    # 0 字节 NFO 不应被视为刮削成功
    assert scan_result == [video]
