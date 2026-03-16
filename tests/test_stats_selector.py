import pytest

from shared.models import PlayerInfo, StatItem
from data_fetcher.stats_selector import StatsSelector


@pytest.fixture
def selector():
    return StatsSelector.__new__(StatsSelector)


@pytest.fixture
def forward_player():
    return PlayerInfo(
        player_id="p1", name="Test Forward", team_id="t1",
        team_name="Team A", position="Forward", shirt_number=9,
    )


@pytest.fixture
def goalkeeper_player():
    return PlayerInfo(
        player_id="p2", name="Test GK", team_id="t1",
        team_name="Team A", position="Goalkeeper", shirt_number=1,
    )


class TestFallbackSelect:
    def test_forward_with_stats(self, selector, forward_player):
        raw_stats = {
            "goals_in_match": 2,
            "season_goals": 15,
            "assists_in_match": 1,
            "season_assists": 8,
            "shots_on_target": 3,
            "passes_accurate": 42,
        }
        result = selector._fallback_select(raw_stats, forward_player)
        assert len(result) == 5
        assert all(isinstance(s, StatItem) for s in result)
        # Should prioritize match goals for a forward
        assert result[0].label == "Gols no jogo"
        assert result[0].value == "2"

    def test_goalkeeper_with_stats(self, selector, goalkeeper_player):
        raw_stats = {
            "saves": 5,
            "season_saves": 48,
            "clean_sheets": 1,
            "goals_conceded": 1,
        }
        result = selector._fallback_select(raw_stats, goalkeeper_player)
        assert len(result) == 5
        assert result[0].label == "Defesas"

    def test_empty_stats_pads_to_5(self, selector, forward_player):
        result = selector._fallback_select({}, forward_player)
        assert len(result) == 5
        assert all(s.label == "-" for s in result)

    def test_fewer_than_5_available_pads(self, selector, forward_player):
        raw_stats = {"goals_in_match": 1, "season_goals": 10}
        result = selector._fallback_select(raw_stats, forward_player)
        assert len(result) == 5


class TestExtractPlayerStats:
    def test_extracts_from_ma2(self, selector):
        ma2 = {
            "matchStats": {
                "teamStats": [
                    {
                        "playerStats": [
                            {"playerId": "p1", "stats": {"passes": 50, "tackles": 3}},
                        ],
                    },
                ],
            },
        }
        result = selector._extract_player_stats_from_opta("p1", ma2, {}, {})
        assert result["passes"] == 50
        assert result["tackles"] == 3

    def test_extracts_goals_from_ma3(self, selector):
        ma3 = {
            "matchEvents": {
                "events": [
                    {"playerId": "p1", "typeId": 16},
                    {"playerId": "p1", "typeId": 16},
                    {"playerId": "p1", "typeId": 17},
                    {"playerId": "p2", "typeId": 16},
                ],
            },
        }
        result = selector._extract_player_stats_from_opta("p1", {}, ma3, {})
        assert result["goals_in_match"] == 2
        assert result["assists_in_match"] == 1

    def test_extracts_season_from_tm4(self, selector):
        tm4 = {
            "seasonStats": {
                "teams": [
                    {
                        "players": [
                            {"playerId": "p1", "stats": {"goals": 12, "assists": 5}},
                        ],
                    },
                ],
            },
        }
        result = selector._extract_player_stats_from_opta("p1", {}, {}, tm4)
        assert result["season_goals"] == 12
        assert result["season_assists"] == 5

    def test_player_not_found(self, selector):
        result = selector._extract_player_stats_from_opta("unknown", {}, {}, {})
        assert result == {}
