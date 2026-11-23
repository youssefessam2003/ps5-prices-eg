"""Regression tests for real gaps found during the November source audit."""
import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classify import classify
from collect import merge_source, run_source, stats_for, with_known_products
from discovery import canonical_url, next_pages, product_links, sitemap_links
from http_sources import _shopify_items, jsonld, product_page, shopify, to_price, woo
from sources import SOURCES

SRC = {"id": "test", "name": "Egypt Store", "url": "https://store.example", "kind": "jsonld"}


def ld(value):
    return '<script type="application/ld+json">' + json.dumps(value) + '</script>'


def product(name="PS5 Slim Digital Console", **offer):
    return {"@type": "Product", "name": name, "offers": {
        "@type": "Offer", "price": "43000", "priceCurrency": "EGP",
        "availability": "https://schema.org/InStock", **offer}}


def variation_form(variants):
    from html import escape
    return '<form data-product_id="28218" data-product_variations="' + escape(json.dumps(variants), quote=True) + '''">
        <select name="attribute_pa_condition"><option value="new">New</option>
        <option value="used">Excellent condition</option></select></form>'''


class Response:
    def __init__(self, data=None, text="", headers=None, url="https://store.example/search"):
        self.data, self.text, self.headers, self.url = data, text, headers or {}, url
        self.content = text.encode()

    def json(self):
        return self.data


