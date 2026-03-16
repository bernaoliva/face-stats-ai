from __future__ import annotations

import asyncio
import logging
import os

import gspread
from tenacity import retry, stop_after_attempt, wait_fixed

from shared.models import StatItem

logger = logging.getLogger(__name__)

# Fórmulas que puxam dados do DB automaticamente (locale PT-BR usa ;)
# Foto do jogador: VLOOKUP nome → headshot URL no DataBase Jogadores
_PLAYER_PIC = '=IFERROR(IMAGE(VLOOKUP(A2;\'DataBase Jogadores\'!$D$5:$E$1026;2;0);1);"")'
# Nome do time: VLOOKUP nome → TIME no DataBase Jogadores
_TEAM_NAME = '=IFERROR(VLOOKUP(A2;\'DataBase Jogadores\'!$D$5:$G$1026;4;0);"")'
# Logo do time: VLOOKUP nome → time → VLOOKUP time → logo URL no Database
_TEAM_LOGO = '=IFERROR(IMAGE(VLOOKUP(VLOOKUP(A2;\'DataBase Jogadores\'!$D$5:$G$1026;4;0);Database!$D$4:$F$1554;3;0);1);"")'


class SheetsWriter:
    def __init__(self) -> None:
        self._gc = gspread.service_account()
        spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID", "")
        worksheet_name = os.getenv("SHEETS_WORKSHEET_NAME", "Sheet1")
        self._sheet = self._gc.open_by_key(spreadsheet_id).worksheet(worksheet_name)

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(0.2))
    def _write_sync(
        self,
        player_name: str,
        stats: list[StatItem],
        timestamp: str,
    ) -> None:
        """Escreve jogador + stats no layout Flowics.

        Layout (mesmo padrão estético do DataBase Jogadores):
          A: JOGADOR   B: PIC         C: TIME        D: PICTO       E-I: STATS (frase corrida)
          (nome)       (foto jogador) (nome time)    (logo time)    "12 gols na temporada"
        """
        # Pad stats to exactly 5
        padded = list(stats[:5])
        while len(padded) < 5:
            padded.append(StatItem(label="-", value="-"))

        # Stats como frase corrida: "12 gols na temporada"
        stat_phrases = []
        for s in padded:
            if s.label == "-":
                stat_phrases.append("")
            else:
                stat_phrases.append(f"{s.value} {s.label}")

        headers = [
            "JOGADOR", "PIC", "TIME", "PICTO",
            "STAT 1", "STAT 2", "STAT 3", "STAT 4", "STAT 5",
        ]

        values = [
            player_name,
            _PLAYER_PIC,
            _TEAM_NAME,
            _TEAM_LOGO,
        ] + stat_phrases

        self._sheet.clear()
        self._sheet.batch_update(
            [
                {"range": "A1:I1", "values": [headers]},
                {"range": "A2:I2", "values": [values]},
            ],
            value_input_option="USER_ENTERED",
        )
        logger.info("Wrote stats for %s to Sheets (Flowics layout)", player_name)

    async def write_player_stats(
        self,
        player_name: str,
        stats: list[StatItem],
        timestamp: str,
    ) -> None:
        await asyncio.to_thread(self._write_sync, player_name, stats, timestamp)

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(0.2))
    def _write_name_sync(self, player_name: str, timestamp: str) -> None:
        """Escreve só o nome (sem stats) — usado pelo script de reconhecimento."""
        headers = ["JOGADOR", "PIC", "TIME", "PICTO"]
        values = [player_name, _PLAYER_PIC, _TEAM_NAME, _TEAM_LOGO]

        self._sheet.clear()
        self._sheet.batch_update(
            [
                {"range": "A1:D1", "values": [headers]},
                {"range": "A2:D2", "values": [values]},
            ],
            value_input_option="USER_ENTERED",
        )
        logger.info("Wrote player name '%s' to Sheets (with team/photo formulas)", player_name)

    async def write_player_name(self, player_name: str, timestamp: str) -> None:
        await asyncio.to_thread(self._write_name_sync, player_name, timestamp)
