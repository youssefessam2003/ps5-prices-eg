"""Bounded product discovery from a store's public pages and sitemaps.

Search engines are used to research sources, never as a price feed. Every returned
URL must belong to the configured store and is fetched again by the collector.
"""
import html as html_lib
import re
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from classify import classify

CONSOLE_URL = re.compile(r"ps\s*5|play\s*station\s*5|بلاي\s*ستيشن\s*5|بلايستيشن", re.I)
CONSOLE_HINT_URL = re.compile(r"slim|silm|digital|disc|console|edition|standard|\b1\s*tb|cfi|سليم|ديجيتال|جهاز", re.I)
ACCESSORY_URL = re.compile(
    r"disc\s*drive|controller\s*(?:white|black|only)|wireless\s*controller|"
    r"charging|charger|headset|portal|cover|faceplate|cooling|stand\s*(?:for|only)|"
    r"\bssd\b.*\bfor\b|\bfor\b.*\bconsole\b|\bfabrika\b|\bused\b", re.I
)
TRACKING = {"srsltid", "fbclid", "gclid", "_pos", "_sid", "_ss", "ref"}


def canonical_url(base, href):
    """Drop tracking, retaining identity queries (variant, slug, product_id, id)."""
    u = urlsplit(urljoin(base, html_lib.unescape(str(href))))
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if k not in TRACKING and not k.startswith("utm_")]
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(query), ""))


def same_store(src, url):
    u = urlsplit(url)
    hosts = [urlsplit(src["url"]).hostname, *src.get("allowed_hosts", [])]
    return u.scheme in ("http", "https") and (u.hostname or "").removeprefix("www.") in {
        (h or "").removeprefix("www.") for h in hosts
    }


def console_candidate(url, title=""):
    slug = re.sub(r"[-_/™®]+", " ", unquote(url).lower())
    return bool(classify(title) or (CONSOLE_URL.search(slug) and CONSOLE_HINT_URL.search(slug)
                                   and not ACCESSORY_URL.search(slug)))


def product_links(src, page, html):
    """Read actual anchors, including relative URLs and opaque product IDs."""
    soup = BeautifulSoup(html, "html.parser")
    rx = re.compile(src["link"], re.I) if src.get("link") else None
    links = []

    def add(href, title=""):
        if re.search(r"[<>\"\s]", str(href)):
            return
        u = canonical_url(page, href)
        if not same_store(src, u) or (rx and not (rx.search(u) or rx.search(str(href)))):
            return
        if console_candidate(u, title) or (rx and re.search(r"/p/[0-9a-f-]{36}", u, re.I)):
            if u not in links:
                links.append(u)

    for a in soup.select("a[href]"):
        img = a.select_one("img[alt]")
        title = a.get_text(" ", strip=True) or a.get("title", "") or (img.get("alt", "") if img else "")
        add(a["href"], title)
    # Some storefronts put their product routes in hydration scripts, not anchors.
    if rx:
        for script in soup.find_all("script"):
            raw = script.get_text().replace(r"\/", "/")
            for m in rx.finditer(raw):
                # Never turn the path inside an external URL into a store URL.
                if m.start() and raw[m.start() - 1] not in ('"', "'", " ", "\n", "\t", "=", ":", "[", ","):
                    continue
                add(m.group(0))
    return links


def next_pages(src, page, html):
    soup = BeautifulSoup(html, "html.parser")
    pages = []
    anchors = soup.select('a[rel~="next"], a.next, .pages-item-next a, li.next a, a.pagination__next')
    # Some independent stores expose only a plain "Next" link, without rel/class.
    for a in soup.select('a[href]'):
        labels = (a.get_text(" ", strip=True), a.get("aria-label", ""))
        if any(re.fullmatch(r"(?:next(?:\s+page)?|التالي(?:ة)?|الصفحة التالية)\s*[»›→]?", label, re.I)
               for label in labels):
            anchors.append(a)
    for a in anchors:
        if not a.get("href"):
            continue
        u = canonical_url(page, a["href"])
        if same_store(src, u) and u not in pages:
            pages.append(u)
    return pages


def sitemap_links(src, fetch, warn):
    """Optional sitemap fallback; never crawl an unbounded catalogue."""
    queue = list(src.get("sitemaps", []))
    seen, links = set(), []
    budget = src.get("max_sitemaps", 8)
    while queue and len(seen) < budget:
        url = canonical_url(src["url"], queue.pop(0))
        if url in seen or not same_store(src, url):
            continue
        seen.add(url)
        try:
            root = ElementTree.fromstring(fetch(url).content)
        except Exception as e:
            warn(f"Sitemap {url}: {type(e).__name__}: {e}")
            continue
        locations = [n.text.strip() for n in root.iter() if n.tag.rsplit("}", 1)[-1] == "loc" and n.text]
        if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
            # Product maps first; omit blog/image/category maps.
            children = [u for u in locations if not re.search(r"blog|post|image|categor|page-sitemap", u, re.I)]
            queue.extend(sorted(children, key=lambda u: "product" not in u.lower()))
        else:
            for u in locations:
                u = canonical_url(url, u)
                if same_store(src, u) and console_candidate(u) and u not in links:
                    links.append(u)
    if queue:
        warn(f"Sitemap limit reached ({budget}); coverage is partial")
    return links
