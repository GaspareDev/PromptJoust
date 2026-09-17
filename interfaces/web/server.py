"""
PromptJoust Web API Server.

FastAPI application providing:
- Boss roster endpoint (`GET /api/bosses`)
- Available LLM providers endpoint (`GET /api/providers`)
- Real-time match simulation endpoint (`POST /api/simulate`)
- Static file serving for the Cyberpunk Web SPA UI
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from models import (
    BossData,
    MatchResult,
    FighterStats,
    DifficultyLevel,
    DIFFICULTY_CONFIGS,
    SimulationRequest,
)
from core.config import settings
from core.sanitizer import (
    validate_and_allocate_stats,
    sanitize_tactical_prompt,
    SanitizationError,
    EXTRA_ATTRIBUTE_POINTS,
    MAX_PROMPT_LENGTH,
)
from core.engine import MatchEngine
from providers import get_provider, PROVIDERS


app = FastAPI(
    title="PromptJoust API",
    description="Autonomous LLM Tactical RPG Arena Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content" / "bosses"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def load_bosses() -> Dict[str, BossData]:
    """
    Scans the `content/bosses/*.json` directory and loads all Boss dossier models.
    """
    bosses = {}
    for f in sorted(CONTENT_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                boss = BossData.model_validate(data)
                bosses[boss.id] = boss
        except Exception:
            pass
    return bosses


@app.get("/api/bosses")
def get_bosses():
    """
    Returns public dossier details for all available bosses.
    Excludes `secret_personality_prompt` to protect game integrity.
    """
    bosses = load_bosses()
    public_bosses = []
    for b in bosses.values():
        public_bosses.append({
            "id": b.id,
            "name": b.name,
            "floor": b.floor,
            "stats": b.stats.to_dict(),
            "public_lore": b.public_lore,
            "visible_hints": b.visible_hints,
        })
    return public_bosses


@app.get("/api/providers")
def get_providers():
    """
    Returns list of configured and supported LLM provider names.
    """
    return list(PROVIDERS.keys())


@app.get("/api/difficulties")
def get_difficulties():
    """
    Returns metadata and combat modifiers for all difficulty tiers.
    """
    return [cfg.model_dump() for cfg in DIFFICULTY_CONFIGS.values()]


@app.post("/api/simulate", response_model=MatchResult)
async def simulate_match(req: SimulationRequest):
    """
    Executes a complete 10-round combat simulation against the selected Boss.

    1. Validates boss existence.
    2. Validates and allocates stat bonuses according to chosen difficulty.
    3. Sanitizes user tactical prompt enforcing character limits.
    4. Initializes requested LLM provider (or defaults to environment config).
    5. Runs MatchEngine loop with scaled boss stats and returns full RoundLog & MatchResult.
    """
    bosses = load_bosses()
    if req.boss_id not in bosses:
        raise HTTPException(status_code=404, detail=f"Boss '{req.boss_id}' not found.")

    boss = bosses[req.boss_id]

    try:
        hero_stats = validate_and_allocate_stats(
            hp_bonus=req.hp_bonus,
            atk_bonus=req.atk_bonus,
            def_bonus=req.def_bonus,
            sta_bonus=req.sta_bonus,
            difficulty=req.difficulty,
        )
    except SanitizationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        clean_prompt = sanitize_tactical_prompt(req.tactical_prompt, difficulty=req.difficulty, allow_empty=True)
    except SanitizationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        provider = get_provider(
            provider_name=req.provider,
            api_key=req.api_key,
            model=req.model,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Provider initialization error: {e}")

    engine = MatchEngine(
        hero_name=req.hero_name,
        hero_stats=hero_stats,
        hero_prompt=clean_prompt,
        boss=boss,
        provider=provider,
        difficulty=req.difficulty,
    )

    result = await engine.run_match_async()
    return result


@app.post("/api/simulate/stream")
async def simulate_match_stream(req: SimulationRequest):
    """
    Executes real-time turn-by-turn combat simulation streaming events via Server-Sent Events (SSE).

    Emits SSE events:
    - 'init': initial combatant stats and match configuration
    - 'round': generated RoundLog after each turn resolves
    - 'complete': final MatchResult upon tournament conclusion
    """
    bosses = load_bosses()
    if req.boss_id not in bosses:
        raise HTTPException(status_code=404, detail=f"Boss '{req.boss_id}' not found.")

    boss = bosses[req.boss_id]

    try:
        hero_stats = validate_and_allocate_stats(
            hp_bonus=req.hp_bonus,
            atk_bonus=req.atk_bonus,
            def_bonus=req.def_bonus,
            sta_bonus=req.sta_bonus,
            difficulty=req.difficulty,
        )
    except SanitizationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        clean_prompt = sanitize_tactical_prompt(req.tactical_prompt, difficulty=req.difficulty, allow_empty=True)
    except SanitizationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        provider = get_provider(
            provider_name=req.provider,
            api_key=req.api_key,
            model=req.model,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Provider initialization error: {e}")

    engine = MatchEngine(
        hero_name=req.hero_name,
        hero_stats=hero_stats,
        hero_prompt=clean_prompt,
        boss=boss,
        provider=provider,
        difficulty=req.difficulty,
    )

    async def event_generator():
        async for item in engine.stream_match():
            event_name = item["event"]
            payload = json.dumps(item["data"])
            yield f"event: {event_name}\ndata: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")



if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def run():
    import uvicorn
    print("\n" + "=" * 60)
    print("⚔️ PROMPT JOUST WEB ARENA")
    print(f"👉 Open in browser: http://localhost:{settings.server_port} or http://127.0.0.1:{settings.server_port}")
    print("=" * 60 + "\n")
    reload_env = os.getenv("RELOAD", "true" if settings.debug else "false").lower() == "true"
    uvicorn.run("interfaces.web.server:app", host=settings.server_host, port=settings.server_port, reload=reload_env)


if __name__ == "__main__":
    run()

