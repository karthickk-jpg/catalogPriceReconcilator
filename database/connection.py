from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config.settings import DATABASE_URL
from utils.helpers import get_logger

logger = get_logger("database")

# Initialize engine
# echo=False to avoid logging all SQL queries in production, but can be set to True for debugging.
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Safe for SQLite when used with multi-threaded Streamlit
)

# Scoped session maker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

# Declarative Base
Base = declarative_base()


@contextmanager
def get_db():
    """Context manager to yield database sessions safely and handle commits/rollbacks."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session rollback due to exception: {str(e)}", exc_info=True)
        raise e
    finally:
        session.close()


def init_db():
    """Initializes schema tables if they do not already exist in the SQLite database."""
    try:
        logger.info("Initializing database schemas...")
        Base.metadata.create_all(bind=engine)
        _apply_migrations()
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}", exc_info=True)
        raise e


def _apply_migrations():
    """Applies additive column migrations for existing databases."""
    import sqlite3
    from config.settings import DATABASE_PATH

    if not DATABASE_PATH.exists():
        return

    from database.migrate import NEW_COLUMNS

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        for table, columns in NEW_COLUMNS.items():
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            for col_name, col_def in columns:
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Migration: added '{col_name}' to '{table}'")
        conn.commit()
    finally:
        conn.close()
