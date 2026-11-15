"""Every place that sells new PS5 consoles in Egypt that we know about.

kind:
  shopify  - Shopify store, read from its public /products.json (has real stock flags)
  woo      - WooCommerce store, read from its public Store API (has real stock flags)
  jsonld   - read listing/search pages, open each PS5 product page, read the schema.org
             Product data the store publishes (price + InStock/OutOfStock)
  browser  - big marketplaces that only render in a real browser (Amazon, Noon, Jumia, Carrefour)
  manual   - social-media pages and physical shops with no machine-readable prices.
             Listed in the app's directory; you can log their prices from the app.
"""

SOURCES = [
    # ---- Marketplaces (real browser) ----
    {"id": "amazon", "name": "Amazon.eg", "kind": "browser", "url": "https://www.amazon.eg",
     "search": ["https://www.amazon.eg/s?k=playstation+5+slim+console&language=en_AE",
                "https://www.amazon.eg/s?k=ps5+slim+digital&language=en_AE",
                "https://www.amazon.eg/s?k=ps5+slim+disc&language=en_AE"]},
    {"id": "noon", "name": "Noon", "kind": "browser", "url": "https://www.noon.com/egypt-en/",
     "search": ["https://www.noon.com/egypt-en/search/?q=playstation%205%20slim",
                "https://www.noon.com/egypt-en/search/?q=ps5%20slim%20digital"]},
    {"id": "jumia", "name": "Jumia", "kind": "browser", "url": "https://www.jumia.com.eg",
     "search": ["https://www.jumia.com.eg/catalog/?q=playstation+5+slim",
                "https://www.jumia.com.eg/catalog/?q=ps5+slim+digital"]},
    {"id": "carrefour", "name": "Carrefour Egypt", "kind": "browser", "url": "https://www.carrefouregypt.com",
     "search": ["https://www.carrefouregypt.com/mafegy/en/c/NFEGY4090101",
                "https://www.carrefouregypt.com/mafegy/en/search?keyword=playstation%205%20slim"]},

    # ---- Electronics chains ----
    {"id": "btech", "name": "B.TECH", "kind": "jsonld", "url": "https://btech.com",
     "search": ["https://btech.com/en/c/gaming-area/consoles/playstation"],
     "link": r"/en/p/[^\"'#\s]+"},
    {"id": "2b", "name": "2B", "kind": "jsonld", "url": "https://2b.com.eg",
     "search": ["https://2b.com.eg/en/gaming/playstation.html"], "render": True,
     "link": r"https://2b\.com\.eg/en/[a-z0-9-]*(?:playstation|ps5)[a-z0-9-]*\.html"},
    {"id": "raneen", "name": "Raneen", "kind": "jsonld", "url": "https://www.raneen.com",
     "search": ["https://www.raneen.com/en/catalogsearch/result/?q=playstation+5+slim"], "render": True,
     "link": r"https://www\.raneen\.com/en/[a-z0-9-]*(?:playstation|ps5|ps-5)[a-z0-9-]*"},
    {"id": "raya", "name": "Raya Shop", "kind": "jsonld", "url": "https://www.rayashop.com",
     "search": ["https://www.rayashop.com/en/catalogsearch/result/?q=playstation+5"], "render": True,
     "link": r"https://www\.rayashop\.com/en/[a-z0-9-]*(?:playstation|ps5)[a-z0-9-]*(?:\.html)?"},
    {"id": "elaraby", "name": "El Araby Group", "kind": "jsonld", "url": "https://www.elarabygroup.com",
     "search": ["https://www.elarabygroup.com/en/gaming-and-entertainment/playstation/playstation5"], "render": True,
     "link": r"https://www\.elarabygroup\.com/en/[a-z0-9-]*(?:playstation|ps5)[a-z0-9-]*"},
    {"id": "dubaiphone", "name": "Dubai Phone", "kind": "jsonld", "url": "https://www.dubaiphone.net",
     "search": ["https://www.dubaiphone.net/?s=playstation+5&post_type=product"], "render": True,
     "link": r"https://www\.dubaiphone\.net/product/[a-z0-9%-]*(?:playstation|ps5)[a-z0-9%-]*/?"},
    {"id": "elnekhely", "name": "El Nekhely Technology", "kind": "jsonld", "url": "https://elnekhelytechnology.com",
     "search": ["https://elnekhelytechnology.com/index.php?route=product/search&search=playstation%205"], "render": True,
     "link": r"https://elnekhelytechnology\.com/[^\"'\s]*(?:playstation|ps5)[^\"'\s]*"},

    # ---- Gaming stores ----
    {"id": "games2egypt", "name": "Games2Egypt", "kind": "jsonld", "url": "https://www.games2egypt.com",
     "search": ["https://www.games2egypt.com/Category/3289/ps5-consoles"],
     "link": r"/Product/\d+/[a-z0-9-]+"},
    {"id": "gamesworld", "name": "Games World Egypt", "kind": "jsonld", "url": "https://www.gamesworldegypt.com",
     "search": ["https://www.gamesworldegypt.com/devices-accessories/ps/playstation-console"],
     "link": r"https://www\.gamesworldegypt\.com/devices-accessories/ps/playstation-console/[^\"'\s]+"},
    {"id": "gamerzlounge", "name": "GamerZ Lounge", "kind": "jsonld", "url": "https://gamerzlounge.me",
     "search": ["https://gamerzlounge.me/playstation/playstation-5/ps5-consoles"], "render": True,
     "link": r"https://gamerzlounge\.me/[a-z0-9()%-]*(?:playstation-5|ps5)[a-z0-9()%-]*"},
    {"id": "kaafo", "name": "Kaafo", "kind": "jsonld", "url": "https://kaafo.net",
     "search": ["https://kaafo.net/ar-eg/categories/269189"], "render": True,
     "link": r"https://kaafo\.net/[^\"'\s]*/products/[^\"'\s]+"},
    {"id": "shamy", "name": "Shamy Stores", "kind": "shopify", "url": "https://shamystores.com"},
    {"id": "xprs", "name": "XPRS", "kind": "shopify", "url": "https://myxprs.com"},
    {"id": "tharaa", "name": "Tharaa Store", "kind": "shopify", "url": "https://tharaastore.com"},
    {"id": "dream2000", "name": "Dream 2000", "kind": "shopify", "url": "https://dream2000.com"},
    {"id": "ahw", "name": "AHW Store", "kind": "shopify", "url": "https://ahw.store"},
    {"id": "miami", "name": "Miami Centers", "kind": "woo", "url": "https://miamicenters.com"},
    {"id": "ts3era", "name": "Ts3era", "kind": "woo", "url": "https://ts3era.com"},
    {"id": "shiko", "name": "Shiko Game Store", "kind": "woo", "url": "https://shikogamestore.com"},
    {"id": "avocato", "name": "El Avocato Mobile", "kind": "woo", "url": "https://elavocatomobile.net"},
    {"id": "zaky", "name": "Zaky Store", "kind": "woo", "url": "https://zakystore.com"},
    {"id": "mobilaty", "name": "Mobilaty", "kind": "woo", "url": "https://mobilaty.com"},

    # ---- No machine-readable prices: social pages / physical shops ----
    {"id": "fb_marketplace", "name": "Facebook Marketplace & gaming groups", "kind": "manual",
     "url": "https://www.facebook.com/marketplace/cairo/search?query=ps5%20slim"},
    {"id": "dubizzle", "name": "Dubizzle (OLX)", "kind": "manual",
     "url": "https://www.dubizzle.com.eg/en/video-games-consoles/q-ps5-slim/"},
    {"id": "opensooq", "name": "OpenSooq", "kind": "manual",
     "url": "https://eg.opensooq.com/ar/find?term=ps5%20slim"},
    {"id": "vodafone", "name": "Vodafone Shop", "kind": "manual", "url": "https://eshop.vodafone.com.eg"},
    {"id": "sigma", "name": "Sigma Computer", "kind": "manual", "url": "https://www.sigma-computer.com"},
    {"id": "compume", "name": "CompuMe", "kind": "manual", "url": "https://www.compume.com.eg"},
    {"id": "techvalley", "name": "Technology Valley", "kind": "manual", "url": "https://www.facebook.com/search/top?q=technology%20valley%20egypt"},
    {"id": "elbostan", "name": "El Bostan Mall (Downtown gaming shops)", "kind": "manual",
     "url": "https://maps.google.com/?q=El+Bostan+Mall+Cairo"},
]
