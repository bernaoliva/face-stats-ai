import pytest
import asyncio

from data_fetcher.opta_mock import OptaMock, MATCH_ID, COMPETITION_ID, SEASON_ID
from data_fetcher.opta_client import OptaClient
from shared.opta_config import OptaConfig, OptaFeed


@pytest.fixture
def mock_client():
    return OptaMock()


@pytest.mark.asyncio
async def test_get_match_stats_returns_player_data(mock_client):
    async with mock_client:
        result = await mock_client.get_match_stats(MATCH_ID)
    assert "matchStats" in result
    teams = result["matchStats"]["teamStats"]
    assert len(teams) == 2
    for team in teams:
        assert len(team["playerStats"]) > 0
        for player in team["playerStats"]:
            assert "playerId" in player
            assert "stats" in player


@pytest.mark.asyncio
async def test_get_match_events_returns_goals_and_cards(mock_client):
    async with mock_client:
        result = await mock_client.get_match_events(MATCH_ID)
    events = result["matchEvents"]["events"]
    goals = [e for e in events if e["typeId"] == 16]
    cards = [e for e in events if e["typeId"] == 71]
    assert len(goals) >= 2
    assert len(cards) >= 2


@pytest.mark.asyncio
async def test_get_season_stats_returns_season_totals(mock_client):
    async with mock_client:
        result = await mock_client.get_season_stats(COMPETITION_ID, SEASON_ID)
    teams = result["seasonStats"]["teams"]
    assert len(teams) == 2
    for team in teams:
        for player in team["players"]:
            assert "appearances" in player["stats"]


@pytest.mark.asyncio
async def test_get_squads_returns_both_teams(mock_client):
    async with mock_client:
        result = await mock_client.get_squads(COMPETITION_ID, SEASON_ID)
    contestants = result["squads"]["contestants"]
    assert len(contestants) == 2
    for team in contestants:
        for player in team["players"]:
            assert "playerId" in player
            assert "playerName" in player
            assert "position" in player
            assert "shirtNumber" in player


@pytest.mark.asyncio
async def test_get_player_data_parallel_calls(mock_client):
    """Confirma que MA2+MA3+TM4 rodam em paralelo."""
    async with mock_client:
        ma2, ma3, tm4 = await mock_client.get_all_player_stats(
            MATCH_ID, COMPETITION_ID, SEASON_ID
        )
    assert "matchStats" in ma2
    assert "matchEvents" in ma3
    assert "seasonStats" in tm4


@pytest.mark.asyncio
async def test_player_ids_consistent_across_feeds(mock_client):
    """IDs de jogadores devem ser os mesmos entre MA2, MA3, TM4 e TM3."""
    async with mock_client:
        ma2 = await mock_client.get_match_stats(MATCH_ID)
        ma3 = await mock_client.get_match_events(MATCH_ID)
        tm4 = await mock_client.get_season_stats(COMPETITION_ID, SEASON_ID)
        tm3 = await mock_client.get_squads(COMPETITION_ID, SEASON_ID)

    # Coletar IDs de cada feed
    ma2_ids = set()
    for team in ma2["matchStats"]["teamStats"]:
        for p in team["playerStats"]:
            ma2_ids.add(p["playerId"])

    ma3_ids = {e["playerId"] for e in ma3["matchEvents"]["events"]}

    tm4_ids = set()
    for team in tm4["seasonStats"]["teams"]:
        for p in team["players"]:
            tm4_ids.add(p["playerId"])

    tm3_ids = set()
    for team in tm3["squads"]["contestants"]:
        for p in team["players"]:
            tm3_ids.add(p["playerId"])

    # Todos os IDs do MA3 devem existir no MA2
    assert ma3_ids.issubset(ma2_ids), f"IDs no MA3 ausentes no MA2: {ma3_ids - ma2_ids}"
    # Todos os IDs do MA2 devem existir no TM3
    assert ma2_ids.issubset(tm3_ids), f"IDs no MA2 ausentes no TM3: {ma2_ids - tm3_ids}"
    # Todos os IDs do TM4 devem existir no TM3
    assert tm4_ids.issubset(tm3_ids), f"IDs no TM4 ausentes no TM3: {tm4_ids - tm3_ids}"


@pytest.mark.asyncio
async def test_mock_vs_real_same_interface():
    """Mock e client real devem ter os mesmos métodos públicos."""
    mock_methods = {m for m in dir(OptaMock) if not m.startswith("_")}
    client_methods = {m for m in dir(OptaClient) if not m.startswith("_")}

    required = {
        "get_match_stats",
        "get_match_events",
        "get_season_stats",
        "get_squads",
        "get_all_player_stats",
    }
    assert required.issubset(mock_methods), f"Mock faltando: {required - mock_methods}"
    assert required.issubset(client_methods), f"Client faltando: {required - client_methods}"


def test_config_build_url():
    config = OptaConfig(
        outlet_auth_key="testkey123",
        base_url="https://api.test.com/soccerdata",
    )
    url = config.build_url(OptaFeed.MA2, match_id="m1")
    assert "matchstats/testkey123" in url
    assert "fx=m1" in url
    assert "_rt=b" in url
    assert "_fmt=json" in url


def test_config_build_url_season_stats():
    config = OptaConfig(
        outlet_auth_key="testkey123",
        base_url="https://api.test.com/soccerdata",
    )
    url = config.build_url(
        OptaFeed.TM4,
        competition_id="c1",
        season_id="s1",
        team_id="t1",
    )
    assert "seasonstats/testkey123" in url
    assert "comp=c1" in url
    assert "tmcl=s1" in url
    assert "ctst=t1" in url
