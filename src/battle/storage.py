from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class BattleStorage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with closing(self.connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS battle_runs (
                        battle_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        max_turns INTEGER NOT NULL,
                        frame_count INTEGER NOT NULL DEFAULT 0,
                        winner TEXT,
                        red_score REAL,
                        blue_score REAL,
                        reason TEXT,
                        team_config_json TEXT NOT NULL,
                        scenario_config_json TEXT NOT NULL,
                        summary_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS battle_frames (
                        battle_id TEXT NOT NULL,
                        turn_index INTEGER NOT NULL,
                        turn INTEGER NOT NULL,
                        frame_json TEXT NOT NULL,
                        PRIMARY KEY (battle_id, turn_index),
                        FOREIGN KEY (battle_id) REFERENCES battle_runs(battle_id) ON DELETE CASCADE
                    )
                    """
                )

    def upsert_run(
        self,
        *,
        battle_id: str,
        status: str,
        mode: str,
        max_turns: int,
        frame_count: int,
        team_config: dict[str, Any],
        scenario_config: dict[str, Any],
        summary: dict[str, Any] | None,
    ) -> None:
        result = (summary or {}).get("result") or {}
        winner = result.get("winner")
        reason = result.get("reason")
        red_score = result.get("red_score")
        blue_score = result.get("blue_score")
        now = _utc_now()
        with closing(self.connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO battle_runs (
                        battle_id, created_at, updated_at, status, mode, max_turns,
                        frame_count, winner, red_score, blue_score, reason,
                        team_config_json, scenario_config_json, summary_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(battle_id) DO UPDATE SET
                        updated_at=excluded.updated_at,
                        status=excluded.status,
                        mode=excluded.mode,
                        max_turns=excluded.max_turns,
                        frame_count=excluded.frame_count,
                        winner=excluded.winner,
                        red_score=excluded.red_score,
                        blue_score=excluded.blue_score,
                        reason=excluded.reason,
                        team_config_json=excluded.team_config_json,
                        scenario_config_json=excluded.scenario_config_json,
                        summary_json=excluded.summary_json
                    """,
                    (
                        battle_id,
                        now,
                        now,
                        status,
                        mode,
                        int(max_turns),
                        int(frame_count),
                        winner,
                        red_score,
                        blue_score,
                        reason,
                        _json_dumps(team_config),
                        _json_dumps(scenario_config),
                        _json_dumps(summary) if summary is not None else None,
                    ),
                )

    def upsert_frame(self, battle_id: str, turn_index: int, frame: dict[str, Any]) -> None:
        with closing(self.connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO battle_frames (battle_id, turn_index, turn, frame_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(battle_id, turn_index) DO UPDATE SET
                        turn=excluded.turn,
                        frame_json=excluded.frame_json
                    """,
                    (battle_id, int(turn_index), int(frame.get("turn", turn_index)), _json_dumps(frame)),
                )

    def load_run(self, battle_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT * FROM battle_runs WHERE battle_id = ?", (battle_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_history_item(row, include_payload=True)

    def load_frames(self, battle_id: str) -> list[dict[str, Any]]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT frame_json FROM battle_frames WHERE battle_id = ? ORDER BY turn_index ASC",
                (battle_id,),
            ).fetchall()
        return [_json_loads(row["frame_json"], {}) for row in rows]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM battle_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [self._row_to_history_item(row) for row in rows]

    def _row_to_history_item(self, row: sqlite3.Row, include_payload: bool = False) -> dict[str, Any]:
        item = {
            "battle_id": row["battle_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "mode": row["mode"],
            "max_turns": row["max_turns"],
            "frame_count": row["frame_count"],
            "winner": row["winner"],
            "red_score": row["red_score"],
            "blue_score": row["blue_score"],
            "reason": row["reason"],
        }
        if include_payload:
            item["team_config"] = _json_loads(row["team_config_json"], {})
            item["scenario_config"] = _json_loads(row["scenario_config_json"], {})
            item["summary"] = _json_loads(row["summary_json"], None)
        return item
