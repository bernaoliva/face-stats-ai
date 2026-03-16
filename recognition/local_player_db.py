from __future__ import annotations

import json
import logging

import numpy as np

from shared.models import PlayerInfo

logger = logging.getLogger(__name__)


class LocalPlayerDB:
    """Player database backed by a local JSON file (no Firestore needed)."""

    def __init__(self, db_path: str) -> None:
        self._players: dict[str, PlayerInfo] = {}
        self._player_ids: list[str] = []
        self._embedding_matrix: np.ndarray = np.empty((0, 512), dtype=np.float32)
        self._load(db_path)

    def _load(self, db_path: str) -> None:
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)

        players: dict[str, PlayerInfo] = {}
        ids: list[str] = []
        embeddings: list[list[float]] = []

        for entry in data.get("players", []):
            player_id = entry.get("player_id", "")
            embedding = entry.get("embedding")
            if not embedding or len(embedding) != 512:
                logger.warning("Skipping player %s: invalid embedding", player_id)
                continue

            players[player_id] = PlayerInfo(
                player_id=player_id,
                name=entry.get("name", ""),
                team_id=entry.get("team_id", ""),
                team_name=entry.get("team_name", ""),
                position=entry.get("position", ""),
                shirt_number=entry.get("shirt_number"),
            )
            ids.append(player_id)
            embeddings.append(embedding)

        self._players = players
        self._player_ids = ids
        if embeddings:
            self._embedding_matrix = np.array(embeddings, dtype=np.float32)
            norms = np.linalg.norm(self._embedding_matrix, axis=1, keepdims=True)
            norms = np.where(norms > 0, norms, 1.0)
            self._embedding_matrix = self._embedding_matrix / norms
        else:
            self._embedding_matrix = np.empty((0, 512), dtype=np.float32)

        logger.info("Loaded %d players from %s", len(ids), db_path)

    @property
    def player_count(self) -> int:
        return len(self._player_ids)

    def get_all_embeddings(self) -> tuple[list[str], np.ndarray]:
        return self._player_ids, self._embedding_matrix

    def get_player_info(self, player_id: str) -> PlayerInfo | None:
        return self._players.get(player_id)
