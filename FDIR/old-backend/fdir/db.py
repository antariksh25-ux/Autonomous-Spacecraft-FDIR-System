from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class SqliteRepo:
    def __init__(self, db_path: Path):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp_iso TEXT NOT NULL,
              channel TEXT NOT NULL,
              value REAL NOT NULL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(timestamp_iso);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_channel_ts ON telemetry(channel, timestamp_iso);")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS faults (
              fault_id TEXT PRIMARY KEY,
              timestamp_iso TEXT NOT NULL,
              subsystem TEXT NOT NULL,
              component TEXT NOT NULL,
              fault_type TEXT NOT NULL,
              severity TEXT NOT NULL,
              confidence REAL NOT NULL,
              ethical_level TEXT NOT NULL,
              ethical_justification TEXT NOT NULL,
              action_taken TEXT,
              action_rationale TEXT,
              escalated INTEGER NOT NULL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_faults_ts ON faults(timestamp_iso);")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
              seq INTEGER PRIMARY KEY,
              timestamp_iso TEXT NOT NULL,
              level TEXT NOT NULL,
              stage TEXT NOT NULL,
              message TEXT NOT NULL,
              details_json TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def insert_telemetry(self, timestamp_iso: str, values: Dict[str, float]) -> None:
        cur = self._conn.cursor()
        rows = [(timestamp_iso, k, float(v)) for k, v in values.items()]
        if rows:
            cur.executemany("INSERT INTO telemetry(timestamp_iso, channel, value) VALUES (?, ?, ?)", rows)
            self._conn.commit()

    def upsert_fault(self, row: Dict[str, Any]) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO faults(
              fault_id, timestamp_iso, subsystem, component, fault_type, severity, confidence,
              ethical_level, ethical_justification, action_taken, action_rationale, escalated
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fault_id) DO UPDATE SET
              timestamp_iso=excluded.timestamp_iso,
              subsystem=excluded.subsystem,
              component=excluded.component,
              fault_type=excluded.fault_type,
              severity=excluded.severity,
              confidence=excluded.confidence,
              ethical_level=excluded.ethical_level,
              ethical_justification=excluded.ethical_justification,
              action_taken=excluded.action_taken,
              action_rationale=excluded.action_rationale,
              escalated=excluded.escalated;
            """,
            (
                row["fault_id"],
                row["timestamp_iso"],
                row["subsystem"],
                row["component"],
                row["fault_type"],
                row["severity"],
                float(row["confidence"]),
                row["ethical_level"],
                row["ethical_justification"],
                row.get("action_taken"),
                row.get("action_rationale"),
                int(bool(row.get("escalated"))),
            ),
        )
        self._conn.commit()

    def insert_log(self, seq: int, timestamp_iso: str, level: str, stage: str, message: str, details_json: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO logs(seq, timestamp_iso, level, stage, message, details_json) VALUES (?, ?, ?, ?, ?, ?)",
            (seq, timestamp_iso, level, stage, message, details_json),
        )
        self._conn.commit()

    def list_faults(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM faults ORDER BY timestamp_iso DESC LIMIT ?", (max(1, int(limit)),))
        return [dict(r) for r in cur.fetchall()]

    def list_logs(self, since_seq: int = 0, limit: int = 200) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM logs WHERE seq > ? ORDER BY seq ASC LIMIT ?",
            (int(since_seq), max(1, int(limit))),
        )
        return [dict(r) for r in cur.fetchall()]
