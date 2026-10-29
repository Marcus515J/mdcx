import pytest
from lxml import etree

from mdcx.config.enums import NfoInclude
from mdcx.core import nfo as nfo_module
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.types import CrawlersResult, FileInfo, score_to_10


class _RenderedTitle:
    def __init__(self, text: str):
        self.text = text


def _build_file_info(tmp_path) -> FileInfo:
    file_info = FileInfo.empty()
    file_info.number = "ABC-123"
    file_info.file_path = tmp_path / "ABC-123.mp4"
    file_info.folder_path = tmp_path
    file_info.file_name = "ABC-123"
    return file_info


def _configure_nfo_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nfo_module.manager.config, "download_files", [])
    monkeypatch.setattr(nfo_module.manager.config, "keep_files", [])
    monkeypatch.setattr(nfo_module.manager.config, "outline_format", [])
    monkeypatch.setattr(nfo_module.manager.config, "main_mode", 1)
    monkeypatch.setattr(nfo_module.manager.config, "naming_media", "number title")
    monkeypatch.setattr(nfo_module.manager.config, "update_titletemplate", "number title")
    monkeypatch.setattr(nfo_module.manager.config, "nfo_include_new", [NfoInclude.SCORE, NfoInclude.WANTED])
    monkeypatch.setattr(nfo_module.manager.config, "nfo_tagline", "release")
    monkeypatch.setattr(nfo_module.manager.config, "actor_no_name", "佚名")
    monkeypatch.setattr(nfo_module, "render_name", lambda *args, **kwargs: _RenderedTitle("标题"))


def _build_data() -> CrawlersResult:
    data = CrawlersResult.empty()
    data.number = "ABC-123"
    data.title = "标题"
    data.score = "4.20"
    data.score_max = "5"
    data.score_count = "123"
    data.wanted = "99"
    data.field_sources[CrawlerResultFields.SCORE] = "javlibrary"
    data.field_sources[CrawlerResultFields.WANTED] = "javlibrary"
    return data


def test_score_to_10():
    assert score_to_10("4.20", "5") == "8.4"
    assert score_to_10("4.53", "5") == "9.06"
    assert score_to_10("8.4", "10") == "8.4"
    assert score_to_10("", "5") == ""
    assert score_to_10("4.2", "") == ""
    assert score_to_10("0", "5") == ""
    assert score_to_10("0.0", "5") == ""
    assert score_to_10("abc", "5") == ""


@pytest.mark.asyncio
async def test_write_nfo_rating_votes_wanted_new_format(monkeypatch: pytest.MonkeyPatch, tmp_path):
    _configure_nfo_writer(monkeypatch)
    data = _build_data()

    nfo_file = tmp_path / "ABC-123.nfo"
    result = await nfo_module.write_nfo(_build_file_info(tmp_path), data, nfo_file, tmp_path, update=True)

    assert result is True
    root = etree.fromstring(nfo_file.read_bytes())
    assert root.findtext("rating") == "8.4"
    assert root.findtext("ratingsource") == "javlibrary"
    assert root.findtext("votes") == "123"
    assert root.findtext("wanted") == "99"
    assert root.findtext("wantedsource") == "javlibrary"
    assert root.findtext("criticrating") is None


@pytest.mark.asyncio
async def test_write_nfo_omits_rating_when_max_unknown_or_zero(monkeypatch: pytest.MonkeyPatch, tmp_path):
    _configure_nfo_writer(monkeypatch)

    data = _build_data()
    data.score_max = ""
    data.score_count = ""
    nfo_file = tmp_path / "ABC-123.nfo"
    assert await nfo_module.write_nfo(_build_file_info(tmp_path), data, nfo_file, tmp_path, update=True) is True
    root = etree.fromstring(nfo_file.read_bytes())
    assert root.findtext("rating") is None
    assert root.findtext("votes") is None
    assert root.findtext("ratingsource") is None
    assert root.findtext("wanted") == "99"

    data = _build_data()
    data.score = "0.0"
    data.score_count = ""
    assert await nfo_module.write_nfo(_build_file_info(tmp_path), data, nfo_file, tmp_path, update=True) is True
    root = etree.fromstring(nfo_file.read_bytes())
    assert root.findtext("rating") is None
    assert root.findtext("votes") is None

    data = _build_data()
    data.score = ""
    data.score_max = ""
    data.score_count = ""
    assert await nfo_module.write_nfo(_build_file_info(tmp_path), data, nfo_file, tmp_path, update=True) is True
    root = etree.fromstring(nfo_file.read_bytes())
    assert root.findtext("rating") is None
    assert root.findtext("votes") is None


@pytest.mark.asyncio
async def test_write_nfo_omits_votes_when_count_unknown(monkeypatch: pytest.MonkeyPatch, tmp_path):
    _configure_nfo_writer(monkeypatch)
    data = _build_data()
    data.score_count = ""

    nfo_file = tmp_path / "ABC-123.nfo"
    assert await nfo_module.write_nfo(_build_file_info(tmp_path), data, nfo_file, tmp_path, update=True) is True
    root = etree.fromstring(nfo_file.read_bytes())
    assert root.findtext("rating") == "8.4"
    assert root.findtext("ratingsource") == "javlibrary"
    assert root.findtext("votes") is None


@pytest.mark.asyncio
async def test_read_nfo_new_format_round_trip(tmp_path):
    nfo_file = tmp_path / "ABC-123.nfo"
    nfo_file.write_text(
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>ABC-123 标题</title>
  <rating>8.4</rating>
  <ratingsource>javlibrary</ratingsource>
  <votes>123</votes>
  <wanted>99</wanted>
  <wantedsource>javdb</wantedsource>
</movie>
""",
        encoding="utf-8",
    )

    json_data, _ = await nfo_module.get_nfo_data(tmp_path / "ABC-123.mp4", "ABC-123")

    assert json_data is not None
    assert json_data.score == "8.4"
    assert json_data.score_max == "10"
    assert json_data.score_count == "123"
    assert json_data.wanted == "99"
    assert json_data.field_sources[CrawlerResultFields.SCORE] == "javlibrary"
    assert json_data.field_sources[CrawlerResultFields.WANTED] == "javdb"


@pytest.mark.asyncio
async def test_read_nfo_old_format_votes_is_wanted_not_score_count(tmp_path):
    nfo_file = tmp_path / "ABC-123.nfo"
    nfo_file.write_text(
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>ABC-123 标题</title>
  <rating>4.2</rating>
  <criticrating>42</criticrating>
  <votes>88</votes>
</movie>
""",
        encoding="utf-8",
    )

    json_data, _ = await nfo_module.get_nfo_data(tmp_path / "ABC-123.mp4", "ABC-123")

    assert json_data is not None
    assert json_data.score == "4.2"
    # 旧格式 rating 原样保留数值, 回写不再换算
    assert json_data.score_max == "10"
    # 旧 votes 为想看人数, 不能认作评分人数
    assert json_data.score_count == ""
    assert json_data.wanted == "88"
