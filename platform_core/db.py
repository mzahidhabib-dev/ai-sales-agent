"""
platform_core/db.py

PostgreSQL connection helper.

Rules compliance:
  Rule 9  — Fail-fast if required env vars are missing (no silent misconfiguration).
  Rule 15 — Credentials (password) NEVER appear in any log line, even on failure.

Required environment variables:
  POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB
Optional:
  POSTGRES_PORT (default: 5432)
"""

import pg8000.dbapi
from platform_core.logging_config import get_logger
from platform_core.security.secrets import get_secret

logger = get_logger(__name__)

# --- Load secrets via Centralized Secrets Manager ---
DB_USER = get_secret("POSTGRES_USER")
DB_PASSWORD = get_secret("POSTGRES_PASSWORD")  # never logged
DB_HOST = get_secret("POSTGRES_HOST")
DB_PORT = int(get_secret("POSTGRES_PORT", "5432"))
DB_NAME = get_secret("POSTGRES_DB")


def get_connection() -> pg8000.dbapi.Connection:
    """
    Opens and returns a new PostgreSQL connection.

    Returns:
        pg8000.dbapi.Connection

    Raises:
        pg8000.dbapi.DatabaseError: on connection failure.
            Caller is responsible for logging and handling this error.
            Rule 15: password is never included in the log — only host/port/db are safe to log.
    """
    try:
        conn = pg8000.dbapi.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        )
        return conn
    except Exception as e:
        # Rule 15: log host/port/db only — NEVER log DB_PASSWORD
        logger.error(
            "Failed to connect to PostgreSQL",
            extra={
                "host": DB_HOST,
                "port": DB_PORT,
                "db": DB_NAME,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching pg8000 connection error; re-raising to caller",
            },
        )
        raise

