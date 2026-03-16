"""Simulador de transmissão ao vivo: processa pasta de imagens como se fossem frames de câmera."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

import cv2

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from recognition.face_embedder import FaceEmbedder
from recognition.local_player_db import LocalPlayerDB
from recognition.matcher import FaceMatcher
from shared.models import PlayerInfo
from shared.opta_config import OptaConfig

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _list_images(images_dir: str) -> list[Path]:
    p = Path(images_dir)
    files = sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED_EXTS)
    return files


async def process_frame(
    image_path: Path,
    embedder: FaceEmbedder,
    matcher: FaceMatcher,
    player_db: LocalPlayerDB,
    debounce: dict[str, float],
    debounce_seconds: float,
    use_sheets: bool,
    match_id: str,
    competition_id: str,
    season_id: str,
) -> None:
    print(f"\n[{image_path.name}]")

    image = cv2.imread(str(image_path))
    if image is None:
        print("  Erro ao ler imagem")
        return

    # Detectar rosto + embedding
    embedding = embedder.get_embedding(image)
    if embedding is None:
        print("  Nenhum rosto detectado")
        return

    print("  Rosto detectado")

    # Match contra DB
    player_ids, embedding_matrix = player_db.get_all_embeddings()
    player_id, similarity = matcher.match(embedding, player_ids, embedding_matrix)

    if player_id is None:
        print(f"  Nao reconhecido (melhor similaridade: {similarity:.3f}, threshold: {matcher.threshold})")
        return

    player_info_db = player_db.get_player_info(player_id)
    player_name = player_info_db.name if player_info_db else player_id
    team_name = player_info_db.team_name if player_info_db else ""

    # Debounce
    now = time.monotonic()
    last = debounce.get(player_id, 0)
    elapsed = now - last
    if elapsed < debounce_seconds:
        print(f"  Reconhecido: {player_name} ({similarity:.3f}) - {team_name}")
        print(f"  DEBOUNCE: mesmo jogador ha {elapsed:.1f}s (min: {debounce_seconds}s)")
        return

    debounce[player_id] = now
    print(f"  Reconhecido: {player_name} (similaridade: {similarity:.3f}) - {team_name}")

    # Buscar stats
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

    from data_fetcher.stats_selector import StatsSelector
    selector = StatsSelector()

    raw_stats = selector._extract_player_stats_from_opta(player_id, ma2, ma3, tm4)

    if not raw_stats:
        # Usar stats genéricas do mock para demo
        for team in ma2.get("matchStats", {}).get("teamStats", []):
            for p in team.get("playerStats", []):
                raw_stats = p.get("stats", {})
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
        team_name=team_name,
        position=player_info_db.position if player_info_db else "",
        shirt_number=player_info_db.shirt_number if player_info_db else None,
    )

    stats = await selector.select_stats(player_info, raw_stats)

    print(f"  Stats:")
    for s in stats:
        print(f"    {s.value} {s.label}")

    if use_sheets:
        from data_fetcher.sheets_writer import SheetsWriter
        writer = SheetsWriter()
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        await writer.write_player_stats(player_name, stats, timestamp)
        print(f"  Planilha atualizada!")
    else:
        print(f"  (--no-sheets: planilha nao atualizada)")


async def run(
    images_dir: str,
    db_path: str,
    fps: float,
    debounce_seconds: float,
    threshold: float,
    use_sheets: bool,
    match_id: str,
    competition_id: str,
    season_id: str,
) -> None:
    player_db = LocalPlayerDB(db_path)
    print(f"DB carregado: {player_db.player_count} jogadores")

    embedder = FaceEmbedder(use_gpu=False)
    matcher = FaceMatcher(threshold=threshold)
    debounce: dict[str, float] = {}
    interval = 1.0 / fps

    images = _list_images(images_dir)
    if not images:
        print(f"Nenhuma imagem encontrada em '{images_dir}'")
        return

    print(f"Processando {len(images)} imagens a {fps} fps (debounce: {debounce_seconds}s)\n")
    print("=" * 50)

    for i, image_path in enumerate(images, 1):
        start = time.monotonic()
        print(f"\n[{i}/{len(images)}]", end="")

        await process_frame(
            image_path, embedder, matcher, player_db,
            debounce, debounce_seconds, use_sheets,
            match_id, competition_id, season_id,
        )

        elapsed = time.monotonic() - start
        await asyncio.sleep(max(0, interval - elapsed))

    print("\n" + "=" * 50)
    print(f"Concluido. {len(images)} frames processados.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulador de transmissão: processa pasta de imagens como stream ao vivo"
    )
    parser.add_argument("--images-dir", required=True, help="Pasta com frames (JPG/PNG)")
    parser.add_argument("--db", required=True, help="Caminho do DB local (JSON)")
    parser.add_argument("--fps", type=float, default=2.0, help="Frames por segundo simulados (default: 2)")
    parser.add_argument("--debounce", type=float, default=30.0, help="Segundos entre reconhecimentos do mesmo jogador (default: 30)")
    parser.add_argument("--threshold", type=float, default=0.6, help="Similaridade minima (default: 0.6)")
    parser.add_argument("--no-sheets", action="store_true", help="Nao escrever na planilha")
    parser.add_argument("--match-id", default=os.getenv("MATCH_ID", "mock-brasileirao-2026-01"))
    parser.add_argument("--competition-id", default=os.getenv("COMPETITION_ID", "mock-brasileirao-2026"))
    parser.add_argument("--season-id", default=os.getenv("SEASON_ID", "mock-brasileirao-2026-season"))
    args = parser.parse_args()

    asyncio.run(run(
        args.images_dir, args.db, args.fps, args.debounce,
        args.threshold, not args.no_sheets,
        args.match_id, args.competition_id, args.season_id,
    ))


if __name__ == "__main__":
    main()
