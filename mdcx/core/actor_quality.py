"""Actor validity shared by source post-processing and the quality gate."""

import re

from ..config.resources import resources
from ..manual import ManualConfig

# Existing actor-search exclusions in core/amazon.py; keep exact-name matching.
ACTOR_PLACEHOLDERS = frozenset({"未知演员", "未知演員", "女优不明", "女優不明", "人物不明"})

_SUREN_PURE_NAME_RE = re.compile(
    r"^[\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fc-\u30fe\u4e00-\u9fff\u3400-\u4dbfA-Za-z々ヶ〆]+"
    r"(?:[・· ][\u3041-\u3096\u309d-\u309f\u30a1-\u30fa\u30fc-\u30fe\u4e00-\u9fff\u3400-\u4dbfA-Za-z々ヶ〆]+)*$"
)
_SUREN_HONORIFIC_SUFFIX_RE = re.compile(r"(?:さん|ちゃん|くん|様|さま|氏|殿|たん|サン|チャン|クン|サマ)$")
_SUREN_DIGIT_AGE_RE = re.compile(r"[0-9０-９]+\s*[歳才]")
_SUREN_KANJI_AGE_RE = re.compile(r"(?:[一二三四五六七八九]?十[一二三四五六七八九]?)\s*[歳才]")
_SUREN_BRACKET_RE = re.compile(r"[()（）\[\]【】「」]")
_SUREN_ASCII_NON_NAME_RE = re.compile(r"(?<![A-Za-z])(?:AV|OL|JD|JK|JC|CA|RQ|Web|WEB|web)(?![A-Za-z])")

_SUREN_EXACT_NON_NAME_PHRASES = frozenset(
    {
        *(p.upper() for p in ACTOR_PLACEHOLDERS),
        "女優",
        "女优",
        "AV女優",
        "AV女优",
        "男優",
        "男优",
        "未知男優",
        "未知男优",
        "は別人",
        "別人",
        "别人",
        "同名別人",
        "同名别人",
        "数据错误",
        "數據錯誤",
        "酸素",
        "錯誤",
        "错误",
        "再生不能",
        "編集不可",
        "编辑不可",
        "名誉毀損",
        "名誉毁损",
        "名譽毀損",
        "複数",
        "复数",
        "複數",
        "多数",
        "多數",
        "素人",
        "素人妻",
        "素人娘",
        "素人少女",
        "素人奥様",
        "素人１",
        "S級素人",
        "S级素人",
        "SOD",
        "SOD女子社員",
        "人妻",
        "本妻",
        "患者",
        "援交",
        "援交娘",
        "円光",
        "円光娘",
        "援助交际",
        "援助交際",
        "万引き娘",
        "年轻女孩",
        "年轻女子",
        "元読者モデル",
        "貧乳美女",
        "贫乳美女",
        "ギャル２人組",
        "ギャル２人组",
        "不明",
        "匿名",
        "未確認",
        "未确认",
        "削除",
        "删除",
        "該当なし",
        "なし",
        "無し",
        "エラー",
        "データ",
        "ERROR",
        "UNKNOWN",
        "NONE",
        "NULL",
        "N/A",
        "NA",
        "ANONYMOUS",
    }
)

_SUREN_ALWAYS_NON_NAME_SUBSTRINGS = (
    "別人",
    "别人",
    "错误",
    "錯誤",
    "不能",
    "不可",
    "編集",
    "编辑",
    "再生",
    "名譽",
    "名誉",
    "複数",
    "复数",
    "複數",
    "多数",
    "多數",
    "人組",
    "人组",
    "データ",
    "エラー",
    "削除",
    "删除",
    "未確認",
    "未确认",
    "該当",
    "不明",
    "女子社員",
    "AV女優",
    "AV女优",
    "未知男優",
    "未知男优",
    "未知女優",
    "未知女优",
    "読者モデル",
    "貧乳",
    "贫乳",
    "円光",
    "万引き",
    "患者",
    "本妻",
    "奥様",
    "素人娘",
    "素人妻",
    "素人少女",
    "素人奥様",
    "S級素人",
    "S级素人",
)

