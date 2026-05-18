"""
Prewarm the image cache for every catalog item missing an image.

Walks the in-memory catalog, calls ``tools.image_resolver.resolve_image()``
for each item without ``image_urls``, and writes results to
``data/image_cache.json``. After this finishes the home/search/detail
endpoints serve images instantly with no network calls.

Resolver chain (defined in ``tools/image_resolver.py``):
    Wikipedia summary  →  Wikipedia search  →  Wikimedia Commons  →  Picsum

Run from the ``backend`` dir:
    python -m scripts.backfill_images               # all missing items
    python -m scripts.backfill_images --limit 100   # smoke test
    python -m scripts.backfill_images --refresh     # re-resolve everything
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import catalog  # noqa: E402
from tools import image_resolver  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")

_lock = threading.Lock()


def resolve_one(it: catalog.CatalogItem) -> str:
    try:
        return image_resolver.resolve_image(category=it.type, name=it.name, city=it.city)
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve failed for %s/%s: %s", it.type, it.name, exc)
        return ""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="stop after N items (0 = all)")
    p.add_argument("--refresh", action="store_true", help="ignore cache, re-resolve all")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    if args.refresh and image_resolver.CACHE_FILE.exists():
        image_resolver.CACHE_FILE.unlink()

    items = catalog.load_catalog()
    pending = [it for it in items if not it.image_urls]
    if args.limit:
        pending = pending[: args.limit]
    log.info("backfilling %d items (workers=%d)", len(pending), args.workers)

    done = 0
    total = len(pending)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(resolve_one, it): it for it in pending}
        for f in as_completed(futures):
            done += 1
            if done % 100 == 0 or done == total:
                log.info("  %d / %d resolved", done, total)

    log.info("done — cache file: %s", image_resolver.CACHE_FILE)


if __name__ == "__main__":
    main()
