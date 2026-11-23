"""Live prices from public Shopify, WooCommerce and structured product pages."""
import html as html_lib
import json
import math
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from classify import classify, sane_price
from discovery import canonical_url, next_pages, product_links, same_store, sitemap_links

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}
S = requests.Session()
S.headers.update(UA)
SHOPIFY_UA = "PS5PricesEgypt/1.0 (+https://github.com/youssefessam2003/ps5-prices-eg)"
MAX_PRODUCT_PAGES = 60
QUERIES = ("playstation 5", "ps5", "بلايستيشن 5", "بلاي ستيشن 5")


def warning(src, message):
    messages = src.setdefault("_diagnostics", {}).setdefault("warnings", [])
    message = str(message)[:400]
    if message not in messages:
        messages.append(message)


def metric(src, name, amount=1):
    diag = src.setdefault("_diagnostics", {})
    diag[name] = diag.get(name, 0) + amount


def get(url, **kw):
    timeout = kw.pop("timeout", 30)
    for attempt in range(3):
        r = S.get(url, timeout=timeout, **kw)
        if r.status_code == 429 and attempt < 2:
            retry = r.headers.get("Retry-After", "")
            if retry.isdigit() and int(retry) <= 30:
                time.sleep(max(int(retry), 1))
                continue
        r.raise_for_status()
        if "charset" not in r.headers.get("Content-Type", "").lower():
            r.encoding = "utf-8"
        if re.search(r"<title[^>]*>\s*(?:just a moment|attention required|access denied|vercel security)", r.text, re.I):
            raise RuntimeError("Store returned an access challenge instead of product data")
        return r


def to_price(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    text = str(value).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    text = text.replace("٬", "").replace("٫", ".").replace(",", "")
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)
    return float(matches[0]) if len(matches) == 1 else None


def round_amount(value):
    """Match Dart's positive-money rounding (Python round uses ties-to-even)."""
    return math.floor(value + 0.5)


def make(src, title, url, price, in_stock, old_price=None, seller=None, key=None):
    title = html_lib.unescape(title or "")
    c = classify(title)
    price = to_price(price)
    if not c or not sane_price(price) or not url:
        return None
    url = canonical_url(src["url"], url)
    if not same_store(src, url):
        return None
    old = to_price(old_price)
    return {
        "id": f"{src['id']}:{key or url}", "source": src["id"], "store": src["name"],
        "seller": seller, "title": re.sub(r"\s+", " ", title).strip(), "url": url,
        "price": round_amount(price), "old_price": round_amount(old) if old and old > price else None,
        "in_stock": bool(in_stock), **c,
    }


def unique(items):
    return list({i["id"]: i for i in items}.values())


def _json(response, expected):
    data = response.json()
    if not isinstance(data, expected):
        raise ValueError(f"Unexpected product API response from {response.url}")
    return data


def shopify_get(url, **kw):
    # Identify the collector honestly. The old, hardcoded Chrome UA caused
    # local_rate_limited responses on otherwise-public Shopify product APIs.
    return get(url, headers={"User-Agent": SHOPIFY_UA}, **kw)


def _shopify_items(src, product, divisor=1):
    out = []
    variants = product.get("variants")
    if not isinstance(variants, list):
        raise ValueError("Shopify product is missing variants/availability")
    for v in variants:
        if v.get("requires_selling_plan"):
            continue
        title = product["title"]
        if v.get("title") not in (None, "Default Title"):
            title += " " + v["title"]
        url = f"{src['url'].rstrip('/')}/products/{product['handle']}"
        if len(variants) > 1:
            url += f"?variant={v['id']}"
        price, old = to_price(v.get("price")), to_price(v.get("compare_at_price"))
        item = make(src, title, url, price / divisor if price is not None else None,
                    v.get("available") is True, old / divisor if old is not None else None, key=v["id"])
        if item:
            out.append(item)
    return out


def _shopify_catalog(src, paths):
    out, seen = [], set()
    for path in paths:
        for page in range(1, src.get("max_catalog_pages", 6) + 1):
            data = _json(shopify_get(urljoin(src["url"].rstrip('/') + '/', path),
                             params={"limit": 250, "page": page}), dict)
            if not isinstance(data.get("products"), list):
                raise ValueError("Shopify endpoint did not return a products array")
            products = data["products"]
            metric(src, "catalog_pages")
            for p in products:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    out.extend(_shopify_items(src, p))
            if len(products) < 250:
                break
            time.sleep(0.5)
        else:
            warning(src, "Catalogue page limit reached; coverage is partial")
    metric(src, "products_examined", len(seen))
    return unique(out)


def shopify_full(src, br=None):
    return _shopify_catalog(src, ["products.json"])


