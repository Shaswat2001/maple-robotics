import sqlite3
import json
import time
from pathlib import Path
from typing import List, Optional
from contextlib import contextmanager

from vla.utils.logging import get_logger

log = get_logger("state")

STATE_DIR = Path.home() / ".vla"
DB_FILE = STATE_DIR / "state.db"


def _ensure_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _get_conn():
    """Get a database connection with proper settings."""
    _ensure_dir()
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row  # Access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with _get_conn() as conn:
        conn.executescript("""
            -- Pulled policy models
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                path TEXT NOT NULL,
                repo TEXT,
                pulled_at REAL NOT NULL,
                UNIQUE(name, version)
            );
            
            -- Pulled environments
            CREATE TABLE IF NOT EXISTS envs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                image TEXT NOT NULL,
                pulled_at REAL NOT NULL
            );
            
            -- Running containers (both policies and envs)
            CREATE TABLE IF NOT EXISTS containers (
                id TEXT PRIMARY KEY,  -- container_id
                type TEXT NOT NULL,   -- 'policy' or 'env'
                name TEXT NOT NULL,   -- e.g., 'openvla-7b-abc123'
                backend TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                metadata TEXT  -- JSON blob for extra data
            );
            
            -- Evaluation run history
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,  -- run_id
                policy_id TEXT NOT NULL,
                env_id TEXT NOT NULL,
                task TEXT NOT NULL,
                instruction TEXT,
                started_at REAL NOT NULL,
                finished_at REAL,
                steps INTEGER,
                total_reward REAL,
                success INTEGER,  -- 0 or 1
                terminated INTEGER,
                truncated INTEGER,
                video_path TEXT,
                metadata TEXT  -- JSON blob
            );
            
            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_containers_type ON containers(type);
            CREATE INDEX IF NOT EXISTS idx_containers_status ON containers(status);
            CREATE INDEX IF NOT EXISTS idx_runs_policy ON runs(policy_id);
            CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task);
        """)
    log.debug("Database initialized")

def add_policy(name: str, version: str, path: str, repo: str = None) -> int:
    """Add or update a pulled policy."""
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO policies (name, version, path, repo, pulled_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name, version) DO UPDATE SET
                path = excluded.path,
                repo = excluded.repo,
                pulled_at = excluded.pulled_at
        """, (name, version, path, repo, time.time()))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_policy(name: str, version: str) -> Optional[dict]:
    """Get a pulled policy."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM policies WHERE name = ? AND version = ?",
            (name, version)
        ).fetchone()
        return dict(row) if row else None


def list_policies() -> List[dict]:
    """List all pulled policies."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM policies ORDER BY pulled_at DESC").fetchall()
        return [dict(row) for row in rows]


def remove_policy(name: str, version: str) -> bool:
    """Remove a pulled policy."""
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM policies WHERE name = ? AND version = ?",
            (name, version)
        )
        return cursor.rowcount > 0

def add_env(name: str, image: str) -> int:
    """Add or update a pulled environment."""
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO envs (name, image, pulled_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                image = excluded.image,
                pulled_at = excluded.pulled_at
        """, (name, image, time.time()))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_env(name: str) -> Optional[dict]:
    """Get a pulled environment."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM envs WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def list_envs() -> List[dict]:
    """List all pulled environments."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM envs ORDER BY pulled_at DESC").fetchall()
        return [dict(row) for row in rows]

def add_container(
    container_id: str,
    type: str,
    name: str,
    backend: str,
    host: str,
    port: int,
    status: str = "starting",
    metadata: dict = None,
) -> str:
    """Register a running container."""
    with _get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO containers 
            (id, type, name, backend, host, port, status, started_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            container_id, type, name, backend, host, port, status,
            time.time(), json.dumps(metadata or {})
        ))
    return container_id


