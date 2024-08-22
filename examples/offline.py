"""Show both pagination patterns without a network or external client."""

from itertools import islice

from api_pagination_kit import iter_cursors, iter_page_numbers


def demo_page_numbers() -> None:
    pages = {0: ("paper clips", "labels"), 1: ("folders",)}

    def fetch(page: int) -> tuple[str, ...]:
        return pages.get(page, ())  # The third request finds the empty sentinel.

    items = iter_page_numbers(fetch, start_page=0, max_pages=3)
    print(f"Numbered: {list(items)}")


def demo_cursors() -> None:
    pages: dict[str | None, tuple[tuple[str, ...], str | None]] = {
        None: (("notebook",), "demo-gap"),
        "demo-gap": ((), "demo-last"),
        "demo-last": (("pencil", "eraser"), None),
    }
    requests: list[str | None] = []

    def fetch(cursor: str | None) -> tuple[tuple[str, ...], str | None]:
        requests.append(cursor)
        return pages[cursor]

    items = iter_cursors(fetch)
    print(f"Cursor preview: {list(islice(items, 1))}")
    print(f"Requests after preview: {requests}")
    print(f"Cursor remainder: {list(items)}")
    print(f"Requests after completion: {requests}")


if __name__ == "__main__":
    demo_page_numbers()
    demo_cursors()
