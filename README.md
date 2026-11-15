# PS5 Prices · Egypt

Tracks new **PS5 Slim Digital** and **PS5 Slim Disc** prices across Egyptian stores every day,
and shows them in a Flutter phone app (lowest / highest / median / most common price, every
seller's offer, and price curves over time).

```
collector/   Python: reads every store, writes data/
  sources.py        the list of stores (add new ones here)
  classify.py       decides "is this a new PS5 Slim console? digital or disc? bundle?"
  http_sources.py   Shopify / WooCommerce / schema.org product pages
  browser_sources.py Amazon, Noon, Jumia, Carrefour + JavaScript stores (real Chrome)
  collect.py        runs everything, writes data/snapshots/<date>.json, latest.json, history.json
data/        published price data (the app downloads latest.json + history.json)
app/         Flutter app (Android)
run_daily.ps1  collect + publish; scheduled once a day
```

## How freshness is guaranteed
* Only listings fetched **today** are shown; each carries `seen_at`.
* Only offers the store marks **in stock** count (Shopify `available`, WooCommerce `is_in_stock`,
  schema.org `InStock`, marketplace offers with an Add-to-cart).
* Every seller on Amazon/Noon is a separate offer, so one product can have 5+ prices.
* Used / open-box / refurbished, PS5 Pro, PS4, accessories and the standalone disc drive are filtered out.

## Run by hand
```
python collector/collect.py --headed       # all stores
python collector/collect.py --only noon    # one store
```

## Social media / shops
Facebook pages, Marketplace, Dubizzle and walk-in shops have no machine-readable prices.
They're listed in the app's **Stores** tab; tap **Log a price** to add what you saw.
