from videocenter.core.config import Settings, get_settings
from videocenter.services.parsers.registry import ParserRegistry
from videocenter.services.parsers.webpage import GenericWebPageParser


def create_default_parser_registry(settings: Settings | None = None) -> ParserRegistry:
    selected = settings or get_settings()
    return ParserRegistry(
        [GenericWebPageParser()],
        timeout_seconds=selected.parser_timeout_seconds,
        max_attempts=selected.parser_max_attempts,
        retry_delay_seconds=selected.parser_retry_delay_seconds,
        retry_max_delay_seconds=selected.parser_retry_max_delay_seconds,
    )
