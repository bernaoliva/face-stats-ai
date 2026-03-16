from __future__ import annotations

import asyncio
import base64
import logging
import time

import aiohttp
import cv2
import structlog

from capture.config import CaptureConfig
from capture.face_detector import FaceDetector
from capture.stream_reader import StreamReader

logger = structlog.get_logger()


async def run_pipeline(config: CaptureConfig) -> None:
    reader = StreamReader(
        source=config.capture_source,
        ndi_name=config.capture_ndi_name,
        rtmp_url=config.capture_rtmp_url,
    )
    detector = FaceDetector(min_confidence=config.capture_face_confidence)

    # Debounce: player_id -> last_trigger_time
    debounce: dict[str, float] = {}
    interval = 1.0 / config.capture_fps

    async with aiohttp.ClientSession() as session:
        logger.info("capture.started", source=config.capture_source, fps=config.capture_fps)

        while True:
            start = time.monotonic()

            frame = reader.read_frame()
            if frame is None:
                logger.debug("capture.no_frame")
                await asyncio.sleep(interval)
                continue

            faces = detector.detect_faces(frame)
            if not faces:
                await asyncio.sleep(max(0, interval - (time.monotonic() - start)))
                continue

            for crop, confidence, bbox in faces:
                # Encode crop as JPEG base64
                _, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
                face_b64 = base64.b64encode(buf.tobytes()).decode()

                # Call recognition service
                try:
                    async with session.post(
                        f"{config.recognition_url}/recognize",
                        json={
                            "face_image_base64": face_b64,
                            "match_id": config.match_id,
                        },
                        timeout=aiohttp.ClientTimeout(total=2.0),
                    ) as resp:
                        result = await resp.json()
                except Exception:
                    logger.error("capture.recognition_failed", exc_info=True)
                    continue

                if not result.get("recognized"):
                    logger.debug(
                        "capture.not_recognized",
                        similarity=result.get("similarity", 0),
                    )
                    continue

                player = result["player"]
                player_id = player["player_id"]
                player_name = player["name"]

                # Debounce check
                now = time.monotonic()
                last = debounce.get(player_id, 0)
                if now - last < config.capture_debounce_seconds:
                    logger.debug(
                        "capture.debounced",
                        player=player_name,
                        seconds_ago=round(now - last, 1),
                    )
                    continue

                debounce[player_id] = now
                logger.info(
                    "capture.player_recognized",
                    player=player_name,
                    similarity=round(result["similarity"], 3),
                )

                # Fire-and-forget: trigger stats pipeline
                asyncio.create_task(
                    _trigger_stats(session, config, player),
                )

            elapsed = time.monotonic() - start
            await asyncio.sleep(max(0, interval - elapsed))


async def _trigger_stats(
    session: aiohttp.ClientSession,
    config: CaptureConfig,
    player: dict,
) -> None:
    try:
        async with session.post(
            f"{config.data_fetcher_url}/stats",
            json={
                "player": player,
                "match_id": config.match_id,
                "competition_id": config.competition_id,
                "season_id": config.season_id,
            },
            timeout=aiohttp.ClientTimeout(total=5.0),
        ) as resp:
            result = await resp.json()
            logger.info(
                "capture.stats_written",
                player=result.get("player_name"),
                stats_count=len(result.get("stats", [])),
            )
    except Exception:
        logger.error("capture.stats_failed", exc_info=True)


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    config = CaptureConfig()
    if not config.match_id:
        print("ERROR: MATCH_ID environment variable is required")
        return

    asyncio.run(run_pipeline(config))


if __name__ == "__main__":
    main()
