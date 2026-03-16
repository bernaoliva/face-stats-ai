"""Enrich local_players.json with additional photos.

Scans a folder for extra photos, matches them to existing players by filename,
and re-averages the stored embeddings to improve recognition accuracy.

Filename matching rules (order tried):
  1. Exact: "PH Ganso.jpg" → player_id "PH Ganso"
  2. Underscore-to-space: "PH_Ganso.jpg" → "PH Ganso"
  3. Accent-insensitive: "Ignacio.jpg" → "Ignácio"
  4. Prefix match + suffix strip: "Cano_jogo.jpg" → "Cano"

Usage:
  python -m setup.enrich_db --extra extra_photos/ --db local_players.json

Put photos in extra_photos/ named after the player:
  extra_photos/Cano_jogo.jpg       → updates "Cano"
  extra_photos/PH_Ganso.jpg        → updates "PH Ganso"
  extra_photos/Ignacio_perfil.jpg  → updates "Ignácio"
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


def _build_lookup(players: list[dict]) -> dict[str, int]:
    """Map normalized player_id → index in players list."""
    return {_normalize(p["player_id"]): i for i, p in enumerate(players)}


def _match_player(stem: str, lookup: dict[str, int]) -> str | None:
    """Find best player_id match for a photo filename stem."""
    # Strip common suffixes like _jogo, _2, _perfil, _match, etc.
    def _candidates(s: str):
        yield s
        # strip trailing _word or _number
        parts = s.rsplit("_", 1)
        if len(parts) == 2:
            yield parts[0]
        parts = s.rsplit(" ", 1)
        if len(parts) == 2:
            yield parts[0]

    norm_stem = _normalize(stem)
    for candidate in _candidates(norm_stem):
        if candidate in lookup:
            return candidate
    return None


def discover_extra_photos(extra_dir: Path) -> dict[str, list[Path]]:
    """Map normalized_player_id → list of photo paths."""
    groups: dict[str, list[Path]] = {}
    for f in sorted(extra_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            key = _normalize(f.stem)
            groups.setdefault(key, []).append(f)
        elif f.is_dir():
            # subdirectory named after player
            key = _normalize(f.name)
            photos = [p for p in sorted(f.iterdir()) if p.suffix.lower() in SUPPORTED_EXTS]
            if photos:
                groups.setdefault(key, []).extend(photos)
    return groups


def enrich_db(extra_dir: str, db_path: str, output_path: str) -> None:
    with open(db_path, encoding="utf-8") as f:
        data = json.load(f)

    players: list[dict] = data["players"]
    lookup = _build_lookup(players)

    extra_photos = discover_extra_photos(Path(extra_dir))
    logger.info("Found %d photo groups in '%s'", len(extra_photos), extra_dir)

    embedder = FaceEmbedder(use_gpu=False)
    updated = 0
    skipped_no_match = []
    skipped_no_face = []

    for norm_stem, paths in tqdm(extra_photos.items(), desc="Enriching players"):
        # Try to match to a player
        matched_key = _match_player(norm_stem, lookup)
        if matched_key is None:
            skipped_no_match.append(norm_stem)
            continue

        idx = lookup[matched_key]
        player = players[idx]

        new_embeddings: list[np.ndarray] = []
        for photo_path in paths:
            image = cv2.imread(str(photo_path))
            if image is None:
                logger.warning("Could not read: %s", photo_path)
                continue
            emb = embedder.get_embedding(image)
            if emb is not None:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    new_embeddings.append(emb / norm)
            else:
                logger.warning("No face detected in: %s", photo_path)
                skipped_no_face.append(str(photo_path))

        if not new_embeddings:
            continue

        # Re-average: treat existing embedding as 1 sample
        existing = np.array(player["embedding"], dtype=np.float32)
        all_embeddings = [existing] + new_embeddings
        mean_emb = np.mean(all_embeddings, axis=0)
        norm = np.linalg.norm(mean_emb)
        if norm > 0:
            players[idx]["embedding"] = (mean_emb / norm).tolist()

        logger.info(
            "Updated '%s' with %d new photo(s) (total averaged: %d)",
            player["player_id"], len(new_embeddings), len(all_embeddings),
        )
        updated += 1

    data["players"] = players
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("Done. %d players updated. Output: %s", updated, output_path)
    if skipped_no_match:
        logger.warning("No player match found for: %s", ", ".join(skipped_no_match))
    if skipped_no_face:
        logger.warning("No face detected in: %s", ", ".join(skipped_no_face))


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
