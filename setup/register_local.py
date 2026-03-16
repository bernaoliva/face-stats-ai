"""Generate a local JSON player database from photos and metadata."""
from __future__ import annotations

import argparse
import json
import logging
import os

import cv2
import numpy as np
from tqdm import tqdm

from recognition.face_embedder import FaceEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def discover_photos(photos_dir: str) -> dict[str, list[str]]:
    """Discover player photos: either {player_id}.jpg or {player_id}/ directory."""
    entries = sorted(os.listdir(photos_dir))
    player_photos: dict[str, list[str]] = {}

    for entry in entries:
        full_path = os.path.join(photos_dir, entry)
        if os.path.isdir(full_path):
            player_id = entry
            photos = [
                os.path.join(full_path, f)
                for f in os.listdir(full_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if photos:
                player_photos[player_id] = photos
        elif entry.lower().endswith((".jpg", ".jpeg", ".png")):
            player_id = os.path.splitext(entry)[0]
            player_photos.setdefault(player_id, []).append(full_path)

    return player_photos


def register_local(photos_dir: str, meta_path: str, output_path: str) -> None:
    embedder = FaceEmbedder(use_gpu=False)

    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    player_photos = discover_photos(photos_dir)
    logger.info("Found %d players in %s", len(player_photos), photos_dir)

    players_out: list[dict] = []

    for player_id, photos in tqdm(player_photos.items(), desc="Processing players"):
        if player_id not in metadata:
            logger.warning("No metadata for player %s, skipping", player_id)
            continue

        embeddings: list[np.ndarray] = []
        for photo_path in photos:
            image = cv2.imread(photo_path)
            if image is None:
                logger.warning("Could not read: %s", photo_path)
                continue

            emb = embedder.get_embedding(image)
            if emb is not None:
                embeddings.append(emb)
            else:
                logger.warning("No face detected: %s", photo_path)

        if not embeddings:
            logger.warning("No valid embeddings for player %s", player_id)
            continue

        # Average embeddings + re-normalize
        avg_embedding = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm

        meta = metadata[player_id]
        players_out.append({
            "player_id": player_id,
            "name": meta.get("name", ""),
            "team_id": meta.get("team_id", ""),
            "team_name": meta.get("team_name", ""),
            "position": meta.get("position", ""),
            "shirt_number": meta.get("shirt_number"),
            "embedding": avg_embedding.tolist(),
        })

    output = {"players": players_out}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("Saved %d players to %s", len(players_out), output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate local JSON player database from photos"
    )
    parser.add_argument(
        "--photos-dir", required=True, help="Directory with player photos"
    )
    parser.add_argument(
        "--meta", required=True, help="Path to players_meta.json"
    )
    parser.add_argument(
        "--output", default="local_players.json", help="Output JSON path"
    )
    args = parser.parse_args()

    register_local(args.photos_dir, args.meta, args.output)


if __name__ == "__main__":
    main()
