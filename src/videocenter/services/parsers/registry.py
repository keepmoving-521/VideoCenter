import asyncio
import urllib.error
from collections.abc import Iterable

from videocenter.services.parsers.base import ParseRequest, ParseResult, ResourceParser
from videocenter.services.parsers.errors import (
    ParseFailedError,
    ParserNotFoundError,
    ParseTimeoutError,
)


class ParserRegistry:
    def __init__(
        self,
        parsers: Iterable[ResourceParser] = (),
        *,
        timeout_seconds: float = 30,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.5,
        retry_max_delay_seconds: float = 5,
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
        self._parsers: dict[str, ResourceParser] = {}
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

    async def parse(self, request: ParseRequest) -> ParseResult:
        parser = self.select(request)
        last_error: Exception | None = None
        timed_out = False
        for attempt in range(1, self.max_attempts + 1):
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    result = await parser.parse(request)
                if not isinstance(result, ParseResult):
                    raise TypeError(f"解析器 {parser.name} 返回了无效的解析结果")
                return result
            except TimeoutError as exc:
                last_error = exc
                timed_out = True
            except Exception as exc:
                if not self._is_retryable(exc):
                    raise
                last_error = exc
                timed_out = False

            if attempt < self.max_attempts:
                delay = min(
                    self.retry_delay_seconds * (2 ** (attempt - 1)),
                    self.retry_max_delay_seconds,
                )
                if delay:
                    await asyncio.sleep(delay)

        if timed_out:
            raise ParseTimeoutError(
                parser_name=parser.name,
                hostname=request.hostname,
                attempts=self.max_attempts,
                timeout_seconds=self.timeout_seconds,
            ) from last_error
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
    ) -> ParseResult:
        return await self.parse(
            ParseRequest(
                source_url,
                preferred_language=preferred_language,
            )
        )
