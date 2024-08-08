import pytest

from api_pagination_kit import CursorCycleError, PaginationError, iter_cursors


def test_empty_page_continues_and_empty_string_is_a_cursor() -> None:
    calls: list[str | None] = []
    pages: dict[str | None, tuple[list[str], str | None]] = {
        None: (["first"], "gap"),
        "gap": ([], ""),
        "": (["first", "last"], None),
    }

    def fetch(cursor: str | None) -> tuple[list[str], str | None]:
        calls.append(cursor)
        return pages[cursor]

    items = iter_cursors(fetch)
    assert calls == []
    assert next(items) == "first"
    assert calls == [None]
    assert next(items) == "first"
    assert calls == [None, "gap", ""]
    assert list(items) == ["last"]
    assert calls == [None, "gap", ""]


def test_empty_terminal_page_is_exhaustion() -> None:
    def fetch(cursor: str | None) -> tuple[list[str], None]:
        assert cursor is None
        return [], None

    assert list(iter_cursors(fetch)) == []


def test_cycle_back_to_start_raises_after_page_items_without_refetching() -> None:
    calls: list[str | None] = []
    start = "synthetic-start-token"

    def fetch(cursor: str | None) -> tuple[list[int], str]:
        calls.append(cursor)
        if cursor == start:
            return [1], "next"
        return [2, 3], start

    items = iter_cursors(fetch, start_cursor=start)
    assert [next(items), next(items), next(items)] == [1, 2, 3]
    with pytest.raises(CursorCycleError) as error:
        next(items)
    assert isinstance(error.value, PaginationError)
    assert start not in str(error.value)
    assert calls == [start, "next"]
    assert list(items) == []


def test_empty_self_loop_is_detected_during_one_pull() -> None:
    calls: list[str | None] = []

    def fetch(cursor: str | None) -> tuple[list[int], str]:
        calls.append(cursor)
        return [], ""

    with pytest.raises(CursorCycleError):
        next(iter_cursors(fetch, start_cursor=""))
    assert calls == [""]


def test_start_cursor_rejects_non_strings_without_fetching() -> None:
    def fetch(cursor: str | None) -> tuple[list[str], None]:
        pytest.fail(f"Unexpected fetch for {cursor!r}")

    with pytest.raises(TypeError, match="start_cursor"):
        iter_cursors(fetch, start_cursor=0)  # type: ignore[arg-type]


def test_invalid_continuation_is_rejected_before_page_items() -> None:
    items = iter_cursors(lambda _: (["unreachable"], 0))  # type: ignore[arg-type, return-value]
    with pytest.raises(TypeError, match="next_cursor"):
        next(items)
