import asyncio
import contextlib
import ipaddress
import re
import threading
from collections.abc import Callable
from urllib.parse import urlsplit

from aiolimiter import AsyncLimiter
from httpx import AsyncClient, Timeout
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam


def is_loopback_url(url: str) -> bool:
    """Recognize literal loopback hosts without DNS resolution."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,  # https://api.openai.com/v1
        proxy: str | None = None,
        timeout: Timeout,
        rate: tuple[float, float],
    ):
        local = is_loopback_url(base_url)
        self.client = AsyncOpenAI(
            api_key=api_key or ("local" if local else ""),
            base_url=base_url,
            http_client=AsyncClient(
                proxy=None if local else proxy,
                trust_env=not local,
                timeout=timeout,
                follow_redirects=not local,
            ),
            timeout=timeout,
            max_retries=0,
        )
        self.limiter = AsyncLimiter(*rate)
        self._closed = False
        self._close_requested = False
        self._active_requests = 0
        self._active_lock = asyncio.Lock()
        self._lease_lock = threading.Lock()
        self._leases = 0

    def retain(self) -> None:
        with self._lease_lock:
            if self._closed:
                raise RuntimeError("LLM 客户端已关闭")
            self._leases += 1

    async def release(self) -> None:
        with self._lease_lock:
            if self._leases > 0:
                self._leases -= 1
        if self._close_requested:
            await self._close_if_idle()

    def _lease_count(self) -> int:
        with self._lease_lock:
            return self._leases

    async def _begin_request(self) -> None:
        async with self._active_lock:
            if self._closed:
                raise RuntimeError("LLM 客户端已关闭")
            self._active_requests += 1

    async def _end_request(self) -> None:
        async with self._active_lock:
            self._active_requests = max(self._active_requests - 1, 0)

    async def _is_idle(self) -> bool:
        async with self._active_lock:
            return self._active_requests == 0 and self._lease_count() == 0

    async def _close_if_idle(self) -> bool:
        if not await self._is_idle():
            return False
        await self.close()
        return True

    async def close_when_idle(self, *, poll_interval: float = 0.2) -> None:
        self._close_requested = True
        while not await self._is_idle():
            await asyncio.sleep(poll_interval)
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._close_requested = True
        self._closed = True
        with contextlib.suppress(Exception):
            await self.client.close()

    async def ask(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_try: int,
        log_fn: Callable[[str], None] = lambda _: None,
        extra_body: object | None = None,
    ) -> str | None:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        wait = 1
        await self._begin_request()
        try:
            for attempt in range(max_try):
                async with self.limiter:
                    try:
                        chat = await self.client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            extra_body=extra_body,
                        )
                        text = chat.choices[0].message.content if chat.choices else None
                        if text:
                            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
                        return text
                    except Exception as e:
                        # Do not log provider bodies, URLs or credentials.
                        log_fn(f"⚠️ LLM API 请求失败: {type(e).__name__}")
                if attempt + 1 < max_try:
                    log_fn(f"🔁 LLM API {wait}s 后重试")
                    await asyncio.sleep(wait)
                    wait *= 2
            log_fn("❌ LLM API 请求失败, 已达最大尝试次数\n")
            return None
        finally:
            await self._end_request()
