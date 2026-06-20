from collections.abc import Iterable

from videocenter.services.parsers.base import ParseRequest, ParseResult, ResourceParser
from videocenter.services.parsers.errors import ParserNotFoundError


class ParserRegistry:
    def __init__(self, parsers: Iterable[ResourceParser] = ()) -> None:
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
        result = await parser.parse(request)
        if not isinstance(result, ParseResult):
            raise TypeError(f"解析器 {parser.name} 返回了无效的解析结果")
        return result

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
