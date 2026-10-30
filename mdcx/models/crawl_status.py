"""Per-call observations; recording these must never affect network retry/circuit decisions."""

import copy
import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from functools import wraps


class CrawlStatus(StrEnum):
    NOT_FOUND = "正常未收录"
    MISSING = "正常字段缺失"
    REQUEST_ERROR = "请求错误"
    PARSE_ERROR = "解析异常"
    SKIPPED = "停站跳过"


ERROR_STATUSES = {CrawlStatus.REQUEST_ERROR, CrawlStatus.PARSE_ERROR, CrawlStatus.SKIPPED}
QUALITY_FIELDS = ("score", "outline", "actors", "thumb")


@dataclass(frozen=True)
class CrawlIssue:
    status: CrawlStatus
    reason: str


@dataclass
class SiteReport:
    site: str
    issues: list[CrawlIssue] = field(default_factory=list)
    missing: dict[str, CrawlStatus] = field(default_factory=dict)

    @property
    def has_error(self) -> bool:
        return any(issue.status in ERROR_STATUSES for issue in self.issues)


observations: ContextVar[list[CrawlIssue] | None] = ContextVar("crawl_observations", default=None)
request_cache: ContextVar[dict | None] = ContextVar("crawl_request_cache", default=None)


def record_status(status: CrawlStatus, reason: object) -> None:
    if (items := observations.get()) is not None:
        issue = CrawlIssue(status, str(reason))
        if issue not in items:
            items.append(issue)


def record_request_error(error: object) -> None:
    reason = str(error)
    if any(i.status == CrawlStatus.SKIPPED and i.reason in reason for i in observations.get() or []):
        return
    status = (
        CrawlStatus.SKIPPED
        if getattr(error, "status", None) == CrawlStatus.SKIPPED
        else CrawlStatus.NOT_FOUND
        if re.search(r"\bHTTP 404\b", reason)
        else CrawlStatus.REQUEST_ERROR
    )
    record_status(status, reason)


def record_parse_error(error: object) -> None:
    record_status(CrawlStatus.PARSE_ERROR, error)


def observe_http(*, cache: bool = False):
    """Observe only the final return; reuse successful decoded metadata within one movie."""

    def decorate(method):
        @wraps(method)
        async def observed(self, *args, **kwargs):
            saved = request_cache.get() if cache else None
            key = (method.__name__, repr(args), repr(sorted(kwargs.items())))
            if saved is not None and key in saved:
                return copy.deepcopy(saved[key])
            try:
                result, error = await method(self, *args, **kwargs)
            except Exception as error:
                if getattr(error, "status", None) == CrawlStatus.SKIPPED:
                    record_status(CrawlStatus.SKIPPED, error)
                raise
            if result is None and error:
                if args and args[0] == "HEAD" and re.search(r"\bHTTP 405\b", str(error)):
                    record_status(CrawlStatus.NOT_FOUND, "HEAD 405，沿用已有 GET 回退")
                elif "解析失败" in str(error):
                    record_parse_error(error)
                else:
                    record_request_error(error)
            elif saved is not None and result is not None and not error:
                saved[key] = copy.deepcopy((result, error))
            return result, error

        return observed

    return decorate
