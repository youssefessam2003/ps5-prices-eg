"""Collect today's PS5 Slim prices from every source and write data/ files.

Usage:
  python collect.py                 # all sources
  python collect.py --only amazon noon
  python collect.py --skip-browser  # only plain-HTTP stores
  python collect.py --headed        # show the browser window
"""
import argparse
import json
import statistics
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sources import SOURCES  # noqa: E402
from http_sources import COLLECTORS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
CAIRO = timezone(timedelta(hours=2))  # Egypt standard time; DST shift doesn't matter for a daily date
try:
    from zoneinfo import ZoneInfo
    CAIRO = ZoneInfo("Africa/Cairo")
except Exception:
    pass


def now():
    return datetime.now(CAIRO)


def run_source(src, br):
    t0 = time.time()
    try:
        if src["kind"] == "browser":
            from browser_sources import marketplace
            items = marketplace(src, br)
        else:
            items = COLLECTORS[src["kind"]](src, br)
        stamp = now().isoformat(timespec="seconds")
        for it in items:
            it["seen_at"] = stamp
        status = {"status": "ok", "count": len(items),
                  "in_stock": sum(1 for i in items if i["in_stock"])}
    except Exception as e:
        items = []
        status = {"status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
        traceback.print_exc(limit=1)
    status.update(fetched_at=now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 1))
    return items, status


def stats_for(items):
    prices = sorted(i["price"] for i in items)
    if not prices:
        return None
    buckets = Counter(round(p / 500) * 500 for p in prices)
    common, common_n = buckets.most_common(1)[0]
    cheapest = min(items, key=lambda i: i["price"])
    return {
        "count": len(prices),
        "stores": len({i["source"] for i in items}),
        "min": prices[0], "max": prices[-1],
        "median": round(statistics.median(prices)),
        "avg": round(statistics.mean(prices)),
        "common": common, "common_count": common_n,
        "cheapest_id": cheapest["id"],
    }


def all_stats(listings):
    # Same defaults as the app: in stock, title confirms it's the Slim model.
    live = [i for i in listings if i["in_stock"] and i.get("slim_confirmed", True)]
    out = {}
    for model in ("digital", "disc"):
        m = [i for i in live if i["model"] == model]
        out[model] = {"console": stats_for([i for i in m if not i["bundle"]]), "all": stats_for(m)}
    return out


def build(today):
    """Rebuild latest.json + history.json from every daily snapshot."""
    snaps = sorted(SNAP.glob("*.json"))
    days, series = [], {}
    for f in snaps[-400:]:
        s = json.loads(f.read_text(encoding="utf-8"))
        days.append({"date": s["date"], "stats": all_stats(s["listings"])})
        for i in s["listings"]:
            e = series.setdefault(i["id"], {k: i.get(k) for k in ("store", "source", "seller", "title", "url", "model", "bundle")})
            e.setdefault("points", []).append([s["date"], i["price"], 1 if i["in_stock"] else 0])
    (DATA / "history.json").write_text(json.dumps({"days": days, "listings": series}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    cur = json.loads((SNAP / f"{today}.json").read_text(encoding="utf-8"))
    prev = None
    for f in reversed(snaps):
        if f.stem < today:
            prev = json.loads(f.read_text(encoding="utf-8"))
            break
    prev_price = {i["id"]: i["price"] for i in (prev or {}).get("listings", []) if i["in_stock"]}
    for i in cur["listings"]:
        p = prev_price.get(i["id"])
        i["prev_price"] = p
        pts = series.get(i["id"], {}).get("points", [])
        i["first_seen"] = pts[0][0] if pts else today
    cur["stats"] = all_stats(cur["listings"])
    cur["prev_stats"] = all_stats(prev["listings"]) if prev else None
    cur["prev_date"] = prev["date"] if prev else None
    cur["directory"] = [{k: s.get(k) for k in ("id", "name", "kind", "url")} for s in SOURCES]
    (DATA / "latest.json").write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--skip-browser", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()

    SNAP.mkdir(parents=True, exist_ok=True)
    today = now().date().isoformat()
    path = SNAP / f"{today}.json"
    snap = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"date": today, "sources": {}, "listings": []}

    if not a.build_only:
        todo = [s for s in SOURCES if s["kind"] != "manual" and (not a.only or s["id"] in a.only)]
        needs_browser = not a.skip_browser and any(s["kind"] == "browser" or s.get("render") for s in todo)
        if a.skip_browser:
            todo = [s for s in todo if s["kind"] != "browser"]
        br = None
        if needs_browser:
            from browser_sources import Browser
            br = Browser(headless=not a.headed)
        try:
            for src in todo:
                print(f"-> {src['id']}", flush=True)
                items, status = run_source(src, br)
                print(f"   {status}", flush=True)
                if status["status"] == "ok" or src["id"] not in snap["sources"]:
                    # replace that source's rows with the fresh ones (a failed retry keeps the earlier good run of today)
                    snap["listings"] = [i for i in snap["listings"] if i["source"] != src["id"]] + items
                    snap["sources"][src["id"]] = status
        finally:
            if br:
                br.close()
        snap["generated_at"] = now().isoformat(timespec="seconds")
        path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    build(today)
    s = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))["stats"]
    for m in ("digital", "disc"):
        print(m, json.dumps(s[m]["console"]))


if __name__ == "__main__":
    main()
