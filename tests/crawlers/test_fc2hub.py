from pathlib import Path

import pytest
from lxml import etree

from mdcx.config.enums import Language
from mdcx.config.manager import manager
from mdcx.crawlers.fc2hub import Fc2hubCrawler, getOutline
from mdcx.models.types import CrawlerInput

DATA_DIR = Path(__file__).parent / "data" / "fc2hub"


def _load_sample_tree(number: str):
    html_text = (DATA_DIR / f"{number}.html").read_text(encoding="utf-8")
    return etree.fromstring(html_text, etree.HTMLParser())


class FakeFc2hubClient:
    async def get_text(self, url, **kwargs):
        if url == "https://javten.com/search?kw=1940476":
            return '<html><head><link href="https://javten.com/id1940476/" /></head></html>', ""
        if url == "https://javten.com/id1940476/":
            return (
                """
                <html>
                  <body>
                    <h1>FC2-1940476</h1><h1>Hub Sample Title</h1>
                    <a data-fancybox="gallery" href="//example.test/cover.jpg"></a>
                    <div style="padding: 0"><a href="//example.test/extra.jpg"></a></div>
                    <div class="col-8">seller</div>
                    <p class="card-text"><a href="/tag/a">tag-a</a><a href="/tag/b">tag-b</a></p>
                    <div class="col des">outline text</div>
                    <div class="player-api" data-id="4866909"></div>
                  </body>
                </html>
                """,
                "",
            )
        if url == "https://adult.contents.fc2.com/api/v2/videos/4866909/sample":
            return '{"path":"https://example.test/hub.mp4?mid=token"}', ""
        return None, f"unexpected url: {url}"


@pytest.mark.asyncio
async def test_fc2hub_crawler_searches_detail_and_sample_api(monkeypatch):
    monkeypatch.setattr(manager.config, "fields_rule", "")
    crawler = Fc2hubCrawler(client=FakeFc2hubClient(), base_url="https://javten.com")
    res = await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="FC2-1940476",
            short_number="FC2-1940476",
            language=Language.UNDEFINED,
            org_language=Language.UNDEFINED,
        )
    )

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.data.number == "FC2-1940476"
    assert res.data.title == "Hub Sample Title"
    assert res.data.outline == "outline text"
    assert res.data.originalplot == "outline text"
    assert res.data.tags == ["tag-a", "tag-b"]
    assert res.data.studio == "seller"
    assert res.data.thumb == "https://example.test/cover.jpg"
    assert res.data.extrafanart == ["https://example.test/extra.jpg"]
    assert res.data.trailer == "https://example.test/hub.mp4?mid=token"
    assert res.data.source == "fc2hub"


@pytest.mark.parametrize(
    "number",
    [
        "FC2-4851122",
        "FC2-857170",
        "FC2-725517",
        "FC2-972018",
        "FC2-832286",
        "FC2-4676584",
        "FC2-4960750",
        "FC2-1013835",
    ],
)
def test_fc2hub_outline_excludes_scripts_styles_and_watermarks(number: str):
    raw_html = (DATA_DIR / f"{number}.html").read_text(encoding="utf-8")
    # Inject inline Cloudflare challenge script and style inside <div class="col des">
    injected_html = raw_html.replace(
        "</body>\n            </div>",
        "<style>.des-hidden{display:none}</style>"
        "<script>(function(){function c(){var b=a.contentDocument||a.contentWindow.document;"
        "if(b){var d=b.createElement('script');d.innerHTML=\"window.__CF$cv$params={r:'9d2922a3ce230973'}\";"
        "b.getElementsByTagName('head')[0].appendChild(d)}}})();</script></body>\n            </div>",
        1,
    )
    tree = etree.fromstring(injected_html, etree.HTMLParser())
    outline = getOutline(tree)

    assert outline
    assert "\n" in outline
    assert "window.__CF$cv$params" not in outline
    assert "createElement" not in outline
    assert "cloudflareinsights" not in outline
    assert ".des-hidden" not in outline
    assert "MC45MDRjMDg5ZS" not in outline
    assert "MC45NTFjMTI4My" not in outline


