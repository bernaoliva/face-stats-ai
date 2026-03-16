"""Batch upload player face embeddings from a directory of photos."""
from __future__ import annotations

import argparse
import logging
import os

import cv2
import numpy as np
from tqdm import tqdm

from shared.gcp_utils import get_firestore_client
from recognition.face_embedder import FaceEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_embeddings(match_id: str, photos_dir: str) -> None:
    embedder = FaceEmbedder(use_gpu=False)
    db = get_firestore_client()
    players_ref = db.collection("matches").document(match_id).collection("players")

    # Discover player photos: either {player_id}.jpg or {player_id}/ directory
    entries = sorted(os.listdir(photos_dir))
    player_photos: dict[str, list[str]] = {}

    for entry in entries:
        full_path = os.path.join(photos_dir, entry)
        if os.path.isdir(full_path):
            # Directory of multiple photos for one player
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

    logger.info("Found %d players in %s", len(player_photos), photos_dir)

    batch = db.batch()
    batch_count = 0

    for player_id, photos in tqdm(player_photos.items(), desc="Processing players"):
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

        doc_ref = players_ref.document(player_id)
        batch.update(doc_ref, {"embedding": avg_embedding.tolist()})
        batch_count += 1

        # Firestore batch limit is 500
        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()

    logger.info("Uploaded embeddings for %d players", len(player_photos))


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch upload player face embeddings")
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--photos-dir", required=True, help="Directory with player photos")
    args = parser.parse_args()

    upload_embeddings(args.match_id, args.photos_dir)


if __name__ == "__main__":
    main()