SUREN_NON_NAME_WORDS = (
    "AV女優",
    "AV女优",
    "女優",
    "女优",
    "男優",
    "男优",
    "素人",
    "人妻",
    "夫妻",
    "主婦",
    "若妻",
    "新妻",
    "既婚",
    "未亡人",
    "専業主婦",
    "大学生",
    "女子大生",
    "専門学生",
    "専門学校生",
    "大学院生",
    "短大生",
    "音大生",
    "美大生",
    "医大生",
    "看護学生",
    "女学生",
    "女子高生",
    "学生",
    "学部",
    "年生",
    "会社員",
    "社員",
    "新卒",
    "新入社員",
    "公務員",
    "銀行員",
    "正社員",
    "派遣",
    "勤務",
    "事務員",
    "事務職",
    "事務",
    "医療事務",
    "受付嬢",
    "受付",
    "秘書",
    "店員",
    "販売員",
    "販売職",
    "営業職",
    "専門職",
    "技術職",
    "総合職",
    "店長",
    "オーナー",
    "社長",
    "経営者",
    "歯科助手",
    "助手",
    "看護師",
    "看護婦",
    "ナース",
    "女医",
    "医師",
    "薬剤師",
    "医療従事者",
    "介護士",
    "介護職",
    "保育士",
    "幼稚園教諭",
    "女教師",
    "教師",
    "講師",
    "家庭教師",
    "塾講師",
    "セラピスト",
    "エステティシャン",
    "エステ",
    "マッサージ",
    "美容師",
    "美容部員",
    "ネイリスト",
    "アパレル",
    "ショークラブ",
    "ダンサー",
    "デザイナー",
    "食品メーカー",
    "メーカー",
    "クリエイター",
    "エンジニア",
    "プログラマー",
    "アーティスト",
    "ミュージシャン",
    "自営業",
    "フリーランス",
    "モデル",
    "タレント",
    "アイドル",
    "グラドル",
    "グラビア",
    "レースクイーン",
    "レースクィーン",
    "コンパニオン",
    "キャンギャル",
    "ラウンドガール",
    "ホステス",
    "キャバ嬢",
    "キャバ",
    "風俗嬢",
    "風俗",
    "ソープ",
    "デリヘル",
    "ラウンジ",
    "スナック",
    "バーテンダー",
    "バーテン",
    "ウェイトレス",
    "ウエイトレス",
    "カフェ",
    "パティシエ",
    "料理人",
    "栄養士",
    "調理師",
    "インストラクター",
    "トレーナー",
    "チアリーダー",
    "チアガール",
    "バレリーナ",
    "インフルエンサー",
    "ライバー",
    "配信者",
    "ユーチューバー",
    "コスプレイヤー",
    "コスプレ",
    "フリーター",
    "アルバイト",
    "バイト",
    "パート",
    "無職",
    "ニート",
    "家事手伝い",
    "スチュワーデス",
    "客室乗務員",
    "グランドスタッフ",
    "バスガイド",
    "アナウンサー",
    "リポーター",
    "キャスター",
    "声優",
    "ピアニスト",
    "バイオリニスト",
    "一般女性",
    "一般人",
    "女子社員",
    "女子アナ",
    "ギャル",
    "美少女",
    "お姉さん",
    "熟女",
    "美魔女",
    "痴女",
    "ママ",
    "妊婦",
    "清楚系",
    "初撮り",
    "初登場",
    "初体験",
    "専属",
    "出演",
    "応募",
    "投稿",
    "個人撮影",
    "ハメ撮り",
    "ナンパ",
    "中出し",
    "連発",
    "絶叫",
    "アナル",
    "潮吹き",
    "巨乳",
    "爆乳",
    "美乳",
    "貧乳",
    "美巨乳",
    "貧乳",
    "贫乳",
    "円光",
    "援交",
    "スレンダー",
    "ドM",
    "ドS",
    "M女",
    "エロい",
    "エロ",
    "現役",
    "クリニック",
    "病院",
    "ホテル",
    "ショップ",
    "未知女优",
    "未知女優",
    "业余",
    "护士",
    "空姐",
    "老师",
    "模特",
    "主妇",
    "辣妹",
    "萝莉",
    "御姐",
)


