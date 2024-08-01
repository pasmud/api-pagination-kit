import json
from collections.abc import Iterator
from itertools import islice
from pathlib import Path

import pytest

from api_pagination_kit import (
    CursorCycleError,
    PageLimitError,
    PaginationCancelledError,
    iter_cursors,
    iter_page_numbers,
)

VECTORS = Path(__file__).with_name("regression_vectors")
ERRORS = {
    "cancelled": PaginationCancelledError,
    "cycle": CursorCycleError,
    "limit": PageLimitError,
}


@pytest.mark.parametrize(
    "case",
    [pytest.param(path, id=path.stem) for path in sorted(VECTORS.glob("*.json"))],
)
def test_regression_vector(case: Path) -> None:
    vector = json.loads(case.read_text(encoding="utf-8"))
    pages = {page["token"]: page for page in vector["pages"]}
    options = vector.get("options", {}).copy()
    expected = vector["expected"]
    fetched: list[int | str | None] = []
    consumed: list[object] = []
    yielded: list[object] = []
    cancel_checks: list[int] = []
    cancel_at = vector.get("cancel_at")
    cancel_after_items = vector.get("cancel_after_items")

    def should_cancel() -> bool:
        cancel_checks.append(len(fetched))
        return (cancel_at is not None and len(fetched) >= cancel_at) or (
            cancel_after_items is not None and len(yielded) >= cancel_after_items
        )

    def lookup(token: int | str | None) -> dict:
        fetched.append(token)
        assert token in pages, f"unexpected request {token!r}; trace: {fetched!r}"
        return pages[token]

    def page_items(page: dict) -> Iterator[object]:
        for item in page["items"]:
            consumed.append(item)
            yield item

    def fetch_number(number: int) -> Iterator[object]:
        return page_items(lookup(number))

    def fetch_cursor(cursor: str | None) -> tuple[Iterator[object], str | None]:
        page = lookup(cursor)
        return page_items(page), page["next"]

    if cancel_at is not None or cancel_after_items is not None:
        options["should_cancel"] = should_cancel
    if vector["mode"] == "numbered":
        stream = iter_page_numbers(fetch_number, **options)
    else:
        assert vector["mode"] == "cursor"
        stream = iter_cursors(fetch_cursor, **options)
    assert fetched == consumed == cancel_checks == []

    error = expected.get("error")
    take = vector.get("take")
    pulls = stream if take is None else islice(stream, take)
    if error is None:
        for item in pulls:
            yielded.append(item)
    else:
        assert take is None
        with pytest.raises(ERRORS[error]) as caught:
            for item in pulls:
                yielded.append(item)
        assert caught.value.pages_fetched == len(expected["fetches"])
        if isinstance(caught.value, PageLimitError):
            assert caught.value.max_pages == options["max_pages"]
        if isinstance(caught.value, CursorCycleError):
            assert caught.value.first_seen_on_page == expected["first_seen_on_page"]
    if take is None:
        with pytest.raises(StopIteration):
            next(stream)
    else:
        assert len(yielded) == take

    assert fetched == expected["fetches"]
    assert yielded == consumed == expected["items"]
    if "should_cancel" in options:
        check_count = len(expected["fetches"]) + (error == "cancelled")
        assert cancel_checks == list(range(check_count))
