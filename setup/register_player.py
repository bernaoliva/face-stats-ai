"""Register a single player face embedding in Firestore."""
from __future__ import annotations

import argparse
import logging

import cv2
import numpy as np

from shared.gcp_utils import get_firestore_client
from recognition.face_embedder import FaceEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_player(match_id: str, player_id: str, photo_path: str) -> None:
    embedder = FaceEmbedder(use_gpu=False)
    image = cv2.imread(photo_path)
    if image is None:
        logger.error("Could not read image: %s", photo_path)
        return

    embedding = embedder.get_embedding(image)
    if embedding is None:
        logger.error("No face detected in: %s", photo_path)
        return

    db = get_firestore_client()
    doc_ref = (
        db.collection("matches")
        .document(match_id)
        .collection("players")
        .document(player_id)
    )

    doc_ref.update({"embedding": embedding.tolist()})
    logger.info("Registered embedding for player %s in match %s", player_id, match_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a player face embedding")
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--player-id", required=True)
    parser.add_argument("--photo", required=True, help="Path to player photo")
    args = parser.parse_args()

    register_player(args.match_id, args.player_id, args.photo)


if __name__ == "__main__":
    main()
