# How this project works

The repository has a Python collector and an Android Flutter client. There is no
price database or app-side store scraper. Standard builds download static JSON
from the GitHub `main/data` folder configured in `app/lib/data/repo.dart`. Private
live-refresh builds connect to `collector/serve.py` through authorized ADB, request
fresh collection jobs, follow their progress and fetch a completed snapshot.
See [the live-refresh workflow](live-refresh.md).

## Collection and discovery

`collector/sources.py` is the source registry. It contains automatic marketplaces,
Egyptian electronics/gaming stores, and a separate manual directory. IDs are the
join key between registry entries, collection health and offers.

`collector/collect.py` runs the selected collectors, stamps observations in Cairo
time, and checkpoints after each source. An unsuccessful retry retains successful
offers from the same day and records the latest failure plus `retained_from`.
Yesterday's prices are never copied into a new day's offers. Previously discovered
product **URLs** can be reused, but their prices and stock are fetched again.

`collector/discovery.py` discovers links from relative/absolute anchors, embedded
routes, next-page links and optional bounded XML sitemaps. URLs must belong to the
configured store. Tracking parameters are removed; `variant`, `product_id`, `id`,
`slug` and `combination_id` are preserved. This matters for OpenCart/iKlinik, where
removing the query would collapse different products into one listing.

`collector/http_sources.py` supports:

- Shopify console collection catalogues, or Arabic/English predictive searches
  expanded through search pages when the ten-product limit is reached. Individual
  Ajax product responses supply variant prices and availability. The read-only
  `cart.js` currency confirms EGP; Ajax prices in piastres are divided by 100.
- Paginated WooCommerce Store API searches, with the declared currency minor unit.
  Variable price ranges are resolved through the product page rather than assumed
  to be the price of an available variant. Embedded variation forms preserve each
  option's condition, price and stock even when the API has no price range. A used
  variant cannot supply the new variant's price or availability.
- JSON-LD Product / ProductGroup / ItemList data and Magento's main-product Offer
  microdata. An AggregateOffer's `lowPrice` alone is not a seller offer. Foreign
  currency and explicitly used/refurbished conditions are excluded.

Social pages also serve as discovery entry points. Verified business profiles,
cross-linked websites and review notes live in the registry and public directory.
Stores with readable current prices become automatic sources; other verified
shops remain manual entries with their direct public page. Social posts themselves
are not scraped into prices. See the [social audit](social-source-research.md).

`collector/browser_sources.py` uses the repository's existing Playwright/Chrome
integration for Amazon, Noon, Jumia, Carrefour and stores requiring rendering.
It follows exposed next-page links and deduplicates product keys between searches.
Amazon/Noon seller panels are expanded when available. Search-card stock is an
indication of availability; seller-panel failures are recorded as warnings. This
does not guarantee that every marketplace seller or delivery-area offer is exposed.

`collector/classify.py` filters consoles, separates Digital/Disc and bundles,
detects the Slim model and region, and rejects used/open-box/refurbished/Fabrika,
Pro, accessories and standalone drives. Explicit Slim/CFI-2xxx evidence takes
priority over storage capacity: newer Slim Digital listings can say 825GB.
Ambiguous model titles remain `slim_confirmed: false` and are hidden by default.

## Data and app

- `data/snapshots/YYYY-MM-DD.json`: observations and health for each daily run.
- `data/latest.json`: today's offers, source directory, statistics and previous prices.
- `data/history.json`: up to 400 days of aggregate and per-listing history.
- `app/assets/data/`: the bundled offline fallback, copied from the generated data.
- `app/lib/data/models.dart`: parses the JSON and computes filtered statistics.
- `app/lib/data/repo.dart`: loads network/cache/bundled data; persists filters and
  manually logged prices in SharedPreferences. Manual prices count for 72 hours.
- `app/lib/ui/`: overview/distribution, offers and sorting, per-offer history,
  source directory and manual logging. No collector credentials are in the client.

The app can display its last download or bundled data while offline; its timestamp
must be read when assessing freshness. Automatic in-stock, confirmed-Slim,
non-bundle offers are the default scope of the headline statistics.
On the default feed, startup compares the cached and bundled observation timestamps,
and an older server response cannot replace newer local data. This lets an APK
update deliver newly collected sources even before that snapshot reaches the feed.
An explicit custom feed retains its own loading behavior.
Money/statistical rounding uses the same half-up rule as Dart, including median
half-pounds and common-price buckets.

`run_daily.ps1` pulls the repository, collects, copies the fallback assets, commits
data and pushes to GitHub. Running it publishes data, so use the Python command
directly when validating changes locally.

## Verification and operation

```powershell
python -m pip install -r collector/requirements.txt
python collector/collect.py --list-sources
python collector/collect.py --only gamecave ehab aghezty
python collector/collect.py --skip-browser --data-dir logs/validation
python collector/collect.py --headed
python -m unittest discover -s collector/tests -v
cd app
flutter test
flutter build apk --release
```

`--skip-browser` prevents launching Chrome; render-enabled stores are still tried
over HTTP. `--data-dir` isolates snapshots and derived files. `--only` rejects
unknown IDs. The collector requires installed Google Chrome for browser sources.

Source health includes `search_pages`, `product_links`, `products_examined`,
`catalog_pages`, `warnings` and timestamps where applicable. Empty discovery,
invalid API shapes and entirely unreadable candidate products are reported as
errors. A valid API can legitimately return no matching consoles. Search and crawl
limits are bounded and explicitly warn when reached; coverage is not exhaustive.