def shopify(src, br=None):
    """Read console collections, or expand targeted search past the ten-hit cap.

    Fetch matching product JSON to preserve every variant's price and stock.
    """
    # Ajax monetary values use the presentment currency's subunits. Read-only
    # cart.js confirms EGP before converting piastres; it does not add to a cart.
    currency = _json(shopify_get(f"{src['url'].rstrip('/')}/cart.js"), dict).get("currency")
    if currency != "EGP":
        raise ValueError(f"Expected EGP Shopify storefront, received {currency!r}")
    if src.get("collections"):
        result = _shopify_catalog(src, [f"collections/{c}/products.json" for c in src["collections"]])
        if result:
            return result
        warning(src, "Console collections yielded no matches; trying targeted searches")
    handles, errors = {}, []
    for q in src.get("queries", (*QUERIES, "ps5 slim", "playstation 5 digital", "playstation 5 disc")):
        try:
            data = _json(shopify_get(f"{src['url'].rstrip('/')}/search/suggest.json", params={
                "q": q, "resources[type]": "product", "resources[limit]": 10,
                "resources[options][unavailable_products]": "last"}), dict)
            products = data["resources"]["results"]["products"]
            if not isinstance(products, list):
                raise ValueError("Invalid Shopify search products")
            metric(src, "search_pages")
            for p in products:
                if classify(p.get("title", "")):
                    handles[p["handle"]] = p
            if len(products) >= 10:
                for page in range(1, src.get("max_search_pages", 3) + 1):
                    response = shopify_get(f"{src['url'].rstrip('/')}/search", params={
                        "q": q, "type": "product", "page": page})
                    metric(src, "search_pages")
                    cfg = {**src, "link": r"/products/[^/?#]+"}
                    for u in product_links(cfg, response.url, response.text):
                        handle = u.split("/products/", 1)[1].split("?")[0].rstrip('/')
                        handles.setdefault(handle, {})
                    if not next_pages(cfg, response.url, response.text):
                        break
                else:
                    warning(src, f"Search page limit reached for {q}; coverage is partial")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (404, 417):
                warning(src, "Predictive search unavailable; reading paginated catalogue")
                return shopify_full(src)
            errors.append(str(e))
            if e.response is not None and e.response.status_code in (403, 429):
                break
        except (ValueError, KeyError, requests.RequestException) as e:
            errors.append(str(e))
        time.sleep(0.3)
    out = []
    metric(src, "product_links", len(handles))
    limit = src.get("max_product_pages", MAX_PRODUCT_PAGES)
    for handle in list(handles)[:limit]:
        try:
            data = _json(shopify_get(f"{src['url'].rstrip('/')}/products/{handle}.js"), dict)
            out.extend(_shopify_items(src, data, divisor=100))
            metric(src, "products_examined")
        except Exception as e:
            errors.append(f"{handle}: {type(e).__name__}: {e}")
            if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code in (403, 429):
                break
        time.sleep(0.3)
    if len(handles) > limit:
        warning(src, "Product page limit reached; coverage is partial")
    for e in errors:
        warning(src, e)
    if not out and errors:
        raise RuntimeError("; ".join(errors)[:500])
    return unique(out)


def woo(src, br=None):
    out, seen, errors = [], set(), []
    for q in src.get("queries", QUERIES):
        for page in range(1, src.get("max_search_pages", 5) + 1):
            try:
                r = get(f"{src['url'].rstrip('/')}/wp-json/wc/store/v1/products", params={
                    "search": q, "per_page": 100, "page": page})
                products = _json(r, list)
                metric(src, "search_pages")
                for p in products:
                    if p["id"] in seen:
                        continue
                    seen.add(p["id"])
                    pr = p.get("prices", {})
                    if pr.get("currency_code") != "EGP":
                        warning(src, "Ignored product without confirmed EGP currency")
                        continue
                    div = 10 ** int(pr.get("currency_minor_unit", 2))
                    price, reg = to_price(pr.get("price")), to_price(pr.get("regular_price"))
                    title = html_lib.unescape(p.get("name", ""))
                    if (p.get("type") == "variable" or pr.get("price_range")) and classify(title):
                        try:
                            variants = product_page(src, p["permalink"], get(p["permalink"]).text)
                            out.extend(variants)
                            if not variants:
                                warning(src, f"No eligible new-console variants resolved: {p['permalink']}")
                        except Exception as e:
                            errors.append(f"Variants {p['permalink']}: {type(e).__name__}: {e}")
                        continue
                    item = make(src, title, p.get("permalink"), price / div if price else None,
                                p.get("is_in_stock") is True and p.get("is_purchasable", True),
                                reg / div if reg else None, key=p["id"])
                    if item:
                        out.append(item)
                total = r.headers.get("X-WP-TotalPages")
                if (total and page >= int(total)) or (not total and len(products) < 100):
                    break
            except Exception as e:
                errors.append(f"{q} page {page}: {type(e).__name__}: {e}")
                break
            time.sleep(0.5)
        else:
            warning(src, f"Search page limit reached for {q}; coverage is partial")
        if errors and not seen:
            break
        time.sleep(0.3)
    metric(src, "products_examined", len(seen))
    for e in errors:
        warning(src, e)
    if not out and errors:
        raise RuntimeError("; ".join(errors)[:500])
    return unique(out)


