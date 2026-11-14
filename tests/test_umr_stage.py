import xml.etree.ElementTree as ET

import pytest

from mdcx.config.enums import CDChar, NfoInclude, SuffixSort, TagInclude
from mdcx.config.manager import manager
from mdcx.core.file import get_file_info_v2, get_output_name
from mdcx.core.naming import NameRenderOptions, NamingTarget, render_name
from mdcx.core.nfo import get_nfo_data, write_nfo
from mdcx.core.tag_priority import prioritize_nfo_tags
from mdcx.core.translate import translate_info
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags
from mdcx.models.types import CrawlersResult
from mdcx.number import get_file_number


@pytest.fixture(autouse=True)
def stage_config(monkeypatch):
    # 所有输入及输出均为测试临时文件，配置修改仅在内存中生效。
    values = {
        "umr_style": "-破解",
        "cnword_style": "-C",
        "cnword_char": ["-C.", "-C-", "ch.", "字幕"],
        "suffix_sort": [SuffixSort.MOWORD, SuffixSort.CNWORD, SuffixSort.DEFINITION],
        "cd_char": [CDChar.LETTER, CDChar.ENDC, CDChar.DIGITAL, CDChar.MIDDLE_NUMBER],
        "cd_name": 1,
        "prevent_char": "",
        "sub_type": [".srt"],
        "string": [],
        "no_escape": [],
        "main_mode": 1,
        "success_file_rename": True,
        "success_file_move": True,
        "soft_link": 0,
        "naming_file": "{{ number }}",
        "folder_name": "{{ number }}",
        "folder_moword": True,
        "folder_cnword": True,
        "file_moword": True,
        "file_cnword": True,
        "file_hd": False,
        "file_name_max": 200,
        "subtitle_add": False,
    }
    for key, value in values.items():
        monkeypatch.setattr(manager.config, key, value)
    monkeypatch.setattr(Flags, "file_mode", FileMode.Default)


def result_for(info):
    data = CrawlersResult.empty()
    data.number = info.number
    data.title = "测试标题"
    data.mosaic = info.mosaic
    return data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "expected", "subtitle", "cd", "stage"),
    [
        ("-LTX", "-破解-LTX", False, "", "LTX"),
        ("-U-LTX", "-破解-LTX", False, "", "LTX"),
        ("-UC", "-破解-C", True, "", ""),
        ("-UCL", "-破解-CL", True, "", "L"),
        ("-UCLTX", "-破解-CLTX", True, "", "LTX"),
        ("-U", "-破解", False, "", ""),
        ("-破解-L", "-破解-L", False, "", "L"),
        ("-破解-C", "-破解-C", True, "", ""),
        ("-破解-CL", "-破解-CL", True, "", "L"),
        ("-破解-LTX", "-破解-LTX", False, "", "LTX"),
        ("-破解-C-LTX", "-破解-CLTX", True, "", "LTX"),
        ("-破解-CLTX", "-破解-CLTX", True, "", "LTX"),
        ("-LTX-CD1", "-破解-LTX", False, "-CD1", "LTX"),
        ("-UC-CD1", "-破解-C", True, "-CD1", ""),
        ("-UCL-CD2", "-破解-CL", True, "-CD2", "L"),
        ("-UCLTX-CD1", "-破解-CLTX", True, "-CD1", "LTX"),
        ("-破解-L-CD1", "-破解-L", False, "-CD1", "L"),
        ("-破解-C-CD2", "-破解-C", True, "-CD2", ""),
        ("-破解-CL-CD2", "-破解-CL", True, "-CD2", "L"),
        ("-破解-LTX-CD1", "-破解-LTX", False, "-CD1", "LTX"),
        ("-破解-C-LTX-CD2", "-破解-CLTX", True, "-CD2", "LTX"),
        ("-破解-CLTX-CD1", "-破解-CLTX", True, "-CD1", "LTX"),
        ("-ltx", "-破解-LTX", False, "", "LTX"),
        ("-ucl", "-破解-CL", True, "", "L"),
        ("-ucltx", "-破解-CLTX", True, "", "LTX"),
        ("-uc4k", "-破解-C", True, "", ""),
    ],
)
async def test_stage_output_and_rescrape_are_idempotent(tmp_path, suffix, expected, subtitle, cd, stage):
    path = tmp_path / f"TEST-123{suffix}.mp4"
    info = await get_file_info_v2(path, copy_sub=False)
    assert get_file_number(str(path), []) == info.number == "TEST-123"
    assert info.destroyed == "-破解"
    assert info.mosaic == "无码破解"
    assert info.has_sub is subtitle
    assert info.umr_stage == stage
    assert info.c_word == ("-C" if subtitle else "")
    assert info.cd_part == cd
    assert info.crawl_task().destroyed == "-破解"
    assert info.crawl_task().mosaic == "无码破解"
    assert info.file_show_name == f"TEST-123{expected}{cd}"
    output = get_output_name(info, result_for(info), tmp_path, ".mp4")
    assert output[0].name == f"TEST-123{expected}"
    assert output[1].name == f"TEST-123{expected}{cd}.mp4"
    assert output[2].name == f"TEST-123{expected}{cd}.nfo"
    again = await get_file_info_v2(output[1], copy_sub=False)
    assert again.file_show_name == info.file_show_name
    assert again.cd_part == info.cd_part
    assert again.has_sub is subtitle
    assert again.umr_stage == stage
    assert get_output_name(again, result_for(again), tmp_path, ".mp4")[:3] == output[:3]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "expected_cd", "sub"),
    [
        ("-L", "-CD12", False),
        ("-C", "-CD3", False),
        ("-CD1", "-CD1", False),
        ("-U-CD1", "-CD1", False),
    ],
)
async def test_unrelated_cd_rules_are_unchanged(tmp_path, suffix, expected_cd, sub):
    info = await get_file_info_v2(tmp_path / f"TEST-123{suffix}.mp4", copy_sub=False)
    assert info.cd_part == expected_cd
    assert info.has_sub is sub
    assert info.umr_stage == ""


