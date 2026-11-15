"""Collectors for stores that publish prices over plain HTTP."""
import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from classify import classify, sane_price

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}
S = requests.Session()
S.headers.update(UA)

MAX_PRODUCT_PAGES = 40


def get(url, **kw):
    for attempt in range(3):
        r = S.get(url, timeout=30, **kw)
        if r.status_code == 429 and attempt < 2:
            time.sleep(int(r.headers.get("Retry-After", 0) or 0) or 30 * (attempt + 1))
            continue
        r.raise_for_status()
        return r


def to_price(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.]", "", str(v).replace(",", ""))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def make(src, title, url, price, in_stock, old_price=None, seller=None, key=None):
    c = classify(title)
    price = to_price(price)
    if not c or not sane_price(price):
        return None
    old = to_price(old_price)
    return {
        "id": f"{src['id']}:{key or url}",
        "source": src["id"],
        "store": src["name"],
        "seller": seller,
        "title": re.sub(r"\s+", " ", title).strip(),
        "url": url,
        "price": round(price),
        "old_price": round(old) if old and old > price else None,
        "in_stock": bool(in_stock),
        **c,
    }


# ---------------- Shopify ----------------
def shopify(src, br=None):
    """Shopify's predictive search returns matching products with live price + availability (2 requests per store)."""
    out, seen = [], set()
    try:
        for q in ("playstation 5", "ps5"):
            r = get(f"{src['url']}/search/suggest.json",
                    params={"q": q, "resources[type]": "product", "resources[limit]": 10,
                            "resources[options][unavailable_products]": "last"})
            for p in r.json().get("resources", {}).get("results", {}).get("products", []):
                if p["handle"] in seen:
                    continue
                seen.add(p["handle"])
                url = src["url"] + p["url"].split("?")[0]
                old = p.get("compare_at_price_max") or p.get("compare_at_price_min")
                item = make(src, p["title"], url, p.get("price") or p.get("price_min"), p.get("available"),
                            old if old and str(old) not in ("0", "0.0", "0.00") else None, key=p["handle"])
                if item:
                    out.append(item)
            time.sleep(3)
        return out
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (404, 417):
            return shopify_full(src)
        raise


def shopify_full(src, br=None):
    out, page = [], 1
    while page <= 6:
        data = get(f"{src['url']}/products.json?limit=250&page={page}").json()
        prods = data.get("products", [])
        if not prods:
            break
        for p in prods:
            for v in p.get("variants", []):
                title = p["title"] if v.get("title") in (None, "Default Title") else f"{p['title']} {v['title']}"
                url = f"{src['url']}/products/{p['handle']}" + (f"?variant={v['id']}" if len(p["variants"]) > 1 else "")
                item = make(src, title, url, v.get("price"), v.get("available"), v.get("compare_at_price"), key=v["id"])
                if item:
                    out.append(item)
        page += 1
        time.sleep(1.5)
    return out


# ---------------- WooCommerce Store API ----------------
def woo(src, br=None):
    out, seen = [], set()
    for q in ("playstation 5", "ps5", "بلايستيشن 5", "بلاي ستيشن 5"):
        r = get(f"{src['url']}/wp-json/wc/store/v1/products", params={"search": q, "per_page": 100})
        try:
            prods = r.json()
        except ValueError:
            continue
        for p in prods if isinstance(prods, list) else []:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            pr = p.get("prices", {})
            minor = int(pr.get("currency_minor_unit", 2) or 0)
            div = 10 ** minor
            price = to_price(pr.get("price"))
            reg = to_price(pr.get("regular_price"))
            title = BeautifulSoup(p.get("name", ""), "html.parser").get_text()
            item = make(src, title, p.get("permalink"), price / div if price else None,
                        p.get("is_in_stock") and p.get("is_purchasable", True),
                        reg / div if reg else None, key=p["id"])
            if item:
                out.append(item)
        time.sleep(1)
    return out


# ---------------- schema.org Product pages ----------------
def _ld_products(html):
    soup = BeautifulSoup(html, "html.parser")
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.string or sc.get_text() or "")
        except ValueError:
            continue
        stack = d if isinstance(d, list) else [d]
        while stack:
            it = stack.pop()
            if isinstance(it, list):
                stack.extend(it)
                continue
            if not isinstance(it, dict):
                continue
            if "@graph" in it:
                stack.extend(it["@graph"])
            t = it.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                yield it
            elif t == "ProductGroup":
                stack.extend(it.get("hasVariant", []))


def _offer_list(offers):
    if isinstance(offers, dict):
        if offers.get("@type") == "AggregateOffer":
            inner = offers.get("offers")
            return _offer_list(inner) if inner else [offers]
        return [offers]
    if isinstance(offers, list):
        return [o for o in offers if isinstance(o, dict)]
    return []


CONSOLE_SLUG = re.compile(r"(slim|digital|disc|console|edition|standard|1tb|cfi|%d8%b3%d9%84%d9%8a%d9%85|/p/[0-9a-f-]{36})", re.I)


def jsonld(src, br=None):
    links = []
    rx = re.compile(src["link"], re.I)
    errors = []
    for page in src["search"]:
        try:
            html = br.html(page) if (br and src.get("render")) else get(page).text
        except Exception as e:
            errors.append(f"{page}: {e}")
            continue
        for m in rx.findall(html):
            u = urljoin(page, m.split('"')[0]).replace("&amp;", "&")
            slug = u.lower()
            # Only open pages that look like PS5 consoles (skip games/accessories by URL first).
            if re.search(r"(playstation-?5|ps-?5|%d8%a8%d9%84%d8%a7%d9%8a|playstation5|/p/[0-9a-f-]{36})", slug) \
                    and CONSOLE_SLUG.search(slug) \
                    and not re.search(r"(controller-white|controller-black|wireless-controller$|-stand(?:-|$)|cover|charger|portal|-pro-|pro-console|headset|disc-drive)", slug):
                if u not in links:
                    links.append(u)
        time.sleep(1)
    if errors and not links:
        raise RuntimeError("; ".join(errors)[:300])
    out = []
    for u in links[:MAX_PRODUCT_PAGES]:
        try:
            html = get(u).text
            if br and src.get("render") and "application/ld+json" not in html:
                html = br.html(u, 2)
        except Exception:
            continue
        for p in _ld_products(html):
            name = p.get("name") or ""
            for o in _offer_list(p.get("offers")):
                avail = str(o.get("availability", ""))
                in_stock = ("InStock" in avail) or ("LimitedAvailability" in avail) or ("PreOrder" in avail and False)
                price = o.get("price") or o.get("lowPrice")
                seller = (o.get("seller") or {}).get("name") if isinstance(o.get("seller"), dict) else None
                item = make(src, name, o.get("url") or u, price, in_stock, seller=seller,
                            key=(o.get("url") or u).split("?")[0] + (f"#{seller}" if seller else ""))
                if item:
                    out.append(item)
        time.sleep(1)
    # same product can appear twice (ld duplicates); keep one per id
    uniq = {}
    for it in out:
        uniq.setdefault(it["id"], it)
    return list(uniq.values())


COLLECTORS = {"shopify": shopify, "woo": woo, "jsonld": jsonld}
