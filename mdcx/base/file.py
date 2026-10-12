import asyncio
import os
import re
import shutil
import stat
import time
import traceback
from pathlib import Path
from uuid import uuid4

import aiofiles
import aiofiles.os

from ..config.enums import DownloadableFile, KeepableFile, NoEscape, Switch
from ..config.extend import get_movie_path_setting
from ..config.manager import manager
from ..config.models import CleanAction
from ..config.resource_policy import resource_policy
from ..config.resources import resources
from ..models.enums import FileMode
from ..models.flags import Flags
from ..models.log_buffer import LogBuffer
from ..number import get_file_number
from ..signals import signal
from ..utils import executor, get_current_time, get_used_time
from ..utils.file import copy_file_async, copy_file_sync, delete_file_async, delete_file_sync, move_file_async

LARGE_LIST_SORT_THRESHOLD = 50000
_large_list_warned: set[str] = set()
_success_list_save_lock = asyncio.Lock()
_SUCCESS_REPLACE_RETRY_MAX = 8
_SUCCESS_REPLACE_RETRY_BASE_SLEEP = 0.15


def _path_lines_for_write(paths: list[Path] | set[Path], list_name: str):
    if len(paths) > LARGE_LIST_SORT_THRESHOLD:
        if list_name not in _large_list_warned:
            signal.show_log_text(f" ⚠ {list_name} 数量较大（{len(paths)}），保存时将跳过排序以降低内存占用。")
            _large_list_warned.add(list_name)
        for path in paths:
            yield str(path) + "\n"
        return
    for path_str in sorted(str(path) for path in paths):
        yield path_str + "\n"


def _build_success_tmp_path(success_path: Path) -> Path:
    return success_path.with_name(f"{success_path.name}.{os.getpid()}.{uuid4().hex}.tmp")


def _ensure_file_writable(path: Path) -> None:
    if not path.exists():
        return
    current_mode = path.stat().st_mode
    if not (current_mode & stat.S_IWRITE):
        path.chmod(current_mode | stat.S_IWRITE)


async def _replace_success_file_with_retry(success_tmp_path: Path, success_path: Path) -> None:
    try:
        await asyncio.to_thread(_ensure_file_writable, success_path)
    except Exception:
        signal.show_log_text(" ⚠ success.txt 文件属性检查失败，将继续尝试保存。")

    for attempt in range(1, _SUCCESS_REPLACE_RETRY_MAX + 1):
        try:
            await asyncio.to_thread(os.replace, success_tmp_path, success_path)
            return
        except PermissionError:
            if attempt == 1:
                signal.show_log_text(" ⚠ success.txt 正在被占用，正在重试保存...")
            if attempt >= _SUCCESS_REPLACE_RETRY_MAX:
                raise
            await asyncio.sleep(_SUCCESS_REPLACE_RETRY_BASE_SLEEP * attempt)


async def _cleanup_success_tmp_file(success_tmp_path: Path) -> None:
    try:
        if await aiofiles.os.path.exists(success_tmp_path):
            await aiofiles.os.remove(success_tmp_path)
    except Exception:
        pass


async def move_other_file(number: str, folder_old_path: Path, folder_new_path: Path, file_name: str, naming_rule: str):
    # 软硬链接模式不移动
    if manager.config.soft_link != 0:
        return

    # 目录相同不移动
    if folder_new_path == folder_old_path:
        return

    # 更新模式 或 读取模式
    if manager.config.main_mode == 3 or manager.config.main_mode == 4:
        if manager.config.update_mode == "c" and not manager.config.success_file_rename:
            return

    elif not manager.config.success_file_move and not manager.config.success_file_rename:
        return

    files = await aiofiles.os.listdir(folder_old_path)
    for old_file in files:
        if os.path.splitext(old_file)[1].lower() in manager.config.media_type:
            continue
        if (
            number in old_file or file_name in old_file or naming_rule in old_file
        ) and "-cd" not in old_file.lower():  # 避免多分集时，其他分级的内容被移走
            old_file_old_path = folder_old_path / old_file
            old_file_new_path = folder_new_path / old_file
            if (
                old_file_old_path != old_file_new_path
                and await aiofiles.os.path.exists(old_file_old_path)
                and not await aiofiles.os.path.exists(old_file_new_path)
            ):
                await move_file_async(old_file_old_path, old_file_new_path)
                LogBuffer.log().write(f"\n 🍀 Move {old_file} done!")


