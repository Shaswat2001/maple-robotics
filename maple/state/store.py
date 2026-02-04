"""
State management for the MAPLE daemon.

This module provides persistent state tracking using SQLite for the MAPLE
daemon. It manages policies, environments, containers, and evaluation runs
with a robust database-backed storage system.

Key features:
- SQLite-based persistent storage with WAL mode for concurrency
- Policy and environment registry tracking
- Container lifecycle management (both policies and environments)
- Evaluation run history and statistics
- Automatic database initialization and schema management
- Context manager for safe database operations

The database schema includes:
- policies: Downloaded/pulled policy models
- envs: Downloaded environment images
- containers: Currently running containers (policies and envs)
- runs: Evaluation run history with metrics and outcomes

All database operations use proper transaction handling and support
concurrent access through SQLite's WAL (Write-Ahead Logging) mode.
"""

import json
import time
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import List, Optional, Dict

from maple.utils.logging import get_logger

log = get_logger("state")

STATE_DIR = Path.home() / ".maple"
DB_FILE = STATE_DIR / "state.db"

def _ensure_dir() -> None:
    """
    Ensure the state directory exists.
    
    Creates the MAPLE state directory with proper permissions if it
    doesn't already exist. Safe to call multiple times.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)

@contextmanager
def _get_conn():
    """
    Get a database connection with proper settings.
    
    Context manager that provides a configured SQLite connection with
    WAL mode enabled for better concurrent access, foreign key constraints
    enabled, and row factory set for dictionary-style column access.
    
    Automatically commits on success and rolls back on exceptions. Always
    closes the connection when exiting the context.
    
    :return: SQLite connection object configured for MAPLE state management.
    """
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

def init_db() -> None:
    """
    Initialize database schema.
    
    Creates all required tables and indexes if they don't exist. Safe to
    call multiple times (idempotent). Tables include policies, envs,
    containers, and runs with appropriate indexes for common queries.
    
    Automatically called on module import to ensure database is ready.
    """
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
    """
    Add or update a pulled policy.
    
    Registers a downloaded policy model in the database. If a policy with
    the same name and version already exists, updates its path, repo, and
    pulled timestamp.
    
    :param name: Name of the policy model.
    :param version: Version identifier of the policy.
    :param path: Filesystem path where the policy is stored.
    :param repo: Optional repository URL or identifier.
    :return: Database row ID of the inserted or updated policy.
    """
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


def get_policy(name: str, version: str) -> Optional[Dict]:
    """
    Get a pulled policy.
    
    Retrieves policy information from the database by name and version.
    
    :param name: Name of the policy model.
    :param version: Version identifier of the policy.
    :return: Dictionary containing policy data, or None if not found.
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM policies WHERE name = ? AND version = ?",
            (name, version)
        ).fetchone()
        return dict(row) if row else None


def list_policies() -> List[Dict]:
    """
    List all pulled policies.
    
    Returns all registered policies ordered by most recently pulled first.
    
    :return: List of dictionaries containing policy data.
    """
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM policies ORDER BY pulled_at DESC").fetchall()
        return [dict(row) for row in rows]


def remove_policy(name: str, version: str) -> bool:
    """
    Remove a pulled policy.
    
    Deletes a policy record from the database. Does not delete the actual
    model files from disk.
    
    :param name: Name of the policy model.
    :param version: Version identifier of the policy.
    :return: True if a policy was deleted, False if not found.
    """
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM policies WHERE name = ? AND version = ?",
            (name, version)
        )
        return cursor.rowcount > 0


def add_env(name: str, image: str) -> int:
    """
    Add or update a pulled environment.
    
    Registers a downloaded environment in the database. If an environment
    with the same name already exists, updates its image and pulled timestamp.
    
    :param name: Name of the environment.
    :param image: Docker image identifier.
    :return: Database row ID of the inserted or updated environment.
    """
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
    """
    Get a pulled environment.
    
    Retrieves environment information from the database by name.
    
    :param name: Name of the environment.
    :return: Dictionary containing environment data, or None if not found.
    """
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM envs WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def list_envs() -> List[dict]:
    """
    List all pulled environments.
    
    Returns all registered environments ordered by most recently pulled first.
    
    :return: List of dictionaries containing environment data.
    """
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
    """
    Register a running container.
    
    Adds a container to the tracking database. If a container with the same
    ID already exists, replaces it with the new information.
    
    :param container_id: Unique container identifier.
    :param type: Container type ('policy' or 'env').
    :param name: Human-readable container name.
    :param backend: Container backend being used.
    :param host: Host address where container is running.
    :param port: Port number for container communication.
    :param status: Current container status.
    :param metadata: Optional dictionary of additional container metadata.
    
    :return: The container ID that was registered.
    """
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
    """
    Update container status.
    
    Changes the status field for a tracked container.
    
    :param container_id: Unique container identifier.
    :param status: New status value to set.
    """
    with _get_conn() as conn:
        conn.execute(
            "UPDATE containers SET status = ? WHERE id = ?",
            (status, container_id)
        )


