from datetime import timedelta

import pytest

from videocenter.core.exceptions import ConflictError, NotFoundError
from videocenter.services.parse_workflow import ParseWorkflowStore
from videocenter.services.parsers import ParseResult


def result() -> ParseResult:
    return ParseResult(
        title="Movie",
        source_site="Example",
        source_page_url="https://example.com/movie/1",
    )


def test_confirmation_tokens_are_single_use():
    store = ParseWorkflowStore()
    preview_id, _ = store.create_preview(result())
    confirmation_id, _ = store.confirm(preview_id, result())

    assert store.consume_confirmation(confirmation_id).title == "Movie"
    with pytest.raises(ConflictError):
        store.consume_confirmation(confirmation_id)


def test_expired_preview_is_not_confirmable():
    store = ParseWorkflowStore(ttl=timedelta(microseconds=-1))
    preview_id, _ = store.create_preview(result())

    with pytest.raises(NotFoundError):
        store.confirm(preview_id, result())
