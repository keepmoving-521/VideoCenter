from videocenter.core.exceptions import BadRequestError


class UnsupportedWebsiteError(BadRequestError):
    """Raised when no registered parser supports a resource website."""

    def __init__(
        self,
        source_url: str,
        hostname: str,
        supported_hosts: tuple[str, ...] = (),
    ) -> None:
        message = f"暂不支持网站：{hostname}" if hostname else "暂不支持该资源网站"
        super().__init__(
            message,
            code="UNSUPPORTED_WEBSITE",
            details={
                "hostname": hostname or None,
                "supported_hosts": list(supported_hosts),
            },
        )
        self.source_url = source_url
        self.hostname = hostname
        self.supported_hosts = supported_hosts


class ParserNotFoundError(UnsupportedWebsiteError):
    """Backward-compatible name used by R01-R03 callers."""
