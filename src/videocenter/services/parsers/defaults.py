from videocenter.services.parsers.registry import ParserRegistry
from videocenter.services.parsers.webpage import GenericWebPageParser


def create_default_parser_registry() -> ParserRegistry:
    return ParserRegistry([GenericWebPageParser()])
