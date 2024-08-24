from collections.abc import Callable, Iterator

import pytest

from api_pagination_kit import (
    NumberedPage,
    PageLimitError,
    iter_numbered_pages,
    iter_page_numbers,
)


@pytest.mark.parametrize("paginate", [iter_page_numbers, iter_numbered_pages])
def test_known_end_completes_at_the_limit_without_an_extra_fetch(
    paginate: Callable[..., Iterator[object]],
) -> None:
    calls: list[int] = []

    def fetch(number: int) -> tuple[int]:
        calls.append(number)
        return (number,)

    results = paginate(
        fetch,
        start_page=0,
        end_page=1,
        max_pages=2,
        should_cancel=lambda: len(calls) == 2,
    )
    assert calls == []
    if paginate is iter_numbered_pages:
        assert list(results) == [NumberedPage(0, (0,)), NumberedPage(1, (1,))]
    else:
        assert list(results) == [0, 1]
    assert calls == [0, 1]


def test_zero_is_a_valid_inclusive_end_page() -> None:
    assert list(iter_page_numbers(lambda n: (n,), start_page=0, end_page=0)) == [0]


def test_empty_response_stops_before_known_end() -> None:
    calls: list[int] = []

    def fetch(number: int) -> tuple[int, ...]:
        calls.append(number)
        return (42,) if number == 1 else ()

    assert list(iter_numbered_pages(fetch, end_page=4)) == [NumberedPage(1, (42,))]
    assert calls == [1, 2]


def test_known_end_does_not_override_a_smaller_page_budget() -> None:
    calls: list[int] = []

    def fetch(number: int) -> tuple[int]:
        calls.append(number)
        return (number,)

    items = iter_page_numbers(fetch, end_page=2, max_pages=1)
    assert next(items) == 1
    with pytest.raises(PageLimitError):
        next(items)
    assert calls == [1]


@pytest.mark.parametrize(
    ("end_page", "error"), [(True, TypeError), (2.5, TypeError), (1, ValueError)]
)
def test_known_end_is_validated_at_construction(
    end_page: object, error: type[Exception]
) -> None:
    with pytest.raises(error, match="end_page"):
        iter_numbered_pages(lambda _: (), start_page=2, end_page=end_page)  # type: ignore[arg-type]
