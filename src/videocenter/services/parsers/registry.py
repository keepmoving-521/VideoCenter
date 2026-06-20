import asyncio
import logging
import time
import urllib.error
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from uuid import uuid4

from videocenter.services.parsers.base import ParseRequest, ParseResult, ResourceParser
from videocenter.services.parsers.cache import ParseResultCache
from videocenter.services.parsers.errors import (
    ParseFailedError,
    ParserNotFoundError,
    ParseTimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InFlightParse:
    task: asyncio.Task[ParseResult]
    task_id: str


class ParserRegistry:
    def __init__(
        self,
        parsers: Iterable[ResourceParser] = (),
        *,
        timeout_seconds: float = 30,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.5,
        retry_max_delay_seconds: float = 5,
        cache: ParseResultCache | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("解析超时时间必须大于零")
        if max_attempts < 1:
            raise ValueError("解析尝试次数必须大于零")
        if retry_delay_seconds < 0 or retry_max_delay_seconds < retry_delay_seconds:
            raise ValueError("解析重试延迟配置无效")
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_max_delay_seconds = retry_max_delay_seconds
        self.cache = cache if cache is not None else ParseResultCache()
        self._parsers: dict[str, ResourceParser] = {}
        self._inflight: dict[str, InFlightParse] = {}
        self._inflight_lock = Lock()
        for parser in parsers:
            self.register(parser)

    def register(self, parser: ResourceParser) -> None:
        name = parser.name.strip()
        if not name:
            raise ValueError("解析器名称不能为空")
        if name in self._parsers:
            raise ValueError(f"解析器名称已注册：{name}")
        if any(not host.strip() or "://" in host or "/" in host for host in parser.supported_hosts):
            raise ValueError(f"解析器 {name} 的 supported_hosts 配置无效")
        self._parsers[name] = parser

    def unregister(self, name: str) -> ResourceParser:
        try:
            return self._parsers.pop(name)
        except KeyError as exc:
            raise KeyError(f"解析器未注册：{name}") from exc

    def list_parsers(self) -> tuple[ResourceParser, ...]:
        return tuple(
            sorted(
                self._parsers.values(),
                key=lambda parser: (-parser.priority, parser.name),
            )
        )

    def supported_hosts(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    host.casefold().rstrip(".")
                    for parser in self._parsers.values()
                    for host in parser.supported_hosts
                }
            )
        )

    def select(self, request: ParseRequest) -> ResourceParser:
        parsers = self.list_parsers()
        host_parsers = tuple(
            parser
            for parser in parsers
            if parser.supported_hosts and parser.matches_host(request.hostname)
        )
        generic_parsers = tuple(parser for parser in parsers if not parser.supported_hosts)
        for parser in (*host_parsers, *generic_parsers):
            if parser.supports(request):
                return parser
        raise ParserNotFoundError(
            request.source_url,
            request.hostname,
            self.supported_hosts(),
        )

    def select_url(
        self,
        source_url: str,
        *,
        preferred_language: str | None = None,
    ) -> ResourceParser:
        return self.select(
            ParseRequest(
                source_url,
                preferred_language=preferred_language,
            )
        )

    async def parse(
        self,
        request: ParseRequest,
        *,
        task_id: str | None = None,
    ) -> ParseResult:
        parser = self.select(request)
        selected_task_id = task_id or uuid4().hex
        cache_key = self._cache_key(parser, request)
        log_context = {
            "parse_task_id": selected_task_id,
            "parser": parser.name,
            "hostname": request.hostname,
        }
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.info(
                "Parse cache hit",
                extra={**log_context, "parse_event": "cache_hit"},
            )
            return cached

        with self._inflight_lock:
            inflight = self._inflight.get(cache_key)
            is_owner = inflight is None
            if inflight is None:
                task = asyncio.create_task(
                    self._parse_uncached(
                        parser,
                        request,
                        cache_key=cache_key,
                        task_id=selected_task_id,
                    )
                )
                inflight = InFlightParse(task=task, task_id=selected_task_id)
                self._inflight[cache_key] = inflight
                task.add_done_callback(
                    lambda completed, key=cache_key, current=inflight: self._remove_inflight(
                        key, current
                    )
                )

        if not is_owner:
            logger.info(
                "Duplicate parse joined in-flight task",
                extra={
                    **log_context,
                    "parse_event": "duplicate_wait",
                    "shared_parse_task_id": inflight.task_id,
                },
            )
        return await asyncio.shield(inflight.task)

    def _remove_inflight(self, cache_key: str, inflight: InFlightParse) -> None:
        with self._inflight_lock:
            current = self._inflight.get(cache_key)
            if current is inflight:
                self._inflight.pop(cache_key, None)

    async def _parse_uncached(
        self,
        parser: ResourceParser,
        request: ParseRequest,
        *,
        cache_key: str,
        task_id: str,
    ) -> ParseResult:
        log_context = {
            "parse_task_id": task_id,
            "parser": parser.name,
            "hostname": request.hostname,
        }
        started_at = time.perf_counter()
        logger.info(
            "Parse task started",
            extra={
                **log_context,
                "parse_event": "started",
                "max_attempts": self.max_attempts,
                "timeout_seconds": self.timeout_seconds,
            },
        )
        last_error: Exception | None = None
        timed_out = False
        for attempt in range(1, self.max_attempts + 1):
            attempt_started_at = time.perf_counter()
            logger.info(
                "Parse attempt started",
                extra={
                    **log_context,
                    "parse_event": "attempt_started",
                    "attempt": attempt,
                },
            )
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    result = await parser.parse(request)
                if not isinstance(result, ParseResult):
                    raise TypeError(f"解析器 {parser.name} 返回了无效的解析结果")
                self.cache.set(cache_key, result)
                logger.info(
                    "Parse task completed",
                    extra={
                        **log_context,
                        "parse_event": "completed",
                        "attempt": attempt,
                        "duration_ms": round(
                            (time.perf_counter() - started_at) * 1000,
                            2,
                        ),
                    },
                )
                return result
            except TimeoutError as exc:
                last_error = exc
                timed_out = True
                error_name = "TimeoutError"
            except Exception as exc:
                if not self._is_retryable(exc):
                    logger.exception(
                        "Parse task failed without retry",
                        extra={
                            **log_context,
                            "parse_event": "failed",
                            "attempt": attempt,
                            "error_type": type(exc).__name__,
                            "duration_ms": round(
                                (time.perf_counter() - started_at) * 1000,
                                2,
                            ),
                        },
                    )
                    raise
                last_error = exc
                timed_out = False
                error_name = type(exc).__name__

            if attempt < self.max_attempts:
                delay = min(
                    self.retry_delay_seconds * (2 ** (attempt - 1)),
                    self.retry_max_delay_seconds,
                )
                logger.warning(
                    "Parse attempt will retry",
                    extra={
                        **log_context,
                        "parse_event": "retry",
                        "attempt": attempt,
                        "error_type": error_name,
                        "attempt_duration_ms": round(
                            (time.perf_counter() - attempt_started_at) * 1000,
                            2,
                        ),
                        "retry_delay_seconds": delay,
                    },
                )
                if delay:
                    await asyncio.sleep(delay)

        if timed_out:
            logger.error(
                "Parse task timed out",
                extra={
                    **log_context,
                    "parse_event": "timeout",
                    "attempts": self.max_attempts,
                    "duration_ms": round(
                        (time.perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )
            raise ParseTimeoutError(
                parser_name=parser.name,
                hostname=request.hostname,
                attempts=self.max_attempts,
                timeout_seconds=self.timeout_seconds,
            ) from last_error
        logger.error(
            "Parse task exhausted retries",
            extra={
                **log_context,
                "parse_event": "failed",
                "attempts": self.max_attempts,
                "error_type": type(last_error).__name__ if last_error else "UnknownError",
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
            },
        )
        raise ParseFailedError(
            parser_name=parser.name,
            hostname=request.hostname,
            attempts=self.max_attempts,
            reason=type(last_error).__name__ if last_error else "UnknownError",
        ) from last_error

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, urllib.error.HTTPError):
            return exc.code == 429 or 500 <= exc.code < 600
        return isinstance(
            exc,
            (
                ConnectionError,
                urllib.error.URLError,
            ),
        )

    async def parse_url(
        self,
        source_url: str,
        *,
        preferred_language: str | None = None,
        task_id: str | None = None,
    ) -> ParseResult:
        return await self.parse(
            ParseRequest(
                source_url,
                preferred_language=preferred_language,
            ),
            task_id=task_id,
        )

    @staticmethod
    def _cache_key(parser: ResourceParser, request: ParseRequest) -> str:
        raw_key = f"{parser.name}\0{request.source_url}\0{request.preferred_language or ''}"
        return sha256(raw_key.encode()).hexdigest()
