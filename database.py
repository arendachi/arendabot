"""
Работа с базой данных SQLite для бота объявлений недвижимости.
"""
import sqlite3
from contextlib import contextmanager
from typing import Optional

DB_PATH = "realty.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Создаёт таблицу объявлений, если её ещё нет."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                rooms INTEGER NOT NULL,
                floor INTEGER NOT NULL,
                floors_total INTEGER,
                area REAL,
                price INTEGER NOT NULL,
                property_type TEXT NOT NULL CHECK (property_type IN ('residential', 'non_residential')),
                title TEXT,
                description TEXT,
                contact TEXT,
                source_listing_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # Миграция для уже существующих баз (на случай, если таблица была создана раньше без новых колонок)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(listings)").fetchall()}
        if "floors_total" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN floors_total INTEGER")
        if "area" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN area REAL")
        if "source_listing_id" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN source_listing_id TEXT")


def add_listing(
    region: str,
    rooms: int,
    floor: int,
    price: int,
    property_type: str,
    floors_total: Optional[int] = None,
    area: Optional[float] = None,
    title: str = "",
    description: str = "",
    contact: str = "",
    source_listing_id: Optional[str] = None,
) -> int:
    """Добавляет объявление, возвращает его id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO listings (region, rooms, floor, floors_total, area, price, property_type,
                                   title, description, contact, source_listing_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (region, rooms, floor, floors_total, area, price, property_type,
             title, description, contact, source_listing_id),
        )
        return cur.lastrowid


def get_distinct_regions() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT region FROM listings ORDER BY region").fetchall()
        return [r["region"] for r in rows]


def search_listings(
    region: Optional[str] = None,
    rooms: Optional[int] = None,
    floor_min: Optional[int] = None,
    floor_max: Optional[int] = None,
    floors_total_min: Optional[int] = None,
    floors_total_max: Optional[int] = None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    property_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """Гибкий поиск объявлений по любому набору фильтров."""
    query = "SELECT * FROM listings WHERE 1=1"
    params: list = []

    if region:
        query += " AND region = ?"
        params.append(region)
    if rooms is not None:
        query += " AND rooms = ?"
        params.append(rooms)
    if floor_min is not None:
        query += " AND floor >= ?"
        params.append(floor_min)
    if floor_max is not None:
        query += " AND floor <= ?"
        params.append(floor_max)
    if floors_total_min is not None:
        query += " AND floors_total >= ?"
        params.append(floors_total_min)
    if floors_total_max is not None:
        query += " AND floors_total <= ?"
        params.append(floors_total_max)
    if area_min is not None:
        query += " AND area >= ?"
        params.append(area_min)
    if area_max is not None:
        query += " AND area <= ?"
        params.append(area_max)
    if price_min is not None:
        query += " AND price >= ?"
        params.append(price_min)
    if price_max is not None:
        query += " AND price <= ?"
        params.append(price_max)
    if property_type:
        query += " AND property_type = ?"
        params.append(property_type)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def count_listings(**filters) -> int:
    """Считает количество объявлений с тем же набором фильтров, что и search_listings."""
    filters.pop("limit", None)
    filters.pop("offset", None)
    rows = search_listings(**filters, limit=100000, offset=0)
    return len(rows)


def get_listing_by_source_id(source_listing_id: str) -> Optional[sqlite3.Row]:
    """Проверяет, было ли уже добавлено объявление с таким внешним ID (например, ID из JoyEstate)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM listings WHERE source_listing_id = ?", (source_listing_id,)
        ).fetchone()


def get_listing_by_id(listing_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()


def seed_demo_data():
    """Заполняет базу тестовыми объявлениями, если она пуста (удобно для проверки бота)."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
        if count > 0:
            return

    demo = [
        ("Ташкент", 1, 3, 9, 32.0, 45000, "residential", "Уютная студия в центре"),
        ("Ташкент", 2, 5, 9, 54.0, 62000, "residential", "2-комнатная с балконом"),
        ("Ташкент", 3, 9, 12, 78.0, 89000, "residential", "Просторная квартира у метро"),
        ("Ташкент", 4, 2, 5, 95.0, 110000, "residential", "Семейная квартира с ремонтом"),
        ("Самарканд", 1, 1, 4, 30.0, 28000, "residential", "Студия рядом с парком"),
        ("Самарканд", 2, 4, 9, 48.0, 41000, "residential", "2 комнаты, новый дом"),
        ("Самарканд", 3, 6, 9, 65.0, 55000, "non_residential", "Офисное помещение"),
        ("Бухара", 2, 2, 4, 44.0, 35000, "residential", "2-комнатная квартира"),
        ("Бухара", 1, 7, 9, 38.0, 30000, "non_residential", "Помещение под магазин"),
        ("Андижан", 3, 3, 5, 60.0, 47000, "residential", "3-комнатная квартира"),
    ]
    for region, rooms, floor, floors_total, area, price, ptype, title in demo:
        add_listing(region, rooms, floor, price, ptype, floors_total=floors_total, area=area, title=title)
