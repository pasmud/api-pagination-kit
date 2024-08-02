# API Pagination Kit

Typed, synchronous pagination iterators for Python 3.11+, with no runtime
dependencies. Supply a fetch function and iterate over its items.

`iter_page_numbers(fetch_page, start_page=1)` fetches consecutive page numbers
until a page returns no items. The fetch function takes an integer and returns
an iterable of items. A short nonempty page does not stop the iterator.

Install from a local checkout with `python -m pip install .`.
