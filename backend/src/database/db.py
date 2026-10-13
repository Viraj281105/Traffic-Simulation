import contextlib
import os
import sqlite3
import threading
from typing import Generator, Set

DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "simulation.db")
)
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB_PATH)

# Database files init_db() has already prepared in this process.
_initialized_paths: Set[str] = set()
_initialized_paths_lock = threading.Lock()
# Serialises ensure_db_initialized()'s slow path. Concurrent init_db() runs on
# one file race each other's migrations (both read a column as missing, both
# ALTER TABLE) and fail with "database is locked" / "duplicate column name".
_init_lock = threading.Lock()


def init_db() -> None:
    """Initializes the SQLite database tables if they do not exist, and applies safe migrations."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # closing(): a failed statement must not leak the connection. The CREATE
    # and ALTER statements each take effect as they run, so a retry after a
    # partial failure resumes where this one stopped.
    with contextlib.closing(sqlite3.connect(DB_PATH, timeout=5.0)) as conn:
        _create_schema(conn)

    with _initialized_paths_lock:
        _initialized_paths.add(DB_PATH)


def _create_schema(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # Enable WAL mode, busy timeout, and Foreign Key support
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Configurations table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS configurations (
            id TEXT PRIMARY KEY,
            config_json TEXT NOT NULL
        );
        """
    )

    # 2. Simulation Runs table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            status TEXT NOT NULL,
            elapsed REAL NOT NULL,
            intersection_type TEXT NOT NULL DEFAULT 'unknown',
            random_seed INTEGER NOT NULL DEFAULT 0,
            arrival_rate REAL DEFAULT 0.5,
            duration REAL DEFAULT 60.0,
            batch_id TEXT,
            config_json TEXT NOT NULL DEFAULT '{}',
            summary_metrics_json TEXT NOT NULL DEFAULT '{}',
            git_commit TEXT,
            provenance_json TEXT,
            name TEXT,
            notes TEXT,
            tags_json TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 3. Scenario Suites table (V1.7)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_suites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            run_ids_json TEXT NOT NULL DEFAULT '[]',
            config_variations_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Safe migration: ensure existing tables receive any missing columns
    cursor.execute("PRAGMA table_info(simulation_runs);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    columns_to_add = [
        ("intersection_type", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("random_seed", "INTEGER NOT NULL DEFAULT 0"),
        ("arrival_rate", "REAL DEFAULT 0.5"),
        ("duration", "REAL DEFAULT 60.0"),
        ("batch_id", "TEXT"),
        ("config_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("summary_metrics_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("git_commit", "TEXT"),
        ("provenance_json", "TEXT"),
        ("name", "TEXT"),
        ("notes", "TEXT"),
        ("tags_json", "TEXT"),
        ("user_id", "TEXT"),
        ("email", "TEXT"),
        ("suite_id", "TEXT"),
    ]
    for col_name, col_def in columns_to_add:
        if col_name not in existing_cols:
            cursor.execute(
                f"ALTER TABLE simulation_runs ADD COLUMN {col_name} {col_def};"
            )

    # Scenario suites belong to their creator. Suites stored before this
    # column existed keep user_id NULL and are visible to admins only.
    cursor.execute("PRAGMA table_info(scenario_suites);")
    if "user_id" not in {row[1] for row in cursor.fetchall()}:
        cursor.execute("ALTER TABLE scenario_suites ADD COLUMN user_id TEXT;")

    # Indexes on simulation_runs for fast querying and filtering
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sim_runs_type ON simulation_runs(intersection_type);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sim_runs_seed ON simulation_runs(random_seed);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sim_runs_batch ON simulation_runs(batch_id);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sim_runs_created ON simulation_runs(created_at DESC);"
    )

    # 3. Run Metrics table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_metrics (
            run_id TEXT,
            tick INTEGER,
            metrics_json TEXT NOT NULL,
            PRIMARY KEY (run_id, tick),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(id) ON DELETE CASCADE
        );
        """
    )

    # 4. Sweep Sessions table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sweep_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            config_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 5. Saved Replays table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_replays (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            config_json TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Safe migration for saved_replays
    cursor.execute("PRAGMA table_info(saved_replays);")
    sr_cols = {row[1] for row in cursor.fetchall()}
    if "user_id" not in sr_cols:
        cursor.execute("ALTER TABLE saved_replays ADD COLUMN user_id TEXT;")
    if "email" not in sr_cols:
        cursor.execute("ALTER TABLE saved_replays ADD COLUMN email TEXT;")

    # Safe migration for sweep_sessions
    cursor.execute("PRAGMA table_info(sweep_sessions);")
    ss_cols = {row[1] for row in cursor.fetchall()}
    if "user_id" not in ss_cols:
        cursor.execute("ALTER TABLE sweep_sessions ADD COLUMN user_id TEXT;")
    if "email" not in ss_cols:
        cursor.execute("ALTER TABLE sweep_sessions ADD COLUMN email TEXT;")

    # 6. Users table — lightweight registry of everyone who has logged in via Cognito.
    #    `sub` is the immutable Cognito identifier (never changes even if email changes).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            sub TEXT PRIMARY KEY,
            email TEXT,
            username TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Safe migration for users table
    cursor.execute("PRAGMA table_info(users);")
    u_cols = {row[1] for row in cursor.fetchall()}
    if "username" not in u_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT;")
    if "last_seen" not in u_cols:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
        )

    # Index for fast lookup by email
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

    conn.commit()


def ensure_db_initialized() -> None:
    """Runs init_db() unless it already ran for this database file.

    Request handlers call this before touching the database. They used to
    call init_db() itself, which re-runs every CREATE/PRAGMA/migration
    statement and commits — about 19 ms per request on a local disk, more
    than the query it guarded. The schema is still created on first use of a
    file, and again if that file has since been removed (the tests point
    DB_PATH at fresh temporary files).
    """
    if _is_initialized(DB_PATH):
        return
    with _init_lock:
        # Another thread may have finished it while this one waited.
        if not _is_initialized(DB_PATH):
            init_db()


def _is_initialized(path: str) -> bool:
    with _initialized_paths_lock:
        ready = path in _initialized_paths
    return ready and os.path.exists(path)


@contextlib.contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a database connection with foreign keys and busy timeout set.

    Use as ``with get_db_connection() as conn: ...`` — this is a real
    context manager (not a bare generator relied on for its GC-triggered
    cleanup), so the connection is deterministically closed via __exit__
    regardless of how the with-block exits.
    """
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
