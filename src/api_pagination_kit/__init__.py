"""Pull-based pagination over injected fetch callables."""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Generic, TypeVar

__all__ = [
    "CursorCycleError",
    "CursorPage",
    "NumberedPage",
    "PageLimitError",
    "PaginationCancelledError",
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

    def __init__(self, *args: object, pages_fetched: int | None = None) -> None:
        super().__init__(*args)
        self.pages_fetched = pages_fetched


class CursorCycleError(PaginationError):
    """A cursor would be fetched for a second time."""

    def __init__(
        self,
        *args: object,
        pages_fetched: int | None = None,
        first_seen_on_page: int | None = None,
    ) -> None:
        super().__init__(*args, pages_fetched=pages_fetched)
        self.first_seen_on_page = first_seen_on_page


class PageLimitError(PaginationError):
    """A further fetch would exceed the caller's page limit."""

    def __init__(
        self,
        *args: object,
        pages_fetched: int | None = None,
        max_pages: int | None = None,
    ) -> None:
        super().__init__(*args, pages_fetched=pages_fetched)
        self.max_pages = max_pages


class PaginationCancelledError(PaginationError):
    """The caller cancelled pagination before the next fetch."""


def _validate_guards(max_pages: int, should_cancel: Callable[[], bool] | None) -> None:
    if isinstance(max_pages, bool) or not isinstance(max_pages, int):
        raise TypeError("max_pages must be an integer")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if should_cancel is not None and not callable(should_cancel):
        raise TypeError("should_cancel must be callable or None")


def _check_cancel(should_cancel: Callable[[], bool] | None, pages_fetched: int) -> None:
    if should_cancel is not None and should_cancel():
        raise PaginationCancelledError(
            "pagination cancelled before the next page fetch",
            pages_fetched=pages_fetched,
        )


def _page_limit_error(max_pages: int) -> PageLimitError:
    return PageLimitError(
        f"pagination requires more than {max_pages} page fetches",
        pages_fetched=max_pages,
        max_pages=max_pages,
    )


def _numbered_responses(
    fetch_page: Callable[[int], Iterable[T]],
    *,
    start_page: int,
    end_page: int | None,
    max_pages: int,
    should_cancel: Callable[[], bool] | None,
) -> Iterator[tuple[int, Iterable[T]]]:
    if isinstance(start_page, bool) or not isinstance(start_page, int):
        raise TypeError("start_page must be an integer")
    if start_page < 0:
        raise ValueError("start_page must be nonnegative")
    if end_page is not None:
        if isinstance(end_page, bool) or not isinstance(end_page, int):
            raise TypeError("end_page must be an integer or None")
        if end_page < start_page:
            raise ValueError("end_page must be at least start_page")
    _validate_guards(max_pages, should_cancel)

    def responses() -> Iterator[tuple[int, Iterable[T]]]:
        for pages_fetched in range(max_pages):
            _check_cancel(should_cancel, pages_fetched)
            page_number = start_page + pages_fetched
            yield page_number, fetch_page(page_number)
            if page_number == end_page:
                return
        raise _page_limit_error(max_pages)

    return responses()


def iter_page_numbers(
    fetch_page: Callable[[int], Iterable[T]],
    *,
    start_page: int = 1,
    end_page: int | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
    should_cancel: Callable[[], bool] | None = None,
) -> Iterator[T]:
    """Yield items in order until the first empty page or inclusive end page.

    ``fetch_page`` receives consecutive page numbers starting at ``start_page``.
    Supply ``end_page`` when the last page is known to avoid an extra fetch.
    Fetches are deferred until iteration. If another fetch would exceed
    ``max_pages``, a further pull raises ``PageLimitError``. If ``should_cancel``
    returns true before an allowed fetch, ``PaginationCancelledError`` is raised
    instead of fetching.
    """
    responses = _numbered_responses(
        fetch_page,
        start_page=start_page,
        end_page=end_page,
        max_pages=max_pages,
        should_cancel=should_cancel,
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
    end_page: int | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
    should_cancel: Callable[[], bool] | None = None,
) -> Iterator[NumberedPage[T]]:
    """Batch pages from the same traversal as ``iter_page_numbers``."""
    responses = _numbered_responses(
        fetch_page,
        start_page=start_page,
        end_page=end_page,
        max_pages=max_pages,
        should_cancel=should_cancel,
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
    should_cancel: Callable[[], bool] | None,
) -> Iterator[tuple[str | None, Iterable[T], str | None]]:
    if start_cursor is not None and not isinstance(start_cursor, str):
        raise TypeError("start_cursor must be a string or None")
    _validate_guards(max_pages, should_cancel)

    def responses() -> Iterator[tuple[str | None, Iterable[T], str | None]]:
        cursor = start_cursor
        seen: dict[str | None, int] = {}
        for pages_fetched in range(max_pages):
            _check_cancel(should_cancel, pages_fetched)
            seen[cursor] = pages_fetched + 1
            page_items, next_cursor = fetch_page(cursor)
            if next_cursor is not None and not isinstance(next_cursor, str):
                raise TypeError("next_cursor must be a string or None")
            yield cursor, page_items, next_cursor
            if next_cursor is None:
                return
            if next_cursor in seen:
                raise CursorCycleError(
                    "fetch returned a previously requested cursor",
                    pages_fetched=pages_fetched + 1,
                    first_seen_on_page=seen[next_cursor],
                )
            cursor = next_cursor
        raise _page_limit_error(max_pages)

    return responses()


def iter_cursors(
    fetch_page: Callable[[str | None], tuple[Iterable[T], str | None]],
    *,
    start_cursor: str | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
    should_cancel: Callable[[], bool] | None = None,
) -> Iterator[T]:
    """Yield items from ``(items, next_cursor)`` responses in cursor order.

    The first call receives ``start_cursor``. A response's ``None`` cursor ends
    iteration after its items; all strings, including ``""``, continue even
    after an empty page. A repeated cursor raises ``CursorCycleError`` before
    it is fetched again, after the preceding page's items have been yielded.
    A further distinct cursor beyond ``max_pages`` fetches raises
    ``PageLimitError``. Empty pages count toward this limit. If ``should_cancel``
    returns true before an allowed fetch, ``PaginationCancelledError`` is raised
    instead of fetching.
    """
    responses = _cursor_responses(
        fetch_page,
        start_cursor=start_cursor,
        max_pages=max_pages,
        should_cancel=should_cancel,
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
    should_cancel: Callable[[], bool] | None = None,
) -> Iterator[CursorPage[T]]:
    """Yield cursor batches, including empty pages and the terminal response."""
    responses = _cursor_responses(
        fetch_page,
        start_cursor=start_cursor,
        max_pages=max_pages,
        should_cancel=should_cancel,
    )
    return (
        CursorPage(cursor, tuple(page_items), next_cursor)
        for cursor, page_items, next_cursor in responses
    )
