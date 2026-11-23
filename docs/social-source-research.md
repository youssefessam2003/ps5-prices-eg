# Social-source expansion — 15 November 2026

This second research pass follows public social pages to their own storefronts.
Local store directories and search results supplied leads; the business's public
Facebook page, linked website and catalogue supplied the verification. No prices
from search snippets, old reposts, comments or private messages were imported.

Eight verified businesses were added: two automatic sources and six manual store
entries. The registry now contains **43 automatic sources and 12 manual entries**.
Follower counts below are rounded figures displayed by Facebook on the review
date, not a measure of stock, service quality or an endorsement.

## Verified public pages and website checks

| Business / primary social page | Followers observed | Linked website / result | Integration |
| --- | --- | --- | --- |
| [Games Spot](https://www.facebook.com/p/Games-spot-61566368139737/) | 686K | [gamesspoteg.com](https://gamesspoteg.com/); linked from the page, with reciprocal social links | Automatic Product JSON-LD from [new consoles](https://gamesspoteg.com/en/category/new-consoles/) and [PS5 bundles](https://gamesspoteg.com/en/category/ps5-bundles/) |
| [Game Valley](https://www.facebook.com/GAMEVALLEY/) | 243K | [gamevalley.com](https://www.gamevalley.com/) returned HTTP 404 during review | Manual; direct business page in the app's Stores tab |
| [شركة الربيع / El Rabee](https://www.facebook.com/m.rabi3.org) | 153K | Public Alexandria shop page explicitly describes PS5 sales/repair; no price/stock feed verified | Manual |
| [Gamers Colony](https://www.facebook.com/GamerColonyEG/) | 61K | [gamerscolony.net](https://gamerscolony.net/) linked from the page and back to its social profiles | Automatic WooCommerce Store API plus individual variation forms |
| [المدير QK / ElModeer QK](https://www.facebook.com/elmodeerqk/) | 48K | [Official link hub](https://link.gettap.co/elmodeerqk142471) and [elmodeerqk.com](https://elmodeerqk.com/); [PS5 section](https://elmodeerqk.com/playstation-5) has no readable current console price/stock | Manual |
| [الشايب / Elshayeb](https://www.facebook.com/ELSHAYEB2018/) | 47K | [Official site](https://www.elshayebstore.com/); its [console sales section](https://www.elshayebstore.com/sales/consoles) currently lists PS4 packages | Manual; verify a new Slim offer before recording one |
| [Gamers Store · Alexandria](https://www.facebook.com/GamersStore18) | 21K | Public buy/sell/trade console shop with Alexandria branches; no independent price feed verified | Manual; separate business from Gamers Colony |
| [PS Game Store · Mokattam](https://www.facebook.com/PS.GAME.STORE.EG/) | 2.4K | [Linked client-rendered catalogue](https://ps-game-store.base44.app/) did not expose a verified current PS5 price/stock feed | Manual |

The registry retains verified Facebook, Instagram and TikTok links where observed,
the review date, website and integration notes. These are exported in the public
`latest.json` directory. The app opens each manual entry's business page and
supports **Log a price**; additional metadata is preserved in the JSON for future
directory work. Manual business entries do not imply an available new Slim console.

## Data issues found and fixed

- Games Spot uses opaque numeric product URLs. Discovery reads actual anchor
  titles rather than requiring `ps5` in every product URL. The generic catalogue
  ignored the tested `search=PS5` parameter and traversed unrelated products, so
  collection uses the two verified console categories instead. Plain text `Next`
  and Arabic next-page links are also now supported by shared discovery.
- Games Spot's [Digital product](https://gamesspoteg.com/en/products/108/) has a
  shared description that says CD edition and explicitly includes ten games.
  Edition still comes from the product title; the included-game package is marked
  as a bundle. Ordinary packaging with one controller/cable does not create a
  bundle. Special named editions are also separated from base-console statistics.
- Gamers Colony's generic PS5 search is saturated by accessories. Targeted Arabic
  and English Slim queries discover the consoles without relying on the first
  hundred generic results.
- Gamers Colony mixes new and used conditions on the same page. Its [Digital
  SOLO product](https://gamerscolony.net/product/playstation-5-slim-digital-verision/)
  exposed a used EGP 31,999 variation in stock and a new EGP 42,999 variation out of
  stock. The aggregate minimum/in-stock flag cannot describe the new console.
  Embedded WooCommerce variation data now supplies each condition's own price,
  availability and purchase URL. Used/refurbished options are excluded, and the
  new out-of-stock offer remains out of stock. Unresolved variations and missing
  currency evidence produce warnings rather than guessed offers.

## Excluded or pending leads

- The EGY GAMES STORE Alexandria Facebook lead returned “content isn't available”;
  it was not added as a verified business.
- Similar “GameSpot” names and older domains were not merged into Games Spot
  without current identity/link evidence.
- Account-only/game-credit sellers and non-Egyptian stores were not added as
  Egyptian hardware sources merely because they mention PlayStation.
- Social post images and installment adverts without a verifiable current cash
  price, exact edition, condition and stock remain manual research, not live offers.

## Validation

The two new automatic sources were fetched live in an isolated validation run,
then collected into the local daily snapshot after the fixes. Final source checks:

| Source | Parsed offers | Marked in stock | Coverage |
| --- | ---: | ---: | --- |
| Games Spot | 4 | 0 | Two console categories, four product pages; no crawl warnings |
| Gamers Colony | 12 | 9 | Three targeted query responses, 32 distinct products examined; no crawl warnings |

The merged daily snapshot now has **202 offers**, including **114 marked in stock**.
The automatic source health report has **38 successful checks and five errors**;
the earlier errors are documented in [the first audit](source-research.md).
All **28 Python regression tests** pass, including mixed new/used variations,
unreadable variation forms, currency checks, explicit bundle contents and plain
next-page traversal. The actual Dart `Snapshot`/`Stats` models also parse the
generated data and reproduce its default statistics. Bundled app assets match the
generated JSON. These changes are local; the repository feed has not been pushed.