def test_fc2hub_4851122_excludes_adjacent_works_and_keeps_main_plot():
    tree = _load_sample_tree("FC2-4851122")
    outline = getOutline(tree)

    # Adjacent work titles and recommendation blocks must not appear
    assert "【豪華６発射】" not in outline
    assert "【特別２作品！】" not in outline
    assert "聖なる夜をサンタコスプレで彩る" not in outline
    assert "fc2おすすめVR" not in outline
    assert "レジェンド女優" not in outline
    # Top discount banner and bottom video specs/disclaimers must not appear
    assert "1980（3日間限定）" not in outline
    assert "[動画情報]" not in outline
    assert "[注意事項]" not in outline

    # Main plot must be preserved intact
    assert outline.startswith("色白アマチュアバンドボーカル vs ジゴロアニキ ＆ 中出し大好きボーイ タクヤ")
    assert "ステージの上で可愛く、キレイな美声を轟かせ、観客を盛り上げる美女ヴォーカルのなつこちゃん。" in outline
    assert (
        "「夏のワタシはフラミンゴ（仮）」でファンとなつこちゃん共に盛り上がっているのを見るのが楽しみです！！"
        in outline
    )


@pytest.mark.parametrize(
    "number, expected_snippet, forbidden_snippets",
    [
        (
            "FC2-4851122",
            "ステージの上で可愛く、キレイな美声を轟かせ、観客を盛り上げる美女ヴォーカルのなつこちゃん。",
            ["聖なる夜をサンタコスプレで彩る", "[動画情報]", "1980（3日間限定）"],
        ),
        (
            "FC2-857170",
            "そんな架純ちゃんとの５回目のホテルデートは…\n昼間に高層ホテルでの待ち合わせになりました！",
            [
                "ご存じない方のために簡単に彼女との馴れ初めを",
                "☆今回の購入者レビュープレゼントは",
                "こちらの作品もオススメです",
                "ファイル形式：MP4",
            ],
        ),
        (
            "FC2-725517",
            "処女喪失から２ヶ月…久しぶりに会ってくれた架純ちゃん♥",
            [
                "ご存じない方のために簡単に彼女との馴れ初めを",
                "☆今回の購入者レビュープレゼントは",
                "こちらの作品もオススメです",
                "Windws　Media　Player",
            ],
        ),
        (
            "FC2-972018",
            "今回お届けする作品は撮影時期でいうと、この浴衣デートの少し前になります！",
            [
                "モデル募集掲示板で知り合いました",
                "☆今回の購入者レビュープレゼントは",
                "こちらの作品もオススメです",
            ],
        ),
        (
            "FC2-832286",
            "…実は３回目の撮影のあと、しばらく連絡が取れない状態が続きまして…",
            [
                "ご存じない方のために簡単に彼女との馴れ初めを",
                "☆今回の購入者レビュープレゼントは",
                "こちらの作品もオススメです",
            ],
        ),
        (
            "FC2-4676584",
            "出会い系アプリ等を駆使して撮影しています。",
            [
                "※サンプル画像はボカシをかけています",
                "本作品に登場する人物は18歳以上",
                "画像、動画等の無断転載",
            ],
        ),
        (
            "FC2-4960750",
            "まずはつぼみちゃんの淫らなお股をチェック～マン汁でパンツもびっしょり濡れちゃったよ！！",
            [
                "◎本作品はFC2,Incのみでの販売となります",
                "◎海外法人として運営国の法律に基づいた販売",
                "■購入特典",
                "◇収録時間",
                "本作品に登場する人物は18歳以上",
            ],
        ),
        (
            "FC2-1013835",
            "最近は学業とアルバイトで忙しくしているということだったので",
            [
                "ご存じない方のために簡単に彼女との馴れ初めを",
                "処女喪失から２ヶ月",
                "４回目のホテルデートでは",
            ],
        ),
    ],
)
def test_fc2hub_samples_preserve_main_plot_and_strip_noise(
    number: str, expected_snippet: str, forbidden_snippets: list[str]
):
    tree = _load_sample_tree(number)
    outline = getOutline(tree)

    assert expected_snippet in outline
    for forbidden in forbidden_snippets:
        assert forbidden not in outline
