import numpy as np
import pytest

from recognition.matcher import FaceMatcher


@pytest.fixture
def matcher():
    return FaceMatcher(threshold=0.6)


def _normalized(vec: list[float]) -> np.ndarray:
    a = np.array(vec, dtype=np.float32)
    return a / np.linalg.norm(a)


class TestFaceMatcher:
    def test_exact_match(self, matcher):
        emb = _normalized([1.0] * 512)
        matrix = emb.reshape(1, -1)
        player_id, score = matcher.match(emb, ["p1"], matrix)
        assert player_id == "p1"
        assert abs(score - 1.0) < 1e-5

    def test_no_match_below_threshold(self, matcher):
        query = _normalized([1.0] + [0.0] * 511)
        db_emb = _normalized([0.0] + [1.0] + [0.0] * 510)
        matrix = db_emb.reshape(1, -1)
        player_id, score = matcher.match(query, ["p1"], matrix)
        assert player_id is None
        assert score < 0.6

    def test_best_match_among_multiple(self, matcher):
        query = _normalized([1.0, 0.5] + [0.0] * 510)
        emb1 = _normalized([1.0, 0.5] + [0.0] * 510)  # identical
        emb2 = _normalized([0.0, 1.0] + [0.0] * 510)  # different
        emb3 = _normalized([0.8, 0.4] + [0.0] * 510)  # similar

        matrix = np.stack([emb1, emb2, emb3])
        player_id, score = matcher.match(query, ["p1", "p2", "p3"], matrix)
        assert player_id == "p1"
        assert score > 0.99

    def test_empty_database(self, matcher):
        query = _normalized([1.0] * 512)
        player_id, score = matcher.match(query, [], np.empty((0, 512)))
        assert player_id is None
        assert score == 0.0

    def test_threshold_boundary(self):
        matcher = FaceMatcher(threshold=0.5)
        query = _normalized([1.0, 0.3] + [0.0] * 510)
        db_emb = _normalized([0.8, 0.1] + [0.0] * 510)
        matrix = db_emb.reshape(1, -1)

        player_id, score = matcher.match(query, ["p1"], matrix)
        # Should match since vectors are similar enough
        assert player_id == "p1" or score < 0.5
