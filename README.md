# API Pagination Kit

Typed, synchronous pagination iterators for Python 3.11+ with no runtime
dependencies. Your fetch function handles requests and response decoding;
the kit decides which page to request next and yields the items in order.

## Install and try it locally

From a local checkout:

```sh
python -m pip install .
python examples/offline.py
```

The [offline demo](examples/offline.py) uses in-memory pages and synthetic
cursors. It shows a zero-based page sequence, and a cursor traversal in which
requesting a single item fetches just the first page:

```text
Numbered: ['paper clips', 'labels', 'folders']
Cursor preview: ['notebook']
Requests after preview: [None]
Cursor remainder: ['pencil', 'eraser']
Requests after completion: [None, 'demo-gap', 'demo-last']
```

## API

Both functions are imported from `api_pagination_kit` and return a single-use
`Iterator[T]`. Results preserve the fetcher's item order, including duplicates.
Pages may contain any iterable of `T`, including a generator.

| Function | Fetch callable | End condition |
| --- | --- | --- |
| `iter_page_numbers(fetch_page, *, start_page=1, max_pages=1000)` | `Callable[[int], Iterable[T]]` | Stops at the first empty page. A short nonempty page still advances. |
| `iter_cursors(fetch_page, *, start_cursor=None, max_pages=1000)` | `Callable[[str \| None], tuple[Iterable[T], str \| None]]` | Stops after yielding the items from a response whose next cursor is `None`. |

- **Page numbers:** `start_page` is a nonnegative integer. Page numbers increase
  by one; an API whose last page is nonempty needs a final empty response to
  signal completion under this pattern.
- **Cursors:** `start_cursor` is the first value passed to the callable (`None`
  for a fresh traversal by default). Each fetch returns `(items, next_cursor)`.
  Cursor strings are opaque, and `""` is a valid continuation. An empty page with
  a continuation advances, and an empty page with `None` ends normally.

### Pull-based execution and errors

- Creating the iterator validates the options but performs no fetch or item
  work. Fetches are synchronous, with no prefetch or buffering of items by the
  kit. A page's iterable is consumed before the next fetch; stopping iteration
  stops further requests. A single cursor pull may cross several empty pages.
- `max_pages` is a positive integer and counts requests, including empty pages.
  Normal termination exactly at the limit is allowed. If another fetch would
  exceed the limit, `PageLimitError` is raised after the items from the last
  allowed page have been yielded, before a further fetch can happen.
- `CursorCycleError` is raised before a repeated cursor can be fetched, after
  the current page's items have been yielded. A repeated continuation at the
  limit raises `CursorCycleError` rather than `PageLimitError`. Both are
  subclasses of `PaginationError` (`RuntimeError`).
- Invalid option types raise `TypeError` at construction; booleans are not
  accepted as integers. Out-of-range integer options raise `ValueError`.
  An invalid continuation type raises `TypeError` before any items from that
  response are yielded.
- Fetch and item-source errors propagate on the pull that encounters them;
  items already yielded stay yielded, and the iterator cannot resume after an
  error. As with any Python generator, a `StopIteration` raised directly by the
  fetch callable becomes `RuntimeError`, while exhaustion of a page's item
  iterable is normal. Retries and timeouts belong in the injected callable;
  the page budget is not a timeout or an item limit.

## Development

```sh
python -m pip install '.[test]'
python -m pytest
```
