import sqlite3
from pathlib import Path

# Nom du fichier de base de données
DB_PATH = Path(__file__).with_name("alarme_domestique.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email         TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS capteurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    type      TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evenements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id   INTEGER,
    event_time  DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    audio_path  TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(sensor_id) REFERENCES capteurs(id)
);
"""

def init_db(db_path: Path = DB_PATH):
    """
    Crée la base SQLite et les tables au lancement du script
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f" Base de données : {db_path}")
    finally:
        conn.close()

def select_sql(sql: str, params: tuple = (), db_path: Path = DB_PATH) -> list[tuple]:
    """
    Exécute une requête SELECT

    Retourne : list de tuples
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()

def insert_sql(sql: str, params: tuple = (), db_path: Path = DB_PATH):
    """
    Exécute une requête INSERT.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()

def delete_sql(sql: str, params: tuple = (), db_path: Path = DB_PATH):
    """
    Exécute une requête DELETE.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()