def _has_suren_disqualifying_marker(name: str) -> bool:
    if name in ACTOR_PLACEHOLDERS or name.upper() in _SUREN_EXACT_NON_NAME_PHRASES:
        return True
    stripped_at = name.lstrip("@＠")
    if stripped_at and stripped_at.upper() in _SUREN_EXACT_NON_NAME_PHRASES:
        return True
    if _SUREN_BRACKET_RE.search(name):
        return True
    if _SUREN_DIGIT_AGE_RE.search(name) or _SUREN_KANJI_AGE_RE.search(name):
        return True
    if any(_SUREN_HONORIFIC_SUFFIX_RE.search(part) for part in name.split()):
        return True
    if _SUREN_ASCII_NON_NAME_RE.search(name):
        return True
    return any(word in name for word in _SUREN_ALWAYS_NON_NAME_SUBSTRINGS)


def _normalize_mapping_lookup(value: str) -> str:
    normalized = value.strip().upper()
    for full_char, half_char in ManualConfig.FULL_HALF_CHAR:
        normalized = normalized.replace(full_char, half_char)
    return normalized


def _has_suren_description_word(name: str, *, allow_suren_stage_word: bool = False) -> bool:
    for word in SUREN_NON_NAME_WORDS:
        if allow_suren_stage_word and word == "素人":
            continue
        if word in name:
            return True
    return False


def _mapping_actor_trust(name: str) -> bool | None:
    """Return True only for a non-FC-seller @jp main name, False for a known FC seller, or None otherwise."""
    xml_actor = getattr(resources, "actor_mapping_data", None)
    if xml_actor is None or len(xml_actor) == 0:
        return None
    normalized_name = _normalize_mapping_lookup(name)
    for fc_node in xml_actor.xpath("//a[contains(@keyword, '【FC卖家】')]"):
        candidates = [
            fc_node.get("jp") or "",
            fc_node.get("zh_cn") or "",
            fc_node.get("zh_tw") or "",
            *(fc_node.get("keyword") or "").split(","),
        ]
        for candidate in candidates:
            item = candidate.strip()
            if item and (item == name or _normalize_mapping_lookup(item) == normalized_name):
                return False
    jp_nodes = xml_actor.xpath("//a[@jp=$name]", name=name)
    if not jp_nodes:
        return None
    return True


def is_pure_suren_actor(actor: str) -> bool:
    """Return whether a suren actor value is a clean stage name without age, honorific, job, or extra symbols."""
    if not isinstance(actor, str):
        return False
    name = actor.strip()
    if not name or not any(char.isalnum() for char in name):
        return False
    if _has_suren_disqualifying_marker(name):
        return False
    mapping_trust = _mapping_actor_trust(name)
    if mapping_trust is False:
        return False
    if mapping_trust is True:
        return not _has_suren_description_word(name, allow_suren_stage_word=True)
    if not _SUREN_PURE_NAME_RE.fullmatch(name):
        return False
    return not _has_suren_description_word(name, allow_suren_stage_word=False)


def valid_actor_names(actors):
    return [
        name
        for actor in actors or []
        if isinstance(actor, str)
        and (name := actor.strip())
        and name not in ACTOR_PLACEHOLDERS
        and any(char.isalnum() for char in name)
    ]


def valid_suren_actor_names(actors) -> list[str]:
    """Return actor names only when every non-placeholder entry passes pure-name validation for suren."""
    cleaned = valid_actor_names(actors)
    if not cleaned:
        return []
    if all(is_pure_suren_actor(name) for name in cleaned):
        return cleaned
    return []
