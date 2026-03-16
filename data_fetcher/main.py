from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings

from shared.models import StatsRequest, StatsResponse
from shared.opta_config import OptaConfig
from data_fetcher.opta_client import OptaClient
from data_fetcher.opta_mock import OptaMock
from data_fetcher.stats_selector import StatsSelector
from data_fetcher.sheets_writer import SheetsWriter

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    sheets_enabled: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
opta_config = OptaConfig()

_opta_client: OptaClient | OptaMock | None = None
_stats_selector: StatsSelector | None = None
_sheets_writer: SheetsWriter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _opta_client, _stats_selector, _sheets_writer

    if opta_config.use_mock:
        logger.info("Modo MOCK ativo — usando OptaMock")
        _opta_client = OptaMock()
    else:
        _opta_client = OptaClient(opta_config)
    await _opta_client.__aenter__()
    _stats_selector = StatsSelector()

    if settings.sheets_enabled:
        try:
            _sheets_writer = SheetsWriter()
        except Exception:
            logger.warning("Google Sheets not configured, writing disabled", exc_info=True)

    yield

    if _opta_client:
        await _opta_client.__aexit__(None, None, None)


app = FastAPI(title="Data Fetcher", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/stats", response_model=StatsResponse)
async def get_stats(request: StatsRequest):
    assert _opta_client is not None
    assert _stats_selector is not None

    # 1. Fetch all Opta data in parallel
    ma2, ma3, tm4 = await _opta_client.get_all_player_stats(
        match_id=request.match_id,
        competition_id=request.competition_id,
        season_id=request.season_id,
    )

    # 2. Extract raw stats for this player
    raw_stats = _stats_selector._extract_player_stats_from_opta(
        request.player.player_id, ma2, ma3, tm4,
    )

    # 3. Select best 5 stats via Gemini (with fallback)
    stats = await _stats_selector.select_stats(request.player, raw_stats)

    timestamp = datetime.now(timezone.utc).isoformat()

    # 4. Write to Sheets (non-blocking on failure)
    if _sheets_writer:
        try:
            await _sheets_writer.write_player_stats(
                request.player.name, stats, timestamp,
            )
        except Exception:
            logger.error("Failed to write to Sheets", exc_info=True)

    return StatsResponse(
        player_name=request.player.name,
        stats=stats,
        timestamp=timestamp,
    )
