from __future__ import annotations

import numpy as np


class FaceMatcher:
    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def match(
        self,
        query_embedding: np.ndarray,
        player_ids: list[str],
        embedding_matrix: np.ndarray,
    ) -> tuple[str | None, float]:
        """Match a query embedding against the player database.

        Args:
            query_embedding: 512-dim L2-normalized vector.
            player_ids: List of player IDs corresponding to matrix rows.
            embedding_matrix: NxD matrix of L2-normalized embeddings.

        Returns:
            (player_id, similarity) if match found, else (None, best_score).
        """
        if len(player_ids) == 0 or embedding_matrix.shape[0] == 0:
            return None, 0.0

        # Dot product = cosine similarity for L2-normalized vectors
        similarities = embedding_matrix @ query_embedding
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= self.threshold:
            return player_ids[best_idx], best_score

        return None, best_score
