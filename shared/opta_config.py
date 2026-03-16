from __future__ import annotations

from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class OptaFeed(str, Enum):
    MA2 = "matchstats"
    MA3 = "matchevent"
    TM4 = "seasonstats"
    TM3 = "squads"


class OptaConfig(BaseSettings):
    """Configuração da API Opta/Stats Perform."""

    model_config = SettingsConfigDict(
        env_prefix="OPTA_",
        env_file=".env",
        extra="ignore",
    )

    outlet_auth_key: str = ""
    auth_method: str = "url_key"  # "url_key" ou "oauth"

    # OAuth (só usado se auth_method == "oauth")
    oauth_token_endpoint: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""

    # General
    base_url: str = "https://api.performfeeds.com/soccerdata"
    use_mock: bool = False
    request_timeout: int = 3
    max_retries: int = 2

    def build_url(
        self,
        feed: OptaFeed,
        *,
        match_id: str | None = None,
        competition_id: str | None = None,
        season_id: str | None = None,
        team_id: str | None = None,
    ) -> str:
        """Monta a URL do feed com outlet key no path."""
        base = f"{self.base_url}/{feed.value}/{self.outlet_auth_key}"

        params = ["_rt=b", "_fmt=json"]

        if feed == OptaFeed.MA2 and match_id:
            params.append(f"fx={match_id}")
        elif feed == OptaFeed.MA3 and match_id:
            params.append(f"fx={match_id}")
        elif feed == OptaFeed.TM4:
            if competition_id:
                params.append(f"comp={competition_id}")
            if season_id:
                params.append(f"tmcl={season_id}")
            if team_id:
                params.append(f"ctst={team_id}")
        elif feed == OptaFeed.TM3:
            if competition_id:
                params.append(f"comp={competition_id}")
            if season_id:
                params.append(f"tmcl={season_id}")
            if team_id:
                params.append(f"ctst={team_id}")

        return f"{base}?{'&'.join(params)}"