def remove_container(container_id: str) -> bool:
    """
    Remove a container from tracking.
    
    Deletes a container record from the database. Does not stop or remove
    the actual container.
    
    :param container_id: Unique container identifier.
    
    :return: True if a container was removed, False if not found.
    """
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM containers WHERE id = ?", (container_id,))
        return cursor.rowcount > 0


def get_container(container_id: str) -> Optional[dict]:
    """
    Get a container by ID.
    
    Retrieves container information from the database. Deserializes the
    metadata JSON field into a dictionary.
    
    :param container_id: Unique container identifier.
    
    :return: Dictionary containing container data with parsed metadata, or None if not found.
    """
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM containers WHERE id = ?", (container_id,)).fetchone()
        if row:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            return d
        return None


def get_container_by_name(name: str) -> Optional[dict]:
    """
    Get a container by name.
    
    Retrieves container information from the database by container name.
    Deserializes the metadata JSON field into a dictionary.
    
    :param name: Container name to search for.
    
    :return: Dictionary containing container data with parsed metadata, or None if not found.
    """
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM containers WHERE name = ?", (name,)).fetchone()
        if row:
            d = dict(row)
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            return d
        return None


def list_containers(type: str = None, status: str = None) -> List[dict]:
    """
    List containers with optional filters.
    
    Returns all tracked containers, optionally filtered by type and/or status.
    Results are ordered by most recently started first. Deserializes metadata
    for all returned containers.
    
    :param type: Optional filter for container type ('policy' or 'env').
    :param status: Optional filter for container status.
    
    :return: List of dictionaries containing container data with parsed metadata.
    """
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
    """
    Clear all container records.
    
    Removes all container tracking entries from the database. Typically used
    when the daemon restarts to clean up stale container references.
    """
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
    """
    Start tracking a run.
    
    Creates a new evaluation run record in the database with initial metadata.
    The run starts in an incomplete state until finish_run() is called.
    
    :param run_id: Unique identifier for this run.
    :param policy_id: Identifier of the policy being evaluated.
    :param env_id: Identifier of the environment being used.
    :param task: Task name or identifier.
    :param instruction: Optional natural language instruction for the task.
    :param metadata: Optional dictionary of additional run metadata.
    
    :return: The run ID that was registered.
    """
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO runs (id, policy_id, env_id, task, instruction, started_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, policy_id, env_id, task, instruction, time.time(), json.dumps(metadata or {})))
    return run_id


def finish_run(run_id: str,
               steps: int,
               total_reward: float,
               success: bool,
               terminated: bool,
               truncated: bool,
               video_path: str = None,
            ) -> None:
    """
    Record run completion.
    
    Updates a run record with final metrics and outcome information.
    
    :param run_id: Unique identifier of the run to update.
    :param steps: Number of steps taken during the run.
    :param total_reward: Cumulative reward achieved.
    :param success: Whether the run was successful.
    :param terminated: Whether the episode terminated naturally.
    :param truncated: Whether the episode was truncated (e.g., timeout).
    :param video_path: Optional path to recorded video of the run.
    """
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


def get_run(run_id: str) -> Optional[Dict]:
    """
    Get a run by ID.
    
    Retrieves run information from the database. Deserializes the metadata
    JSON field and converts integer boolean fields back to Python booleans.
    
    :param run_id: Unique identifier of the run.
    :return: Dictionary containing run data with parsed metadata and boolean fields, or None if not found.
    """
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


def list_runs(policy_id: str = None, task: str = None, limit: int = 100) -> List[Dict]:
    """
    List runs with optional filters.
    
    Returns evaluation runs, optionally filtered by policy ID and/or task name.
    Results are ordered by most recent first and limited to the specified count.
    Deserializes metadata for all returned runs.
    
    :param policy_id: Optional filter for runs using a specific policy.
    :param task: Optional filter for runs of a specific task (partial match).
    :param limit: Maximum number of runs to return.
    :return: List of dictionaries containing run data with parsed metadata.
    """
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


def get_run_stats(policy_id: str = None, task: str = None) -> Dict:
    """
    Get aggregate statistics for runs.
    
    Computes summary statistics across completed runs, optionally filtered
    by policy ID and/or task name. Includes success rates, reward statistics,
    and step counts.
    
    :param policy_id: Optional filter for runs using a specific policy.
    :param task: Optional filter for runs of a specific task (partial match).
    :return: Dictionary containing aggregate statistics including total runs,
           successful runs, success rate, and reward/step averages and extrema.
    """
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


def load_state() -> Dict:
    """
    Legacy function for backwards compatibility.
    
    Returns the current state in the old JSON format for compatibility with
    code that expects the previous state management structure.
    
    :return: Dictionary containing lists of policies, environments, and containers.
    """
    init_db()
    return {
        "policies": list_policies(),
        "envs": list_envs(),
        "containers": list_containers(),
    }


# Initialize on import
init_db()