"""Cliente async para Opta SDAPI com suporte a URL auth e OAuth."""
from __future__ import annotations

import asyncio
import logging
import time
from types import TracebackType

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from shared.opta_config import OptaConfig, OptaFeed

logger = logging.getLogger(__name__)


class OptaClient:
    """Cliente async para Opta Sports Data API.

    Suporta dois métodos de autenticação:
    - url_key: outlet auth key no path da URL (requer IP whitelisting)
    - oauth: OAuth 2.0 Client Credentials com bearer token
    """

    def __init__(self, config: OptaConfig | None = None) -> None:
        self._config = config or OptaConfig()
        self._session: aiohttp.ClientSession | None = None
        self._oauth_token: str | None = None
        self._oauth_expires_at: float = 0.0

    async def __aenter__(self) -> OptaClient:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    # --- Auth ---

    async def _ensure_oauth_token(self) -> str:
        """Obtém ou renova o token OAuth 2.0 via Client Credentials."""
        if self._oauth_token and time.time() < self._oauth_expires_at - 60:
            return self._oauth_token

        assert self._session is not None
        endpoint = self._config.oauth_token_endpoint
        if not endpoint:
            raise ValueError("OPTA_OAUTH_TOKEN_ENDPOINT não configurado")

        data = {
            "grant_type": "client_credentials",
            "client_id": self._config.oauth_client_id,
            "client_secret": self._config.oauth_client_secret,
        }

        logger.info("Renovando token OAuth em %s", endpoint)
        async with self._session.post(
            endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()

        self._oauth_token = body["access_token"]
        self._oauth_expires_at = time.time() + body.get("expires_in", 3600)
        logger.info("Token OAuth obtido, expira em %ds", body.get("expires_in", 3600))
        return self._oauth_token

    async def _get_headers(self) -> dict[str, str]:
        """Retorna headers de autenticação conforme o método configurado."""
        if self._config.auth_method == "oauth":
            token = await self._ensure_oauth_token()
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _build_url(
        self,
        feed: OptaFeed,
        **kwargs: str | None,
    ) -> str:
        """Monta a URL usando o config."""
        return self._config.build_url(feed, **kwargs)

    # --- Fetch ---

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, max=2),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def _fetch(self, url: str) -> dict:
        """Faz GET com retry e autenticação."""
        assert self._session is not None, "Use OptaClient como async context manager"
        headers = await self._get_headers()
        async with self._session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _safe_fetch(self, url: str) -> dict:
        """Fetch com fallback para dict vazio em caso de erro."""
        try:
            return await self._fetch(url)
        except Exception:
            logger.warning("Opta fetch falhou: %s", url, exc_info=True)
            return {}

    # --- Feeds ---

    async def get_match_stats(self, match_id: str) -> dict:
        """MA2 — estatísticas de jogo por jogador."""
        url = self._build_url(OptaFeed.MA2, match_id=match_id)
        return await self._safe_fetch(url)

    async def get_match_events(self, match_id: str) -> dict:
        """MA3 — eventos: gols, cartões, substituições."""
        url = self._build_url(OptaFeed.MA3, match_id=match_id)
        return await self._safe_fetch(url)

    async def get_season_stats(
        self,
        competition_id: str,
        season_id: str,
        team_id: str | None = None,
    ) -> dict:
        """TM4 — stats acumuladas da temporada."""
        url = self._build_url(
            OptaFeed.TM4,
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
        )
        return await self._safe_fetch(url)

    async def get_squads(
        self,
        competition_id: str,
        season_id: str,
        team_id: str | None = None,
    ) -> dict:
        """TM3 — elencos dos times."""
        url = self._build_url(
            OptaFeed.TM3,
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
        )
        return await self._safe_fetch(url)

    async def get_all_player_stats(
        self,
        match_id: str,
        competition_id: str,
        season_id: str,
    ) -> tuple[dict, dict, dict]:
        """Orquestra MA2+MA3+TM4 em paralelo."""
        ma2, ma3, tm4 = await asyncio.gather(
            self.get_match_stats(match_id),
            self.get_match_events(match_id),
            self.get_season_stats(competition_id, season_id),
        )
        return ma2, ma3, tm4
