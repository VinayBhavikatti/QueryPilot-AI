from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        "mysql+pymysql://",
        creator=lambda: __import__("pymysql").connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
            connect_timeout=5,
            read_timeout=settings.query_timeout_seconds,
            write_timeout=settings.query_timeout_seconds,
        ),
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def get_schema() -> str:
    """Return only table and column metadata for the configured schema."""
    settings = get_settings()
    allowed = settings.allowed_tables
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME, ORDINAL_POSITION"
            ),
            {"schema": settings.mysql_database},
        ).mappings()
        grouped: dict[str, list[str]] = {}
        for row in rows:
            table = row["TABLE_NAME"]
            if allowed is None or table in allowed:
                nullable = " NULL" if row["IS_NULLABLE"] == "YES" else " NOT NULL"
                grouped.setdefault(table, []).append(f"{row['COLUMN_NAME']} {row['COLUMN_TYPE']}{nullable}")
    if not grouped:
        return "No visible tables were discovered."
    return "\n".join(f"{table}({', '.join(columns)})" for table, columns in grouped.items())


def execute_read_query(sql: str, limit: int) -> tuple[list[str], list[dict]]:
    """Execute a validated SELECT within a read-only transaction and cap output."""
    raw_connection = get_engine().raw_connection()
    cursor = None
    try:
        # Configure the next transaction before starting it. The MySQL account
        # must still have SELECT-only grants; this is an additional guard.
        cursor = raw_connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("START TRANSACTION READ ONLY")
        try:
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description or []]
            rows = [dict(zip(columns, row)) for row in cursor.fetchmany(limit)]
            raw_connection.rollback()
            return columns, rows
        except Exception:
            raw_connection.rollback()
            raise
    finally:
        if cursor is not None:
            cursor.close()
        raw_connection.close()
