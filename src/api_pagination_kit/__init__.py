"""Pull-based pagination over injected fetch callables."""

from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar

__all__ = [
    "CursorCycleError",
    "PaginationError",
    "iter_cursors",
    "iter_page_numbers",
]

T = TypeVar("T")


class PaginationError(RuntimeError):
    """Base class for pagination guard failures."""


class CursorCycleError(PaginationError):
    """A cursor would be fetched for a second time."""


def iter_page_numbers(
    fetch_page: Callable[[int], Iterable[T]],
    *,
    start_page: int = 1,
) -> Iterator[T]:
    """Yield items in order until the first empty page.

    ``fetch_page`` receives consecutive page numbers starting at ``start_page``.
    Fetches are deferred until iteration and exceptions propagate unchanged.
    """
    if isinstance(start_page, bool) or not isinstance(start_page, int):
        raise TypeError("start_page must be an integer")
    if start_page < 0:
        raise ValueError("start_page must be nonnegative")

    def items() -> Iterator[T]:
        page_number = start_page
        while True:
            empty = True
            for item in fetch_page(page_number):
                empty = False
                yield item
            if empty:
                return
            page_number += 1

    return items()


def iter_cursors(
    fetch_page: Callable[[str | None], tuple[Iterable[T], str | None]],
    *,
    start_cursor: str | None = None,
) -> Iterator[T]:
    """Yield items from ``(items, next_cursor)`` responses in cursor order.

    The first call receives ``start_cursor``. A response's ``None`` cursor ends
    iteration after its items; all strings, including ``""``, continue even
    after an empty page. A repeated cursor raises ``CursorCycleError`` before
    it is fetched again, after the preceding page's items have been yielded.
    """
    if start_cursor is not None and not isinstance(start_cursor, str):
        raise TypeError("start_cursor must be a string or None")

    def items() -> Iterator[T]:
        cursor = start_cursor
        seen: set[str | None] = set()
        while True:
            if cursor in seen:
                raise CursorCycleError("fetch returned a previously requested cursor")
            seen.add(cursor)
            page_items, next_cursor = fetch_page(cursor)
            if next_cursor is not None and not isinstance(next_cursor, str):
                raise TypeError("next_cursor must be a string or None")
            for item in page_items:
                yield item
            if next_cursor is None:
                return
            cursor = next_cursor

    return items()