@pytest.mark.asyncio
async def test_plain_c_subtitle_rule_and_letter_setting_remain_configurable(tmp_path, monkeypatch):
    monkeypatch.setattr(manager.config, "cd_char", [CDChar.LETTER])
    info = await get_file_info_v2(tmp_path / "TEST-123-C.mp4", copy_sub=False)
    assert info.cd_part == ""
    assert info.has_sub
    assert info.file_show_name == "TEST-123-C"
    monkeypatch.setattr(manager.config, "cd_char", [])
    info = await get_file_info_v2(tmp_path / "TEST-123-L.mp4", copy_sub=False)
    assert info.cd_part == ""
    assert info.destroyed == info.umr_stage == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        ("-LTX", "-修复-LTX"),
        ("-UC", "-修复-中字"),
        ("-UCL", "-修复-中字L"),
        ("-UCLTX", "-修复-中字LTX"),
        ("-修复-L", "-修复-L"),
        ("-修复-中字", "-修复-中字"),
        ("-修复-中字L", "-修复-中字L"),
        ("-修复-LTX", "-修复-LTX"),
        ("-修复-中字-LTX", "-修复-中字LTX"),
        ("-修复-中字LTX", "-修复-中字LTX"),
    ],
)
async def test_custom_markers_and_cd_roundtrip(tmp_path, monkeypatch, suffix, expected):
    monkeypatch.setattr(manager.config, "umr_style", "-修复")
    monkeypatch.setattr(manager.config, "cnword_style", "-中字")
    info = await get_file_info_v2(tmp_path / f"TEST-123{suffix}-CD1.mp4", copy_sub=False)
    assert info.file_show_name == f"TEST-123{expected}-CD1"
    output = get_output_name(info, result_for(info), tmp_path, ".mp4")
    assert output[1].stem == info.file_show_name
    again = await get_file_info_v2(output[1], copy_sub=False)
    assert again.file_show_name == info.file_show_name
    assert again.cd_part == "-CD1"


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["-UHD", "-LTXextra", "-破解-LTXextra"])
async def test_stage_requires_a_complete_token(tmp_path, suffix):
    info = await get_file_info_v2(tmp_path / f"TEST-123{suffix}.mp4", copy_sub=False)
    assert info.umr_stage == ""