def update_container_status(container_id: str, status: str):
    """Update container status."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE containers SET status = ? WHERE id = ?",
            (status, container_id)
        )


def remove_container(container_id: str) -> bool:
    """Remove a container from tracking."""
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM containers WHERE id = ?", (container_id,))
        return cursor.rowcount > 0


def get_container(container_id: str) -> Optional[dict]:
    """Get a container by ID."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM containers WHERE id = ?", (container_id,)).fetchone()
        if row:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            return d
        return None


def get_container_by_name(name: str) -> Optional[dict]:
    """Get a container by name."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM containers WHERE name = ?", (name,)).fetchone()
        if row:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            return d
        return None


def list_containers(type: str = None, status: str = None) -> List[dict]:
    """List containers with optional filters."""
    query = "SELECT * FROM containers WHERE 1=1"
    params = []
    
    if type:
        query += " AND type = ?"
        params.append(type)
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY started_at DESC"
    
    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            result.append(d)
        return result


def clear_containers():
    """Clear all container records (for daemon restart)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM containers")

def add_run(
    run_id: str,
    policy_id: str,
    env_id: str,
    task: str,
    instruction: str = None,
    metadata: dict = None,
) -> str:
    """Start tracking a run."""
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO runs (id, policy_id, env_id, task, instruction, started_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, policy_id, env_id, task, instruction, time.time(), json.dumps(metadata or {})))
    return run_id


def finish_run(
    run_id: str,
    steps: int,
    total_reward: float,
    success: bool,
    terminated: bool,
    truncated: bool,
    video_path: str = None,
):
    """Record run completion."""
    with _get_conn() as conn:
        conn.execute("""
            UPDATE runs SET
                finished_at = ?,
                steps = ?,
                total_reward = ?,
                success = ?,
                terminated = ?,
                truncated = ?,
                video_path = ?
            WHERE id = ?
        """, (time.time(), steps, total_reward, int(success), int(terminated), int(truncated), video_path, run_id))


def get_run(run_id: str) -> Optional[dict]:
    """Get a run by ID."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            d["success"] = bool(d["success"]) if d["success"] is not None else None
            d["terminated"] = bool(d["terminated"]) if d["terminated"] is not None else None
            d["truncated"] = bool(d["truncated"]) if d["truncated"] is not None else None
            return d
        return None


def list_runs(
    policy_id: str = None,
    task: str = None,
    limit: int = 100,
) -> List[dict]:
    """List runs with optional filters."""
    query = "SELECT * FROM runs WHERE 1=1"
    params = []
    
    if policy_id:
        query += " AND policy_id = ?"
        params.append(policy_id)
    if task:
        query += " AND task LIKE ?"
        params.append(f"%{task}%")
    
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    
    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            d["success"] = bool(d["success"]) if d["success"] is not None else None
            result.append(d)
        return result


def get_run_stats(policy_id: str = None, task: str = None) -> dict:
    """Get aggregate stats for runs."""
    query = """
        SELECT 
            COUNT(*) as total_runs,
            SUM(success) as successful_runs,
            AVG(total_reward) as avg_reward,
            AVG(steps) as avg_steps,
            MIN(total_reward) as min_reward,
            MAX(total_reward) as max_reward
        FROM runs
        WHERE finished_at IS NOT NULL
    """
    params = []
    
    if policy_id:
        query += " AND policy_id = ?"
        params.append(policy_id)
    if task:
        query += " AND task LIKE ?"
        params.append(f"%{task}%")
    
    with _get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return {
            "total_runs": row["total_runs"] or 0,
            "successful_runs": row["successful_runs"] or 0,
            "success_rate": (row["successful_runs"] / row["total_runs"]) if row["total_runs"] else 0,
            "avg_reward": row["avg_reward"],
            "avg_steps": row["avg_steps"],
            "min_reward": row["min_reward"],
            "max_reward": row["max_reward"],
        }

def load_state() -> dict:
    """
    Legacy function for backwards compatibility.
    Returns state in the old JSON format.
    """
    init_db()
    return {
        "policies": list_policies(),
        "envs": list_envs(),
        "containers": list_containers(),
    }

# Initialize on import
init_db()
