from __future__ import annotations

import base64
import logging
import os
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings

from shared.models import RecognitionRequest, RecognitionResponse
from recognition.face_embedder import FaceEmbedder
from recognition.player_db import PlayerDB
from recognition.local_player_db import LocalPlayerDB
from recognition.matcher import FaceMatcher

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    recognition_threshold: float = 0.6
    match_id: str = ""
    recognition_use_gpu: bool = True
    player_db_mode: str = "firestore"
    local_db_path: str = "local_players.json"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

_embedder: FaceEmbedder | None = None
_player_db: PlayerDB | LocalPlayerDB | None = None
_matcher: FaceMatcher | None = None


def _load_player_db() -> PlayerDB | LocalPlayerDB | None:
    if settings.player_db_mode == "local":
        return LocalPlayerDB(settings.local_db_path)
    elif settings.match_id:
        return PlayerDB(settings.match_id)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _player_db, _matcher

    _embedder = FaceEmbedder(use_gpu=settings.recognition_use_gpu)
    _matcher = FaceMatcher(threshold=settings.recognition_threshold)
    _player_db = _load_player_db()

    yield


app = FastAPI(title="Recognition Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "players_loaded": _player_db.player_count if _player_db else 0,
    }


@app.post("/recognize", response_model=RecognitionResponse)
async def recognize(request: RecognitionRequest):
    global _player_db

    if _embedder is None or _matcher is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Load player DB on first request if match_id provided (Firestore mode only)
    if settings.player_db_mode == "firestore":
        if _player_db is None or _player_db.match_id != request.match_id:
            _player_db = PlayerDB(request.match_id)

    if _player_db is None:
        raise HTTPException(status_code=503, detail="Player database not loaded")

    # Decode base64 image
    try:
        img_bytes = base64.b64decode(request.face_image_base64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Failed to decode image")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    # Get embedding
    embedding = _embedder.get_embedding(image)
    if embedding is None:
        return RecognitionResponse(recognized=False, similarity=0.0)

    # Match against database
    player_ids, embedding_matrix = _player_db.get_all_embeddings()
    player_id, similarity = _matcher.match(embedding, player_ids, embedding_matrix)

    if player_id is None:
        return RecognitionResponse(recognized=False, similarity=similarity)

    player_info = _player_db.get_player_info(player_id)
    return RecognitionResponse(
        player=player_info,
        similarity=similarity,
        recognized=True,
    )


@app.post("/reload")
async def reload(match_id: str):
    global _player_db
    _player_db = PlayerDB(match_id)
    return {
        "status": "ok",
        "match_id": match_id,
        "players_loaded": _player_db.player_count,
    }
