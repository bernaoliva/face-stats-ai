from __future__ import annotations

from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class OptaFeed(str, Enum):
    MATCH = "match"
    MA2 = "matchstats"
    MA3 = "matchevent"
    TM4 = "seasonstats"
    TM3 = "squads"
    TC = "tournamentcalendar"
    TS = "tournamentschedule"


class OptaConfig(BaseSettings):
    """Configuração da API Opta/Stats Perform."""

    model_config = SettingsConfigDict(
        env_prefix="OPTA_",
        env_file=".env",
        extra="ignore",
    )

    outlet_auth_key: str = ""
    auth_method: str = "oauth"  # "url_key" ou "oauth"

    # OAuth
    oauth_token_endpoint: str = "https://oauth.performgroup.com/oauth/token"
    secret_key_1: str = ""
    secret_key_2: str = ""

    # Deprecated aliases (backwards compat)
    oauth_client_id: str = ""
    oauth_client_secret: str = ""

    # General
    base_url: str = "https://api.performfeeds.com/soccerdata"
    use_mock: bool = False
    request_timeout: int = 10
    max_retries: int = 2

    # Brasileirao Serie A defaults
    competition_id: str = "scf9p4y91yjvqvg5jndxzhxj"
    season_id: str = "752zalnunu0zkdfbbm915kys4"

    @property
    def active_secret_key(self) -> str:
        """Returns the active secret key (key 1, falls back to old client_id)."""
        return self.secret_key_1 or self.oauth_client_id

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

        # MA2/MA3: fixture UUID in path (not as query param)
        if feed in (OptaFeed.MA2, OptaFeed.MA3) and match_id:
            base = f"{self.base_url}/{feed.value}/{self.outlet_auth_key}/{match_id}"

        params = ["_rt=b", "_fmt=json"]

        if feed == OptaFeed.MATCH:
            if competition_id:
                params.append(f"comp={competition_id}")
            if season_id:
                params.append(f"tmcl={season_id}")
        elif feed in (OptaFeed.TM4, OptaFeed.TM3, OptaFeed.TS):
            if competition_id:
                params.append(f"comp={competition_id}")
            if season_id:
                params.append(f"tmcl={season_id}")
            if team_id:
                params.append(f"ctst={team_id}")

        return f"{base}?{'&'.join(params)}"
