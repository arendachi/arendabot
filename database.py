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
                owner_name TEXT,
                owner_phone TEXT,
                address TEXT,
                landmark TEXT,
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
        if "owner_name" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN owner_name TEXT")
        if "owner_phone" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN owner_phone TEXT")
        if "address" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN address TEXT")
        if "landmark" not in existing_cols:
            conn.execute("ALTER TABLE listings ADD COLUMN landmark TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listing_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listing_photos_listing_id ON listing_photos(listing_id)"
        )


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
    address: Optional[str] = None,
    landmark: Optional[str] = None,
) -> int:
    """Добавляет объявление, возвращает его id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO listings (region, rooms, floor, floors_total, area, price, property_type,
                                   title, description, contact, source_listing_id, address, landmark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (region, rooms, floor, floors_total, area, price, property_type,
             title, description, contact, source_listing_id, address, landmark),
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


def update_owner_info(listing_id: int, owner_name: str, owner_phone: str) -> bool:
    """
    Обновляет приватную информацию о владельце квартиры (видна только админу,
    не публикуется в канал и не показывается обычным пользователям бота).
    Возвращает True, если запись с таким id существует и была обновлена.
    """
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE listings SET owner_name = ?, owner_phone = ? WHERE id = ?",
            (owner_name, owner_phone, listing_id),
        )
        return cur.rowcount > 0


def get_listing_by_id(listing_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()


def replace_listing_photos(listing_id: int, file_ids: list[str]) -> bool:
    """
    Полностью заменяет фотографии объявления: удаляет все старые и сохраняет новые
    (до 10 штук) в переданном порядке. Возвращает True, если объявление существует.
    """
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not exists:
            return False
        conn.execute("DELETE FROM listing_photos WHERE listing_id = ?", (listing_id,))
        for position, file_id in enumerate(file_ids[:10]):
            conn.execute(
                "INSERT INTO listing_photos (listing_id, file_id, position) VALUES (?, ?, ?)",
                (listing_id, file_id, position),
            )
        return True


def get_listing_photos(listing_id: int) -> list[str]:
    """Возвращает список file_id фотографий объявления в порядке добавления."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT file_id FROM listing_photos WHERE listing_id = ? ORDER BY position",
            (listing_id,),
        ).fetchall()
        return [row["file_id"] for row in rows]


def count_listing_photos(listing_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM listing_photos WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        return row["c"]


def seed_demo_data():
    """Заполняет базу тестовыми объявлениями, если она пуста (удобно для проверки бота)."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
        if count > 0:
            return

    demo = [
        ("Чиланзар", 1, 3, 9, 32.0, 280, "residential", "Уютная студия в центре"),
        ("Чиланзар", 2, 5, 9, 54.0, 450, "residential", "2-комнатная с балконом"),
        ("Юнусабад", 3, 9, 12, 78.0, 700, "residential", "Просторная квартира у метро"),
        ("Юнусабад", 4, 2, 5, 95.0, 950, "residential", "Семейная квартира с ремонтом"),
        ("Мирзо Улугбек", 1, 1, 4, 30.0, 320, "residential", "Студия рядом с парком"),
        ("Мирзо Улугбек", 2, 4, 9, 48.0, 480, "residential", "2 комнаты, новый дом"),
        ("Миробод", 3, 6, 9, 65.0, 650, "non_residential", "Офисное помещение"),
        ("Яккасарай", 2, 2, 4, 44.0, 400, "residential", "2-комнатная квартира"),
        ("Сергели", 1, 7, 9, 38.0, 350, "non_residential", "Помещение под магазин"),
        ("Алмазар", 3, 3, 5, 60.0, 550, "residential", "3-комнатная квартира"),
    ]
    for region, rooms, floor, floors_total, area, price, ptype, title in demo:
        add_listing(region, rooms, floor, price, ptype, floors_total=floors_total, area=area, title=title)
