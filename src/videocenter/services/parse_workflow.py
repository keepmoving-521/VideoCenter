from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from videocenter.core.exceptions import BadRequestError, ConflictError, NotFoundError
from videocenter.services.parsers import ParseResult

PREVIEW_TTL = timedelta(minutes=30)


@dataclass(frozen=True, slots=True)
class StoredParseResult:
    result: ParseResult
    expires_at: datetime


class ParseWorkflowStore:
    def __init__(self, ttl: timedelta = PREVIEW_TTL) -> None:
        self.ttl = ttl
        self._previews: dict[str, StoredParseResult] = {}
        self._confirmations: dict[str, StoredParseResult] = {}
        self._consumed_confirmations: set[str] = set()
        self._lock = Lock()

    def create_preview(self, result: ParseResult) -> tuple[str, datetime]:
        with self._lock:
            self._cleanup()
            preview_id = uuid4().hex
            expires_at = datetime.now(UTC) + self.ttl
            self._previews[preview_id] = StoredParseResult(result, expires_at)
            return preview_id, expires_at

    def confirm(
        self,
        preview_id: str,
        result: ParseResult,
    ) -> tuple[str, datetime]:
        with self._lock:
            self._cleanup()
            preview = self._previews.pop(preview_id, None)
            if preview is None:
                raise NotFoundError(
                    "预解析结果不存在或已过期",
                    code="PARSE_PREVIEW_NOT_FOUND",
                )
            if result.source_page_url != preview.result.source_page_url:
                raise BadRequestError(
                    "确认结果不能修改来源页面地址",
                    code="PARSE_SOURCE_URL_MISMATCH",
                )
            confirmation_id = uuid4().hex
            expires_at = datetime.now(UTC) + self.ttl
            self._confirmations[confirmation_id] = StoredParseResult(
                result,
                expires_at,
            )
            return confirmation_id, expires_at

    def consume_confirmation(self, confirmation_id: str) -> ParseResult:
        with self._lock:
            self._cleanup()
            if confirmation_id in self._consumed_confirmations:
                raise ConflictError(
                    "解析确认结果已保存",
                    code="PARSE_CONFIRMATION_ALREADY_USED",
                )
            confirmation = self._confirmations.pop(confirmation_id, None)
            if confirmation is None:
                raise NotFoundError(
                    "解析确认结果不存在或已过期",
                    code="PARSE_CONFIRMATION_NOT_FOUND",
                )
            self._consumed_confirmations.add(confirmation_id)
            return confirmation.result

    def restore_confirmation(
        self,
        confirmation_id: str,
        result: ParseResult,
    ) -> None:
        with self._lock:
            self._consumed_confirmations.discard(confirmation_id)
            self._confirmations[confirmation_id] = StoredParseResult(
                result,
                datetime.now(UTC) + self.ttl,
            )

    def clear(self) -> None:
        with self._lock:
            self._previews.clear()
            self._confirmations.clear()
            self._consumed_confirmations.clear()

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        self._previews = {
            key: value for key, value in self._previews.items() if value.expires_at > now
        }
        self._confirmations = {
            key: value for key, value in self._confirmations.items() if value.expires_at > now
        }


parse_workflow_store = ParseWorkflowStore()