def _ld_products(html):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(reversed(node))
            elif isinstance(node, dict):
                types = node.get("@type", [])
                if "Product" in ([types] if isinstance(types, str) else types):
                    yield node
                for key in ("@graph", "hasVariant", "itemListElement", "item", "mainEntity"):
                    if key in node:
                        stack.append(node[key])


def _offer_list(offers):
    if isinstance(offers, list):
        return [o for v in offers for o in _offer_list(v)]
    if isinstance(offers, dict):
        if offers.get("@type") == "AggregateOffer":
            # A summary lowPrice doesn't prove a purchasable seller/variant.
            return _offer_list(offers.get("offers"))
        return [offers]
    return []


def _node_value(node):
    if node is None:
        return None
    return node.get("content") or node.get("href") or node.get_text(" ", strip=True)


def _included_extras(description):
    """Recognize an explicit bundle contents list without reclassifying the model.

    Games Spot's shared description calls even Digital consoles 'CD edition'.
    Use only the stated included extras here; edition/condition come from titles.
    """
    raw = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), str(description or ""))
    text = BeautifulSoup(html_lib.unescape(raw), "html.parser").get_text(" ", strip=True)
    contents = re.search(r"\bbundle\s+includes?\s*:?(.{0,1400})", text, re.I | re.S)
    return bool(contents and re.search(
        r"\b(?:[1-9]\d*|one|two)\s+games?\b|\b(?:extra|additional)\s+(?:\w+\s+){0,3}controllers?\b|"
        r"\b(?:2|two)\s+(?:(?:wireless|dualsense)\s+)*controllers?\b", contents[1], re.I))


def _woo_page_variants(src, url, soup, products):
    """Read a WooCommerce variation form, keeping new/used prices and stock apart.

    None means there is no embedded form; [] means a form exists but supplies no
    eligible offers. Never fall back to an aggregate price after seeing a form.
    """
    forms = soup.select('form[data-product_variations]')
    if not forms:
        return None
    out = []
    for form in forms:
        parent = next((p for p in products if str(p.get("sku")) == form.get("data-product_id")), None)
        if parent is None and len(products) == 1:
            parent = products[0]
        if not parent or not classify(parent.get("name", "")):
            continue
        offers = parent.get("offers", [])
        offers = offers if isinstance(offers, list) else [offers]
        currencies = {str(o.get("priceCurrency", "")).upper() for o in offers if isinstance(o, dict)}
        conditions = [parent.get("itemCondition"), *(o.get("itemCondition") for o in offers if isinstance(o, dict))]
        if currencies != {"EGP"} or any(c and str(c).rsplit('/', 1)[-1] != "NewCondition" for c in conditions):
            warning(src, f"Variation form has unconfirmed currency or a non-new parent: {url}")
            continue
        try:
            variants = json.loads(form["data-product_variations"])
        except (TypeError, ValueError):
            variants = None
        if not isinstance(variants, list):
            warning(src, f"Variation details not embedded in page: {url}")
            continue
        labels = {select.get("name"): {o.get("value"): o.get_text(" ", strip=True)
                  for o in select.select('option[value]')} for select in form.select('select[name]')}
        for v in variants:
            if not isinstance(v, dict) or not v.get("variation_id"):
                continue
            attrs = v.get("attributes", {})
            if not isinstance(attrs, dict) or any(not val for val in attrs.values()):
                warning(src, f"Unresolved variation attributes: {url}")
                continue
            suffix = " ".join(labels.get(k, {}).get(val, str(val).replace('-', ' ')) for k, val in attrs.items())
            # Check raw condition slugs too, even if the displayed option omits
            # 'Used' or 'Refurbished' in its marketing label.
            conditions = " ".join(str(val).replace('-', ' ') for k, val in attrs.items() if 'condition' in k)
            if conditions and not classify(parent["name"] + " " + conditions):
                continue
            title = parent["name"] + " " + suffix
            u = urlsplit(url)
            query = dict(parse_qsl(u.query, keep_blank_values=True))
            query.update(variation_id=str(v["variation_id"]), **attrs)
            target = urlunsplit((u.scheme, u.netloc, u.path, urlencode(query), ""))
            stock = v.get("is_in_stock") is True and v.get("is_purchasable", True) is True and v.get("variation_is_active", True) is True
            item = make(src, title, target, v.get("display_price"), stock,
                        v.get("display_regular_price"), key=v["variation_id"])
            if item:
                out.append(item)
    return unique(out)


