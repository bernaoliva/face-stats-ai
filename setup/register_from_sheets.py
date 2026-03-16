"""Generate local player DB from headshots in the Google Sheets database.

Usa augmentação de imagem (flip, rotações, brilho) para gerar múltiplas
variantes de cada headshot, calculando a média dos embeddings resultantes.
Isso torna o reconhecimento mais robusto para fotos de transmissão ao vivo.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from recognition.face_embedder import FaceEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_sheet_data() -> list[dict]:
    """Read player data from the DataBase Jogadores sheet."""
    import gspread

    gc = gspread.service_account()
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID", "")
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet("DataBase Jogadores")

    # Columns: B=TIME, C=NOME DO JOGADOR, D=NOME REDUZIDO, E=HEADSHOT, G=TIME, J=ID
    rows = ws.get("B5:J1026")

    players = []
    for row in rows:
        if len(row) < 9:
            row.extend([""] * (9 - len(row)))

        team_upper = row[0]  # B
        name = row[2]        # D - NOME REDUZIDO
        headshot_url = row[3]  # E
        team = row[5]        # G
        player_id = row[8]   # J

        if not name or not headshot_url or not headshot_url.startswith("http"):
            continue

        players.append({
            "player_id": name,  # usar nome como ID (único)
            "name": name,
            "team_name": team or team_upper,
            "headshot_url": headshot_url,
        })

    return players


def download_image(url: str) -> np.ndarray | None:
    """Download image from URL and return as BGR numpy array."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            img_bytes = resp.read()
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.warning("Failed to download %s: %s", url, e)
        return None


def _augment(image: np.ndarray) -> list[np.ndarray]:
    """Gera variantes augmentadas do headshot para embedding mais robusto."""
    h, w = image.shape[:2]
    cx, cy = w // 2, h // 2
    variants = [image]  # original sempre incluído

    # Flip horizontal (rosto olhando para o outro lado)
    variants.append(cv2.flip(image, 1))

    # Rotações leves (-12° e +12°)
    for angle in (-12, 12):
        M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        variants.append(rotated)

    # Variação de brilho (mais escuro e mais claro)
    for alpha in (0.75, 1.25):
        bright = np.clip(image.astype(np.float32) * alpha, 0, 255).astype(np.uint8)
        variants.append(bright)

    return variants


def get_robust_embedding(image: np.ndarray, embedder: FaceEmbedder) -> np.ndarray | None:
    """Gera embedding médio a partir do original + variantes augmentadas."""
    embeddings = []
    for variant in _augment(image):
        emb = embedder.get_embedding(variant)
        if emb is not None:
            norm = np.linalg.norm(emb)
            if norm > 0:
                embeddings.append(emb / norm)

    if not embeddings:
        return None

    # Média e renormalização L2
    mean_emb = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(mean_emb)
    return mean_emb / norm if norm > 0 else None


def register_from_sheets(output_path: str) -> None:
    logger.info("Reading player data from Google Sheets...")
    players_data = fetch_sheet_data()
    logger.info("Found %d players with headshot URLs", len(players_data))

    embedder = FaceEmbedder(use_gpu=False)
    players_out: list[dict] = []
    skipped = 0

    # Handle duplicate names
    seen: dict[str, int] = {}

    for player in tqdm(players_data, desc="Processing players"):
        image = download_image(player["headshot_url"])
        if image is None:
            skipped += 1
            continue

        embedding = get_robust_embedding(image, embedder)
        if embedding is None:
            logger.warning("No face detected: %s", player["name"])
            skipped += 1
            continue

        # Garante player_id único
        pid = player["player_id"]
        if pid in seen:
            seen[pid] += 1
            pid = f"{pid} {seen[pid]}"
        else:
            seen[pid] = 1

        players_out.append({
            "player_id": pid,
            "name": player["name"],
            "team_id": "",
            "team_name": player["team_name"],
            "position": "",
            "shirt_number": None,
            "embedding": embedding.tolist(),
        })

    output = {"players": players_out}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(
        "Done! %d players saved, %d skipped. Output: %s",
        len(players_out), skipped, output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate local player DB from Google Sheets headshots (with augmentation)"
    )
    parser.add_argument("--output", default="local_players.json", help="Output JSON path")
    args = parser.parse_args()
    register_from_sheets(args.output)


if __name__ == "__main__":
    main()
