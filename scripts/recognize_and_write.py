"""Pipeline completo: imagem → reconhecimento → stats (mock) → Gemini → Sheets Flowics."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import cv2

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from recognition.face_embedder import FaceEmbedder
from recognition.local_player_db import LocalPlayerDB
from recognition.matcher import FaceMatcher
from shared.models import PlayerInfo
from shared.opta_config import OptaConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run(
    image_path: str,
    db_path: str,
    threshold: float,
    use_sheets: bool,
    match_id: str,
    competition_id: str,
    season_id: str,
) -> None:
    # ── 1. Reconhecimento facial ──
    player_db = LocalPlayerDB(db_path)
    logger.info("Loaded %d players from DB", player_db.player_count)

    if player_db.player_count == 0:
        print("No players in database. Run setup.register_from_sheets first.")
        return

    embedder = FaceEmbedder(use_gpu=False)
    matcher = FaceMatcher(threshold=threshold)

    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: could not read image '{image_path}'")
        return

    embedding = embedder.get_embedding(image)
    if embedding is None:
        print("No face detected in the image.")
        return

    player_ids, embedding_matrix = player_db.get_all_embeddings()
    player_id, similarity = matcher.match(embedding, player_ids, embedding_matrix)

    if player_id is None:
        print(f"No match found (best similarity: {similarity:.3f}, threshold: {threshold})")
        return

    player_info_db = player_db.get_player_info(player_id)
    player_name = player_info_db.name if player_info_db else player_id

    print(f"\nReconhecido: {player_name} (similaridade: {similarity:.3f})")
    if player_info_db:
        print(f"  Time: {player_info_db.team_name}")

    # ── 2. Buscar stats (mock ou real) ──
    opta_config = OptaConfig()

    if opta_config.use_mock:
        from data_fetcher.opta_mock import OptaMock
        client = OptaMock()
    else:
        from data_fetcher.opta_client import OptaClient
        client = OptaClient(opta_config)

    async with client:
        ma2, ma3, tm4 = await client.get_all_player_stats(
            match_id=match_id,
            competition_id=competition_id,
            season_id=season_id,
        )

    # ── 3. Extrair e selecionar stats via Gemini ──
    from data_fetcher.stats_selector import StatsSelector

    selector = StatsSelector()

    raw_stats = selector._extract_player_stats_from_opta(player_id, ma2, ma3, tm4)

    if not raw_stats:
        print(f"  Sem stats para {player_name} nos dados Opta (player_id={player_id})")
        print("  Usando stats genéricas do mock...")
        # Tentar com o primeiro jogador do mock para demo
        for team in ma2.get("matchStats", {}).get("teamStats", []):
            for p in team.get("playerStats", []):
                raw_stats = p.get("stats", {})
                # Adicionar season stats do mesmo jogador
                pid = p["playerId"]
                for t in tm4.get("seasonStats", {}).get("teams", []):
                    for sp in t.get("players", []):
                        if sp["playerId"] == pid:
                            for k, v in sp.get("stats", {}).items():
                                raw_stats[f"season_{k}"] = v
                            break
                if raw_stats:
                    break
            if raw_stats:
                break

    player_info = PlayerInfo(
        player_id=player_id,
        name=player_name,
        team_id=player_info_db.team_id if player_info_db else "",
        team_name=player_info_db.team_name if player_info_db else "",
        position=player_info_db.position if player_info_db else "",
        shirt_number=player_info_db.shirt_number if player_info_db else None,
    )

    print(f"\n  Stats brutas: {len(raw_stats)} métricas encontradas")
    stats = await selector.select_stats(player_info, raw_stats)

    print(f"\n  Top 5 stats selecionadas:")
    for s in stats:
        print(f"    - {s.value} {s.label}")

    # ── 4. Escrever na planilha ──
    if use_sheets:
        from data_fetcher.sheets_writer import SheetsWriter

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        writer = SheetsWriter()
        await writer.write_player_stats(player_name, stats, timestamp)
        print(f"\n  Escrito na planilha Google Sheets!")
    else:
        print("\n  (--no-sheets: planilha não atualizada)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline completo: imagem → reconhecimento → stats → Sheets"
    )
    parser.add_argument("--image", required=True, help="Caminho da imagem do jogador")
    parser.add_argument("--db", required=True, help="Caminho do DB local (JSON)")
    parser.add_argument(
        "--threshold", type=float, default=0.6, help="Threshold de match (default: 0.6)"
    )
    parser.add_argument(
        "--no-sheets", action="store_true", help="Não escrever no Google Sheets"
    )
    parser.add_argument(
        "--match-id", default=os.getenv("MATCH_ID", "mock-fla-pal-2026-01"),
        help="ID da partida Opta",
    )
    parser.add_argument(
        "--competition-id", default=os.getenv("COMPETITION_ID", "mock-brasileirao-2026"),
        help="ID da competição Opta",
    )
    parser.add_argument(
        "--season-id", default=os.getenv("SEASON_ID", "mock-brasileirao-2026-season"),
        help="ID da temporada Opta",
    )
    args = parser.parse_args()

    asyncio.run(run(
        args.image, args.db, args.threshold, not args.no_sheets,
        args.match_id, args.competition_id, args.season_id,
    ))


if __name__ == "__main__":
    main()
