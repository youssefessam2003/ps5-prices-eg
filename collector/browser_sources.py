"""Collectors that need a real browser (marketplaces and JavaScript-rendered stores).

Plain Chrome via Playwright, loading public search/product pages the way a shopper would.
If a site shows a CAPTCHA or blocks the visit, that source is reported as blocked for the day.
"""
import re
import time

from classify import classify
from http_sources import make, metric, warning
from discovery import canonical_url, same_store

SEARCH_JS = {
    "amazon": r"""
() => [...document.querySelectorAll('[data-component-type="s-search-result"]')].map(d => {
  const t = (d.querySelector('h2') || {}).innerText || '';
  const p = (d.querySelector('.a-price:not(.a-text-price) .a-offscreen') || {}).textContent || '';
  const o = (d.querySelector('.a-price.a-text-price .a-offscreen') || {}).textContent || '';
  const more = (d.innerText.match(/(\d+)\s+new offers?/i) || [])[1] || '';
  return {key: d.dataset.asin, title: t, price: p, old: o, url: 'https://www.amazon.eg/dp/' + d.dataset.asin,
          stock: !/currently unavailable/i.test(d.innerText), more};
})""",
    "noon": r"""
() => { const seen = new Set(); return [...document.querySelectorAll('a[href*="/p/"]')].filter(a => {
  const h = a.href.split('?')[0]; if (seen.has(h)) return false; seen.add(h); return true; }).map(a => {
  const txt = a.innerText; const m = txt.match(/EGP\s*([\d,]+(?:\.\d+)?)/g) || [];
  const sku = (a.href.match(/\/(N\w+V|Z\w+Z)\/p/) || [])[1] || a.href;
  const title = (a.querySelector('[data-qa="product-name"], h2') || {}).innerText || txt.split('\n').find(l => /playstation|ps5/i.test(l)) || '';
  return {key: sku, title, price: m[0] || '', old: m[1] || '', url: a.href.split('?')[0], stock: true};
}); }""",
    "jumia": r"""
() => [...document.querySelectorAll('article.prd a.core')].map(a => ({
  key: a.getAttribute('href'), title: (a.querySelector('.name') || {}).textContent || '',
  price: (a.querySelector('.prc') || {}).textContent || '', old: (a.querySelector('.old') || {}).textContent || '',
  url: 'https://www.jumia.com.eg' + a.getAttribute('href'), stock: true }))""",
    "carrefour": r"""
() => { const base = h => h.split('?')[0]; const groups = {};
  for (const a of document.querySelectorAll('a[href*="/p/"]')) (groups[base(a.getAttribute('href'))] ||= []).push(a);
  return Object.entries(groups).map(([h, as]) => {
    const title = as.map(a => a.innerText.trim()).sort((x, y) => y.length - x.length)[0] || '';
    let c = as[0], card = null;
    for (let i = 0; i < 12 && c.parentElement; i++) {
      c = c.parentElement;
      const hs = new Set([...c.querySelectorAll('a[href*="/p/"]')].map(x => base(x.getAttribute('href'))));
      if (hs.size > 1) break;
      if (/EGP/.test(c.innerText)) card = c;
    }
    const txt = card ? card.innerText : '';
    const m = txt.match(/EGP\s*([\d,]+(?:\.\d+)?)(?:\s+([\d,]+(?:\.\d+)?))?/) || [];
    return {key: h, title: title.split('\n').find(l => l.length > 12) || title, price: m[1] || '', old: m[2] || '',
            url: 'https://www.carrefouregypt.com' + as[0].getAttribute('href'), stock: !!m[1] && !/out of stock/i.test(txt)};
  }); }""",
}

WAIT_FOR = {
    "amazon": '[data-component-type="s-search-result"]',
    "noon": 'a[href*="/p/"]',
    "jumia": "article.prd",
    "carrefour": 'a[href*="/p/"]',
}

NEXT_PAGE_JS = r"""
() => {
  const links = [...document.querySelectorAll('a[href]')];
  const next = links.find(a => a.matches('a.s-pagination-next, a[rel~="next"]') ||
    /^(next|next page|التالي|التالية)$/i.test((a.getAttribute('aria-label') || a.title || a.innerText || '').trim()));
  return next && next.getAttribute('aria-disabled') !== 'true' ? next.href : null;
}
"""

AMAZON_OFFERS_JS = r"""
() => [...document.querySelectorAll('#aod-pinned-offer, #aod-offer')].map(o => {
  const txt = o.innerText;
  const p = (txt.match(/EGP\s*([\d,]+\.\d\d)/) || [])[1] || '';
  const cond = ((o.querySelector('#aod-offer-heading') || {}).innerText || '').trim();
  const seller = ((o.querySelector('#aod-offer-soldBy a') || o.querySelector('#aod-offer-soldBy .a-col-right') || {}).innerText || '').trim();
  return {price: p, cond, seller};
})"""

