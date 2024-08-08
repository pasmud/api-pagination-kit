# API Pagination Kit

Typed, synchronous pagination iterators for Python 3.11+, with no runtime
dependencies. Supply a fetch function and iterate over its items.

`iter_page_numbers(fetch_page, start_page=1)` fetches consecutive page numbers
until a page returns no items. The fetch function takes an integer and returns
an iterable of items. A short nonempty page does not stop the iterator.

`iter_cursors(fetch_page, start_cursor=None)` passes opaque string cursors to
a fetch function returning `(items, next_cursor)`. A `None` response cursor
ends iteration after that page; empty pages with a continuation still advance.
A cursor is never requested twice: a cycle raises `CursorCycleError`.

Install from a local checkout with `python -m pip install .`.
