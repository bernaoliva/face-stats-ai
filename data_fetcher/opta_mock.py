"""Mock do OptaClient com dados realistas do Brasileirão (Flamengo x Palmeiras)."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# IDs fictícios mas consistentes entre feeds
MATCH_ID = "mock-fla-pal-2026-01"
COMPETITION_ID = "mock-brasileirao-2026"
SEASON_ID = "mock-brasileirao-2026-season"

# Flamengo
FLA_ID = "fla001"
FLA_PLAYERS = {
    "fla-p01": {"name": "Rossi", "position": "Goalkeeper", "shirtNumber": 1, "nationality": "Argentina", "birthDate": "1995-08-13"},
    "fla-p02": {"name": "Wesley", "position": "Defender", "shirtNumber": 2, "nationality": "Brazil", "birthDate": "2000-03-05"},
    "fla-p03": {"name": "Léo Pereira", "position": "Defender", "shirtNumber": 4, "nationality": "Brazil", "birthDate": "1996-01-13"},
    "fla-p04": {"name": "Ayrton Lucas", "position": "Defender", "shirtNumber": 6, "nationality": "Brazil", "birthDate": "1997-06-19"},
    "fla-p05": {"name": "Pulgar", "position": "Midfielder", "shirtNumber": 5, "nationality": "Chile", "birthDate": "1994-01-15"},
    "fla-p06": {"name": "De la Cruz", "position": "Midfielder", "shirtNumber": 18, "nationality": "Uruguay", "birthDate": "1997-06-09"},
    "fla-p07": {"name": "Gerson", "position": "Midfielder", "shirtNumber": 8, "nationality": "Brazil", "birthDate": "1997-05-20"},
    "fla-p08": {"name": "Arrascaeta", "position": "Midfielder", "shirtNumber": 14, "nationality": "Uruguay", "birthDate": "1994-01-01"},
    "fla-p09": {"name": "Bruno Henrique", "position": "Forward", "shirtNumber": 27, "nationality": "Brazil", "birthDate": "1990-12-30"},
    "fla-p10": {"name": "Pedro", "position": "Forward", "shirtNumber": 9, "nationality": "Brazil", "birthDate": "1997-06-20"},
    "fla-p11": {"name": "Luiz Araújo", "position": "Forward", "shirtNumber": 7, "nationality": "Brazil", "birthDate": "1996-05-14"},
}

# Palmeiras
PAL_ID = "pal001"
PAL_PLAYERS = {
    "pal-p01": {"name": "Weverton", "position": "Goalkeeper", "shirtNumber": 21, "nationality": "Brazil", "birthDate": "1987-12-13"},
    "pal-p02": {"name": "Marcos Rocha", "position": "Defender", "shirtNumber": 2, "nationality": "Brazil", "birthDate": "1988-08-11"},
    "pal-p03": {"name": "Gustavo Gómez", "position": "Defender", "shirtNumber": 15, "nationality": "Paraguay", "birthDate": "1993-05-06"},
    "pal-p04": {"name": "Piquerez", "position": "Defender", "shirtNumber": 22, "nationality": "Uruguay", "birthDate": "1998-06-22"},
    "pal-p05": {"name": "Aníbal Moreno", "position": "Midfielder", "shirtNumber": 5, "nationality": "Argentina", "birthDate": "1999-11-07"},
    "pal-p06": {"name": "Raphael Veiga", "position": "Midfielder", "shirtNumber": 23, "nationality": "Brazil", "birthDate": "1995-06-19"},
    "pal-p07": {"name": "Estêvão", "position": "Forward", "shirtNumber": 41, "nationality": "Brazil", "birthDate": "2007-04-24"},
    "pal-p08": {"name": "Rony", "position": "Forward", "shirtNumber": 10, "nationality": "Brazil", "birthDate": "1995-02-11"},
    "pal-p09": {"name": "Flaco López", "position": "Forward", "shirtNumber": 42, "nationality": "Argentina", "birthDate": "2000-04-02"},
    "pal-p10": {"name": "Zé Rafael", "position": "Midfielder", "shirtNumber": 8, "nationality": "Brazil", "birthDate": "1993-06-01"},
    "pal-p11": {"name": "Richard Ríos", "position": "Midfielder", "shirtNumber": 27, "nationality": "Colombia", "birthDate": "2000-01-02"},
}


def _build_player_match_stats(player_id: str, position: str) -> dict:
    """Gera stats de jogo realistas baseado na posição."""
    import random
    random.seed(hash(player_id))

    base = {
        "playerId": player_id,
        "stats": {
            "minsPlayed": random.randint(60, 90),
            "touches": random.randint(30, 80),
            "passesTotal": random.randint(20, 60),
            "passesAccurate": random.randint(15, 55),
            "foulsCommitted": random.randint(0, 4),
            "foulsSuffered": random.randint(0, 3),
            "duelsWon": random.randint(2, 10),
            "duelsLost": random.randint(1, 8),
            "aerialWon": random.randint(0, 5),
            "aerialLost": random.randint(0, 4),
        },
    }
    stats = base["stats"]

    if "goal" in position.lower():
        stats.update({
            "saves": random.randint(2, 7),
            "punches": random.randint(0, 2),
            "catches": random.randint(1, 4),
            "keeperSweeper": random.randint(0, 3),
            "goalsConceded": random.randint(0, 2),
        })
    elif "forward" in position.lower():
        stats.update({
            "shotsTotal": random.randint(2, 6),
            "shotsOnTarget": random.randint(1, 4),
            "chancesCreated": random.randint(0, 3),
            "offsides": random.randint(0, 3),
            "dribbles": random.randint(1, 5),
        })
    elif "midfielder" in position.lower():
        stats.update({
            "chancesCreated": random.randint(1, 4),
            "crosses": random.randint(0, 5),
            "tacklesWon": random.randint(1, 5),
            "interceptions": random.randint(1, 4),
            "shotsTotal": random.randint(0, 3),
            "shotsOnTarget": random.randint(0, 2),
        })
    else:  # defender
        stats.update({
            "tacklesWon": random.randint(2, 7),
            "interceptions": random.randint(2, 6),
            "clearances": random.randint(2, 8),
            "blockedShots": random.randint(0, 3),
        })

    return base


def _build_player_season_stats(player_id: str, position: str) -> dict:
    """Gera stats de temporada realistas."""
    import random
    random.seed(hash(player_id) + 1)

    stats = {
        "playerId": player_id,
        "stats": {
            "appearances": random.randint(10, 30),
            "minsPlayed": random.randint(800, 2500),
            "yellowCards": random.randint(0, 7),
            "redCards": random.randint(0, 1),
        },
    }
    s = stats["stats"]

    if "forward" in position.lower():
        s.update({
            "goals": random.randint(3, 15),
            "assists": random.randint(1, 8),
            "shotsOnTarget": random.randint(15, 50),
            "shotsTotal": random.randint(30, 80),
        })
    elif "midfielder" in position.lower():
        s.update({
            "goals": random.randint(1, 7),
            "assists": random.randint(3, 12),
            "chancesCreated": random.randint(10, 40),
            "passesAccurate": random.randint(300, 900),
        })
    elif "goal" in position.lower():
        s.update({
            "saves": random.randint(30, 80),
            "cleanSheets": random.randint(3, 12),
            "goalsConceded": random.randint(10, 30),
        })
    else:
        s.update({
            "goals": random.randint(0, 3),
            "tacklesWon": random.randint(20, 60),
            "interceptions": random.randint(15, 50),
            "clearances": random.randint(20, 70),
        })

    return stats


def _build_mock_ma2() -> dict:
    """MA2 — Match Stats (Flamengo 2x1 Palmeiras)."""
    team_stats = []

    for team_id, team_name, players in [
        (FLA_ID, "Flamengo", FLA_PLAYERS),
        (PAL_ID, "Palmeiras", PAL_PLAYERS),
    ]:
        player_stats = [
            _build_player_match_stats(pid, info["position"])
            for pid, info in players.items()
        ]
        team_stats.append({
            "contestantId": team_id,
            "contestantName": team_name,
            "playerStats": player_stats,
        })

    return {"matchStats": {"teamStats": team_stats}}


def _build_mock_ma3() -> dict:
    """MA3 — Match Events (gols, cartões, substituições)."""
    events = [
        # Gol do Pedro (Flamengo) - min 23
        {"eventId": "evt001", "typeId": 16, "playerId": "fla-p10", "contestantId": FLA_ID,
         "timeMin": 23, "timeMinSec": "23:14", "periodId": 1,
         "playerName": "Pedro", "outcome": 1},
        # Assistência do Arrascaeta
        {"eventId": "evt002", "typeId": 17, "playerId": "fla-p08", "contestantId": FLA_ID,
         "timeMin": 23, "timeMinSec": "23:14", "periodId": 1,
         "playerName": "Arrascaeta", "outcome": 1},
        # Cartão amarelo Pulgar - min 35
        {"eventId": "evt003", "typeId": 71, "playerId": "fla-p05", "contestantId": FLA_ID,
         "timeMin": 35, "timeMinSec": "35:02", "periodId": 1,
         "playerName": "Pulgar"},
        # Gol do Flaco López (Palmeiras) - min 52
        {"eventId": "evt004", "typeId": 16, "playerId": "pal-p09", "contestantId": PAL_ID,
         "timeMin": 52, "timeMinSec": "52:31", "periodId": 2,
         "playerName": "Flaco López", "outcome": 1},
        # Cartão amarelo Gustavo Gómez - min 61
        {"eventId": "evt005", "typeId": 71, "playerId": "pal-p03", "contestantId": PAL_ID,
         "timeMin": 61, "timeMinSec": "61:45", "periodId": 2,
         "playerName": "Gustavo Gómez"},
        # Gol do Gerson (Flamengo) - min 78
        {"eventId": "evt006", "typeId": 16, "playerId": "fla-p07", "contestantId": FLA_ID,
         "timeMin": 78, "timeMinSec": "78:20", "periodId": 2,
         "playerName": "Gerson", "outcome": 1},
        # Cartão amarelo Richard Ríos - min 82
        {"eventId": "evt007", "typeId": 71, "playerId": "pal-p11", "contestantId": PAL_ID,
         "timeMin": 82, "timeMinSec": "82:10", "periodId": 2,
         "playerName": "Richard Ríos"},
        # Substituição: Estêvão sai, entra Rony - min 70
        {"eventId": "evt008", "typeId": 18, "playerId": "pal-p07", "contestantId": PAL_ID,
         "timeMin": 70, "timeMinSec": "70:00", "periodId": 2,
         "playerName": "Estêvão", "replacedById": "pal-p08"},
        # Substituição: Bruno Henrique sai, entra Luiz Araújo - min 75
        {"eventId": "evt009", "typeId": 18, "playerId": "fla-p09", "contestantId": FLA_ID,
         "timeMin": 75, "timeMinSec": "75:00", "periodId": 2,
         "playerName": "Bruno Henrique", "replacedById": "fla-p11"},
    ]
    return {"matchEvents": {"events": events}}


def _build_mock_tm4() -> dict:
    """TM4 — Season Stats (Brasileirão 2026)."""
    teams = []
    for team_id, team_name, players in [
        (FLA_ID, "Flamengo", FLA_PLAYERS),
        (PAL_ID, "Palmeiras", PAL_PLAYERS),
    ]:
        player_stats = [
            {**_build_player_season_stats(pid, info["position"]), "playerName": info["name"]}
            for pid, info in players.items()
        ]
        teams.append({
            "contestantId": team_id,
            "contestantName": team_name,
            "players": player_stats,
        })

    return {"seasonStats": {"teams": teams}}


def _build_mock_tm3() -> dict:
    """TM3 — Squads (elencos completos)."""
    squads = []
    for team_id, team_name, players in [
        (FLA_ID, "Flamengo", FLA_PLAYERS),
        (PAL_ID, "Palmeiras", PAL_PLAYERS),
    ]:
        player_list = [
            {
                "playerId": pid,
                "playerName": info["name"],
                "position": info["position"],
                "shirtNumber": info["shirtNumber"],
                "nationality": info["nationality"],
                "birthDate": info["birthDate"],
            }
            for pid, info in players.items()
        ]
        squads.append({
            "contestantId": team_id,
            "contestantName": team_name,
            "players": player_list,
        })

    return {"squads": {"contestants": squads}}


class OptaMock:
    """Mock do OptaClient com dados realistas do Brasileirão."""

    async def __aenter__(self) -> OptaMock:
        logger.info("OptaMock inicializado (modo mock ativo)")
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get_match_stats(self, match_id: str) -> dict:
        """MA2 — stats de jogo."""
        await asyncio.sleep(0.01)  # simular latência
        return _build_mock_ma2()

    async def get_match_events(self, match_id: str) -> dict:
        """MA3 — eventos do jogo."""
        await asyncio.sleep(0.01)
        return _build_mock_ma3()

    async def get_season_stats(
        self,
        competition_id: str,
        season_id: str = "",
        team_id: str | None = None,
    ) -> dict:
        """TM4 — stats da temporada."""
        await asyncio.sleep(0.01)
        return _build_mock_tm4()

    async def get_squads(
        self,
        competition_id: str,
        season_id: str = "",
        team_id: str | None = None,
    ) -> dict:
        """TM3 — elencos."""
        await asyncio.sleep(0.01)
        return _build_mock_tm3()

    async def get_all_player_stats(
        self,
        match_id: str,
        competition_id: str,
        season_id: str,
    ) -> tuple[dict, dict, dict]:
        """Orquestra MA2+MA3+TM4 em paralelo."""
        ma2, ma3, tm4 = await asyncio.gather(
            self.get_match_stats(match_id),
            self.get_match_events(match_id),
            self.get_season_stats(competition_id, season_id),
        )
        return ma2, ma3, tm4
