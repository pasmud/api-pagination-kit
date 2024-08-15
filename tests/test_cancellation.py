from collections.abc import Callable, Iterator

import pytest

from api_pagination_kit import (
    CursorCycleError,
    CursorPage,
    PageLimitError,
    PaginationCancelledError,
    PaginationError,
    iter_cursor_pages,
    iter_cursors,
    iter_numbered_pages,
    iter_page_numbers,
)


@pytest.mark.parametrize("paginate", [iter_page_numbers, iter_numbered_pages])
def test_numbered_cancellation_before_first_fetch(
    paginate: Callable[..., Iterator[object]],
) -> None:
    def fetch(number: int) -> tuple[int]:
        pytest.fail(f"Unexpected fetch for {number}")

    checks: list[bool] = []

    def should_cancel() -> bool:
        checks.append(True)
        return True

    results = paginate(fetch, should_cancel=should_cancel)
    assert checks == []
    with pytest.raises(PaginationCancelledError) as error:
        next(results)
    assert isinstance(error.value, PaginationError)
    assert error.value.pages_fetched == 0
    assert checks == [True]
    assert list(results) == []


@pytest.mark.parametrize("paginate", [iter_cursors, iter_cursor_pages])
def test_cursor_cancellation_after_empty_page(
    paginate: Callable[..., Iterator[object]],
) -> None:
    calls: list[str | None] = []

    def fetch(cursor: str | None) -> tuple[tuple[()], str]:
        calls.append(cursor)
        return (), "next"

    results = paginate(fetch, should_cancel=lambda: bool(calls))
    if paginate is iter_cursor_pages:
        assert next(results) == CursorPage(None, (), "next")
    with pytest.raises(PaginationCancelledError) as error:
        next(results)
    assert error.value.pages_fetched == 1
    assert calls == [None]


def test_cancellation_does_not_interrupt_a_page_in_progress() -> None:
    cancelled = False
    results = iter_page_numbers(lambda n: (n, -n), should_cancel=lambda: cancelled)
    assert next(results) == 1
    cancelled = True
    assert next(results) == -1
    with pytest.raises(PaginationCancelledError) as error:
        next(results)
    assert error.value.pages_fetched == 1


@pytest.mark.parametrize(
    ("continuation", "expected"),
    [(None, StopIteration), ("start", CursorCycleError), ("next", PageLimitError)],
)
def test_cancellation_is_not_checked_when_a_fetch_cannot_follow(
    continuation: str | None, expected: type[Exception]
) -> None:
    calls: list[str | None] = []
    checks: list[None] = []

    def fetch(cursor: str | None) -> tuple[tuple[int], str | None]:
        calls.append(cursor)
        return (1,), continuation

    def should_cancel() -> bool:
        checks.append(None)
        return bool(calls)

    results = iter_cursors(
        fetch, start_cursor="start", max_pages=1, should_cancel=should_cancel
    )
    assert next(results) == 1
    with pytest.raises(expected):
        next(results)
    assert checks == [None]
    assert calls == ["start"]


def test_cancellation_requires_a_callable_at_construction() -> None:
    with pytest.raises(TypeError, match="should_cancel"):
        iter_page_numbers(lambda _: (), should_cancel=True)  # type: ignore[arg-type]
