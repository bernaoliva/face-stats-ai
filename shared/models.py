from __future__ import annotations

from pydantic import BaseModel, Field


class PlayerInfo(BaseModel):
    player_id: str
    name: str
    team_id: str
    team_name: str = ""
    position: str = ""
    shirt_number: int | None = None


class RecognitionRequest(BaseModel):
    face_image_base64: str
    match_id: str


class RecognitionResponse(BaseModel):
    player: PlayerInfo | None = None
    similarity: float = 0.0
    recognized: bool = False


class StatItem(BaseModel):
    label: str
    value: str


class StatsRequest(BaseModel):
    player: PlayerInfo
    match_id: str
    competition_id: str
    season_id: str


class StatsResponse(BaseModel):
    player_name: str
    stats: list[StatItem] = Field(..., min_length=5, max_length=5)
    timestamp: str


class PlayerEmbedding(BaseModel):
    player_id: str
    name: str
    team_id: str
    embedding: list[float] = Field(..., min_length=512, max_length=512)
    shirt_number: int | None = None
