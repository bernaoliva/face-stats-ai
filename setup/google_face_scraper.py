"""Download player face photos from Bing Images for all players in local_players.json.

Searches Bing Images with face filter and downloads the first valid result.

Usage:
    python -m setup.google_face_scraper --db local_players.json --output extra_photos/
    python -m setup.google_face_scraper --db local_players.json --output extra_photos/ --limit 50
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def search_bing_face(query: str) -> list[str]:
    """Search Bing Images with face filter, return image URLs."""
    params = urllib.parse.urlencode({
        "q": query,
        "qft": "+filterui:face-face",
        "form": "IRFLTR",
        "first": "1",
    })
    url = f"https://www.bing.com/images/search?{params}"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Search failed: %s", e)
        return []

    # Extract media URLs from Bing HTML
    raw = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', html)
    urls = [urllib.parse.unquote(u) for u in raw]

    # Filter: prefer known sports image hosts, skip tiny thumbnails
    preferred = []
    others = []
    for u in urls:
        lower = u.lower()
        if any(skip in lower for skip in ["logo", "icon", "badge", "escudo", "banner"]):
            continue
        if any(host in lower for host in ["glbimg.com", "lance.com", "uol.com", "espn", "goal.com", "sofascore", "transfermarkt", "oglobo", "gazeta"]):
            preferred.append(u)
        else:
            others.append(u)

    return (preferred + others)[:5]


def _download_image(url: str, path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        if len(data) < 2000:
            return False
        path.write_bytes(data)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download player face photos from Bing Images")
    parser.add_argument("--db", default="local_players.json", help="Player database")
    parser.add_argument("--output", default="extra_photos", help="Output folder")
    parser.add_argument("--limit", type=int, default=0, help="Max players to process (0=all)")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    with open(args.db, encoding="utf-8") as f:
        data = json.load(f)

    players = data["players"]
    total = len(players) if not args.limit else min(args.limit, len(players))

    downloaded = 0
    skipped = 0
    failed = 0

    print(f"Downloading face photos for {total} players via Bing Images\n")

    for i, player in enumerate(players[:total], 1):
        name = player["name"]
        team = player.get("team_name", "")
        pid = player["player_id"]
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', pid)

        # Skip if already has a google/bing photo
        existing = list(output_dir.glob(f"{safe_name}_google*")) + list(output_dir.glob(f"{safe_name}_bing*"))
        if existing:
            skipped += 1
            continue

        query = f"{name} {team} jogador futebol"
        image_urls = search_bing_face(query)

        success = False
        for img_url in image_urls[:3]:
            ext = ".jpg"
            for e in [".png", ".webp"]:
                if e in img_url.lower():
                    ext = e
                    break

            path = output_dir / f"{safe_name}_bing{ext}"
            if _download_image(img_url, path):
                downloaded += 1
                success = True
                break
            time.sleep(0.3)

        if not success:
            failed += 1

        # Progress
        if i % 50 == 0 or i == total:
            print(f"  [{i}/{total}] downloaded={downloaded} skipped={skipped} failed={failed}")

        time.sleep(args.delay)

    print(f"\n{'='*40}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (existing): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total photos in {args.output}/: {len(list(output_dir.iterdir()))}")


if __name__ == "__main__":
    main()