async def copy_trailer_to_theme_videos(folder_new_path: Path, naming_rule: str) -> None:
    start_time = time.time()
    download_files = manager.config.download_files
    keep_files = manager.config.keep_files
    theme_videos_policy = resource_policy(
        DownloadableFile.THEME_VIDEOS,
        KeepableFile.THEME_VIDEOS,
        download_files=download_files,
        keep_files=keep_files,
    )
    theme_videos_folder_path = folder_new_path / "backdrops"
    theme_videos_new_path = theme_videos_folder_path / "theme_video.mp4"

    # 不保留不下载主题视频时，删除
    if theme_videos_policy.should_remove_existing:
        if await aiofiles.os.path.exists(theme_videos_folder_path):
            shutil.rmtree(theme_videos_folder_path, ignore_errors=True)
        return

    # 保留主题视频并存在时返回
    if theme_videos_policy.should_keep and await aiofiles.os.path.exists(theme_videos_folder_path):
        LogBuffer.log().write(f"\n 🍀 Theme video done! (old)({get_used_time(start_time)}s) ")
        return

    # 不下载主题视频时返回
    if not theme_videos_policy.should_download:
        return

    # 不存在预告片时返回
    trailer_name = manager.config.trailer_simple_name
    trailer_folder = None
    if trailer_name:
        trailer_folder = folder_new_path / "trailers"
        trailer_file_path = trailer_folder / "trailer.mp4"
    else:
        trailer_file_path = folder_new_path / (naming_rule + "-trailer.mp4")
    if not await aiofiles.os.path.exists(trailer_file_path):
        return

    # 存在预告片时复制
    if not await aiofiles.os.path.exists(theme_videos_folder_path):
        await aiofiles.os.makedirs(theme_videos_folder_path)
    if await aiofiles.os.path.exists(theme_videos_new_path):
        await delete_file_async(theme_videos_new_path)
    await copy_file_async(trailer_file_path, theme_videos_new_path)
    LogBuffer.log().write("\n 🍀 Theme video done! (copy trailer)")

    # 不下载并且不保留预告片时，删除预告片
    trailer_policy = resource_policy(
        DownloadableFile.TRAILER,
        KeepableFile.TRAILER,
        download_files=download_files,
        keep_files=manager.config.keep_files,
    )
    if trailer_policy.should_remove_existing:
        await delete_file_async(trailer_file_path)
        if trailer_name and trailer_folder:
            shutil.rmtree(trailer_folder, ignore_errors=True)
        LogBuffer.log().write("\n 🍀 Trailer delete done!")


async def pic_some_deal(number: str, thumb_final_path: Path, fanart_final_path: Path) -> None:
    """
    thumb、poster、fanart 删除冗余的图片
    """
    # 不保存thumb时，清理 thumb
    thumb_policy = resource_policy(
        DownloadableFile.THUMB,
        KeepableFile.THUMB,
        download_files=manager.config.download_files,
        keep_files=manager.config.keep_files,
    )
    if thumb_policy.should_remove_existing:
        if await aiofiles.os.path.exists(fanart_final_path):
            Flags.file_done_dic[number].update(thumb=fanart_final_path)
        else:
            Flags.file_done_dic[number].update(thumb=None)
        if await aiofiles.os.path.exists(thumb_final_path):
            await delete_file_async(thumb_final_path)
            LogBuffer.log().write("\n 🍀 Thumb delete done!")


async def save_success_list(old_path: Path | None = None, new_path: Path | None = None) -> None:
    if old_path and NoEscape.RECORD_SUCCESS_FILE in manager.config.no_escape:
        # 软硬链接时，保存原路径；否则保存新路径
        if manager.config.soft_link != 0:
            Flags.success_list.add(old_path)
        elif new_path:
            Flags.success_list.add(new_path)
            if await aiofiles.os.path.islink(new_path):
                Flags.success_list.add(old_path)
                Flags.success_list.add(new_path.resolve())
    if get_used_time(Flags.success_save_time) > 5 or not old_path:
        Flags.success_save_time = time.time()
        success_tmp_path = Path()
        try:
            async with _success_list_save_lock:
                success_path = resources.u("success.txt")
                success_tmp_path = _build_success_tmp_path(success_path)
                success_list_snapshot = list(Flags.success_list)
                async with aiofiles.open(success_tmp_path, "w", encoding="utf-8", errors="ignore") as f:
                    await f.writelines(_path_lines_for_write(success_list_snapshot, "成功列表"))
                await _replace_success_file_with_retry(success_tmp_path, success_path)
        except Exception as e:
            signal.show_log_text(f"  Save success list Error {str(e)}\n {traceback.format_exc()}")
        finally:
            if success_tmp_path:
                await _cleanup_success_tmp_file(success_tmp_path)
        signal.view_success_file_settext.emit(f"查看 ({len(Flags.success_list)})")


def save_remain_list() -> None:
    """This function is intended to be sync."""
    if Flags.can_save_remain and Switch.REMAIN_TASK in manager.config.switch_on:
        try:
            with open(resources.u("remain.txt"), "w", encoding="utf-8", errors="ignore") as f:
                f.writelines(_path_lines_for_write(Flags.remain_list, "剩余任务列表"))
                Flags.can_save_remain = False
        except Exception as e:
            signal.show_log_text(f"save remain list error: {str(e)}\n {traceback.format_exc()}")


