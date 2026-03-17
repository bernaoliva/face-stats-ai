"""Scrape player headshot photos from official Brasileirao team websites.

Downloads photos to extra_photos/ folder, named by player name, ready
for enrich_db.py to match against local_players.json.

Usage:
    python -m setup.scrape_team_photos [--output extra_photos/]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _fetch(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def _download_image(url: str, path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        if len(data) < 1000:  # too small, probably error page
            return False
        path.write_bytes(data)
        return True
    except Exception as e:
        logger.warning("Failed to download %s: %s", url, e)
        return False


# ============================================================
# Team-specific scrapers
# ============================================================

def scrape_flamengo() -> list[dict]:
    """Flamengo: images.flamengo.com.br pattern."""
    html = _fetch("https://www.flamengo.com.br/elencos/elenco-profissional")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    players = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "images.flamengo.com.br/public/images/players" in src:
            # Player name from alt or nearest text
            name = img.get("alt", "").strip()
            if not name:
                parent = img.find_parent("a") or img.find_parent("div")
                if parent:
                    name = parent.get_text(strip=True)
            if name and len(name) > 1:
                players.append({"name": name, "photo_url": src, "team": "Flamengo"})
    return players


def scrape_fluminense() -> list[dict]:
    """Fluminense: s3.amazonaws.com/assets-fluminense pattern."""
    html = _fetch("https://www.fluminense.com.br/elenco")
    if not html:
        # Try alternate URL
        html = _fetch("https://www.fluminense.com.br/site/elenco")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    players = []
    for link in soup.find_all("a", href=re.compile(r"/jogador/")):
        name = link.get_text(strip=True)
        href = link.get("href", "")
        if name and len(name) > 1:
            # Fetch individual player page for photo
            player_url = "https://www.fluminense.com.br" + href if href.startswith("/") else href
            player_html = _fetch(player_url)
            if player_html:
                psoup = BeautifulSoup(player_html, "html.parser")
                for img in psoup.find_all("img"):
                    src = img.get("src", "")
                    if "player_pictures" in src or "SANTINHO" in src.upper():
                        players.append({"name": name, "photo_url": src, "team": "Fluminense"})
                        break
            time.sleep(0.3)
    return players


def scrape_saopaulo() -> list[dict]:
    """São Paulo: cdn.saopaulofc.net pattern."""
    html = _fetch("https://www.saopaulofc.net/esporte/futebol-masculino-profissional/")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    players = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "cdn.saopaulofc.net" in src and "/2026/" in src:
            name = img.get("alt", "").strip()
            if not name:
                parent = img.find_parent("div")
                if parent:
                    text_el = parent.find(["h3", "h4", "span", "p"])
                    if text_el:
                        name = text_el.get_text(strip=True)
            if name and len(name) > 1:
                players.append({"name": name, "photo_url": src, "team": "São Paulo"})
    return players


def scrape_palmeiras() -> list[dict]:
    """Palmeiras."""
    for url in [
        "https://www.palmeiras.com.br/elenco",
        "https://www.palmeiras.com.br/elenco/time-profissional",
        "https://www.palmeiras.com.br/futebol/elenco",
    ]:
        html = _fetch(url)
        if html and "player" in html.lower():
            soup = BeautifulSoup(html, "html.parser")
            players = []
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "palmeiras" in src.lower() and ("player" in src.lower() or "elenco" in src.lower() or "jogador" in src.lower()):
                    name = img.get("alt", "").strip()
                    if name and len(name) > 1:
                        players.append({"name": name, "photo_url": src, "team": "Palmeiras"})
            if players:
                return players
    return []


def scrape_generic(team_name: str, base_url: str, squad_paths: list[str]) -> list[dict]:
    """Generic scraper: tries multiple squad paths and extracts player images."""
    for path in squad_paths:
        url = base_url.rstrip("/") + path
        html = _fetch(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        players = []

        # Look for player images (usually in cards/divs with player name)
        for img in soup.find_all("img"):
            src = img.get("src", "") or ""
            alt = img.get("alt", "") or ""

            # Skip logos, sponsors, icons
            if any(skip in src.lower() for skip in ["logo", "sponsor", "icon", "badge", "banner", "escudo"]):
                continue
            if not src.startswith("http"):
                continue
            # Must look like a player photo (PNG/JPG, reasonable size pattern)
            if not any(ext in src.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                continue

            name = alt.strip()
            if not name or len(name) < 2:
                # Try to find name from parent element
                parent = img.find_parent(["a", "div", "li", "article"])
                if parent:
                    for el in parent.find_all(["h2", "h3", "h4", "span", "p", "strong"]):
                        text = el.get_text(strip=True)
                        if text and 2 < len(text) < 40 and not any(c.isdigit() for c in text[:3]):
                            name = text
                            break

            if name and len(name) > 1:
                players.append({"name": name, "photo_url": src, "team": team_name})

        if players:
            return players

    return []


# ============================================================
# Team registry
# ============================================================

TEAMS = [
    ("Flamengo", scrape_flamengo),
    ("Fluminense", scrape_fluminense),
    ("São Paulo", scrape_saopaulo),
    ("Palmeiras", scrape_palmeiras),
    ("Botafogo", lambda: scrape_generic("Botafogo", "https://www.botafogo.com.br", ["/elenco/futebol", "/elenco"])),
    ("Corinthians", lambda: scrape_generic("Corinthians", "https://www.corinthians.com.br", ["/futebol/profissional/elenco", "/elenco"])),
    ("Internacional", lambda: scrape_generic("Internacional", "https://www.internacional.com.br", ["/elenco", "/futebol/elenco-profissional"])),
    ("Grêmio", lambda: scrape_generic("Grêmio", "https://gremio.net", ["/futebol/profissional/elenco", "/elenco"])),
    ("Cruzeiro", lambda: scrape_generic("Cruzeiro", "https://www.cruzeiro.com.br", ["/elenco", "/futebol/elenco"])),
    ("Bahia", lambda: scrape_generic("Bahia", "https://www.ecbahia.com", ["/elenco", "/futebol/elenco-profissional"])),
    ("Vasco", lambda: scrape_generic("Vasco", "https://www.vascodagama.com.br", ["/elenco", "/futebol/profissional/elenco"])),
    ("Fortaleza", lambda: scrape_generic("Fortaleza", "https://www.fortalezaec.net", ["/elenco", "/futebol/elenco"])),
    ("Bragantino", lambda: scrape_generic("Bragantino", "https://www.rbbragantino.com.br", ["/elenco", "/futebol/elenco"])),
    ("Mirassol", lambda: scrape_generic("Mirassol", "https://www.mirassolfc.com.br", ["/elenco", "/futebol/elenco"])),
    ("Athletico-PR", lambda: scrape_generic("Athletico-PR", "https://www.athletico.com.br", ["/elenco", "/futebol/elenco-profissional"])),
    ("Coritiba", lambda: scrape_generic("Coritiba", "https://www.coritiba.com.br", ["/elenco", "/futebol/elenco"])),
    ("Chapecoense", lambda: scrape_generic("Chapecoense", "https://chapecoense.com", ["/elenco", "/futebol/elenco"])),
    ("Remo", lambda: scrape_generic("Remo", "https://www.clubedoremo.com.br", ["/elenco", "/futebol/elenco"])),
    ("Atlético-MG", lambda: scrape_generic("Atlético-MG", "https://www.atletico.com.br", ["/elenco", "/futebol/elenco"])),
    ("Juventude", lambda: scrape_generic("Juventude", "https://www.juventude.com.br", ["/elenco", "/futebol/elenco"])),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape player photos from official team websites")
    parser.add_argument("--output", default="extra_photos", help="Output folder for downloaded photos")
    parser.add_argument("--dry-run", action="store_true", help="Only list players, don't download")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    all_players = []
    for team_name, scraper_fn in TEAMS:
        logger.info("Scraping %s...", team_name)
        try:
            players = scraper_fn()
        except Exception as e:
            logger.warning("Error scraping %s: %s", team_name, e)
            players = []

        logger.info("  Found %d players for %s", len(players), team_name)
        all_players.extend(players)
        time.sleep(0.5)

    logger.info("\nTotal: %d players from %d teams", len(all_players), len({p["team"] for p in all_players}))

    if args.dry_run:
        for p in all_players:
            print(f"  {p['team']:>15} | {p['name']:<25} | {p['photo_url'][:80]}")
        return

    # Download photos
    downloaded = 0
    for p in all_players:
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', p["name"])
        ext = ".png" if ".png" in p["photo_url"].lower() else ".jpg"
        photo_path = output_dir / f"{safe_name}{ext}"

        if photo_path.exists():
            logger.debug("Already exists: %s", photo_path)
            continue

        if _download_image(p["photo_url"], photo_path):
            downloaded += 1
            logger.info("  Downloaded: %s (%s)", p["name"], p["team"])
        time.sleep(0.2)

    logger.info("\nDone. Downloaded %d photos to %s/", downloaded, output_dir)

    # Save manifest
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)
    logger.info("Manifest saved to %s", manifest_path)


if __name__ == "__main__":
    main()
