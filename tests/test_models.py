import pytest
from pydantic import ValidationError

from shared.models import (
    PlayerInfo,
    RecognitionRequest,
    RecognitionResponse,
    StatItem,
    StatsRequest,
    StatsResponse,
    PlayerEmbedding,
)


class TestPlayerInfo:
    def test_minimal(self):
        p = PlayerInfo(player_id="p1", name="Test", team_id="t1")
        assert p.player_id == "p1"
        assert p.position == ""
        assert p.shirt_number is None

    def test_full(self):
        p = PlayerInfo(
            player_id="p1", name="Test", team_id="t1",
            team_name="Team A", position="Forward", shirt_number=9,
        )
        assert p.shirt_number == 9


class TestRecognitionRequest:
    def test_valid(self):
        r = RecognitionRequest(face_image_base64="abc123", match_id="m1")
        assert r.match_id == "m1"


class TestRecognitionResponse:
    def test_not_recognized(self):
        r = RecognitionResponse()
        assert r.recognized is False
        assert r.player is None

    def test_recognized(self):
        p = PlayerInfo(player_id="p1", name="Test", team_id="t1")
        r = RecognitionResponse(player=p, similarity=0.85, recognized=True)
        assert r.recognized is True
        assert r.similarity == 0.85


class TestStatsResponse:
    def test_exactly_5_stats(self):
        stats = [StatItem(label=f"L{i}", value=f"V{i}") for i in range(5)]
        r = StatsResponse(player_name="Test", stats=stats, timestamp="2024-01-01T00:00:00Z")
        assert len(r.stats) == 5

    def test_less_than_5_stats_fails(self):
        stats = [StatItem(label="L", value="V")] * 4
        with pytest.raises(ValidationError):
            StatsResponse(player_name="Test", stats=stats, timestamp="t")

    def test_more_than_5_stats_fails(self):
        stats = [StatItem(label="L", value="V")] * 6
        with pytest.raises(ValidationError):
            StatsResponse(player_name="Test", stats=stats, timestamp="t")


class TestPlayerEmbedding:
    def test_valid_512_dim(self):
        e = PlayerEmbedding(
            player_id="p1", name="Test", team_id="t1",
            embedding=[0.1] * 512,
        )
        assert len(e.embedding) == 512

    def test_wrong_dim_fails(self):
        with pytest.raises(ValidationError):
            PlayerEmbedding(
                player_id="p1", name="Test", team_id="t1",
                embedding=[0.1] * 256,
            )