async def _clean_empty_fodlers(path: Path, file_mode: FileMode) -> None:
    start_time = time.time()
    if not manager.config.del_empty_folder or file_mode == FileMode.Again:
        return
    signal.set_label_file_path.emit("🗑 正在清理空文件夹，请等待...")
    signal.show_log_text(" ⏳ Cleaning empty folders...")

    if NoEscape.FOLDER in manager.config.no_escape:
        ignore_dirs = []
    else:
        ignore_dirs = get_movie_path_setting(movie_path_override=path).ignore_dirs

    if not await aiofiles.os.path.exists(path):
        signal.show_log_text(f" 🍀 Clean done!({get_used_time(start_time)}s)")
        signal.show_log_text("=" * 80)
        return

    def task():
        folders: list[Path] = []
        for root, dirs, files in path.walk(top_down=True):
            if _is_garbage_directory(root):
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not _is_garbage_directory(root / d)]
            if (root / "skip").exists():  # 是否有skip文件
                dirs[:] = []  # 忽略当前文件夹子目录
                continue
            if root in ignore_dirs:
                dirs[:] = []  # 忽略当前文件夹子目录
                continue
            dirs_list = [root / d for d in dirs]
            folders.extend(dirs_list)
        folders.sort(reverse=True)
        for folder in folders:
            hidden_file_mac = folder / ".DS_Store"
            hidden_file_windows = folder / "Thumbs.db"
            if os.path.exists(hidden_file_mac):
                delete_file_sync(hidden_file_mac)  # 删除隐藏文件
            if os.path.exists(hidden_file_windows):
                delete_file_sync(hidden_file_windows)  # 删除隐藏文件
            try:
                if not os.listdir(folder):
                    os.rmdir(folder)
                    signal.show_log_text(f" 🗑 Clean empty folder: {folder}")
            except Exception as e:
                signal.show_traceback_log(traceback.format_exc())
                signal.show_log_text(f" 🔴 Delete empty folder error: {str(e)}")

    await asyncio.to_thread(task)
    signal.show_log_text(f" 🍀 Clean done!({get_used_time(start_time)}s)")
    signal.show_log_text("=" * 80)


async def check_and_clean_files() -> None:
    """Run the same cleaner without crawling or requiring a successful scrape."""
    signal.change_buttons_status.emit()
    start_time = time.time()
    movie_paths = get_movie_path_setting().movie_paths
    mode = "演练（不移动、不删除）" if manager.config.garbage_dry_run else "真实处理"
    action = "永久删除单文件" if manager.config.garbage_permanent_delete else "移到待删目录"
    signal.show_log_text(f" 🗑 文件清理：{mode} | {action} | 无需联网刮削")
    matched: set[Path] = set()

    def task():
        for movie_path in movie_paths:
            if not movie_path.is_dir() or movie_path.is_symlink() or _is_garbage_directory(movie_path):
                signal.show_log_text(f" 🗑 跳过清理目录: {movie_path}")
                continue
            ignored = get_movie_path_setting(movie_path_override=movie_path).ignore_dirs
            for root, dirs, names in movie_path.walk(top_down=True):
                if signal.stop or Flags.stop_requested:
                    return
                dirs[:] = [
                    name
                    for name in dirs
                    if not (root / name).is_symlink()
                    and not _is_garbage_directory(root / name)
                    and (root / name) not in ignored
                ]
                if any(name in names for name in ("skip", ".skip", ".ignore")):
                    dirs.clear()
                    continue
                if root != movie_path and not any(path.resolve().is_relative_to(root.resolve()) for path in ignored):
                    entries = _garbage_folder_files(root, manual=True)
                    if entries:
                        matched.update(path for path, _ in entries)
                        _log_pending_garbage_folder(root, entries)
                        dirs.clear()
                        continue
                for name in names:
                    if signal.stop or Flags.stop_requested:
                        return
                    path = root / name
                    if _process_garbage_file(path, manual=True):
                        matched.add(path)
            _quarantine_garbage_folders(movie_path, ignored, manual=True)

    try:
        await asyncio.to_thread(task)
        done = sum(not path.exists() for path in matched)
        failed = len(matched) - done if not manager.config.garbage_dry_run else 0
        signal.show_log_text(
            f" 🎉 文件清理完成：匹配 {len(matched)} 个，已处理 {done} 个，失败 {failed} 个 | {mode} | {get_used_time(start_time)}s"
        )
        signal.set_label_file_path.emit("🗑 文件清理完成！")
    finally:
        signal.reset_buttons_status.emit()


def get_success_list() -> None:
    """This function is intended to be sync"""
    Flags.success_save_time = time.time()
    success_path = resources.u("success.txt")
    if os.path.isfile(success_path):
        with open(success_path, encoding="utf-8", errors="ignore") as f:
            Flags.success_list = {p for path in f if (line := path.strip()) and (p := Path(line)).suffix}
        executor.run(save_success_list())
    signal.view_success_file_settext.emit(f"查看 ({len(Flags.success_list)})")


def _garbage_directory(path: Path) -> Path:
    configured = manager.config.garbage_directory.strip()
    return Path(configured).absolute() if configured else Path(path.absolute().anchor) / "_待删"


def _is_garbage_directory(path: Path) -> bool:
    absolute = path.absolute()
    # Also exclude a custom destination, including when it is the scan root.
    return "_待删" in absolute.parts or absolute.resolve().is_relative_to(_garbage_directory(path).resolve())


