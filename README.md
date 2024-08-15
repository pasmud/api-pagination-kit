# API Pagination Kit

Typed, synchronous pagination iterators for Python 3.11+ with no runtime
dependencies. Your fetch function handles requests and response decoding;
the kit decides which page to request next and yields items or whole pages in order.

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

Import the iterators and page types from `api_pagination_kit`. The item
iterators below return a single-use `Iterator[T]`. All iterators preserve the
fetcher's item order, including duplicates. A fetcher may return any iterable
of `T` for the page items, including a generator.

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

### Whole pages and checkpoints

`iter_numbered_pages` takes the same arguments as `iter_page_numbers` and
yields `NumberedPage[T]` objects with `number` and `items` attributes. It
omits the empty response that signals the end. `iter_cursor_pages` takes the
same arguments as `iter_cursors` and yields `CursorPage[T]` objects with
`cursor`, `items`, and `next_cursor` attributes. It includes empty responses,
even the terminal one, so callers can observe every cursor transition.

Each page iterator consumes one response fully into a tuple before yielding
its batch. Use the item iterators for streaming within a page. A failed item
source does not yield a partial batch.

After processing a cursor batch, you can save its `next_cursor` and pass it
as `start_cursor` in a later run. Treat `None` as completion rather than
restarting, and preserve `""` as a valid checkpoint. A new iterator starts
with a fresh request budget and cycle history; a continuation is checked
for cycles when the current iterator advances. The page representation omits
both cursor fields.

### Pull-based execution and errors

- Creating the iterator validates the options but performs no fetch or item
  work. Fetches are synchronous, with no prefetch. A page's iterable is
  consumed before the next fetch; stopping iteration stops further requests.
  A single pull from `iter_cursors` may cross several empty pages.
- `max_pages` is a positive integer and counts requests, including empty pages.
  Normal termination exactly at the limit is allowed. If another fetch would
  exceed the limit, `PageLimitError` is raised after the items from the last
  allowed page have been yielded, before a further fetch can happen.
- `CursorCycleError` is raised before a repeated cursor can be fetched, after
  the current page's items have been yielded. A repeated continuation at the
  limit raises `CursorCycleError` rather than `PageLimitError`.
- All four iterators accept an optional `should_cancel` callback (for example,
  `stop_event.is_set`). It is called with no arguments just before each
  otherwise permitted fetch, including the first. If it returns true,
  `PaginationCancelledError` closes the iterator without making that fetch.
  It does not interrupt an in-progress call or a page's item stream. Normal
  completion, cycle detection, and the request limit take precedence.
- These three errors subclass `PaginationError` (`RuntimeError`). When raised
  by the kit, `pages_fetched` counts responses already fetched, including empty
  pages. `PageLimitError.max_pages` gives the configured limit, and
  `CursorCycleError.first_seen_on_page` gives the repeated cursor's original
  request position (1-based). These diagnostics do not contain cursor values.
- Invalid option types raise `TypeError` at construction; booleans are not
  accepted as integers. Out-of-range integer options raise `ValueError`.
  An invalid continuation type raises `TypeError` before any items from that
  response are yielded.
- Fetch, cancellation callback, and item-source errors propagate on the pull
  that encounters them; items already yielded stay yielded, and the iterator
  cannot resume after an error. As with any Python generator, a `StopIteration`
  raised directly by the fetch callable or cancellation callback becomes
  `RuntimeError`, while exhaustion of a page's item iterable is normal. Retries
  and timeouts belong in the injected callable; the page budget is not a timeout
  or an item limit.

## Development

```sh
python -m pip install '.[test]' ruff
ruff check
ruff format --check
python -m pytest
```

CI checks the installed package on Python 3.11 and 3.14.
