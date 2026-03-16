"""
Diagnóstico de autenticação da API Opta/Stats Perform.

Rodar com: python -m data_fetcher.test_auth_debug

Tenta todas as combinações de autenticação e reporta resultados.
Útil para debugar quando o suporte da Stats Perform liberar o acesso.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OUTLET = os.getenv("OPTA_OUTLET_AUTH_KEY", "")
SECRET1 = os.getenv("OPTA_OAUTH_CLIENT_ID", "")
SECRET2 = os.getenv("OPTA_OAUTH_CLIENT_SECRET", "")
BASE = os.getenv("OPTA_BASE_URL", "https://api.performfeeds.com/soccerdata")

# Feed simples que não precisa de match_id
TEST_FEED = "tournamentcalendar"


async def _try_request(
    session: aiohttp.ClientSession,
    name: str,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: str | None = None,
) -> tuple[str, int, str]:
    """Tenta uma requisição e retorna (nome, status, detalhes)."""
    try:
        kwargs: dict = {"headers": headers or {}}
        if data:
            kwargs["data"] = data
            kwargs["headers"]["Content-Type"] = "application/x-www-form-urlencoded"

        async with session.request(method, url, **kwargs) as resp:
            body = await resp.text()
            if resp.status == 200:
                return name, 200, f"OK! ({len(body)} bytes)"
            try:
                err = json.loads(body)
                code = err.get("errorCode", "?")
                return name, resp.status, f"errorCode={code}"
            except json.JSONDecodeError:
                return name, resp.status, body[:200]
    except Exception as e:
        return name, 0, f"{type(e).__name__}: {e}"


async def main() -> None:
    print("=" * 60)
    print("  Opta SDAPI — Diagnóstico de Autenticação")
    print("=" * 60)
    print()

    if not OUTLET:
        print("ERRO: OPTA_OUTLET_AUTH_KEY não configurado no .env")
        sys.exit(1)

    print(f"Outlet key: {OUTLET[:8]}...{OUTLET[-4:]}")
    print(f"Secret 1:   {'***' + SECRET1[-4:] if SECRET1 else '(não configurado)'}")
    print(f"Secret 2:   {'***' + SECRET2[-4:] if SECRET2 else '(não configurado)'}")
    print(f"Base URL:   {BASE}")
    print()

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=True) as session:

        results: list[tuple[str, int, str]] = []

        # --- Teste 1: URL key auth (padrão da documentação) ---
        print("[1] URL key auth (outlet no path)...")
        url = f"{BASE}/{TEST_FEED}/{OUTLET}?_rt=b&_fmt=json"
        results.append(await _try_request(session, "URL key (tournamentcalendar)", url))

        # Testar outros feeds
        for feed in ["matchstats", "seasonstats", "standings", "squads"]:
            url = f"{BASE}/{feed}/{OUTLET}?_rt=b&_fmt=json"
            results.append(await _try_request(session, f"URL key ({feed})", url))

        # --- Teste 2: OAuth com secret1=client_id, secret2=client_secret ---
        if SECRET1 and SECRET2:
            print("[2] OAuth (secret1=client_id, secret2=client_secret)...")
            oauth_endpoints = [
                "https://api.performfeeds.com/oauth/token",
                "https://iapi.performfeeds.com/oauth/token",
            ]
            for endpoint in oauth_endpoints:
                body = f"grant_type=client_credentials&client_id={SECRET1}&client_secret={SECRET2}"
                results.append(await _try_request(
                    session, f"OAuth POST ({endpoint})", endpoint,
                    method="POST", data=body,
                ))

            # --- Teste 3: OAuth invertido ---
            print("[3] OAuth invertido (secret2=client_id, secret1=client_secret)...")
            body = f"grant_type=client_credentials&client_id={SECRET2}&client_secret={SECRET1}"
            results.append(await _try_request(
                session, "OAuth invertido", "https://api.performfeeds.com/oauth/token",
                method="POST", data=body,
            ))

            # --- Teste 4: OAuth com outlet como client_id ---
            print("[4] OAuth (outlet=client_id, secret1=secret)...")
            for i, secret in enumerate([SECRET1, SECRET2], 1):
                creds = base64.b64encode(f"{OUTLET}:{secret}".encode()).decode()
                results.append(await _try_request(
                    session, f"OAuth Basic outlet:secret{i}",
                    "https://api.performfeeds.com/oauth/token",
                    method="POST",
                    headers={"Authorization": f"Basic {creds}"},
                    data="grant_type=client_credentials",
                ))

            # --- Teste 5: Bearer token direto com secrets ---
            print("[5] Bearer token direto com secrets...")
            for i, secret in enumerate([SECRET1, SECRET2], 1):
                url = f"{BASE}/{TEST_FEED}/{OUTLET}?_rt=b&_fmt=json"
                results.append(await _try_request(
                    session, f"Bearer secret{i}",
                    url, headers={"Authorization": f"Bearer {secret}"},
                ))

        # --- Resumo ---
        print()
        print("=" * 60)
        print("  RESULTADOS")
        print("=" * 60)
        print()

        success = False
        for name, status, detail in results:
            icon = "OK" if status == 200 else "FAIL"
            print(f"  [{icon}] {status:>3} | {name}")
            print(f"         {detail}")
            print()
            if status == 200:
                success = True

        if success:
            print("Pelo menos um método funcionou!")
        else:
            print("Nenhum método funcionou.")
            print()
            print("Próximos passos:")
            print("  1. Confirme com a Stats Perform se o outlet está ativo")
            print("  2. Peça para liberar o IP do servidor")
            print("  3. Pergunte qual é o token endpoint para OAuth")
            print(f"  4. Enquanto isso, use OPTA_USE_MOCK=true no .env")


if __name__ == "__main__":
    asyncio.run(main())
