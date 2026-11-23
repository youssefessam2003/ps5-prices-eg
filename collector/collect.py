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
import sqlite3
import sys
import time
import traceback
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sources import SOURCES  # noqa: E402
from http_sources import COLLECTORS, round_amount  # noqa: E402

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
    src = {**src, "_diagnostics": {}}
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
    diag = src["_diagnostics"]
    if not items and status["status"] == "ok":
        diag.setdefault("warnings", []).append("No matching console offers returned; inspect source coverage")
    status.update(diag)
    status.update(fetched_at=now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 1))
    return items, status


def write_json(path, value, **options):
    """Checkpoint atomically so an interrupted collection leaves valid JSON."""
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, **options), encoding="utf-8")
    for attempt in range(20):
        try:
            temp.replace(path)
            return
        except PermissionError:
            # Windows briefly locks files while another thread reads them.
            if attempt == 19:
                raise
            time.sleep(.025)


@contextmanager
def collection_lock(root=ROOT):
    """Serialize CLI, scheduled and phone-triggered collections in this workspace."""
    lock = Path(root) / 'logs' / 'collector.lock.sqlite3'
    lock.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(lock, timeout=0)
    try:
        try:
            conn.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as e:
            raise RuntimeError('Another price collection is already running') from e
        yield
    finally:
        conn.close()


def merge_source(snap, src, items, status):
    previous = snap["sources"].get(src["id"], {})
    old_rows = [i for i in snap["listings"] if i["source"] == src["id"]]
    if status["status"] == "ok" or not old_rows:
        snap["listings"] = [i for i in snap["listings"] if i["source"] != src["id"]] + items
    else:
        # Keep good prices collected earlier *today*, while recording this failure.
        good_stamp = previous.get("last_success_at") or previous.get("retained_from")
        if not good_stamp:
            good_stamp = (previous.get("fetched_at") if previous.get("status") == "ok" else
                          max((i.get("seen_at", "") for i in old_rows), default="") or None)
        status.update(retained_from=good_stamp, last_success_at=good_stamp,
                      count=len(old_rows), in_stock=sum(i["in_stock"] for i in old_rows))
    if status["status"] == "ok":
        status["last_success_at"] = status["fetched_at"]
    elif previous.get("last_success_at"):
        status["last_success_at"] = previous["last_success_at"]
    snap["sources"][src["id"]] = status


def with_known_products(src, listings):
    """Previously discovered URLs are seeds only; every price is fetched anew."""
    if src["kind"] != "jsonld":
        return src
    urls = [*src.get("products", []), *(i["url"] for i in listings if i["source"] == src["id"])]
    return {**src, "products": list(dict.fromkeys(urls))}


def stats_for(items):
    prices = sorted(i["price"] for i in items)
    if not prices:
        return None
    buckets = Counter(round_amount(p / 500) * 500 for p in prices)
    common, common_n = buckets.most_common(1)[0]
    cheapest = min(items, key=lambda i: i["price"])
    return {
        "count": len(prices),
        "stores": len({i["source"] for i in items}),
        "min": prices[0], "max": prices[-1],
        "median": round_amount(statistics.median(prices)),
        "avg": round_amount(statistics.mean(prices)),
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


def directory_entry(source):
    """Publish reviewable store/contact provenance, excluding crawl internals."""
    fields = ("id", "name", "kind", "url", "website", "social", "social_checked_at",
              "facebook_followers_observed", "notes")
    return {k: source[k] for k in fields if k in source}


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
    write_json(DATA / "history.json", {"days": days, "listings": series}, separators=(",", ":"))

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
    cur["directory"] = [directory_entry(s) for s in SOURCES]
    write_json(DATA / "latest.json", cur, indent=1)


def main():
    global DATA, SNAP
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--skip-browser", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--data-dir", type=Path, help="Write an isolated validation run here instead of data/")
    ap.add_argument("--list-sources", action="store_true", help="List configured sources without fetching")
    ap.add_argument("--fresh", action="store_true", help="Rebuild current offers entirely from this run; retain no old prices")
    ap.add_argument("--progress-file", type=Path, help="Write live collection progress as atomic JSON")
    ap.add_argument("--progress-offset", type=int, default=0, help="Already-completed sources when resuming this fresh job")
    ap.add_argument("--progress-total", type=int, help="Whole job source count when resuming")
    a = ap.parse_args()
    if a.only:
        unknown = set(a.only) - {s["id"] for s in SOURCES}
        if unknown:
            ap.error("Unknown source IDs: " + ", ".join(sorted(unknown)))
    if a.list_sources:
        for src in SOURCES:
            print(f"{src['id']:16} {src['kind']:8} {src['name']}")
        return
    if a.data_dir:
        DATA = a.data_dir.resolve()
        SNAP = DATA / "snapshots"

    SNAP.mkdir(parents=True, exist_ok=True)
    today = now().date().isoformat()
    path = SNAP / f"{today}.json"
    snap = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"date": today, "sources": {}, "listings": []}

    if not a.build_only:
        known = list(snap["listings"])
        previous = [p for p in sorted(SNAP.glob("*.json")) if p.stem < today]
        if previous:
            known.extend(json.loads(previous[-1].read_text(encoding="utf-8"))["listings"])
        todo = [s for s in SOURCES if s["kind"] != "manual" and (not a.only or s["id"] in a.only)]
        needs_browser = not a.skip_browser and any(s["kind"] == "browser" or s.get("render") for s in todo)
        if a.skip_browser:
            todo = [s for s in todo if s["kind"] != "browser"]
        if a.fresh:
            snap = {"date": today, "sources": {}, "listings": []}

        def progress(completed, source=None, state='running'):
            if a.progress_file:
                a.progress_file.parent.mkdir(parents=True, exist_ok=True)
                write_json(a.progress_file, {
                    'status': state, 'completed': completed + a.progress_offset,
                    'total': a.progress_total if a.progress_total is not None else len(todo),
                    'current_source': source['name'] if source else None,
                    'updated_at': now().isoformat(timespec='seconds'),
                })

        progress(0)
        br = None
        if needs_browser:
            from browser_sources import Browser
            br = Browser(headless=not a.headed)
        try:
            for index, src in enumerate(todo):
                src = with_known_products(src, known)
                progress(index, src)
                print(f"-> {src['id']}", flush=True)
                items, status = run_source(src, br)
                print(f"   {status}", flush=True)
                merge_source(snap, src, items, status)
                snap["generated_at"] = now().isoformat(timespec="seconds")
                write_json(path, snap, indent=1)
                progress(index + 1)
        finally:
            if br:
                br.close()
        snap["generated_at"] = now().isoformat(timespec="seconds")
        write_json(path, snap, indent=1)

    build(today)
    s = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))["stats"]
    for m in ("digital", "disc"):
        print(m, json.dumps(s[m]["console"]))
    if not a.build_only:
        progress(len(todo), state='completed')


if __name__ == "__main__":
    # Detached Windows processes otherwise inherit cp1252 for redirected logs,
    # which can abort a successful source when an Arabic warning is printed.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    with collection_lock():
        main()
