"""Decide whether a store listing is a NEW PS5 Slim console, and which edition."""
import re

AR_NORMALIZE = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ـ": ""})

PS5 = re.compile(r"(ps\s?5|playstation\s?5|play\s?station\s?5|بلاي\s?ستيشن\s?5|بلايستيشن\s?5|بلاى\s?ستيشن\s?5|سوني\s?5)")
SLIM = re.compile(r"(slim\b|سليم|cfi[- ]?20|1\s?tb|1\s?تيرا|1000\s?gb)")
DIGITAL = re.compile(r"(digital|ديجيتال|ديجتال|رقمي|الرقميه|بدون\s?(قرص|اقراص|سي\s?دي))")
DISC = re.compile(r"(disc|disk|standard|blu-?ray|ultra\s?hd|سي\s?دي|\bcd\b|قرص|اقراص|ستاندرد|القياسي|القياسيه)")

# Things that are not a console, or are not new.
REJECT = re.compile(
    r"(\bpro\b|برو|ps\s?4|playstation\s?4|portal|vr\s?2|\bvr\b|controller\s+only|"
    r"used|مستعمل|refurb|renewed|open\s?box|pre-?owned|outlet|"
    r"(?<!with )disc\s?drive(?!.*console)|blu-?ray\s?drive|محرك|"
    r"\bfor\s+(the\s+)?(new\s+)?(sony\s+)?(ps\s?5|playstation)|compatible|متوافق|"
    r"\bstand\b|cover|faceplate|plates?\b|skin|sticker|\bcase\b|\bbag\b|backpack|charging|charger|"
    r"cooling|\bfan\b|mount|dust|headset|cable|remote|"
    r"شنطه|حامل|غطاء|جراب|ستاند|مروحه|شاحن|"
    r"gift\s?card|psn|voucher\s+only|subscription|plus\s+\d+\s*month)"
)
CONSOLE_HINT = re.compile(r"(console|كونسول|جهاز|edition|اصدار|نسخه|slim|سليم|digital|disc|ديجيتال|\b1\s?tb)")

BUNDLE = re.compile(
    r"(extra|additional|اضافي|اضافيه|ذراعين|2\s?controllers|two\s+controllers|bundle|باندل|"
    r"\+|fc\s?2\d|ea\s?sports|call\s+of\s+duty|black\s+ops|ghost\s+of|yotei|fortnite|"
    r"horizon|spider|gran\s+turismo|gta|tekken|astro|anniversary|limited|"
    r"with\s+(game|\d+\s+games)|مع\s+لعبه|مع\s+لعبة|العاب)"
)
REGIONS = [
    ("KSA", r"(ksa|saudi|سعودي)"),
    ("UAE", r"(uae|emirates|اماراتي)"),
    ("Japan", r"(japan|japanese|ياباني)"),
    ("Europe", r"(europe|european|\beu\b|اوروبي|uk\b)"),
    ("Middle East", r"(middle\s+east|\bme\b|شرق\s+اوسط)"),
    ("International", r"(international|دولي|انترناشونال)"),
]


def normalize(text: str) -> str:
    t = (text or "").lower().translate(AR_NORMALIZE)
    t = re.sub(r"[™®()\[\]|,/–—_-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(title: str):
    """Return dict(model, bundle, region) for a new PS5 Slim console, else None."""
    t = normalize(title)
    if not PS5.search(t):
        return None
    if REJECT.search(t):
        return None
    if not CONSOLE_HINT.search(t):
        return None
    is_digital = bool(DIGITAL.search(t))
    is_disc = bool(DISC.search(t)) and not is_digital
    slim = bool(SLIM.search(t))
    if not slim:
        # Every new PS5 sold since 2024 is the Slim model; older "fat" units say 825GB / CFI-1xxx.
        if re.search(r"(825\s?gb|cfi[- ]?1\d)", t) or re.search(r"(standard\s+edition\s+console|original)", t):
            return None
    model = "digital" if is_digital else "disc"
    region = next((name for name, rx in REGIONS if re.search(rx, t)), None)
    return {
        "model": model,
        "bundle": bool(BUNDLE.search(t)),
        "region": region,
        "slim_confirmed": slim,
    }


PRICE_MIN, PRICE_MAX = 18_000, 160_000


def sane_price(p) -> bool:
    return p is not None and PRICE_MIN <= p <= PRICE_MAX


if __name__ == "__main__":
    tests = [
        "Sony PlayStation 5 Slim Console (International Version) Digital Edition With Controller",
        "Sony PlayStation 5 Slim Disc Console KSA Version with Extra Controller and EA FC 27 Game",
        "Sony Disc Drive For Digital Editions Slim",
        "PlayStation Portal Remote Player - PlayStation 5",
        "fashion mania Horizontal Stand for PS5 Slim Console Only",
        "سونى بلاي ستيشن 5 Slim Digital Edition 1 تيرابايت",
        "Sony Playstation 5 Standard Slim (1 year warranty)",
        "Sony PlayStation 5 Pro Console 2TB",
        "Console Sony PlayStation 5 Édition Standard Blanche",
        "Sony Playstation 5 Slim, white with DualSense",
    ]
    for x in tests:
        print(classify(x), "<-", x)
