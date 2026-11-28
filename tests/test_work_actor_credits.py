"""Work credit resolution uses fictional names and never contacts external sites."""

import pytest
from lxml import etree

from mdcx.config.enums import FieldRule, FixedScrapingType, Language
from mdcx.config.manager import manager
from mdcx.config.models import Config
from mdcx.config.resources import resources
from mdcx.core.actor_quality import confirm_work_actor_credits
from mdcx.core.translate import map_actor_names, translate_actor
from mdcx.core.utils import deal_some_field
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.log_buffer import LogBuffer
from mdcx.models.types import CrawlersResult


@pytest.fixture
def setup_credits(monkeypatch):
    config = Config()
    config.actor_realname = False
    monkeypatch.setattr(manager, "config", config)
    monkeypatch.setattr(
        resources,
        "actor_mapping_data",
        etree.fromstring("""
        <html><a jp="星野甲" zh_cn="星野简甲" zh_tw="星野繁甲" keyword=",星野甲,月野乙,"/>
        <a jp="空野丙" zh_cn="空野简丙" zh_tw="空野繁丙" keyword=",空野丙,"/></html>
    """),
    )
    messages = []
    monkeypatch.setattr(LogBuffer.log(), "write", messages.append)
    return config, messages


def result(kind=FixedScrapingType.YOUMA):
    res = CrawlersResult.empty()
    res.number = "FICTION-001"
    res.scraping_type = kind
    res.actors = ["星野甲（月野乙）"]
    res.all_actors = ["空野丙", "星野甲", "星野甲（月野乙）", "月野乙"]
    return res


@pytest.mark.parametrize("kind", [FixedScrapingType.YOUMA, FixedScrapingType.WUMA])
@pytest.mark.parametrize("field", ["title", "outline"])
@pytest.mark.parametrize("credit", ["星野甲", "月野乙"])
@pytest.mark.parametrize("del_char", [False, True])
@pytest.mark.parametrize("brackets", ["星野甲（月野乙）", "星野甲(月野乙)"])
def test_unique_credit_and_all_actors(setup_credits, kind, field, credit, del_char, brackets):
    config, messages = setup_credits
    config.fields_rule = [FieldRule.DEL_CHAR] if del_char else []
    res = result(kind)
    res.actors = [brackets]
    setattr(res, field, "虚构作品 " + credit)
    deal_some_field(res)
    assert res.actors == [credit]
    assert res.all_actors == ["空野丙", credit]
    assert not messages
    # A later translated title cannot change a decision made from raw evidence.
    res.title = "月野乙 星野甲"
    res.outline = ""
    deal_some_field(res)
    assert res.actors == [credit]
    assert res._work_actor_credits == ({credit}, set())


@pytest.mark.parametrize("text", ["星野甲 月野乙", "虚构作品"])
@pytest.mark.parametrize("del_char", [False, True])
def test_ambiguous_preserved_and_logged_once(setup_credits, text, del_char):
    config, messages = setup_credits
    config.fields_rule = [FieldRule.DEL_CHAR] if del_char else []
    res = result()
    res.title = text
    deal_some_field(res)
    res.title = "月野乙"
    deal_some_field(res)
    assert res.actors == ["星野甲（月野乙）"]
    assert res.all_actors == ["空野丙", "星野甲", "星野甲（月野乙）", "月野乙"]
    assert messages == ["\n ⚪ 演员署名未确认"]


@pytest.mark.parametrize("name", ["星野甲（２４歳）", "星野甲(24)", "空野丙"])
@pytest.mark.parametrize("del_char", [False, True])
def test_non_combinations_keep_cleanup(setup_credits, name, del_char):
    config, messages = setup_credits
    config.fields_rule = [FieldRule.DEL_CHAR] if del_char else []
    res = result()
    res.actors = res.all_actors = [name]
    deal_some_field(res)
    expected = name.split("（")[0].split("(")[0] if del_char else name
    assert res.actors == res.all_actors == [expected]
    assert res._work_actor_credits == (set(), set())
    assert not messages


def test_normalizes_width_before_substring_match(setup_credits):
    res = result()
    res.actors = ["STARNAME(MOONNAME)"]
    res.all_actors = []
    res.outline = "虚构作品 ＭＯＯＮＮＡＭＥ"
    deal_some_field(res)
    assert res.actors == ["MOONNAME"]


@pytest.mark.parametrize("kind", [FixedScrapingType.SUREN, FixedScrapingType.FC2])
@pytest.mark.parametrize("del_char", [False, True])
def test_excluded_types_unchanged(setup_credits, kind, del_char):
    config, messages = setup_credits
    config.fields_rule = [FieldRule.DEL_CHAR] if del_char else []
    res = result(kind)
    res.title = "月野乙"
    assert confirm_work_actor_credits(res) == (set(), set())
    assert not hasattr(res, "_work_actor_credits")
    deal_some_field(res)
    assert res.actors == (["星野甲"] if del_char else ["星野甲（月野乙）"])
    assert not messages


@pytest.mark.parametrize("credit, expected", [("星野甲", "星野简甲"), ("月野乙", "月野乙")])
@pytest.mark.parametrize("lang", [Language.ZH_CN, Language.ZH_TW, Language.JP])
async def test_confirmed_credit_mapping_pipeline(setup_credits, credit, expected, lang):
    config, _ = setup_credits
    for field in (CrawlerResultFields.ACTORS, CrawlerResultFields.ALL_ACTORS):
        config.get_field_config(field).language = lang
        config.get_field_config(field).translate = True
    res = result()
    res.title = "虚构作品 " + credit
    deal_some_field(res)
    deal_some_field(res)
    await translate_actor(res)
    expected = {"zh_cn": expected, "zh_tw": expected.replace("简", "繁"), "jp": credit}[lang]
    other = {"zh_cn": "空野简丙", "zh_tw": "空野繁丙", "jp": "空野丙"}[lang]
    assert res.actors == [expected]
    assert res.all_actors == [other, expected]


def test_jp_main_takes_priority_over_keyword_match(setup_credits):
    config, _ = setup_credits
    config.get_field_config(CrawlerResultFields.ACTORS).language = Language.ZH_CN
    resources.actor_mapping_data.insert(
        0, etree.fromstring('<a jp="雨野丁" zh_cn="雨野简丁" keyword=",月野乙,星野甲,"/>')
    )
    res = result()
    res.title = "星野甲"
    deal_some_field(res)
    map_actor_names(res)
    assert res.actors == ["星野简甲"]


@pytest.mark.parametrize("confirmed", [False, True])
def test_no_mapping_table_keeps_input(setup_credits, confirmed):
    res = result()
    if confirmed:
        res.title = "月野乙"
    deal_some_field(res)
    before = res.actors[:]
    resources.actor_mapping_data = None
    map_actor_names(res)
    assert res.actors == before


def test_unconfirmed_and_plain_keep_existing_mapping(setup_credits):
    config, _ = setup_credits
    config.get_field_config(CrawlerResultFields.ACTORS).language = Language.ZH_CN
    res = result()
    res.actors += ["月野乙", "空野丙"]
    deal_some_field(res)
    map_actor_names(res)
    assert res.actors == ["星野甲（月野乙）", "星野简甲", "空野简丙"]
