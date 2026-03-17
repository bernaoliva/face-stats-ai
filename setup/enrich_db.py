"""Enrich local_players.json with additional photos.

Scans a folder for extra photos, matches them to existing players by filename,
and re-averages the stored embeddings to improve recognition accuracy.

Supported filename formats:
  1. "PlayerName.jpg"                    → match by name only
  2. "PlayerName_TeamName_tm.jpg"        → match by name + team (Transfermarkt)
  3. "PlayerName_jogo.jpg"               → strip suffix, match by name
  4. Accent-insensitive: "Ignacio" → "Ignácio"

Usage:
  python -m setup.enrich_db --extra extra_photos/ --db local_players.json
"""
from __future__ import annotations

import argparse
import json
import logging
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from recognition.face_embedder import FaceEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _normalize(s: str) -> str:
    """Lowercase, remove accents, replace underscores/hyphens with spaces."""
    s = s.replace("_", " ").replace("-", " ")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _build_lookup(players: list[dict]) -> dict[str, list[int]]:
    """Map normalized player_id → list of indices (handles duplicates across teams)."""
    lookup: dict[str, list[int]] = {}
    for i, p in enumerate(players):
        key = _normalize(p["player_id"])
        lookup.setdefault(key, []).append(i)
    return lookup


def _parse_filename(stem: str) -> tuple[str, str | None]:
    """Parse filename into (player_name, team_hint).

    Supports:
      "Cano_Fluminense_tm"  → ("Cano", "Fluminense")
      "Cano_jogo"           → ("Cano", None)
      "PH_Ganso"            → ("PH Ganso", None)
      "Cano"                → ("Cano", None)
    """
    # Transfermarkt format: Name_Team_tm
    if stem.endswith("_tm"):
        stem = stem[:-3]  # remove _tm
        # Last part is team name
        # Find the team by checking known suffixes
        parts = stem.rsplit("_", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return stem, None

    # Regular format: strip known suffixes
    for suffix in ["_jogo", "_perfil", "_match", "_bing", "_google"]:
        if stem.endswith(suffix):
            return stem[: -len(suffix)], None

    return stem, None


def _match_player(
    name: str, team_hint: str | None, lookup: dict[str, list[int]], players: list[dict]
) -> int | None:
    """Find best player index for a photo. Uses team_hint to disambiguate."""
    norm_name = _normalize(name)

    # Try exact match, then strip trailing word
    candidates_names = [norm_name]
    parts = norm_name.rsplit(" ", 1)
    if len(parts) == 2:
        candidates_names.append(parts[0])

    for candidate in candidates_names:
        indices = lookup.get(candidate)
        if not indices:
            continue

        if len(indices) == 1 or team_hint is None:
            return indices[0]

        # Multiple players with same name — use team_hint to pick
        norm_team = _normalize(team_hint)
        for idx in indices:
            player_team = _normalize(players[idx].get("team_name", ""))
            if norm_team in player_team or player_team in norm_team:
                return idx

        # No team match — skip to avoid wrong player
        return None

    return None


def discover_extra_photos(extra_dir: Path) -> list[tuple[Path, str, str | None]]:
    """Return list of (photo_path, player_name, team_hint)."""
    results: list[tuple[Path, str, str | None]] = []
    for f in sorted(extra_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            name, team = _parse_filename(f.stem)
            results.append((f, name, team))
        elif f.is_dir():
            name, team = _parse_filename(f.name)
            for photo in sorted(f.iterdir()):
                if photo.suffix.lower() in SUPPORTED_EXTS:
                    results.append((photo, name, team))
    return results


def enrich_db(extra_dir: str, db_path: str, output_path: str) -> None:
    with open(db_path, encoding="utf-8") as f:
        data = json.load(f)

    players: list[dict] = data["players"]
    lookup = _build_lookup(players)

    photos = discover_extra_photos(Path(extra_dir))
    logger.info("Found %d photos in '%s'", len(photos), extra_dir)

    embedder = FaceEmbedder(use_gpu=False)
    updated_indices: set[int] = set()
    skipped_no_match = []
    skipped_no_face = 0

    # Group photos by matched player index
    player_photos: dict[int, list[Path]] = {}
    for photo_path, name, team_hint in photos:
        idx = _match_player(name, team_hint, lookup, players)
        if idx is None:
            skipped_no_match.append(f"{name} ({team_hint or '?'})")
            continue
        player_photos.setdefault(idx, []).append(photo_path)

    logger.info("Matched photos to %d players", len(player_photos))

    for idx, paths in tqdm(player_photos.items(), desc="Enriching players"):
        player = players[idx]

        new_embeddings: list[np.ndarray] = []
        for photo_path in paths:
            image = cv2.imread(str(photo_path))
            if image is None:
                continue
            emb = embedder.get_embedding(image)
            if emb is not None:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    new_embeddings.append(emb / norm)
            else:
                skipped_no_face += 1

        if not new_embeddings:
            continue

        # Re-average: treat existing embedding as 1 sample
        existing = np.array(player["embedding"], dtype=np.float32)
        all_embeddings = [existing] + new_embeddings
        mean_emb = np.mean(all_embeddings, axis=0)
        norm = np.linalg.norm(mean_emb)
        if norm > 0:
            players[idx]["embedding"] = (mean_emb / norm).tolist()

        updated_indices.add(idx)

    data["players"] = players
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("Done. %d players updated. Output: %s", len(updated_indices), output_path)
    if skipped_no_match:
        unique = sorted(set(skipped_no_match))
        logger.warning("No match for %d photos: %s", len(unique), ", ".join(unique[:20]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich player DB with additional photos (re-averages embeddings)"
    )
    parser.add_argument("--extra", required=True, help="Folder with extra photos")
    parser.add_argument("--db", default="local_players.json", help="Input DB path")
    parser.add_argument("--output", default=None, help="Output path (default: overwrite --db)")
    args = parser.parse_args()

    output = args.output or args.db
    enrich_db(args.extra, args.db, output)


if __name__ == "__main__":
    main()
