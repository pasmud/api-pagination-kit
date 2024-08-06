"""Pull-based pagination over injected fetch callables."""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Generic, TypeVar

__all__ = [
    "CursorCycleError",
    "CursorPage",
    "NumberedPage",
    "PageLimitError",
    "PaginationError",
    "iter_cursor_pages",
    "iter_cursors",
    "iter_numbered_pages",
    "iter_page_numbers",
]

T = TypeVar("T")
_DEFAULT_MAX_PAGES = 1_000


@dataclass(frozen=True, slots=True)
class NumberedPage(Generic[T]):
    """A nonempty batch and the page number used to request it."""

    number: int
    items: tuple[T, ...]


@dataclass(frozen=True, slots=True)
class CursorPage(Generic[T]):
    """A batch and its request/continuation cursors, omitted from repr."""

    cursor: str | None = field(repr=False)
    items: tuple[T, ...]
    next_cursor: str | None = field(repr=False)


class PaginationError(RuntimeError):
    """Base class for pagination guard failures."""


class CursorCycleError(PaginationError):
    """A cursor would be fetched for a second time."""


class PageLimitError(PaginationError):
    """A further fetch would exceed the caller's page limit."""


def _validate_page_limit(max_pages: int) -> None:
    if isinstance(max_pages, bool) or not isinstance(max_pages, int):
        raise TypeError("max_pages must be an integer")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")


def _numbered_responses(
    fetch_page: Callable[[int], Iterable[T]],
    *,
    start_page: int,
    max_pages: int,
) -> Iterator[tuple[int, Iterable[T]]]:
    if isinstance(start_page, bool) or not isinstance(start_page, int):
        raise TypeError("start_page must be an integer")
    if start_page < 0:
        raise ValueError("start_page must be nonnegative")
    _validate_page_limit(max_pages)

    def responses() -> Iterator[tuple[int, Iterable[T]]]:
        for page_number in range(start_page, start_page + max_pages):
            yield page_number, fetch_page(page_number)
        raise PageLimitError(f"pagination requires more than {max_pages} page fetches")

    return responses()


def iter_page_numbers(
    fetch_page: Callable[[int], Iterable[T]],
    *,
    start_page: int = 1,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> Iterator[T]:
    """Yield items in order until the first empty page.

    ``fetch_page`` receives consecutive page numbers starting at ``start_page``.
    Fetches are deferred until iteration. If all ``max_pages`` permitted
    fetches produce items, a further pull raises ``PageLimitError`` rather
    than fetching again.
    """
    responses = _numbered_responses(
        fetch_page, start_page=start_page, max_pages=max_pages
    )

    def items() -> Iterator[T]:
        for _, page_items in responses:
            empty = True
            for item in page_items:
                empty = False
                yield item
            if empty:
                return

    return items()


def iter_numbered_pages(
    fetch_page: Callable[[int], Iterable[T]],
    *,
    start_page: int = 1,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> Iterator[NumberedPage[T]]:
    """Yield nonempty numbered batches, consuming one page per pull."""
    responses = _numbered_responses(
        fetch_page, start_page=start_page, max_pages=max_pages
    )

    def pages() -> Iterator[NumberedPage[T]]:
        for number, page_items in responses:
            batch = tuple(page_items)
            if not batch:
                return
            yield NumberedPage(number, batch)

    return pages()


def _cursor_responses(
    fetch_page: Callable[[str | None], tuple[Iterable[T], str | None]],
    *,
    start_cursor: str | None,
    max_pages: int,
) -> Iterator[tuple[str | None, Iterable[T], str | None]]:
    if start_cursor is not None and not isinstance(start_cursor, str):
        raise TypeError("start_cursor must be a string or None")
    _validate_page_limit(max_pages)

    def responses() -> Iterator[tuple[str | None, Iterable[T], str | None]]:
        cursor = start_cursor
        seen: set[str | None] = set()
        for _ in range(max_pages):
            seen.add(cursor)
            page_items, next_cursor = fetch_page(cursor)
            if next_cursor is not None and not isinstance(next_cursor, str):
                raise TypeError("next_cursor must be a string or None")
            yield cursor, page_items, next_cursor
            if next_cursor is None:
                return
            if next_cursor in seen:
                raise CursorCycleError("fetch returned a previously requested cursor")
            cursor = next_cursor
        raise PageLimitError(f"pagination requires more than {max_pages} page fetches")

    return responses()


def iter_cursors(
    fetch_page: Callable[[str | None], tuple[Iterable[T], str | None]],
    *,
    start_cursor: str | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> Iterator[T]:
    """Yield items from ``(items, next_cursor)`` responses in cursor order.

    The first call receives ``start_cursor``. A response's ``None`` cursor ends
    iteration after its items; all strings, including ``""``, continue even
    after an empty page. A repeated cursor raises ``CursorCycleError`` before
    it is fetched again, after the preceding page's items have been yielded.
    A further distinct cursor beyond ``max_pages`` fetches raises
    ``PageLimitError``. Empty pages count toward this limit.
    """
    responses = _cursor_responses(
        fetch_page, start_cursor=start_cursor, max_pages=max_pages
    )

    def items() -> Iterator[T]:
        for _, page_items, _ in responses:
            for item in page_items:
                yield item

    return items()


def iter_cursor_pages(
    fetch_page: Callable[[str | None], tuple[Iterable[T], str | None]],
    *,
    start_cursor: str | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> Iterator[CursorPage[T]]:
    """Yield cursor batches, including empty pages and the terminal response."""
    responses = _cursor_responses(
        fetch_page, start_cursor=start_cursor, max_pages=max_pages
    )
    return (
        CursorPage(cursor, tuple(page_items), next_cursor)
        for cursor, page_items, next_cursor in responses
    )
