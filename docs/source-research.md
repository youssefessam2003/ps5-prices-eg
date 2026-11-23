# Source expansion — 15 November 2026

This is the first web-source audit. A subsequent
[social-media research pass](social-source-research.md) adds Games Spot, Gamers
Colony and six direct business-page entries, bringing the current registry to
43 automatic sources and 12 manual entries. Counts below describe the first pass.

Research uses search engines and comparison sites to discover stores, then checks
the store itself. Search snippets/comparison prices are **not** imported as current
offers. A registered source is not a promise of availability: live health, EGP
currency, model classification and stock determine whether an offer counts.

The registry expands from 26 to 41 automatic sources: 13 new stores and two
existing manual directory entries upgraded to automatic collection. The six
remaining manual entries cover social/classified/physical-shop sources.

## New sources and primary references

| ID | Store / evidence | Integration |
| --- | --- | --- |
| gamecave | [The Game Cave Egypt](https://thegamecaveegypt.com/collections/playstation-5-consoles) | Console collection, per-variant prices and stock |
| ennap | [Ennap console](https://ennap.com/products/sony-playstation-5-ps5-slim-consolestandard-edition) | Shopify search + variants, including sold-out variants |
| cairodrop | [Cairo Drop consoles](https://cairodrop.com/collections/ps) | Shopify console collection |
| rizkalla | [Rizkalla consoles](https://riz.shop/en/collections/video-game-consoles) | Localized Shopify collection |
| ehab | [Ehab Group console](https://www.ehabgroup.com/shop/sony-ps5-standard-edition-slim/) | WooCommerce Store API |
| alfrensia | [Alfrensia consoles](https://alfrensia.com/en/product-category/console/) | WooCommerce; out-of-stock offers retained as such |
| egygamer | [EgyGamer consoles](https://egygamer.com/en/console/console) | Paginated catalogue + Magento Offer microdata |
| tahagame | [Taha Game Digital console](https://tahagame.com/product/playstation-5-slim-console-digital-edition-825gb-3-months-warranty/) | Store search + Product JSON-LD; access can vary |
| imedia | [iMedia console](https://www.imediastores.com/product/sony-playstation-5-standard-slim-console-international-warranty/) | Store search + Product JSON-LD; access can vary |
| sharafdg | [Sharaf DG Egypt console](https://egypt.sharafdg.com/product/sony-playstation-5-slim-console-2023-cd-version-white/) | Search + verified product URLs; HTTP 403 during the audit, no snippet prices imported |
| aghezty | [Aghezty PlayStation category](https://aghezty.com/ar/PlayStation/) | Arabic Product JSON-LD, optional sitemap discovery |
| elshennawy | [El Shennawy consoles](https://www.elshennawy.com/index.php?path=354&route=product%2Fcategory) | OpenCart query URLs + Product JSON-LD |
| iklinik | [iKlinik console](https://iklinikstores.com/product?slug=sony-playstation-5-slim-standard-edition) | ProductGroup variants, preserving combination IDs |

## Existing sources repaired or expanded

- [Vodafone](https://eshop.vodafone.com.eg/en/prod/play-station-5-slim-edition-console-1-years-official-warranty)
  and [Sigma Computer](https://sigma-computer.com/en/search?q=playstation) publish
  structured prices/stock and are now automatic. Sigma's `Silm` typo is recognized.
- Shamy now reads the whole console collection, including unavailable variants,
  rather than only the first ten predictive hits.
- Dream 2000 needs its `/en` locale. Shopify individual products now use the
  documented [Ajax Product API](https://shopify.dev/docs/api/ajax/reference/product).
  The previous hardcoded Chrome user agent produced `local_rate_limited` responses
  for otherwise-public product APIs. Shopify requests now identify this collector.
- General HTTP search supports Arabic/English queries, page traversal and optional
  sitemaps, plus reuse of previously discovered product URLs with fresh fetching.
- Marketplace search follows exposed next links, with query/result deduplication.
  A live Amazon smoke run fetched two pages and 48 distinct search cards.
- El Nekhely discovery accepts `www` product links and searches both `ps5` and
  `playstation 5`. Raya has a verified product seed as a fallback for its client-side
  search page.

## Sources still requiring care

- Raneen, Dubai Phone and Sharaf DG can block automated requests. Their failures
  must remain visible; an unsuccessful retry never invents a current price.
- Kaafo's old category contains renewed consoles and exposes an international
  storefront. Keep EGP and new-condition checks; do not treat converted foreign
  prices or renewed offers as Egyptian new-stock deals.
- CompuMe and Technology Valley need verified direct product feeds before automatic
  prices are enabled. Search-engine shop names alone are insufficient evidence.
- Sigma **Store** (`sigmastores.net`) is separate from Sigma **Computer**. Its bundle
  listing was reviewed, but it needs its own tested offer/variant adapter.
- Facebook Marketplace, gaming groups, Dubizzle, OpenSooq and El Bostan remain
  manual. Logged observations are local to the app and expire from current offers
  after 72 hours.

The audit's machine-readable results are stored in each generated snapshot's
`sources` object. Only offers fetched from the stores themselves enter the data.

## Local validation result

The merged 15 November snapshot contains **186 offers**, up from **118**, including
out-of-stock listings kept for transparency/history. Offers marked in stock rose
from **80 to 105**. The 41 automatic source statuses comprise 36 successful checks
and five errors (Raneen, Dubai Phone, El Nekhely, Kaafo and Sharaf DG). Raneen's
successful earlier observation from the same day is retained with its original
timestamp; the other four errors contribute no prices.

All 37 HTTP sources were checked live. Raneen, Raya, Dubai Phone, El Nekhely and
Sharaf DG were also tried with the browser integration, and Amazon pagination was smoke-tested live.
Noon/Jumia/Carrefour observations are retained from their earlier same-day run.
New marketplace pagination logic is also covered by an isolated regression test.
The 23 Python regression tests pass. The generated JSON was parsed by the actual
Flutter `Snapshot`/`Stats` models, and the bundled assets match the generated files.
This check also exposed and fixed Python/Dart half-pound rounding differences in
the median, average and common-price buckets. This audit updates local files;
publishing the repository/JSON feed is a separate operation.
