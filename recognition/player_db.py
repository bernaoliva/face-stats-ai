from __future__ import annotations

import logging

import numpy as np

from shared.gcp_utils import get_firestore_client
from shared.models import PlayerInfo

logger = logging.getLogger(__name__)


class PlayerDB:
    def __init__(self, match_id: str) -> None:
        self._db = get_firestore_client()
        self._match_id = match_id
        self._players: dict[str, PlayerInfo] = {}
        self._player_ids: list[str] = []
        self._embedding_matrix: np.ndarray = np.empty((0, 512), dtype=np.float32)
        self._load(match_id)

    def _load(self, match_id: str) -> None:
        collection = self._db.collection("matches").document(match_id).collection("players")
        docs = collection.stream()

        players: dict[str, PlayerInfo] = {}
        ids: list[str] = []
        embeddings: list[list[float]] = []

        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue

            player_id = data.get("player_id", doc.id)
            embedding = data.get("embedding")
            if not embedding or len(embedding) != 512:
                logger.warning("Skipping player %s: invalid embedding", player_id)
                continue

            players[player_id] = PlayerInfo(
                player_id=player_id,
                name=data.get("name", ""),
                team_id=data.get("team_id", ""),
                team_name=data.get("team_name", ""),
                position=data.get("position", ""),
                shirt_number=data.get("shirt_number"),
            )
            ids.append(player_id)
            embeddings.append(embedding)

        self._players = players
        self._player_ids = ids
        if embeddings:
            self._embedding_matrix = np.array(embeddings, dtype=np.float32)
            # Ensure rows are L2-normalized
            norms = np.linalg.norm(self._embedding_matrix, axis=1, keepdims=True)
            norms = np.where(norms > 0, norms, 1.0)
            self._embedding_matrix = self._embedding_matrix / norms
        else:
            self._embedding_matrix = np.empty((0, 512), dtype=np.float32)

        logger.info("Loaded %d players for match %s", len(ids), match_id)

    def get_all_embeddings(self) -> tuple[list[str], np.ndarray]:
        return self._player_ids, self._embedding_matrix

    def get_player_info(self, player_id: str) -> PlayerInfo | None:
        return self._players.get(player_id)

    @property
    def player_count(self) -> int:
        return len(self._player_ids)

    @property
    def match_id(self) -> str:
        return self._match_id

    def reload(self, match_id: str) -> None:
        self._match_id = match_id
        self._load(match_id)
