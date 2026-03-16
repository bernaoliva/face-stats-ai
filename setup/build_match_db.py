"""Build match player database in Firestore from Opta squads (TM3)."""
from __future__ import annotations

import argparse
import asyncio
import logging

from shared.gcp_utils import get_firestore_client
from data_fetcher.opta_client import OptaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def build_match_db(
    match_id: str,
    competition_id: str,
    season_id: str,
    team_ids: list[str],
) -> None:
    db = get_firestore_client()
    players_ref = db.collection("matches").document(match_id).collection("players")

    async with OptaClient() as client:
        for team_id in team_ids:
            squads = await client.get_squads(competition_id, season_id, team_id)

            for team in squads.get("squad", []):
                team_name = team.get("teamName", "")
                tid = team.get("teamId", team_id)

                for player in team.get("player", []):
                    player_id = player.get("playerId", "")
                    if not player_id:
                        continue

                    doc_data = {
                        "player_id": player_id,
                        "name": player.get("matchName", player.get("name", "")),
                        "team_id": tid,
                        "team_name": team_name,
                        "position": player.get("position", ""),
                        "shirt_number": player.get("shirtNumber"),
                    }

                    players_ref.document(player_id).set(doc_data, merge=True)
                    logger.info("Added player: %s (%s)", doc_data["name"], player_id)

    logger.info("Match DB built for %s", match_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build match player DB from Opta squads")
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--competition-id", required=True)
    parser.add_argument("--season-id", required=True)
    parser.add_argument("--team-ids", required=True, nargs="+", help="Team IDs (home and away)")
    args = parser.parse_args()

    asyncio.run(build_match_db(args.match_id, args.competition_id, args.season_id, args.team_ids))


if __name__ == "__main__":
    main()