@pytest.mark.asyncio
async def test_ltx_number_prefix_is_not_a_stage_marker(tmp_path):
    info = await get_file_info_v2(tmp_path / "LTX-123.mp4", copy_sub=False)
    assert info.number == "LTX-123"
    assert info.umr_stage == info.destroyed == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("moword", "cnword", "expected"),
    [
        (True, True, "TEST-123-破解-CLTX"),
        (True, False, "TEST-123-破解-LTX"),
        (False, True, "TEST-123-C"),
        (False, False, "TEST-123"),
    ],
)
async def test_display_switches_and_explicit_fields(tmp_path, monkeypatch, moword, cnword, expected):
    monkeypatch.setattr(manager.config, "file_moword", moword)
    monkeypatch.setattr(manager.config, "file_cnword", cnword)
    info = await get_file_info_v2(tmp_path / "TEST-123-UCLTX.mp4", copy_sub=False)
    data = result_for(info)
    assert get_output_name(info, data, tmp_path, ".mp4")[1].stem == expected
    rendered = render_name("{{ moword }} {{ cnword }}", info, data, NameRenderOptions(target=NamingTarget.NFO_TITLE))
    assert rendered.text == "-破解-LTX -C"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix",
    ["-U", "-UC", "-UCL", "-UCLTX", "-破解-L", "-破解-C", "-破解-CL", "-破解-LTX", "-破解-C-LTX", "-破解-CLTX"],
)
async def test_actual_nfo_keeps_tags_and_renders_explicit_version(tmp_path, monkeypatch, suffix):
    for key, value in {
        "download_files": [],
        "keep_files": [],
        "outline_format": [],
        "naming_media": "{{ number }} {{ moword }} {{ cnword }}",
        "nfo_include_new": [NfoInclude.TAG, NfoInclude.GENRE],
    }.items():
        monkeypatch.setattr(manager.config, key, value)
    info = await get_file_info_v2(tmp_path / f"TEST-123{suffix}.mp4", copy_sub=False)
    data = result_for(info)
    data.tags = ["无码破解"] + (["中文字幕"] if info.has_sub else [])
    output = get_output_name(info, data, tmp_path, ".mp4")
    nfo_path = output[2]
    assert await write_nfo(info, data, nfo_path, output[0], update=True)
    root = ET.parse(nfo_path).getroot()
    assert {node.text for node in root.findall("./tag")} == set(data.tags)
    assert {node.text for node in root.findall("./genre")} == set(data.tags)
    title = root.findtext("title")
    assert title.startswith("TEST-123 -破解")
    if info.umr_stage:
        assert info.umr_stage in title


@pytest.mark.asyncio
async def test_local_subtitle_and_default_nfo_title(tmp_path, monkeypatch):
    path = tmp_path / "TEST-123-LTX.mp4"
    path.with_suffix(".srt").write_text("", encoding="utf-8")
    info = await get_file_info_v2(path, copy_sub=False)
    assert info.file_show_name == "TEST-123-破解-CLTX"
    assert info.sub_list == [".srt"]
    for key, value in {
        "download_files": [],
        "keep_files": [],
        "outline_format": [],
        "naming_media": "{{ number }} {{ title }}",
        "nfo_include_new": [],
    }.items():
        monkeypatch.setattr(manager.config, key, value)
    nfo_path = path.with_suffix(".nfo")
    assert await write_nfo(info, result_for(info), nfo_path, tmp_path, update=True)
    assert ET.parse(nfo_path).getroot().findtext("title") == "TEST-123 测试标题"


def test_acceptance_ui_terms_match_source():
    # 验收入口来自本次源码，不把它当作 J 已安装版本的界面实测。
    from pathlib import Path

    root = ET.parse(Path("mdcx/views/MDCx.ui")).getroot()
    expected = {
        "pushButton_tool": "工具",
        "pushButton_select_file": "选择文件",
        "pushButton_start_single_file": "刮削",
    }
    for name, text in expected.items():
        assert root.find(f'.//widget[@name="{name}"]/property[@name="text"]/string').text.strip() == text
    assert root.find(
        './/widget[@name="page_tool"]//widget[@name="groupBox_7"]/property[@name="title"]/string'
    ).text.startswith("单文件刮削")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "expected_tags"),
    [
        ("-UCLTX", ["中文字幕", "无码破解", "LTX破解"]),
        ("-UCL", ["中文字幕", "无码破解", "L破解"]),
        ("-UC", ["中文字幕", "无码破解"]),
        ("-UC4K", ["中文字幕", "无码破解"]),
        ("-破解-C-LTX", ["中文字幕", "无码破解", "LTX破解"]),
        ("-破解-LTX", ["无码破解", "LTX破解"]),
        ("-破解-L", ["无码破解", "L破解"]),
        ("-破解-C", ["中文字幕", "无码破解"]),
    ],
)
async def test_nfo_stage_tags_written_and_rescrape_deduplicated(tmp_path, monkeypatch, suffix, expected_tags):
    for key, value in {
        "download_files": [],
        "keep_files": [],
        "outline_format": [],
        "naming_media": "{{ number }} {{ title }}",
        "nfo_include_new": [NfoInclude.TAG, NfoInclude.GENRE],
        "nfo_tag_include": [TagInclude.MOSAIC, TagInclude.CNWORD],
    }.items():
        monkeypatch.setattr(manager.config, key, value)

    video_path = tmp_path / f"TEST-123{suffix}.mp4"
    info = await get_file_info_v2(video_path, copy_sub=False)
    data = result_for(info)
    data.tag = "普通标签,LTX破解,L破解,无码破解"
    translate_info(data, info.has_sub, info.umr_stage)
    assert [t for t in data.tags if t != "普通标签"] == expected_tags

    output = get_output_name(info, data, tmp_path, ".mp4")
    nfo_path = output[2]
    assert await write_nfo(info, data, nfo_path, output[0], update=True)
    root = ET.parse(nfo_path).getroot()
    tag_nodes = [node.text for node in root.findall("./tag")]
    genre_nodes = [node.text for node in root.findall("./genre")]
    assert tag_nodes == genre_nodes
    assert [t for t in tag_nodes if t != "普通标签"] == expected_tags
    for expected_tag in expected_tags:
        assert tag_nodes.count(expected_tag) == 1

    # 模拟再刮：从已有 NFO 读回并再次组装标签，不应重复
    nfo_path.rename(output[1].with_suffix(".nfo"))
    loaded, _ = await get_nfo_data(output[1], info.number)
    assert loaded is not None
    again_info = await get_file_info_v2(output[1], copy_sub=False)
    translate_info(loaded, again_info.has_sub, again_info.umr_stage)
    assert [t for t in loaded.tags if t != "普通标签"] == expected_tags