class ParsingTests(unittest.TestCase):
    def test_arabic_prices_and_ambiguous_ranges(self):
        self.assertEqual(to_price("٤٢٬٩٩٩٫٠٠ ج.م"), 42999)
        self.assertEqual(to_price("EGP 43,999.00"), 43999)
        self.assertEqual(to_price("EGP -43,999.00"), -43999)
        for bad in ("43000 - 49000", "3500/mo total 43000", True, float("nan")):
            self.assertIsNone(to_price(bad))

    def test_stock_currency_and_condition(self):
        for value, stock in (("InStock", True), ("OutOfStock", False), ("PreOrder", False), ("", False)):
            rows = product_page(SRC, SRC["url"], ld(product(availability=value)))
            self.assertEqual(rows[0]["in_stock"], stock)
        self.assertEqual(product_page(SRC, SRC["url"], ld(product(priceCurrency="AED"))), [])
        self.assertEqual(product_page(SRC, SRC["url"], ld(product(itemCondition="https://schema.org/UsedCondition"))), [])
        self.assertEqual(product_page(SRC, SRC["url"], ld(product(priceCurrency=None))), [])

    def test_microdata_does_not_override_an_explicit_used_condition(self):
        markup = '''<div class="product-info-main"><h1>PS5 Slim Console</h1>
          <div class="product-info-price"><meta itemprop="price" content="40000">
          <meta itemprop="priceCurrency" content="EGP"></div><div class="stock available"></div></div>'''
        self.assertEqual(product_page(SRC, SRC["url"],
            ld(product(itemCondition='https://schema.org/UsedCondition')) + markup), [])

    def test_product_group_retains_query_identity(self):
        a = product(url="/product?slug=ps5-slim&combination_id=804")
        b = product(url="/product?slug=ps5-slim&combination_id=805", price=45000)
        group = {"@type": "ProductGroup", "hasVariant": [a, b]}
        rows = product_page(SRC, SRC["url"], ld(group))
        self.assertEqual(len({r["id"] for r in rows}), 2)
        self.assertIn("combination_id=804", rows[0]["url"])

    def test_nested_item_list_and_duplicate_schema(self):
        value = {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": product()}]}
        self.assertEqual(len(product_page(SRC, SRC["url"], ld(value) + ld(value))), 1)

    def test_aggregate_low_price_is_not_an_offer(self):
        p = product()
        p["offers"] = {"@type": "AggregateOffer", "lowPrice": 20000, "highPrice": 45000,
                       "priceCurrency": "EGP", "availability": "InStock"}
        self.assertEqual(product_page(SRC, SRC["url"], ld(p)), [])
        p["offers"]["offers"] = [product()["offers"]]
        self.assertEqual(product_page(SRC, SRC["url"], ld(p))[0]["price"], 43000)

    def test_woo_new_out_of_stock_is_not_replaced_by_in_stock_used_minimum(self):
        p = product()
        p['sku'] = 28218
        p['offers'] = [{'@type': 'AggregateOffer', 'lowPrice': 31999, 'highPrice': 42999,
                        'priceCurrency': 'EGP', 'availability': 'InStock'}]
        variations = [
            {'variation_id': 57901, 'attributes': {'attribute_pa_condition': 'new'},
             'display_price': 42999, 'display_regular_price': 53000, 'is_in_stock': False,
             'is_purchasable': True, 'variation_is_active': False},
            {'variation_id': 57902, 'attributes': {'attribute_pa_condition': 'used'},
             'display_price': 31999, 'is_in_stock': True, 'is_purchasable': True}]
        markup = ld(p) + variation_form(variations)
        rows = product_page(SRC, SRC['url'] + '/ps5-slim', markup)
        self.assertEqual([(r['id'], r['price'], r['in_stock']) for r in rows], [('test:57901', 42999, False)])
        self.assertIn('variation_id=57901', rows[0]['url'])
        self.assertIn('attribute_pa_condition=new', rows[0]['url'])
        self.assertEqual(rows[0]['old_price'], 53000)
        variations[0].update(is_in_stock=True, variation_is_active=True)
        self.assertTrue(product_page(SRC, SRC['url'], ld(p) + variation_form(variations))[0]['in_stock'])

    def test_woo_unreadable_or_unconfirmed_variations_cannot_fall_back_to_parent(self):
        p = product()
        variation = {'variation_id': 7, 'attributes': {'attribute_pa_condition': 'new'},
                     'display_price': 40000, 'is_in_stock': True}
        for currency in ('AED', None):
            p['offers']['priceCurrency'] = currency
            self.assertEqual(product_page({**SRC}, SRC['url'], ld(p) + variation_form([variation])), [])
        p['offers']['priceCurrency'] = 'EGP'
        p['itemCondition'] = 'https://schema.org/UsedCondition'
        self.assertEqual(product_page({**SRC}, SRC['url'], ld(p) + variation_form([variation])), [])
        del p['itemCondition']
        for unresolved in (False, None, 'broken JSON', [{'variation_id': 7, 'attributes': {'attribute_pa_condition': ''}}]):
            self.assertEqual(product_page({**SRC}, SRC['url'], ld(p) + variation_form(unresolved)), [])

    def test_included_game_bundle_does_not_override_digital_title(self):
        p = product(availability='OutOfStock')
        # Shared store template wrongly says CD; only its explicit extras count.
        p['description'] = r'\u003cp\u003eTHE BUNDLE INCLUDE : 1- PS5 SLIM CD EDITION 2- 1 CONTROLLER 3- 10 GAMES ONLINE OR OFFLINE\u003c/p\u003e'
        row = product_page(SRC, SRC['url'], ld(p))[0]
        self.assertEqual(row['model'], 'digital')
        self.assertTrue(row['bundle'])
        self.assertFalse(row['in_stock'])
        p['description'] = 'The bundle include: PS5 Slim Digital, 1 controller, HDMI cable.'
        self.assertFalse(product_page(SRC, SRC['url'], ld(p))[0]['bundle'])
        self.assertTrue(classify('PS5 SLIM DIGITAL NEW Wolverine')['bundle'])

    def test_magento_microdata_and_recommendations(self):
        html = '''<div class="product-info-main"><h1><span itemprop="name">PS5 Slim Disc Console</span></h1>
          <div class="product-info-price"><meta itemprop="price" content="45500">
          <meta itemprop="priceCurrency" content="EGP"></div><div class="stock available">In stock</div></div>
          <div class="related"><meta itemprop="price" content="19000"></div>'''
        self.assertEqual(product_page(SRC, SRC["url"], html)[0]["price"], 45500)
        self.assertEqual(product_page(SRC, SRC["url"], html.replace("stock available", "stock unavailable"))[0]["in_stock"], False)

    def test_slim_825gb_typo_and_condition(self):
        self.assertTrue(classify("PlayStation 5 Slim Digital Edition 825GB")["slim_confirmed"])
        self.assertTrue(classify("Sony Playstation 5 Disc Silm Console")["slim_confirmed"])
        for name in ("PS5 Slim Disc FABRIKA", "PS5 Slim Digital Used", "PS5 Pro Console", "Disc Drive for PS5 Slim"):
            self.assertIsNone(classify(name), name)

    def test_two_controller_bundle_names(self):
        for suffix in ("2 Wireless Controller", "2 Controllers", "Two Controllers", "Two DualSense Wireless Controllers", "FIFA 24 Digital Voucher"):
            self.assertTrue(classify("PS5 Slim Disc Console with " + suffix)["bundle"])

    def test_shopify_variants_keep_own_price_and_stock(self):
        p = {"title": "PS5 Slim Digital Console", "handle": "ps5-slim", "variants": [
            {"id": 1, "title": "825GB", "price": "38000", "available": False},
            {"id": 2, "title": "1TB", "price": "45000", "available": True}]}
        rows = _shopify_items(SRC, p)
        self.assertEqual([(r["price"], r["in_stock"]) for r in rows], [(38000, False), (45000, True)])
        self.assertIn("variant=2", rows[1]["url"])


class DiscoveryTests(unittest.TestCase):
    def test_relative_opaque_product_urls_and_external_rejection(self):
        src = {**SRC, "link": r"/product\?[^\"\s]+"}
        html = '''<a href="/product?slug=sony-slim&amp;combination_id=804">PS5 Slim Console</a>
          <a href="https://elsewhere.example/product?slug=ps5-slim">PS5 Slim Console</a>'''
        self.assertEqual(product_links(src, SRC["url"], html),
                         ["https://store.example/product?slug=sony-slim&combination_id=804"])

    def test_tracking_removed_product_identity_preserved(self):
        self.assertEqual(canonical_url(SRC["url"], "/index.php?product_id=755&amp;utm_source=google#review"),
                         "https://store.example/index.php?product_id=755")

    def test_pagination_is_same_store_only(self):
        html = '<a rel="next" href="?page=2">Next</a><a class="next" href="https://other.example/">Next</a>'
        self.assertEqual(next_pages(SRC, SRC["url"] + "/search?q=ps5", html),
                         ["https://store.example/search?page=2"])

    def test_plain_next_and_arabic_pagination(self):
        html = '''<a href="?search=PS5&page=2">Next</a><a href="?page=3" aria-label="الصفحة التالية">›</a>
                  <a href="/product/23">Next console</a><a href="https://other.example/?page=9">Next</a>'''
        self.assertEqual(next_pages(SRC, SRC['url'] + '/en/products/?search=PS5', html),
                         ['https://store.example/en/products/?search=PS5&page=2',
                          'https://store.example/en/products/?page=3'])

    def test_bounded_sitemap_index(self):
        index = '<sitemapindex><sitemap><loc>https://store.example/products.xml</loc></sitemap></sitemapindex>'
        urls = '<urlset><url><loc>https://store.example/products/ps5-slim</loc></url><url><loc>https://bad.example/ps5</loc></url></urlset>'
        with patch("http_sources.time.sleep"):
            rows = sitemap_links({**SRC, "sitemaps": ["/sitemap.xml"]},
                                 lambda u: Response(text=index if u.endswith('sitemap.xml') else urls), lambda m: None)
        self.assertEqual(rows, ["https://store.example/products/ps5-slim"])

    @patch("http_sources.time.sleep")
    def test_jsonld_follows_next_page_and_reports_product_failures(self, sleep):
        cfg = {**SRC, "search": [SRC["url"] + "/search"], "link": r"/products/[^\"\s]+"}
        def fetch(u, **kw):
            if u.endswith('/search'):
                return Response(text='<a href="/products/ps5-slim-a">PS5 Slim</a><a rel="next" href="?page=2">Next</a>')
            if "page=2" in u:
                return Response(text='<a href="/products/ps5-slim-b">PS5 Slim</a>')
            if u.endswith('-b'):
                raise RuntimeError("temporary outage")
            return Response(text=ld(product()))
        with patch("http_sources.get", side_effect=fetch):
            rows = jsonld(cfg)
        self.assertEqual(len(rows), 1)
        self.assertEqual(cfg["_diagnostics"]["search_pages"], 2)
        self.assertIn("temporary outage", cfg["_diagnostics"]["warnings"][0])

    @patch("http_sources.time.sleep")
    def test_woo_paginates_scales_egp_and_deduplicates_queries(self, sleep):
        def fetch(u, params):
            n = params["page"]
            return Response([{"id": n, "name": "PS5 Slim Digital Console", "permalink": f"/ps5-slim-{n}",
                "prices": {"price": "4300000", "regular_price": "4500000", "currency_minor_unit": 2,
                           "currency_code": "EGP"}, "is_in_stock": n == 2}], headers={"X-WP-TotalPages": "2"})
        with patch("http_sources.get", side_effect=fetch):
            rows = woo({**SRC, "queries": ["ps5", "playstation 5"]})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["price"], 43000)
        self.assertEqual([r["in_stock"] for r in rows], [False, True])

    @patch('http_sources.time.sleep')
    def test_woo_resolves_variable_conditions_even_without_a_price_range(self, sleep):
        p = {'id': 28218, 'name': 'PS5 Slim Digital Console', 'type': 'variable',
             'permalink': SRC['url'] + '/ps5-slim', 'is_in_stock': True,
             'prices': {'price': '31999', 'currency_code': 'EGP', 'currency_minor_unit': 0}}
        markup = ld(product()) + variation_form([
            {'variation_id': 7, 'attributes': {'attribute_pa_condition': 'new'},
             'display_price': 42999, 'is_in_stock': False},
            {'variation_id': 8, 'attributes': {'attribute_pa_condition': 'used'},
             'display_price': 31999, 'is_in_stock': True}])
        def fetch(u, **kw):
            return Response([p]) if 'wp-json' in u else Response(text=markup)
        with patch('http_sources.get', side_effect=fetch):
            rows = woo({**SRC, 'queries': ['ps5 slim']})
        self.assertEqual([(r['price'], r['in_stock']) for r in rows], [(42999, False)])

    @patch("http_sources.time.sleep")
    def test_saturated_shopify_search_reaches_eleventh_product(self, sleep):
        p = {"id": 11, "title": "PS5 Slim Digital Console", "handle": "ps5-slim-eleven",
             "variants": [{"id": 111, "price": "43000", "available": True}]}
        def fetch(u, **kw):
            if u.endswith('/cart.js'):
                return Response({'currency': 'EGP'})
            if 'suggest.json' in u:
                return Response({"resources": {"results": {"products": [
                    {"handle": str(n), "title": "PS5 game"} for n in range(10)]}}})
            if u.endswith('/search'):
                return Response(text='<a href="/products/ps5-slim-eleven">PS5 Slim Digital Console</a>')
            return Response({**p, 'variants': [{**p['variants'][0], 'price': 4300000}]})
        with patch("http_sources.get", side_effect=fetch):
            rows = shopify({**SRC, "queries": ["ps5"]})
        self.assertEqual(rows[0]["id"], "test:111")


