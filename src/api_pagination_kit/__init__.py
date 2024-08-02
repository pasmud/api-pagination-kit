"""Pull-based pagination over injected fetch callables."""

from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar

__all__ = ["iter_page_numbers"]

T = TypeVar("T")


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
