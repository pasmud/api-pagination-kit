from collections.abc import Iterator
from itertools import islice

import pytest

from api_pagination_kit import PageLimitError, iter_page_numbers


def test_starting_at_zero_and_stopping_at_first_empty_page() -> None:
    pages = {0: ["a"], 1: ["b", "c"], 2: [], 3: ["unreachable"]}
    calls: list[int] = []

    def fetch(number: int) -> list[str]:
        calls.append(number)
        return pages[number]

    assert list(iter_page_numbers(fetch, start_page=0, max_pages=3)) == ["a", "b", "c"]
    assert calls == [0, 1, 2]


def test_first_page_can_be_empty() -> None:
    def fetch(number: int) -> tuple[()]:
        assert number == 1
        return ()

    assert list(iter_page_numbers(fetch)) == []


def test_demand_drives_fetches_and_consumption_of_page_items() -> None:
    events: list[tuple[str, int]] = []

    def fetch(number: int) -> Iterator[int]:
        events.append(("fetch", number))

        def page() -> Iterator[int]:
            for item in range(number * 2, number * 2 + 2):
                events.append(("item", item))
                yield item

        return page()

    items = iter_page_numbers(fetch)
    assert events == []
    assert list(islice(items, 2)) == [2, 3]
    assert events == [("fetch", 1), ("item", 2), ("item", 3)]
    assert next(items) == 4
    assert events[-2:] == [("fetch", 2), ("item", 4)]


@pytest.mark.parametrize("value", [True, 1.0, "1", None])
def test_start_page_rejects_non_integers(value: object) -> None:
    with pytest.raises(TypeError, match="start_page"):
        iter_page_numbers(lambda _: (), start_page=value)  # type: ignore[arg-type]


def test_start_page_rejects_negative_numbers() -> None:
    with pytest.raises(ValueError, match="start_page"):
        iter_page_numbers(lambda _: (), start_page=-1)


def test_limit_counts_pages_and_preserves_all_items_on_last_allowed_page() -> None:
    calls: list[int] = []

    def fetch(number: int) -> list[int]:
        calls.append(number)
        return [number, -number]

    items = iter_page_numbers(fetch, start_page=23, max_pages=2)
    assert list(islice(items, 4)) == [23, -23, 24, -24]
    with pytest.raises(PageLimitError):
        next(items)
    assert calls == [23, 24]
    assert list(items) == []