class CollectionTests(unittest.TestCase):
    def test_fresh_cli_rechecks_known_urls_but_never_reuses_old_prices(self):
        import collect
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshots = root / 'snapshots'
            snapshots.mkdir()
            day = collect.now().date().isoformat()
            other = {**SRC, 'id': 'other'}
            old = {'id': 'old', 'source': 'test', 'store': 'Store', 'title': 'PS5 Slim Digital Console',
                   'url': SRC['url'] + '/known-console', 'model': 'digital', 'bundle': False,
                   'price': 42000, 'in_stock': True, 'slim_confirmed': True}
            (snapshots / (day + '.json')).write_text(json.dumps({
                'date': day, 'sources': {}, 'listings': [old, {**old, 'id': 'old-other', 'source': 'other'}]}))
            new = {**old, 'id': 'fresh', 'price': 43000}
            def run(cfg, br):
                self.assertIn(old['url'], cfg['products'])
                return ([new], {'status': 'ok', 'fetched_at': 'now'}) if cfg['id'] == 'test' else (
                    [], {'status': 'error', 'error': 'blocked', 'fetched_at': 'now'})
            with patch.object(collect, 'DATA', root), patch.object(collect, 'SNAP', snapshots), \
                 patch.object(collect, 'SOURCES', [SRC, other]), patch.object(collect, 'run_source', side_effect=run), \
                 patch('sys.argv', ['collect.py', '--fresh', '--skip-browser', '--data-dir', folder,
                                    '--progress-file', str(root / 'progress.json')]), patch('sys.stdout', io.StringIO()):
                collect.main()
            result = json.loads((root / 'latest.json').read_text())
            self.assertEqual([r['id'] for r in result['listings']], ['fresh'])
            self.assertEqual(result['sources']['other']['status'], 'error')
            progress = json.loads((root / 'progress.json').read_text())
            self.assertEqual((progress['status'], progress['completed'], progress['total']), ('completed', 2, 2))

    def test_aggregate_rounding_matches_flutter_on_half_pounds(self):
        rows = [{'id': str(p), 'source': 'test', 'price': p} for p in (44000, 44001)]
        self.assertEqual(stats_for(rows)['median'], 44001)
        self.assertEqual(stats_for(rows)['avg'], 44001)
        buckets = [{'id': str(p), 'source': 'test', 'price': p} for p in (44250, 44250)]
        self.assertEqual(stats_for(buckets)['common'], 44500)

    def test_known_prices_supply_only_urls_for_fresh_fetch(self):
        old = {'source': 'test', 'url': 'https://store.example/ps5-slim', 'price': 42000, 'seen_at': 'yesterday'}
        cfg = with_known_products(SRC, [old])
        self.assertEqual(cfg['products'], [old['url']])
        self.assertNotIn('price', cfg)
        self.assertNotIn('products', SRC)

    def test_marketplace_follows_next_and_deduplicates_search_results(self):
        from browser_sources import marketplace, NEXT_PAGE_JS
        class FakeBrowser:
            page = None
            current = ""
            def __init__(self):
                self.page = self
            def open(self, url, *args):
                self.current = url
            def evaluate(self, js):
                if js == NEXT_PAGE_JS:
                    return SRC['url'] + '/search?page=2' if '?' not in self.current else None
                key = '2' if '?' in self.current else '1'
                return [{'key': key, 'title': 'PS5 Slim Disc Console', 'price': '45500',
                         'url': SRC['url'] + '/ps5-slim-' + key, 'stock': True}]
        src = {**SRC, 'id': 'jumia', 'search': [SRC['url'] + '/search']}
        self.assertEqual(len(marketplace(src, FakeBrowser())), 2)
        self.assertEqual(src['_diagnostics']['search_pages'], 2)

    def test_unique_source_ids_and_registered_collectors(self):
        from http_sources import COLLECTORS
        self.assertEqual(len(SOURCES), len({s["id"] for s in SOURCES}))
        for src in SOURCES:
            self.assertIn(src['kind'], {*COLLECTORS, 'browser', 'manual'})
            if src['kind'] == 'jsonld':
                self.assertTrue(src.get('search') or src.get('products'))

    def test_failed_retry_records_failure_and_retains_today(self):
        row = {"source": "test", "in_stock": True}
        snap = {"sources": {"test": {"status": "ok", "fetched_at": "earlier"}}, "listings": [row]}
        merge_source(snap, SRC, [], {"status": "error", "fetched_at": "later"})
        self.assertEqual(snap["listings"], [row])
        self.assertEqual(snap["sources"]["test"]["fetched_at"], "later")
        self.assertEqual(snap["sources"]["test"]["retained_from"], "earlier")
        merge_source(snap, SRC, [], {"status": "error", "fetched_at": "third attempt"})
        self.assertEqual(snap["sources"]["test"]["retained_from"], "earlier")

    def test_invalid_api_is_reported_as_error_not_empty_success(self):
        cfg = {**SRC, "kind": "woo", "queries": ["ps5"]}
        with patch("http_sources.get", return_value=Response({"code": "rest_no_route"})), patch("http_sources.time.sleep"):
            with patch("collect.traceback.print_exc"):
                rows, status = run_source(cfg, None)
        self.assertEqual(rows, [])
        self.assertEqual(status["status"], "error")


if __name__ == "__main__":
    unittest.main()
