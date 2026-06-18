import sqlite3
from contextlib import contextmanager

DB_PATH = "arenda.db"


def init_db():
    """Создаёт таблицу квартир, если её ещё нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS apartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            rooms TEXT NOT NULL,
            floor TEXT NOT NULL,
            price INTEGER NOT NULL,
            kind TEXT NOT NULL,
            phone TEXT NOT NULL,
            description TEXT,
            photo_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def add_apartment(region, rooms, floor, price, kind, phone, description, photo_id=None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO apartments (region, rooms, floor, price, kind, phone, description, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (region, rooms, floor, price, kind, phone, description, photo_id))
        conn.commit()
        return cur.lastrowid


def get_apartment(apartment_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM apartments WHERE id = ?", (apartment_id,))
        return cur.fetchone()


def delete_apartment(apartment_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM apartments WHERE id = ?", (apartment_id,))
        conn.commit()
        return cur.rowcount > 0


def search_apartments(region=None, rooms=None, floor=None, price_min=None, price_max=None, kind=None):
    """Поиск квартир по фильтрам. Любой параметр можно не указывать (None = пропустить)."""
    query = "SELECT * FROM apartments WHERE 1=1"
    params = []

    if region:
        query += " AND region = ?"
        params.append(region)
    if rooms:
        query += " AND rooms = ?"
        params.append(rooms)
    if floor:
        query += " AND floor = ?"
        params.append(floor)
    if price_min is not None:
        query += " AND price >= ?"
        params.append(price_min)
    if price_max is not None:
        query += " AND price <= ?"
        params.append(price_max)
    if kind:
        query += " AND kind = ?"
        params.append(kind)

    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def get_all_apartments():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM apartments ORDER BY created_at DESC")
        return cur.fetchall()


def count_apartments():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM apartments")
        return cur.fetchone()["c"]
