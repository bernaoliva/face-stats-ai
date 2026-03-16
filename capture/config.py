from __future__ import annotations

from pydantic_settings import BaseSettings


class CaptureConfig(BaseSettings):
    # Source
    capture_source: str = "ndi"  # "ndi" or "rtmp"
    capture_ndi_name: str = "VMIX"
    capture_rtmp_url: str = "rtmp://localhost/live/stream"

    # Processing
    capture_fps: int = 2
    capture_face_confidence: float = 0.9
    capture_debounce_seconds: int = 30

    # Services
    recognition_url: str = "http://localhost:8081"
    data_fetcher_url: str = "http://localhost:8082"

    # Match context
    match_id: str = ""
    competition_id: str = ""
    season_id: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"
