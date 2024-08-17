from collections.abc import Callable, Iterable, Iterator

import pytest

from api_pagination_kit import (
    PageLimitError,
    PaginationError,
    iter_cursors,
    iter_page_numbers,
)


def paginate(
    mode: str, fetch_items: Callable[[], Iterable[int]], *, max_pages: int
) -> Iterator[int]:
    if mode == "cursor":
        return iter_cursors(lambda _: (fetch_items(), None), max_pages=max_pages)
    return iter_page_numbers(lambda _: fetch_items(), max_pages=max_pages)


@pytest.mark.parametrize("mode", ["number", "cursor"])
@pytest.mark.parametrize(
    ("value", "error_type"),
    [(True, TypeError), (2.5, TypeError), (0, ValueError), (-2, ValueError)],
)
def test_page_limit_is_validated_at_construction(
    mode: str, value: object, error_type: type[Exception]
) -> None:
    def unexpected_fetch() -> Iterable[int]:
        pytest.fail("fetch called before iteration")

    with pytest.raises(error_type, match="max_pages"):
        paginate(mode, unexpected_fetch, max_pages=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", ["number", "cursor"])
def test_fetch_errors_propagate_without_retry(mode: str) -> None:
    failure = OSError("synthetic fetch failure")
    calls = 0

    def fetch() -> Iterable[int]:
        nonlocal calls
        calls += 1
        raise failure

    items = paginate(mode, fetch, max_pages=2)
    assert calls == 0
    with pytest.raises(OSError) as error:
        next(items)
    assert error.value is failure
    assert list(items) == []
    assert calls == 1


@pytest.mark.parametrize("mode", ["number", "cursor"])
def test_item_source_errors_propagate_after_partial_page(mode: str) -> None:
    failure = ValueError("synthetic item failure")

    def fetch() -> Iterator[int]:
        yield 10
        raise failure

    items = paginate(mode, fetch, max_pages=1)
    assert next(items) == 10
    with pytest.raises(ValueError) as error:
        next(items)
    assert error.value is failure
    assert list(items) == []


def test_default_limit_bounds_a_source_that_never_ends() -> None:
    calls = 0

    def fetch(number: int) -> tuple[int]:
        nonlocal calls
        calls += 1
        return (number,)

    with pytest.raises(PageLimitError) as error:
        list(iter_page_numbers(fetch))
    assert isinstance(error.value, PaginationError)
    assert calls == 1_000
