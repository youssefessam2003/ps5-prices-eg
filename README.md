# PS5 Prices · Egypt

Tracks new **PS5 Slim Digital** and **PS5 Slim Disc** prices across Egyptian stores every day,
and shows them in a Flutter phone app (lowest / highest / median / most common price, every
seller's offer, and price curves over time).

```
collector/   Python: reads every store, writes data/
  sources.py        the list of stores (add new ones here)
  discovery.py      paginated links, known product URLs and bounded sitemap discovery
  classify.py       decides "is this a new PS5 Slim console? digital or disc? bundle?"
  http_sources.py   Shopify / WooCommerce / schema.org product pages
  browser_sources.py Amazon, Noon, Jumia, Carrefour + JavaScript stores (real Chrome)
  collect.py        runs everything, writes data/snapshots/<date>.json, latest.json, history.json
data/        published price data (the app downloads latest.json + history.json)
app/         Flutter app (Android)
run_daily.ps1  collect + publish; scheduled once a day
```

## Data quality and freshness
* Every daily snapshot contains observations fetched on its date, with `seen_at`.
  The app can display cached/bundled data while offline; check the displayed timestamp.
* HTTP stores require explicit availability (Shopify `available`, WooCommerce `is_in_stock`,
  schema.org `InStock`). Marketplace search cards indicate availability; seller panels
  are expanded when accessible and failures are recorded as source warnings.
* Each exposed seller on Amazon/Noon is a separate offer. Coverage is bounded and may be partial.
* Used / open-box / refurbished, PS5 Pro, PS4, accessories and the standalone disc drive are filtered out.

## Run by hand
```
python collector/collect.py --headed       # all stores
python collector/collect.py --only noon    # one store
python collector/collect.py --list-sources
python collector/collect.py --skip-browser --data-dir logs/validation  # isolated run
python -m unittest discover -s collector/tests -v
```

Install collector dependencies with `python -m pip install -r collector/requirements.txt`.
Browser sources use installed Google Chrome. The registry now contains **43 automatic
sources** and **12 manual directory entries**; actual availability and access are in
the generated `sources` health report.

See [the architecture walkthrough](docs/architecture.md) and
[source research and integration notes](docs/source-research.md), plus the
[social-media discovery audit](docs/social-source-research.md).

## Live Refresh on the phone

The private companion lets the Refresh button start a new store collection and
show its progress. Run `start_live.ps1` with the authorized phone connected, and
build with the generated private configuration. The computer must stay awake and
connected to the phone; results are collected there and returned to the app.
See [setup, behavior and verification](docs/live-refresh.md).

## Social media / shops
Verified social pages lead to stores such as Games Spot and Gamers Colony, whose
websites now supply automatic prices. Game Valley, ElModeer QK, Elshayeb, El Rabee,
Gamers Store Alexandria and PS Game Store are listed with direct business-page links
in the app's **Stores** tab; tap **Log a price** to record a verified observation.
Marketplace, Dubizzle and other manual entries use the same workflow. Public source
metadata retains reviewed social profiles, website links and collection limitations.
