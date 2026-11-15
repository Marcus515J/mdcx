"""Actor validity shared by source post-processing and the quality gate."""

import re

# Existing actor-search exclusions in core/amazon.py; keep exact-name matching.
ACTOR_PLACEHOLDERS = frozenset({"未知演员", "未知演員", "女优不明", "女優不明", "人物不明"})
MGSTAGE_AGE_MARKER_RE = re.compile(r"\d+\s*歳")
_MGSTAGE_ACTOR_EDGE_SEPS = " \t\r\n,，、/|｜-—_·・:："


def has_mgstage_age_marker(actor: str) -> bool:
    """Return whether an actor string contains an mgstage age marker like '27歳'."""
    return isinstance(actor, str) and bool(MGSTAGE_AGE_MARKER_RE.search(actor))


def has_mgstage_age_markers(actors) -> bool:
    """Return whether any actor entry in the sequence contains an mgstage age marker."""
    return any(has_mgstage_age_marker(actor) for actor in actors or [])


def strip_mgstage_age_marker(actor: str) -> str:
    """Return the name portion before an mgstage age marker, stripped of edge separators."""
    if not isinstance(actor, str):
        return ""
    match = MGSTAGE_AGE_MARKER_RE.search(actor)
    if match is None:
        return actor.strip(_MGSTAGE_ACTOR_EDGE_SEPS)
    return actor[: match.start()].strip(_MGSTAGE_ACTOR_EDGE_SEPS)


def fallback_mgstage_actors(actors) -> list[str]:
    """Strip mgstage age markers from actor entries and filter out invalid names."""
    return valid_actor_names(strip_mgstage_age_marker(actor) for actor in actors or [])


def valid_actor_names(actors):
    return [
        name
        for actor in actors or []
        if isinstance(actor, str)
        and (name := actor.strip())
        and name not in ACTOR_PLACEHOLDERS
        and any(char.isalnum() for char in name)
    ]
