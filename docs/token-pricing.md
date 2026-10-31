# Token details and API-equivalent costs

In **Classic Tasks**, swipe horizontally to move between the dashboard and token
details. On the details page, tap **Today** or **7 days**. The selection stays in
place until changed; pages do not cycle automatically. Physical buttons retain
their existing brightness, theme and settings functions. Touch is ignored while
the screen is off, waiting for the companion, showing an alert, or in settings.
The CST9220 input coordinates follow all four display rotations.

The original Codex / Token usage / USB header is retained, with the center title
vertically aligned. Token totals on the dashboard now include a cost summary.
Details separate uncached input (labelled Input (new)), cached input and output.
Reasoning tokens are a subset of output, not an additional charge/category.

Costs are **USD at Standard API rates**, not subscription charges or an account
invoice. Per-request input length selects short/long context rates. Fast/Batch,
regional premiums, tools and other non-token charges are not included. The
comparison deliberately uses Standard rates even if the Codex turn ran in a
different speed tier.

## Model attribution and missing data

The companion joins local `token_usage_record` response IDs/turn IDs to the model
in `turn_context`. Response IDs are deduplicated across resumed/forked logs.
The selected model is the available evidence, not proof of internal routing.
Old cumulative-only records remain in token totals but do not acquire a fabricated
breakdown. Unknown/internal models (including `codex-auto-review`) remain unpriced.
Requests with cache-write tokens are unpriced because these logs do not establish
the cache retention needed to choose the published write rate.

A **+** after a cost marks a priced subtotal with some usage unpriced. The footer
also warns about missing token breakdowns. In that case category counts need not
sum to the recorded total. **Tokens / pricing** in the desktop control panel shows
model totals, priced subtotals, unpriced token counts and reasons. Small values
are rounded on the device; the desktop retains microdollar calculation precision.

## Pricing source and history

The authoritative source is [OpenAI API pricing](https://developers.openai.com/api/docs/pricing),
using its [machine-readable Markdown](https://developers.openai.com/api/docs/pricing.md).
The bundled baseline was reviewed on 29 October 2026 and applies from that UTC
date. Earlier usage is unpriced: this release does not invent historical rates.

While running, the companion checks the official source at most once every 24
hours, with a bounded network timeout. A whitespace-normalized fingerprint
includes pricing prose, so changes to terms as well as rates prompt a warning.
The tray posts a notification and the control panel retains a warning banner.
Click the tray notification to open a small explanation and rate comparison with
the last accepted revision. A page change does not necessarily mean rates changed.
The same dialog is available from the tray's **Pricing source status** menu item.
Opening it does not accept anything; stale notifications show the current status.
A failed download or changed table schema produces a distinct check-failure
warning and leaves saved prices in use. The main usage/Bluetooth loop is separate.

Use **Tokens / pricing → Check official source → Review pricing update** to
inspect parsed changes and open the official page. **Accept reviewed rates from
now** adds a new dated revision; it does not overwrite earlier rates or reprice
past requests. If context rules/table schema change, the parser must be updated
before a candidate can be accepted. There is no silent automatic rate adoption.

Pricing revisions, pending updates, check state and a summary report are local
under `%USERPROFILE%\.codexmeter\pricing`. The network check sends no usage,
credentials or chat contents. These runtime files are not stored in Git.

## Validation

Python regression tests cover cached-input accounting, multiple models, duplicate
response records, unknown attribution, date/context selection, immutable rate
revisions, source-change/failure states and the 512-byte BLE limit.
`tools/validate_c6_token_cost.py` exercises the page/period UI with serial gesture
injection and captures actual device frames. This verifies UI behavior but does
not replace a physical swipe/tap check by the person holding the display.
