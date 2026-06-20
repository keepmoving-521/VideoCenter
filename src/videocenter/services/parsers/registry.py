from collections.abc import Iterable

from videocenter.services.parsers.base import ParseRequest, ParseResult, ResourceParser


class ParserNotFoundError(LookupError):
    def __init__(self, source_url: str) -> None:
        super().__init__(f"没有可处理该资源地址的解析器：{source_url}")
        self.source_url = source_url


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

    def select(self, request: ParseRequest) -> ResourceParser:
        for parser in self.list_parsers():
            if parser.supports(request):
                return parser
        raise ParserNotFoundError(request.source_url)

    async def parse(self, request: ParseRequest) -> ParseResult:
        parser = self.select(request)
        result = await parser.parse(request)
        if not isinstance(result, ParseResult):
            raise TypeError(f"解析器 {parser.name} 返回了无效的解析结果")
        return result
