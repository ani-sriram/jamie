import os, sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "recipes.db"

def get_connection(db_path: str | None = None):
    path = db_path or str(DEFAULT_DB)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn