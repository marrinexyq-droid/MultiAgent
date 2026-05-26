from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .api_runtime import (
    manager,
    serialize_default_hex_scenario_config,
    serialize_default_scenario_config,
    serialize_default_team_config,
    serialize_role_templates,
    stream_battle,
)
from .config import config
from .terrain import TERRAIN_PRESETS
from .fantasy_api import router as fantasy_router


class BattleCreateRequest(BaseModel):
    mode: str = Field(default="实时推演")
    max_turns: int = Field(default_factory=lambda: config.max_turns)
    team_config: dict | None = None
    scenario_config: dict | None = None


class BattleStartRequest(BaseModel):
    mode: str | None = None


app = FastAPI(title="Battle Console API", version="0.1.0")
app.include_router(fantasy_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/roles")
def get_roles():
    return {
        "default_max_turns": config.max_turns,
        "roles": serialize_role_templates(),
        "default_team_config": serialize_default_team_config(),
        "default_scenario_config": serialize_default_scenario_config(),
        "default_hex_scenario_config": serialize_default_hex_scenario_config(),
        "terrain_presets": {key: {"label": label, "description": desc} for key, (label, desc) in TERRAIN_PRESETS.items()},
    }


@app.post("/api/battles")
def create_battle(payload: BattleCreateRequest):
    session = manager.create_session(payload.mode, payload.max_turns, payload.team_config, payload.scenario_config)
    return {
        "battle_id": session.battle_id,
        "status": session.status,
        "mode": session.mode,
        "max_turns": session.max_turns,
        "scenario_config": session.scenario_config_payload,
        "initial_frame": session.frames[0],
    }


@app.post("/api/battles/{battle_id}/start")
def start_battle(battle_id: str, payload: BattleStartRequest):
    try:
        session = manager.get(battle_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="battle not found") from exc
    if payload.mode:
        session.mode = payload.mode
    session.start()
    return {"battle_id": battle_id, "status": session.status, "mode": session.mode}


@app.get("/api/battles/{battle_id}/stream")
def stream_battle_route(battle_id: str):
    try:
        session = manager.get(battle_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="battle not found") from exc
    return StreamingResponse(stream_battle(session), media_type="text/event-stream")


@app.get("/api/battles/{battle_id}/frames")
def get_frames(battle_id: str):
    try:
        session = manager.get(battle_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="battle not found") from exc
    frames = session.run_all()
    return {
        "battle_id": battle_id,
        "status": session.status,
        "mode": session.mode,
        "frames": frames,
        "summary": session.result,
    }


@app.get("/api/battles/{battle_id}/frame/{turn}")
def get_frame(battle_id: str, turn: int):
    try:
        session = manager.get(battle_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="battle not found") from exc
    frames = session.run_all()
    if turn < 0 or turn >= len(frames):
        raise HTTPException(status_code=404, detail="turn not found")
    return {
        "battle_id": battle_id,
        "turn": turn,
        "frame": frames[turn],
        "summary": session.result,
    }


@app.get("/api/battles/{battle_id}/summary")
def get_summary(battle_id: str):
    try:
        session = manager.get(battle_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="battle not found") from exc
    if session.result is None:
        session.run_all()
    return session.summary_payload()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.battle.api_server:app", host="0.0.0.0", port=8000, reload=False)
