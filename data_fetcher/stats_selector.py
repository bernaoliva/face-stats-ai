from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from shared.models import PlayerInfo, StatItem

logger = logging.getLogger(__name__)

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "5"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq", "gemini", ou "fallback"


def _create_llm_client() -> tuple[str, object | None]:
    """Cria o client LLM baseado no LLM_PROVIDER."""
    provider = LLM_PROVIDER.lower()

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            logger.warning("GROQ_API_KEY nao configurada, usando fallback")
            return "fallback", None
        from groq import AsyncGroq
        return "groq", AsyncGroq(api_key=api_key)

    if provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            logger.warning("GOOGLE_API_KEY nao configurada, usando fallback")
            return "fallback", None
        from google import genai
        return "gemini", genai.Client(api_key=api_key)

    return "fallback", None


class StatsSelector:
    def __init__(self) -> None:
        self._provider, self._client = _create_llm_client()
        self._groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self._gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info("StatsSelector usando provider: %s", self._provider)

    @staticmethod
    def _stat_array_to_dict(stat_array: list[dict]) -> dict:
        """Convert Opta stat array [{type, value}, ...] to flat dict."""
        return {s["type"]: s["value"] for s in stat_array if "type" in s and "value" in s}

    def _extract_player_stats_from_opta(
        self,
        player_id: str,
        ma2: dict,
        ma3: dict,
        tm4: dict,
    ) -> dict:
        stats: dict = {}

        # MA2 — match stats per player (real API format)
        # Real: liveData.lineUp[].player[].stat = [{type, value}, ...]
        for team in ma2.get("liveData", {}).get("lineUp", []):
            for player in team.get("player", []):
                if player.get("playerId") == player_id:
                    stat_list = player.get("stat", [])
                    if isinstance(stat_list, list):
                        stats.update(self._stat_array_to_dict(stat_list))
                    elif isinstance(stat_list, dict):
                        stats.update(stat_list)
                    break

        # Mock format fallback: matchStats.teamStats[].playerStats[].stats = {}
        if not stats:
            for team in ma2.get("matchStats", {}).get("teamStats", []):
                for player in team.get("playerStats", []):
                    if player.get("playerId") == player_id:
                        stats.update(player.get("stats", {}))
                        break

        # MA3 — event-derived stats
        # Real: liveData.event[] with typeId
        goals = 0
        assists = 0
        yellow_cards = 0
        red_cards = 0
        events = (
            ma3.get("liveData", {}).get("event", [])
            or ma3.get("matchEvents", {}).get("events", [])
        )
        for event in events:
            if event.get("playerId") != player_id:
                continue
            etype = event.get("typeId")
            if etype == 16:
                goals += 1
            elif etype == 17:
                assists += 1
            elif etype == 71:
                yellow_cards += 1
            elif etype == 72:
                red_cards += 1
        if goals:
            stats["goals_in_match"] = goals
        if assists:
            stats["assists_in_match"] = assists
        if yellow_cards:
            stats["yellow_cards_in_match"] = yellow_cards
        if red_cards:
            stats["red_cards_in_match"] = red_cards

        # Also extract from goal/card arrays in liveData
        for goal in ma3.get("liveData", {}).get("goal", []):
            if goal.get("scorerId") == player_id:
                stats["goals_in_match"] = stats.get("goals_in_match", 0) + 1
            if goal.get("assistPlayerId") == player_id:
                stats["assists_in_match"] = stats.get("assists_in_match", 0) + 1

        # TM4 — season stats
        # Real: liveData.lineUp[].player[].stat = [{type, value}, ...]
        # or seasonStats.teams[].players[].stats = {}
        for team in tm4.get("liveData", {}).get("lineUp", []):
            for player in team.get("player", []):
                if player.get("playerId") == player_id:
                    stat_list = player.get("stat", [])
                    season_stats = self._stat_array_to_dict(stat_list) if isinstance(stat_list, list) else stat_list
                    for k, v in season_stats.items():
                        stats[f"season_{k}"] = v
                    break

        # Mock fallback
        if not any(k.startswith("season_") for k in stats):
            for team in tm4.get("seasonStats", {}).get("teams", []):
                for player in team.get("players", []):
                    if player.get("playerId") == player_id:
                        for k, v in player.get("stats", {}).items():
                            stats[f"season_{k}"] = v
                        break

        return stats

    def _build_prompt(
        self,
        player: PlayerInfo,
        raw_stats: dict,
        match_context: str = "",
    ) -> str:
        stats_text = json.dumps(raw_stats, ensure_ascii=False, indent=2)
        return f"""Você é um editor de grafismo de transmissão de futebol.

Jogador: {player.name} ({player.position}, camisa {player.shirt_number})
Time: {player.team_name}
{f"Contexto: {match_context}" if match_context else ""}

Estatísticas disponíveis:
{stats_text}

Selecione exatamente 5 estatísticas mais relevantes e interessantes para exibir no grafismo de TV.
Priorize stats do jogo atual, mas inclua stats de temporada se forem impressionantes.
Use labels curtos e em português (ex: "gols na temporada", "passes certos", "finalizações").
Labels em minúsculo.

Responda APENAS com um JSON array de 5 objetos, cada um com "label" e "value".
Labels DEVEM ser em português brasileiro, curtos e sem siglas.
Exemplos de bons labels: "gols na temporada", "passes certos", "desarmes", "finalizações no gol", "jogos na temporada".

[{{"label": "...", "value": "..."}}, ...]"""

    async def select_stats(
        self,
        player: PlayerInfo,
        raw_stats: dict,
        match_context: str = "",
    ) -> list[StatItem]:
        if not raw_stats:
            return self._fallback_select(raw_stats, player)

        if self._provider == "fallback":
            return self._fallback_select(raw_stats, player)

        prompt = self._build_prompt(player, raw_stats, match_context)

        try:
            response = await asyncio.wait_for(
                self._call_llm(prompt),
                timeout=LLM_TIMEOUT,
            )
            # Extrair JSON do response
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            parsed = json.loads(text)
            # Groq json_object retorna {"data": [...]} ou {"stats": [...]}
            if isinstance(parsed, dict):
                for key in parsed:
                    if isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
            items = parsed
            if isinstance(items, list) and len(items) == 5:
                return [StatItem(label=s["label"], value=str(s["value"])) for s in items]
            logger.warning("LLM returned invalid format (%s items), using fallback", len(items) if isinstance(items, list) else "?")
        except asyncio.TimeoutError:
            logger.warning("LLM timeout (%.1fs), using fallback", LLM_TIMEOUT)
        except Exception:
            logger.warning("LLM call failed, using fallback", exc_info=True)

        return self._fallback_select(raw_stats, player)

    async def _call_llm(self, prompt: str) -> str:
        """Chama o LLM configurado (Groq ou Gemini)."""
        if self._provider == "groq":
            return await self._call_groq(prompt)
        return await self._call_gemini(prompt)

    async def _call_groq(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    async def _call_gemini(self, prompt: str) -> str:
        from google.genai import types
        response = await self._client.aio.models.generate_content(
            model=self._gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=300,
                response_mime_type="application/json",
            ),
        )
        return response.text

    def _fallback_select(self, raw_stats: dict, player: PlayerInfo) -> list[StatItem]:
        position = (player.position or "").lower()

        if "goalkeeper" in position or "goleiro" in position:
            priority = [
                "saves", "season_saves", "season_cleanSheets",
                "goalsConceded", "season_goalsConceded", "punches", "catches",
                "keeperSweeper", "season_appearances", "minsPlayed",
            ]
        elif "forward" in position or "atacante" in position or "striker" in position:
            priority = [
                "goals_in_match", "season_goals", "assists_in_match",
                "season_assists", "shotsOnTarget", "season_shotsOnTarget",
                "chancesCreated", "dribbles", "season_appearances", "minsPlayed",
            ]
        elif "midfield" in position or "meia" in position:
            priority = [
                "goals_in_match", "assists_in_match", "season_goals", "season_assists",
                "chancesCreated", "season_chancesCreated", "passesAccurate",
                "season_passesAccurate", "tacklesWon", "season_appearances",
            ]
        else:  # defender
            priority = [
                "tacklesWon", "season_tacklesWon", "interceptions",
                "season_interceptions", "clearances", "season_clearances",
                "aerialWon", "season_goals", "season_appearances", "minsPlayed",
            ]

        selected: list[StatItem] = []
        label_map = {
            # Match stats (snake_case e camelCase)
            "goals_in_match": "gols no jogo",
            "assists_in_match": "assistencias no jogo",
            "yellow_cards_in_match": "cartoes amarelos",
            "minsPlayed": "minutos jogados", "mins_played": "minutos jogados",
            "touches": "toques na bola",
            "passesTotal": "passes tentados", "passes_total": "passes tentados",
            "passesAccurate": "passes certos", "passes_accurate": "passes certos",
            "foulsCommitted": "faltas cometidas", "fouls_committed": "faltas cometidas",
            "foulsSuffered": "faltas sofridas", "fouls_suffered": "faltas sofridas",
            "duelsWon": "duelos ganhos", "duels_won": "duelos ganhos",
            "duelsLost": "duelos perdidos", "duels_lost": "duelos perdidos",
            "aerialWon": "duelos aereos ganhos", "aerial_won": "duelos aereos ganhos",
            "shotsTotal": "finalizacoes", "shots_total": "finalizacoes",
            "shotsOnTarget": "finalizacoes no gol", "shots_on_target": "finalizacoes no gol",
            "chancesCreated": "chances criadas", "chances_created": "chances criadas",
            "dribbles": "dribles certos",
            "offsides": "impedimentos",
            "tacklesWon": "desarmes", "tackles_won": "desarmes",
            "interceptions": "interceptacoes",
            "clearances": "cortes",
            "blockedShots": "chutes bloqueados", "blocked_shots": "chutes bloqueados",
            "crosses": "cruzamentos",
            "saves": "defesas",
            "punches": "socos", "catches": "encaixes",
            "keeperSweeper": "saidas do gol", "keeper_sweeper": "saidas do gol",
            "goalsConceded": "gols sofridos", "goals_conceded": "gols sofridos",
            # Season stats (prefixo season_)
            "season_appearances": "jogos na temporada",
            "season_minsPlayed": "minutos na temporada",
            "season_goals": "gols na temporada",
            "season_assists": "assistencias na temporada",
            "season_yellowCards": "cartoes amarelos na temporada",
            "season_redCards": "cartoes vermelhos na temporada",
            "season_shotsOnTarget": "finalizacoes no gol na temporada",
            "season_shotsTotal": "finalizacoes na temporada",
            "season_chancesCreated": "chances criadas na temporada",
            "season_passesAccurate": "passes certos na temporada",
            "season_tacklesWon": "desarmes na temporada",
            "season_interceptions": "interceptacoes na temporada",
            "season_clearances": "cortes na temporada",
            "season_saves": "defesas na temporada",
            "season_cleanSheets": "jogos sem sofrer gol",
            "season_goalsConceded": "gols sofridos na temporada",
            "goals": "gols", "assists": "assistencias",
        }

        def _humanize(key: str) -> str:
            """camelCase/snake_case -> label legivel."""
            if key in label_map:
                return label_map[key]
            words = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
            return words.replace("_", " ").lower()

        for key in priority:
            if key in raw_stats and len(selected) < 5:
                selected.append(StatItem(label=_humanize(key), value=str(raw_stats[key])))

        # Fill remaining slots with any available stats
        used_labels = {s.label for s in selected}
        for key, value in raw_stats.items():
            if len(selected) >= 5:
                break
            label = _humanize(key)
            if label not in used_labels:
                used_labels.add(label)
                selected.append(StatItem(label=label, value=str(value)))

        # Pad if still under 5
        while len(selected) < 5:
            selected.append(StatItem(label="-", value="-"))

        return selected[:5]
