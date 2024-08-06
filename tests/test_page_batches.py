from collections.abc import Iterator

import pytest

from api_pagination_kit import (
    CursorCycleError,
    CursorPage,
    NumberedPage,
    PageLimitError,
    iter_cursor_pages,
    iter_numbered_pages,
)


def test_numbered_batches_are_pull_based_and_exclude_the_empty_sentinel() -> None:
    calls: list[int] = []

    def fetch(number: int) -> Iterator[str]:
        calls.append(number)
        return iter({0: ("a", "a"), 1: ("b",), 2: ()}[number])

    pages = iter_numbered_pages(fetch, start_page=0, max_pages=3)
    assert calls == []
    first = next(pages)
    assert first == NumberedPage(0, ("a", "a"))
    assert calls == [0]
    assert list(pages) == [NumberedPage(1, ("b",))]
    assert calls == [0, 1, 2]
    assert first.items == ("a", "a")


def test_numbered_batch_is_delivered_before_the_limit_error() -> None:
    calls: list[int] = []

    def fetch(number: int) -> tuple[int]:
        calls.append(number)
        return (number,)

    pages = iter_numbered_pages(fetch, max_pages=1)
    assert next(pages) == NumberedPage(1, (1,))
    with pytest.raises(PageLimitError):
        next(pages)
    assert calls == [1]


def test_cursor_batches_expose_empty_pages_and_allow_resuming_at_a_checkpoint() -> None:
    calls: list[str | None] = []
    responses = {None: (("a",), "gap"), "gap": ((), ""), "": ((), None)}

    def fetch(cursor: str | None) -> tuple[tuple[str, ...], str | None]:
        calls.append(cursor)
        return responses[cursor]

    pages = iter_cursor_pages(fetch)
    assert calls == []
    assert next(pages) == CursorPage(None, ("a",), "gap")
    checkpoint = next(pages)
    assert checkpoint == CursorPage("gap", (), "")
    assert "gap" not in repr(checkpoint)
    assert calls == [None, "gap"]
    assert list(iter_cursor_pages(fetch, start_cursor=checkpoint.next_cursor)) == [
        CursorPage("", (), None)
    ]
    assert calls == [None, "gap", ""]


def test_cursor_batch_is_delivered_before_a_cycle_error_at_the_limit() -> None:
    calls: list[str | None] = []

    def fetch(cursor: str | None) -> tuple[tuple[int], str]:
        calls.append(cursor)
        return (1,), "start"

    pages = iter_cursor_pages(fetch, start_cursor="start", max_pages=1)
    assert next(pages) == CursorPage("start", (1,), "start")
    with pytest.raises(CursorCycleError):
        next(pages)
    assert calls == ["start"]


@pytest.mark.parametrize("mode", ["number", "cursor"])
def test_batch_with_a_failed_item_source_is_not_delivered(mode: str) -> None:
    failure = ValueError("synthetic item failure")

    def source() -> Iterator[int]:
        yield 1
        raise failure

    if mode == "number":
        pages = iter_numbered_pages(lambda _: source())
    else:
        pages = iter_cursor_pages(lambda _: (source(), None))

    with pytest.raises(ValueError) as error:
        next(pages)
    assert error.value is failure
    assert list(pages) == []
