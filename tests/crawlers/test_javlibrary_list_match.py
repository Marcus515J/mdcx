from lxml import etree

from mdcx.crawlers.javlibrary import _is_video_link, get_real_url


def _parse_html(content: str) -> etree._Element:
    return etree.fromstring(content, etree.HTMLParser())


def test_t1_mirror_list_returns_standard_version_over_bluray_relative():
    """T1: 镜像列表页两条 SSNI-126，第一条为蓝光，第二条为普通版（相对地址），优先返回普通版绝对地址。"""
    html_content = """
    <html><body>
      <div class="videos">
        <div class="video">
          <a href="javli_bd.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION （ブルーレイディスク）"></a>
        </div>
        <div class="video">
          <a href="javli4yg4i.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION"></a>
        </div>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.c99i.com/ja")
    assert url == "https://www.c99i.com/ja/javli4yg4i.html"


def test_t2_mirror_list_returns_standard_version_over_bluray_absolute():
    """T2: 同 T1，但 href 为绝对地址，结果相同。"""
    html_content = """
    <html><body>
      <div class="videos">
        <div class="video">
          <a href="https://www.c99i.com/ja/javli_bd.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION （ブルーレイディスク）"></a>
        </div>
        <div class="video">
          <a href="https://www.c99i.com/ja/javli4yg4i.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION"></a>
        </div>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.c99i.com/ja")
    assert url == "https://www.c99i.com/ja/javli4yg4i.html"


def test_t3_official_list_returns_standard_version_over_bluray():
    """T3: 官网列表页两条结果（./?v=javxxxx 格式），优先返回不带蓝光的条目（回归）。"""
    html_content = """
    <html><body>
      <div class="videos">
        <div class="video">
          <a href="./?v=javlibd" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION （ブルーレイディスク）"></a>
        </div>
        <div class="video">
          <a href="./?v=javli4yg4i" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION"></a>
        </div>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.javlibrary.com/ja")
    assert url == "https://www.javlibrary.com/ja/?v=javli4yg4i"


def test_t4_detail_page_branch_1():
    """T4: 详情页（video_title 存在），走分支 1，返回拼接 origin 后的绝对地址（回归）。"""
    html_content = """
    <html><body>
      <div id="video_title">
        <h3><a href="./?v=javli4yg4i">SSNI-126 パイパンむき出し爆乳女教師レ●プ RION</a></h3>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.javlibrary.com/ja")
    assert url == "https://www.javlibrary.com/?v=javli4yg4i"


def test_t5_mirror_list_all_bluray_returns_last_match():
    """T5: 列表页里两条都是蓝光，返回最后一个匹配（与现有行为一致）。"""
    html_content = """
    <html><body>
      <div class="videos">
        <div class="video">
          <a href="javli_bd1.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION （ブルーレイディスク） 1"></a>
        </div>
        <div class="video">
          <a href="javli_bd2.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION （ブルーレイディスク） 2"></a>
        </div>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.c99i.com/ja")
    assert url == "https://www.c99i.com/ja/javli_bd2.html"


def test_t6_mirror_list_number_not_found():
    """T6: 列表页没有该番号，但页面有其它番号的 javxxxx.html 链接，返回空字符串。"""
    html_content = """
    <html><body>
      <div class="videos">
        <div class="video">
          <a href="javli11111.html" title="PRED-110 別の作品 1"></a>
        </div>
        <div class="video">
          <a href="javli22222.html" title="IPX-999 別の作品 2"></a>
        </div>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.c99i.com/ja")
    assert url == ""


def test_t7_unrelated_links_not_misidentified():
    """T7: 页面含导航/排行等无关的 .html 链接，title 恰好不含番号，不被误选。"""
    html_content = """
    <html><body>
      <header>
        <a href="/rankings.html" title="排行榜"></a>
        <a href="/tags.html" title="标签列表"></a>
        <a href="/ja/bestrated.html" title="好评推荐"></a>
        <a href="userswanted.php?mode=add" title="求片清单"></a>
      </header>
      <div class="videos">
        <div class="video">
          <a href="javli4yg4i.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION"></a>
        </div>
      </div>
    </body></html>
    """
    html = _parse_html(html_content)
    url = get_real_url(html, "SSNI-126", "https://www.c99i.com/ja")
    assert url == "https://www.c99i.com/ja/javli4yg4i.html"

    # 如果没有目标番号的视频卡片，导航链接绝不被误判选中
    html_no_target = _parse_html("""
    <html><body>
      <header>
        <a href="/rankings.html" title="排行榜"></a>
        <a href="/tags.html" title="标签列表"></a>
        <a href="/ja/bestrated.html" title="好评推荐"></a>
      </header>
    </body></html>
    """)
    assert get_real_url(html_no_target, "SSNI-126", "https://www.c99i.com/ja") == ""


def test_extra_mirror_href_formats():
    """额外验证：支持前缀 ./ 与根路径 /ja/ 等多种相对路径变体。"""
    html_dot_slash = _parse_html("""
    <html><body>
      <a href="./javli4yg4i.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION"></a>
    </body></html>
    """)
    assert (
        get_real_url(html_dot_slash, "SSNI-126", "https://www.c99i.com/ja") == "https://www.c99i.com/ja/javli4yg4i.html"
    )

    html_path_abs = _parse_html("""
    <html><body>
      <a href="/ja/javli4yg4i.html" title="SSNI-126 パイパンむき出し爆乳女教師レ●プ RION"></a>
    </body></html>
    """)
    assert (
        get_real_url(html_path_abs, "https://www.c99i.com/ja")
        if False
        else get_real_url(html_path_abs, "SSNI-126", "https://www.c99i.com/ja")
        == "https://www.c99i.com/ja/javli4yg4i.html"
    )


def test_video_link_matcher():
    """单元测试：_is_video_link 严格区分视频详情页与无关链接。"""
    assert _is_video_link("javli4yg4i.html")
    assert _is_video_link("./javli4yg4i.html")
    assert _is_video_link("/ja/javli4yg4i.html")
    assert _is_video_link("https://www.c99i.com/ja/javli4yg4i.html")
    assert _is_video_link("https://www.c99i.com/ja/javli4yg4i.html?hl=ja")
    assert _is_video_link("./?v=javli4yg4i")
    assert _is_video_link("/?v=javli4yg4i")
    assert _is_video_link("/ja/?v=javli4yg4i")
    assert _is_video_link("https://www.javlibrary.com/ja/?v=javli4yg4i")

    assert not _is_video_link("")
    assert not _is_video_link("/rankings.html")
    assert not _is_video_link("/tags.html")
    assert not _is_video_link("jav.html")
    assert not _is_video_link("userswanted.php?mode=add")
    assert not _is_video_link("javascript:void(0)")