@pytest.mark.asyncio
async def test_manual_rename_c_to_cl_adds_l_stage_tag_on_rescrape(tmp_path, monkeypatch):
    for key, value in {
        "download_files": [],
        "keep_files": [],
        "outline_format": [],
        "naming_media": "{{ number }} {{ title }}",
        "nfo_include_new": [NfoInclude.TAG, NfoInclude.GENRE],
        "nfo_tag_include": [TagInclude.MOSAIC, TagInclude.CNWORD],
    }.items():
        monkeypatch.setattr(manager.config, key, value)

    # 先按 -UC 刮出无阶段 NFO
    uc_path = tmp_path / "TEST-123-UC.mp4"
    uc_info = await get_file_info_v2(uc_path, copy_sub=False)
    uc_data = result_for(uc_info)
    translate_info(uc_data, uc_info.has_sub, uc_info.umr_stage)
    nfo_path = tmp_path / "TEST-123-破解-C.nfo"
    assert await write_nfo(uc_info, uc_data, nfo_path, tmp_path, update=True)

    # 手动改名为 -破解-CL 后再刮，识别成 L 阶段并补上 L破解 标签
    manual_video = tmp_path / "TEST-123-破解-CL.mp4"
    nfo_path.rename(manual_video.with_suffix(".nfo"))
    loaded, _ = await get_nfo_data(manual_video, "TEST-123")
    assert loaded is not None
    manual_info = await get_file_info_v2(manual_video, copy_sub=False)
    assert manual_info.umr_stage == "L"
    assert manual_info.has_sub is True
    assert manual_info.file_show_name == "TEST-123-破解-CL"
    translate_info(loaded, manual_info.has_sub, manual_info.umr_stage)
    assert loaded.tags == ["中文字幕", "无码破解", "L破解"]
    assert await write_nfo(manual_info, loaded, manual_video.with_suffix(".nfo"), tmp_path, update=True)
    root = ET.parse(manual_video.with_suffix(".nfo")).getroot()
    assert [node.text for node in root.findall("./tag")] == ["中文字幕", "无码破解", "L破解"]
    assert [node.text for node in root.findall("./genre")] == ["中文字幕", "无码破解", "L破解"]


@pytest.mark.asyncio
async def test_nfo_stage_tags_respect_mosaic_toggle(tmp_path, monkeypatch):
    monkeypatch.setattr(manager.config, "nfo_tag_include", [TagInclude.CNWORD])
    info = await get_file_info_v2(tmp_path / "TEST-123-UCLTX.mp4", copy_sub=False)
    data = result_for(info)
    data.tag = "普通标签,LTX破解,无码破解"
    translate_info(data, info.has_sub, info.umr_stage)
    assert data.tags == ["普通标签", "中文字幕"]


def test_stage_tags_are_treated_as_non_content_in_tag_priority():
    assert prioritize_nfo_tags(["LTX破解", "L破解", "无码破解"]) == ["LTX破解", "L破解", "无码破解"]
