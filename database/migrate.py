"""
Migration script: Safely adds new columns introduced in Phase 3 to the existing
cprp.db SQLite database. Uses raw SQLite ALTER TABLE which is additive and safe.
Run once: python database/migrate.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "cprp.db"

NEW_COLUMNS = {
    "comparison_details": [
        ("product_name",  "TEXT"),
        ("brand",         "TEXT"),
        ("category",      "TEXT"),
        ("status",        "TEXT DEFAULT 'Open'"),
    ],
    "reconciliation_runs": [
        ("run_name",          "TEXT"),
        ("critical_mismatches", "INTEGER DEFAULT 0"),
        ("run_type",          "TEXT DEFAULT 'historical'"),
    ],
}


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for table, columns in NEW_COLUMNS.items():
        # Fetch existing column names
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}

        for col_name, col_def in columns:
            if col_name not in existing:
                sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"
                cursor.execute(sql)
                print(f"  [ADDED] '{col_name}' to '{table}'")
            else:
                print(f"  [SKIP]  '{col_name}' already exists in '{table}'")

    conn.commit()
    conn.close()
    print("\nMigration completed successfully.")


if __name__ == "__main__":
    print(f"Running Phase 3 migration on: {DB_PATH}\n")
    migrate()
