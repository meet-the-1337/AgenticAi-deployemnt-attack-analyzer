"""
reconmind.platform_.memory
==========================
Session memory store service.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from reconmind.config import cfg

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(cfg.database.resolved_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def read_memory(session_id: str, key: str) -> Optional[Any]:
    """Read the latest version of a key for a given session."""
    sql = """
        SELECT value FROM session_memory
        WHERE session_id = ? AND key = ?
        ORDER BY version DESC LIMIT 1
    """
    with _get_conn() as conn:
        row = conn.execute(sql, (session_id, key)).fetchone()
        if row:
            return json.loads(row[0])
    return None

def write_memory(session_id: str, key: str, value: Any, written_by_agent: str) -> None:
    """Write a new version of a key to the memory store."""
    sql_version = """
        SELECT MAX(version) FROM session_memory
        WHERE session_id = ? AND key = ?
    """
    sql_insert = """
        INSERT INTO session_memory (
            memory_id, session_id, key, value, version, written_by_agent, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with _get_conn() as conn:
        row = conn.execute(sql_version, (session_id, key)).fetchone()
        current_version = row[0] if row[0] is not None else 0
        new_version = current_version + 1
        
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        value_str = json.dumps(value)
        
        conn.execute(sql_insert, (
            memory_id, session_id, key, value_str, new_version, written_by_agent, timestamp
        ))
        conn.commit()
def clear_session_memory(session_id: str) -> None:
    """Delete all memory entries for a given session.
    Used by the campaign runner to ensure isolation between runs.
    """
    sql = """
        DELETE FROM session_memory WHERE session_id = ?
    """
    with _get_conn() as conn:
        conn.execute(sql, (session_id,))
        conn.commit()