def _garbage_file_rules(path: Path, *, manual: bool = False) -> list[str]:
    """One set of positive rules for scanning, manual cleaning and whole folders."""
    cfg = manager.config
    if not (cfg.garbage_enabled or manual):
        return []
    ext = path.suffix.casefold()
    protected = {".nfo", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
    protected.update(value.casefold() for value in cfg.sub_type)
    protected.update({".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt"})
    if ext in protected or path.is_symlink() or not path.is_file() or _is_garbage_directory(path):
        return []
    name = path.name
    normalized = re.sub(r"\s+", "", name).casefold()
    if CleanAction.CLEAN_IGNORE_EXT in cfg.clean_enable and ext in {value.casefold() for value in cfg.clean_ignore_ext}:
        return []
    if CleanAction.CLEAN_IGNORE_CONTAINS in cfg.clean_enable and any(
        (word := re.sub(r"\s+", "", value).casefold()) and word in normalized for value in cfg.clean_ignore_contains
    ):
        return []
    video = ext in cfg.media_type
    if video:
        if not manual and Flags.file_mode == FileMode.Again and Flags.new_again_dic.get(path, ("", "", ""))[0]:
            return []
        if not manual and Flags.file_mode == FileMode.Single and Flags.appoint_url:
            return []
        number_path = str(path).replace(cfg.prevent_char, "") if cfg.prevent_char else str(path)
        if get_file_number(number_path, manager.computed.escape_string_list, recognized_only=True):
            return []
    rules = []
    if CleanAction.CLEAN_EXT in cfg.clean_enable and ext in {value.casefold() for value in cfg.clean_ext}:
        rules.append(f"清理扩展名:{ext}")
    # Complete filename equality deliberately keeps spaces and case significant.
    if CleanAction.CLEAN_NAME in cfg.clean_enable and name in cfg.clean_name:
        rules.append(f"清理文件名:{name}")
    if CleanAction.CLEAN_CONTAINS in cfg.clean_enable:
        prefix = "黑名单" if video else "清理关键词"
        rules.extend(
            f"{prefix}:{value}"
            for value in cfg.clean_contains
            if (word := re.sub(r"\s+", "", value).casefold()) and word in normalized
        )
    if video:
        if cfg.garbage_domain_rule and any(domain in normalized for domain in (".com", ".net", ".cc", "www.")):
            rules.append("域名样式")
        size = path.stat().st_size
        if size < cfg.file_size * 1024 * 1024:
            rules.append(f"小于 {cfg.file_size:g} MB")
        # A zero/size-only match cannot delete an ordinary note or unknown document.
        if CleanAction.CLEAN_SIZE in cfg.clean_enable and cfg.clean_size > 0 and size <= cfg.clean_size * 1024:
            rules.append(f"无番号视频小于等于 {cfg.clean_size:g} KB")
    return rules


def _garbage_video_rules(path: Path) -> list[str]:
    if path.suffix.casefold() not in manager.config.media_type:
        return []
    return _garbage_file_rules(path)


def _garbage_folder_files(folder: Path, *, manual: bool = False) -> list[tuple[Path, list[str]]]:
    """All contents must match; unknown files, protected files and links retain the tree."""
    if not (manager.config.garbage_enabled or manual) or folder.is_symlink() or _is_garbage_directory(folder):
        return []
    result = []
    try:
        for root, dirs, names in folder.walk(top_down=True):
            if any((root / d).is_symlink() or _is_garbage_directory(root / d) for d in dirs):
                return []
            for name in names:
                path = root / name
                rules = _garbage_file_rules(path, manual=manual)
                if not rules:
                    return []
                result.append((path, rules))
    except OSError as error:
        signal.show_log_text(f" 🔴 无法检查垃圾目录: {folder} | {error}")
        return []
    return result


def _log_pending_garbage_folder(folder: Path, entries: list[tuple[Path, list[str]]]) -> None:
    prefix = "演练" if manager.config.garbage_dry_run else "待处理"
    for path, rules in entries:
        signal.show_log_text(f" 🗑 {prefix}: {path} | {', '.join(rules)} | 刮削结束后整目录移到待删: {folder}")


def _quarantine_garbage_folders(movie_path: Path, ignore_dirs: list[Path], *, manual: bool = False) -> None:
    """After scraping, move only garbage-only subdirectories; never move the media root."""
    cfg = manager.config
    if (
        not (cfg.garbage_enabled or manual)
        or signal.stop
        or Flags.stop_requested
        or not movie_path.is_dir()
        or _is_garbage_directory(movie_path)
    ):
        return
    ignored = {path.resolve() for path in ignore_dirs}
    for root, dirs, _ in movie_path.walk(top_down=True):
        dirs[:] = [
            d
            for d in dirs
            if not (root / d).is_symlink()
            and not _is_garbage_directory(root / d)
            and (root / d).resolve() not in ignored
        ]
        if root == movie_path or root.resolve() in ignored:
            continue
        # An excluded descendant protects its parent as well.
        if any(path.is_relative_to(root.resolve()) for path in ignored):
            continue
        if signal.stop or Flags.stop_requested:
            return
        entries = _garbage_folder_files(root, manual=manual)
        if not entries:
            continue
        prefix = "演练" if cfg.garbage_dry_run else "处理"
        destination = _garbage_directory(root) / root.name
        if cfg.garbage_dry_run:
            signal.show_log_text(f" 🗑 {prefix}目录: {root} | 仅含垃圾文件 | 整目录移到待删 {destination}")
            dirs.clear()
            continue
        try:
            snapshot = {path: path.lstat() for path, _ in entries}
            signature_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
            destination.parent.mkdir(parents=True, exist_ok=True)
            index = 0
            while True:
                try:
                    # copytree creates its destination exclusively, including on another volume.
                    shutil.copytree(root, destination, symlinks=True)
                    break
                except FileExistsError:
                    index += 1
                    destination = destination.parent / f"{root.name}_{index}"
            current = _garbage_folder_files(root, manual=manual)
            if {path for path, _ in current} != set(snapshot) or any(
                any(getattr(path.lstat(), field) != getattr(before, field) for field in signature_fields)
                for path, before in snapshot.items()
            ):
                signal.show_log_text(f" 🔴 垃圾目录内容发生变化，保留源目录: {root} | 已复制到 {destination}")
                dirs.clear()
                continue
            # Remove only verified files; a newly added normal file prevents rmdir, never rmtree.
            for path, rules in entries:
                if any(getattr(path.lstat(), field) != getattr(snapshot[path], field) for field in signature_fields):
                    raise OSError(f"源文件发生变化: {path}")
                path.unlink()
                signal.show_log_text(f" 🗑 处理: {path} | {', '.join(rules)} | 整目录移到待删 {destination}")
            subdirectories = []
            for parent, children, _ in root.walk(top_down=True):
                subdirectories.extend(parent / name for name in children)
            for child in sorted(subdirectories, key=lambda path: len(path.parts), reverse=True):
                child.rmdir()
            root.rmdir()
            signal.show_log_text(f" 🗑 {prefix}目录: {root} | 仅含垃圾文件 | 整目录移到待删 {destination}")
        except OSError as error:
            signal.show_log_text(f" 🔴 垃圾目录移动失败: {root} | 整目录移到待删 {destination} | {error}")
        dirs.clear()


def _process_garbage_file(path: Path, *, defer_folder: bool = False, manual: bool = False) -> bool:
    """Return True for a matched file, even in dry run or on failure: never search it."""
    cfg = manager.config
    try:
        rules = _garbage_file_rules(path, manual=manual)
    except OSError as error:
        signal.show_log_text(f" 🔴 垃圾文件检查失败: {path} | {error}")
        return False
    if not rules:
        return False
    if defer_folder:
        entries = _garbage_folder_files(path.parent, manual=manual)
        if entries:
            _log_pending_garbage_folder(path.parent, [(path, rules)])
            return True
    action = "永久删除" if cfg.garbage_permanent_delete else "移到待删目录"
    try:
        prefix = "演练" if cfg.garbage_dry_run else "处理"
        if cfg.garbage_dry_run:
            signal.show_log_text(f" 🗑 {prefix}: {path} | {', '.join(rules)} | {action}")
            return True
        if cfg.garbage_permanent_delete:
            path.unlink()
            destination = ""
        else:
            directory = _garbage_directory(path)
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / path.name
            index = 0
            while True:
                try:
                    # Reserve exclusively: never overwrite an existing file or symlink.
                    output = destination.open("xb")
                    break
                except FileExistsError:
                    index += 1
                    destination = directory / f"{path.stem}_{index}{path.suffix}"
            try:
                with output, path.open("rb") as source:
                    shutil.copyfileobj(source, output)
                shutil.copystat(path, destination)
                path.unlink()
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        signal.show_log_text(f" 🗑 {prefix}: {path} | {', '.join(rules)} | {action} {destination}")
    except OSError as error:
        signal.show_log_text(f" 🔴 垃圾处理失败: {path} | {', '.join(rules)} | {action}: {error}")
    return True


async def movie_lists(ignore_dirs: list[Path], media_type: list[str], movie_path: Path) -> list[Path]:
    start_time = time.time()
    total = []
    skip_list = ["skip", ".skip", ".ignore"]
    not_skip_success = NoEscape.SKIP_SUCCESS_FILE not in manager.config.no_escape

    signal.show_traceback_log("🔎 遍历待刮削目录....")

    def task():
        i = 100
        skip = 0
        skip_repeat_softlink = 0
        for root, dirs, files in movie_path.walk(top_down=True):
            if _is_garbage_directory(root):
                dirs.clear()
                continue
            for d in dirs.copy():
                if _is_garbage_directory(root / d) or root / d in ignore_dirs or "behind the scenes" in d:
                    dirs.remove(d)

            if manager.config.garbage_enabled and root != movie_path:
                entries = _garbage_folder_files(root)
                if entries and not any(path.resolve().is_relative_to(root.resolve()) for path in ignore_dirs):
                    _log_pending_garbage_folder(root, entries)
                    dirs.clear()
                    continue

            # 文件夹是否存在跳过文件
            for skip_key in skip_list:
                if skip_key in files:
                    dirs.clear()
                    break
            else:
                # 处理文件列表
                for f in files:
                    file_name, file_ext = os.path.splitext(f)

                    # 跳过隐藏文件、预告片、主题视频
                    if re.search(r"^\..+", file_name):
                        continue
                    if "trailer." in f or "trailers." in f:
                        continue
                    if "theme_video." in f:
                        continue

                    # 判断清理文件
                    path = root / f
                    if _process_garbage_file(path):
                        continue
                    # 添加文件
                    temp_total = []
                    if file_ext.lower() in media_type:
                        if os.path.islink(path):
                            real_path = path.readlink()
                            # 清理失效的软链接文件
                            if NoEscape.CHECK_SYMLINK in manager.config.no_escape and not os.path.exists(real_path):
                                result, error_info = delete_file_sync(path)
                                if result:
                                    signal.show_log_text(f" 🗑 Clean dead link: {path} ")
                                else:
                                    signal.show_log_text(f" 🗑 Clean dead link error: {error_info} ")
                                continue
                            if real_path in temp_total:
                                skip_repeat_softlink += 1
                                delete_file_sync(path)
                                continue
                            else:
                                temp_total.append(real_path)

                        if path in temp_total:
                            skip_repeat_softlink += 1
                            continue
                        else:
                            temp_total.append(path)
                        if not_skip_success or path not in Flags.success_list:
                            total.append(path)
                        else:
                            skip += 1

        found_count = len(total)
        if found_count >= i:
            i = found_count + 100
            signal.show_traceback_log(
                f"✅ Found ({found_count})! "
                f"Skip successfully scraped ({skip}) repeat softlink ({skip_repeat_softlink})! "
                f"({get_used_time(start_time)}s)... Still searching, please wait... \u3000"
            )
            signal.show_log_text(
                f"    {get_current_time()} Found ({found_count})! "
                f"Skip successfully scraped ({skip}) repeat softlink ({skip_repeat_softlink})! "
                f"({get_used_time(start_time)}s)... Still searching, please wait... \u3000"
            )
        return total, skip, skip_repeat_softlink

    total, skip, skip_repeat_softlink = await asyncio.to_thread(task)

    total.sort()
    signal.show_traceback_log(
        f"🎉 Done!!! Found ({len(total)})! "
        f"Skip successfully scraped ({skip}) repeat softlink ({skip_repeat_softlink})! "
        f"({get_used_time(start_time)}s) \u3000"
    )
    signal.show_log_text(
        f"    Done!!! Found ({len(total)})! "
        f"Skip successfully scraped ({skip}) repeat softlink ({skip_repeat_softlink})! "
        f"({get_used_time(start_time)}s) \u3000"
    )
    return total


async def get_movie_list(file_mode: FileMode, movie_path: Path, ignore_dirs: list[Path]) -> list[Path]:
    movie_list = []
    if file_mode == FileMode.Default:  # 刮削默认视频目录的文件
        if not await aiofiles.os.path.exists(movie_path):
            signal.show_log_text("\n 🔴 Movie folder does not exist!")
        else:
            signal.show_log_text(f" 🖥 Movie path: {movie_path}")
            signal.show_log_text(" 🔎 Searching all videos, Please wait...")
            signal.set_label_file_path.emit(f"正在遍历待刮削视频目录中的所有视频，请等待...\n {movie_path}")
            if (
                NoEscape.FOLDER in manager.config.no_escape
                or manager.config.main_mode == 3
                or manager.config.main_mode == 4
            ):
                ignore_dirs = []
            try:
                # 获取所有需要刮削的影片列表
                movie_list = await movie_lists(ignore_dirs, manager.config.media_type, movie_path)
            except Exception:
                signal.show_traceback_log(traceback.format_exc())
                signal.show_log_text(traceback.format_exc())
            count_all = len(movie_list)
            signal.show_log_text(" 📺 Find " + str(count_all) + " movies")

    elif file_mode == FileMode.Single:  # 刮削单文件（工具页面）
        file_path = Flags.single_file_path
        if not await aiofiles.os.path.exists(file_path):
            signal.show_log_text(" 🔴 Movie file does not exist!")
        else:
            movie_list.append(file_path)  # 把文件路径添加到movie_list
            signal.show_log_text(f" 🖥 File path: {file_path}")
            if Flags.appoint_url:
                signal.show_log_text(" 🌐 File url: " + Flags.appoint_url)

    return movie_list


async def newtdisk_creat_symlink(
    copy_flag: bool,
    netdisk_path: Path | None = None,
    local_path: Path | None = None,
) -> None:
    from_tool = False
    if not netdisk_path:
        from_tool = True
        signal.change_buttons_status.emit()
    start_time = time.time()
    if not netdisk_path:
        netdisk_path = Path(manager.config.netdisk_path)
    if not local_path:
        local_path = Path(manager.config.localdisk_path)
    signal.show_log_text("🍯 🍯 🍯 开始创建符号链接")
    signal.show_log_text(f" 📁 源路径: {netdisk_path} \n 📁 目标路径：{local_path} \n")
    try:
        if not netdisk_path or not local_path:
            signal.show_log_text(f" 🔴 网盘目录和本地目录不能为空！请重新设置！({get_used_time(start_time)}s)")
            signal.show_log_text("================================================================================")
            if from_tool:
                signal.reset_buttons_status.emit()
            return
        copy_exts = [".nfo", ".jpg", ".png"] + manager.config.sub_type
        file_exts = "|".join(manager.config.media_type).lower().split("|") + copy_exts + manager.config.sub_type

        def task():
            total = 0
            copy_num = 0
            link_num = 0
            fail_num = 0
            skip_num = 0
            done = set()
            for root, _, files in netdisk_path.walk(top_down=True):
                if root == local_path:
                    continue

                local_dir = local_path / root.relative_to(netdisk_path)
                if not local_dir.is_dir():
                    os.makedirs(local_dir)
                for f in files:
                    # 跳过隐藏文件、预告片、主题视频
                    if f.startswith("."):
                        continue
                    if "trailer." in f or "trailers." in f:
                        continue
                    if "theme_video." in f:
                        continue
                    # 跳过未知扩展名
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in file_exts:
                        continue

                    total += 1
                    net_file = root / f
                    local_file = local_dir / f
                    if local_file.is_file():
                        signal.show_log_text(f" {total} 🟠 跳过: 已存在文件或有效的符号链接\n {net_file} ")
                        skip_num += 1
                        continue
                    if local_file.is_symlink():
                        signal.show_log_text(f" {total} 🔴 删除: 无效的符号链接\n {net_file} ")
                        local_file.unlink()

                    if ext in copy_exts:  # 直接复制的文件
                        if not copy_flag:
                            continue
                        copy_file_sync(net_file, local_file)
                        signal.show_log_text(f" {total} 🍀 Copy done!\n {net_file} ")
                        copy_num += 1
                        continue
                    # 不对原文件进行有效性检查以减小可能的网络 IO 开销
                    if net_file in done:
                        signal.show_log_text(
                            f" {total} 🟠 Link skip! Source file already linked, this file is duplicate!\n {net_file} "
                        )
                        skip_num += 1
                        continue
                    done.add(net_file)

                    try:
                        os.symlink(net_file, local_file)
                        signal.show_log_text(f" {total} 🍀 Link done!\n {net_file} ")
                        link_num += 1
                    except Exception as e:
                        print(traceback.format_exc())
                        error_info = ""
                        if "symbolic link privilege not held" in str(e):
                            error_info = "   \n没有创建权限，请尝试管理员权限！或按照教程开启用户权限： https://www.jianshu.com/p/0e307bfe8770"
                        signal.show_log_text(f" {total} 🔴 Link failed!{error_info} \n {net_file} ")
                        signal.show_log_text(traceback.format_exc())
                        fail_num += 1
            return total, copy_num, link_num, skip_num, fail_num

        total, copy_num, link_num, skip_num, fail_num = await asyncio.to_thread(task)
        signal.show_log_text(
            f"\n 🎉🎉🎉 All finished!!!({get_used_time(start_time)}s) Total {total} , "
            f"Linked {link_num} , Copied {copy_num} , Skiped {skip_num} , Failed {fail_num} "
        )
    except Exception:
        print(traceback.format_exc())
        signal.show_log_text(traceback.format_exc())

    signal.show_log_text("================================================================================")
    if from_tool:
        signal.reset_buttons_status.emit()


async def move_file_to_failed_folder(failed_folder: Path, file_path: Path, folder_old_path: Path) -> Path:
    # 更新模式、读取模式，不移动失败文件；不移动文件-关时，不移动； 软硬链接开时，不移动
    main_mode = manager.config.main_mode
    if main_mode == 3 or main_mode == 4 or not manager.config.failed_file_move or manager.config.soft_link != 0:
        LogBuffer.log().write(f"\n 🙊 [Movie] {file_path}")
        return file_path

    # 创建failed文件夹
    if manager.config.failed_file_move == 1 and not await aiofiles.os.path.exists(failed_folder):
        try:
            await aiofiles.os.makedirs(failed_folder)
        except Exception:
            signal.show_traceback_log(traceback.format_exc())
            signal.show_log_text(traceback.format_exc())

    # 获取文件路径
    file_full_name = file_path.name
    file_ext = file_path.suffix
    trailer_old_path_no_filename = folder_old_path / "trailers/trailer.mp4"
    trailer_old_path_with_filename = file_path.with_name(file_path.stem + "-trailer.mp4")

    # 重复改名
    file_new_path = failed_folder / file_full_name
    while await aiofiles.os.path.exists(file_new_path) and file_new_path != file_path:
        file_new_path = file_new_path.with_name(file_new_path.stem + "@" + file_ext)

    # 移动
    try:
        await move_file_async(file_path, file_new_path)
        LogBuffer.log().write("\n 🔴 Move file to the failed folder!")
        LogBuffer.log().write(f"\n 🙊 [Movie] {file_new_path}")
        error_info = LogBuffer.error().get()
        LogBuffer.error().clear()
        LogBuffer.error().write(error_info.replace(str(file_path), str(file_new_path)))

        # 同步移动预告片
        trailer_new_path = file_new_path.with_name(file_new_path.stem + "-trailer.mp4")
        if not await aiofiles.os.path.exists(trailer_new_path):
            try:
                has_trailer = False
                if await aiofiles.os.path.exists(trailer_old_path_with_filename):
                    has_trailer = True
                    await move_file_async(trailer_old_path_with_filename, trailer_new_path)
                elif await aiofiles.os.path.exists(trailer_old_path_no_filename):
                    has_trailer = True
                    await move_file_async(trailer_old_path_no_filename, trailer_new_path)
                if has_trailer:
                    LogBuffer.log().write("\n 🔴 Move trailer to the failed folder!")
                    LogBuffer.log().write(f"\n 🔴 [Trailer] {trailer_new_path}")
            except Exception as e:
                LogBuffer.log().write(f"\n 🔴 Failed to move trailer to the failed folder! \n    {str(e)}")

        # 同步移动字幕
        sub_types = [".chs" + i for i in manager.config.sub_type if ".chs" not in i]
        for sub in sub_types:
            sub_old_path = file_path.with_suffix(sub)
            sub_new_path = file_new_path.with_suffix(sub)
            if await aiofiles.os.path.exists(sub_old_path) and not await aiofiles.os.path.exists(sub_new_path):
                result, error_info = await move_file_async(sub_old_path, sub_new_path)
                if not result:
                    LogBuffer.log().write(f"\n 🔴 Failed to move sub to the failed folder!\n     {error_info}")
                else:
                    LogBuffer.log().write("\n 💡 Move sub to the failed folder!")
                    LogBuffer.log().write(f"\n 💡 [Sub] {sub_new_path}")
        return file_new_path
    except Exception as e:
        LogBuffer.log().write(f"\n 🔴 Failed to move the file to the failed folder! \n    {str(e)}")
        return file_path


async def check_file(file_path: Path, file_escape_size: float) -> bool:
    if await aiofiles.os.path.islink(file_path):
        file_path = file_path.resolve()
        if NoEscape.CHECK_SYMLINK not in manager.config.no_escape:
            return True

    if not await aiofiles.os.path.exists(file_path):
        LogBuffer.error().write("文件不存在")
        return False
    if NoEscape.NO_SKIP_SMALL_FILE not in manager.config.no_escape:
        file_size = await aiofiles.os.path.getsize(file_path) / float(1024 * 1024)
        if file_size < file_escape_size:
            LogBuffer.error().write(
                f"文件小于 {file_escape_size} MB 被过滤!（实际大小 {round(file_size, 2)} MB）已跳过刮削！"
            )
            return False
    return True


async def move_torrent(old_dir: Path, new_dir: Path, file_name: str, number: str, naming_rule: str):
    # 更新模式 或 读取模式
    if manager.config.main_mode == 3 or manager.config.main_mode == 4:
        if manager.config.update_mode == "c" and not manager.config.success_file_rename:
            return

    # 软硬链接开时，不移动
    elif (
        manager.config.soft_link != 0 or not manager.config.success_file_move and not manager.config.success_file_rename
    ):
        return
    torrent_file1 = old_dir / (file_name + ".torrent")
    torrent_file2 = old_dir / (number + ".torrent")
    torrent_file1_new_path = new_dir / (naming_rule + ".torrent")
    torrent_file2_new_path = new_dir / (number + ".torrent")
    if (
        await aiofiles.os.path.exists(torrent_file1)
        and torrent_file1 != torrent_file1_new_path
        and not await aiofiles.os.path.exists(torrent_file1_new_path)
    ):
        await move_file_async(torrent_file1, torrent_file1_new_path)
        LogBuffer.log().write("\n 🍀 Torrent done!")

    if torrent_file2 != torrent_file1 and (
        await aiofiles.os.path.exists(torrent_file2)
        and torrent_file2 != torrent_file2_new_path
        and not await aiofiles.os.path.exists(torrent_file2_new_path)
    ):
        await move_file_async(torrent_file2, torrent_file2_new_path)
        LogBuffer.log().write("\n 🍀 Torrent done!")


async def move_bif(old_dir: Path, new_dir: Path, file_name: str, naming_rule: str) -> None:
    # 更新模式 或 读取模式
    if manager.config.main_mode == 3 or manager.config.main_mode == 4:
        if manager.config.update_mode == "c" and not manager.config.success_file_rename:
            return

    elif not manager.config.success_file_move and not manager.config.success_file_rename:
        return
    bif_old_path = old_dir / (file_name + "-320-10.bif")
    bif_new_path = new_dir / (naming_rule + "-320-10.bif")
    if (
        bif_old_path != bif_new_path
        and await aiofiles.os.path.exists(bif_old_path)
        and not await aiofiles.os.path.exists(bif_new_path)
    ):
        await move_file_async(bif_old_path, bif_new_path)
        LogBuffer.log().write("\n 🍀 Bif done!")


async def move_trailer_video(old_dir: Path, new_dir: Path, file_name: str, naming_rule: str) -> None:
    if manager.config.main_mode < 2 and not manager.config.success_file_move and not manager.config.success_file_rename:
        return
    if manager.config.main_mode > 2:
        update_mode = manager.config.update_mode
        if update_mode == "c" and not manager.config.success_file_rename:
            return

    for media_type in manager.config.media_type:
        trailer_old_path = old_dir / (file_name + "-trailer" + media_type)
        trailer_new_path = new_dir / (naming_rule + "-trailer" + media_type)
        if await aiofiles.os.path.exists(trailer_old_path) and not await aiofiles.os.path.exists(trailer_new_path):
            await move_file_async(trailer_old_path, trailer_new_path)
            LogBuffer.log().write("\n 🍀 Trailer done!")