def product_page(src, url, html):
    """Structured EGP prices and explicit stock, never whole-page number guessing."""
    out = []
    products = list(_ld_products(html))
    soup = BeautifulSoup(html, "html.parser")
    variants = _woo_page_variants(src, url, soup, products)
    if variants is not None:
        return variants
    for p in products:
        for o in _offer_list(p.get("offers")):
            if str(o.get("priceCurrency", "")).upper() != "EGP":
                continue
            condition = str(o.get("itemCondition") or p.get("itemCondition") or "")
            if condition and condition.rsplit("/", 1)[-1] != "NewCondition":
                continue
            stock = str(o.get("availability", "")).rsplit("/", 1)[-1] in ("InStock", "LimitedAvailability")
            seller = o.get("seller", {}).get("name") if isinstance(o.get("seller"), dict) else None
            target = canonical_url(url, o.get("url") or p.get("url") or url)
            item = make(src, p.get("name", ""), target, o.get("price"), stock, seller=seller,
                        key=target + (f"#{seller}" if seller else ""))
            if item:
                if _included_extras(p.get("description")):
                    item["bundle"] = True
                out.append(item)
    if out or any(classify(p.get("name", "")) for p in products):
        return unique(out)
    # Magento's Offer microdata is confined to the main product, not related items.
    info = soup.select_one(".product-info-main")
    if info:
        title = _node_value(info.select_one('h1 [itemprop="name"], h1'))
        price = _node_value(info.select_one('.product-info-price [itemprop="price"]'))
        currency = _node_value(info.select_one('.product-info-price [itemprop="priceCurrency"]'))
        available = info.select_one(".stock.available")
        unavailable = info.select_one(".stock.unavailable")
        if currency == "EGP" and (available or unavailable):
            old_node = info.select_one('.old-price [data-price-amount]')
            old = old_node.get("data-price-amount") if old_node else None
            item = make(src, title, url, price, bool(available) and not unavailable, old)
            if item:
                out.append(item)
    return unique(out)


def jsonld(src, br=None):
    pages, visited = list(src.get("search", [])), set()
    links = [canonical_url(src["url"], u) for u in src.get("products", [])]
    errors = []
    listing_limit = src.get("max_listing_pages", max(4, len(pages)))
    while pages and len(visited) < listing_limit:
        page = canonical_url(src["url"], pages.pop(0))
        if page in visited or not same_store(src, page):
            continue
        visited.add(page)
        try:
            html = br.html(page) if br and src.get("render") else get(page).text
            metric(src, "search_pages")
            links.extend(product_links(src, page, html))
            pages.extend(p for p in next_pages(src, page, html) if p not in visited)
        except Exception as e:
            errors.append(f"Search {page}: {type(e).__name__}: {e}")
        time.sleep(0.3)
    if pages:
        warning(src, f"Listing page limit reached ({listing_limit}); coverage is partial")
    if not links and src.get("sitemaps"):
        links.extend(sitemap_links(src, get, lambda m: warning(src, m)))
    links = list(dict.fromkeys(u for u in links if same_store(src, u)))
    metric(src, "product_links", len(links))
    limit = src.get("max_product_pages", MAX_PRODUCT_PAGES)
    if len(links) > limit:
        warning(src, f"Product page limit reached ({limit}); coverage is partial")
    out = []
    for u in links[:limit]:
        try:
            if br and src.get("render"):
                try:
                    items = product_page(src, u, get(u).text)
                except requests.RequestException:
                    items = []
                if not items:
                    items = product_page(src, u, br.html(u, 2))
            else:
                items = product_page(src, u, get(u).text)
            metric(src, "products_examined")
            out.extend(items)
        except Exception as e:
            errors.append(f"Product {u}: {type(e).__name__}: {e}")
        time.sleep(0.3)
    for e in errors:
        warning(src, e)
    if not out and errors:
        raise RuntimeError("; ".join(errors)[:500])
    if links and not out:
        raise RuntimeError("Product candidates found, but no valid console price/stock could be parsed")
    if not links:
        raise RuntimeError("No console product links discovered; check search route, rendering or source configuration")
    return unique(out)


COLLECTORS = {"shopify": shopify, "woo": woo, "jsonld": jsonld}