NOON_OFFERS_JS = r"""
() => { const l = document.querySelector('[class*="offersList_"]'); if (!l) return [];
  const t = l.innerText; const out = [];
  const re = /EGP\s*([\d,]+(?:\.\d+)?)[\s\S]*?SOLD BY\s*\n([^\n]+)/g; let m;
  while ((m = re.exec(t))) out.push({price: m[1], seller: m[2].trim()});
  return out; }"""

BLOCK_RX = re.compile(r"(captcha|robot check|enter the characters|access denied|verify you are human|unusual traffic)", re.I)


class Browser:
    def __init__(self, headless=True):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        # Headless Chrome is refused by Noon/Carrefour, so we run a normal Chrome window,
        # parked off-screen so the daily run doesn't get in the way.
        args = [] if headless else ["--window-position=-32000,-32000"]
        self.browser = self._pw.chromium.launch(channel="chrome", headless=headless, args=args)
        self.ctx = self.browser.new_context(locale="en-US", timezone_id="Africa/Cairo",
                                            viewport={"width": 1366, "height": 900})
        self.page = self.ctx.new_page()

    def open(self, url, wait=2.5, selector=None):
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if selector:
            try:
                self.page.wait_for_selector(selector, timeout=20000)
            except Exception:
                pass
        time.sleep(wait)
        try:
            self.page.mouse.wheel(0, 4000)
            time.sleep(1)
        except Exception:
            pass
        body = self.page.inner_text("body")[:3000]
        if re.search(r"sorry.*blocked|verify (?:that )?you are human|robot check|enter the characters|access denied|unusual traffic", body, re.I):
            raise RuntimeError("blocked (bot check shown)")
        if BLOCK_RX.search(self.page.title() or ""):
            raise RuntimeError("blocked (bot check shown)")
        return self.page

    def html(self, url, wait=3):
        return self.open(url, wait).content()

    def close(self):
        try:
            self.browser.close()
        finally:
            self._pw.stop()


def marketplace(src, br: Browser):
    rows, seen = [], set()
    errors = []
    visited = set()
    limit = src.get("max_search_pages", 3)
    for first in src["search"]:
        url = first
        for page_number in range(limit):
            if not url or url in visited or not same_store(src, url):
                break
            visited.add(url)
            try:
                br.open(url, 3, WAIT_FOR[src["id"]])
                metric(src, "search_pages")
                for r in br.page.evaluate(SEARCH_JS[src["id"]]):
                    if r["key"] in seen:
                        continue
                    seen.add(r["key"])
                    rows.append(r)
                next_url = br.page.evaluate(NEXT_PAGE_JS)
                url = canonical_url(url, next_url) if next_url else None
                if url and page_number == limit - 1:
                    warning(src, f"Search page limit reached ({limit}); coverage is partial")
            except Exception as e:  # keep other searches going
                errors.append(f"{url}: {e}")
                break
    metric(src, "search_results", len(rows))
    for e in errors:
        warning(src, e)
    if not rows and errors:
        raise RuntimeError("; ".join(errors)[:300])

    out = []
    for r in rows:
        item = make(src, r["title"], r["url"], r["price"], r["stock"], r.get("old"), key=r["key"])
        if not item:
            continue
        out.append(item)
        # Pull every seller's offer for console listings (the user wants all offers, not just the buy box).
        try:
            if src["id"] == "amazon":
                br.open(f"https://www.amazon.eg/gp/product/ajax/aodAjaxMain/?asin={r['key']}&language=en_AE&pc=dp", 2)
                offers = br.page.evaluate(AMAZON_OFFERS_JS)
                offers = [o for o in offers if o["price"] and (not o["cond"] or o["cond"].lower().startswith("new"))]
            elif src["id"] == "noon":
                br.open(r["url"], 2.5)
                btn = br.page.get_by_text("More offers from other sellers", exact=True)
                offers = []
                if btn.count():
                    btn.first.click()
                    time.sleep(2)
                    offers = br.page.evaluate(NOON_OFFERS_JS)
            else:
                offers = []
        except Exception as e:
            warning(src, f"Additional sellers unavailable for {r['key']}: {type(e).__name__}")
            offers = []
        if offers:
            out.pop()  # replace the single search-result row by the per-seller rows
            for o in offers:
                it = make(src, r["title"], r["url"], o["price"], True, r.get("old"),
                          seller=o.get("seller") or None, key=f"{r['key']}#{o.get('seller') or ''}")
                if it:
                    out.append(it)
    uniq = {}
    for it in out:
        if it["id"] not in uniq or it["price"] < uniq[it["id"]]["price"]:
            uniq[it["id"]] = it
    return list(uniq.values())


def rendered_links(br: Browser, pages, link_rx):
    rx = re.compile(link_rx, re.I)
    links = []
    for p in pages:
        html = br.html(p)
        for m in rx.findall(html):
            if m not in links:
                links.append(m)
    return links
