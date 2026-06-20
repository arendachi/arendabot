"""
Парсер текстовых объявлений в формате JoyEstate.

Пример входного текста:

    JoyEstate
    Краткое описание:

    ⚜️  Pайон: chilanzar
    🏬 Адрес: Чиланзар 3 квартал
    📍 Ориентир: Чиланзар 3 квартал

    Информация о квартиры:
    🔻 Комнат: 2
    🔻 Этаж: 2
    🔻 Этажность: 4
    🔻 Площадь: 41 m²

    💰 Цена: $600.00

    🆔: 19487

Парсер написан на регулярных выражениях: он терпим к месту в строке, где стоит
эмодзи, к лишним пробелам и к небольшим вариациям подписей (например "Pайон"
с латинской "P", "кв.м" вместо "m²"), но если разработчик источника поменяет
сам набор полей или порядок слов в подписи — регулярку придётся обновить.
"""
import re
from dataclasses import dataclass
from typing import Optional

import config


@dataclass
class ParsedListing:
    region: str
    rooms: int
    floor: int
    floors_total: Optional[int]
    area: Optional[float]
    price: int
    address: Optional[str]
    landmark: Optional[str]
    source_listing_id: Optional[str]
    property_type: str = "residential"  # JoyEstate-формат не указывает тип явно, по умолчанию считаем жильё


class ParseError(Exception):
    """Не удалось распознать обязательное поле в тексте объявления."""


# Каждый паттерн ищет число/значение после подписи поля, независимо от эмодзи перед ней.
_PATTERNS = {
    "region": re.compile(r"[Pр]айон\s*:\s*([^\n\r]+)", re.IGNORECASE),
    "address": re.compile(r"[Аа]дрес\s*:\s*([^\n\r]+)"),
    "landmark": re.compile(r"[Оо]риентир\s*:\s*([^\n\r]+)"),
    "rooms": re.compile(r"[Кк]омнат\s*:\s*(\d+)"),
    "floor": re.compile(r"[Ээ]таж\s*:\s*(\d+)"),
    "floors_total": re.compile(r"[Ээ]тажность\s*:\s*(\d+)"),
    "area": re.compile(r"[Пп]лощадь\s*:\s*([\d.,]+)\s*(?:m²|м²|кв\.?\s*м)?"),
    "price": re.compile(r"[Цц]ена\s*:\s*\$?\s*([\d.,\s]+)"),
    "source_id": re.compile(r"🆔\s*:\s*(\S+)"),
}


def _clean_number(raw: str) -> str:
    return raw.replace(" ", "").replace(",", ".")


def parse_joyestate_text(text: str) -> ParsedListing:
    """
    Разбирает текст объявления в формате JoyEstate.
    Бросает ParseError, если не нашлись обязательные поля (регион, комнаты, этаж, цена).
    """
    if not text or not text.strip():
        raise ParseError("Пустой текст объявления.")

    fields: dict[str, str] = {}
    for key, pattern in _PATTERNS.items():
        match = pattern.search(text)
        if match:
            fields[key] = match.group(1).strip()

    missing_required = [
        name for name in ("region", "rooms", "floor", "price")
        if name not in fields
    ]
    if missing_required:
        raise ParseError(
            "Не удалось распознать обязательные поля: " + ", ".join(missing_required)
        )

    # Регион: приводим к читаемому виду через словарь алиасов из config
    raw_region = fields["region"].strip()
    region_key = raw_region.lower()
    region = config.DISTRICT_ALIASES.get(region_key, raw_region.capitalize())

    rooms = int(fields["rooms"])
    floor = int(fields["floor"])
    floors_total = int(fields["floors_total"]) if "floors_total" in fields else None
    area = float(_clean_number(fields["area"])) if "area" in fields else None

    price_str = _clean_number(fields["price"])
    # Цена может прийти как "600.00" — отбрасываем дробную часть, в БД цена целая
    price = int(round(float(price_str)))

    return ParsedListing(
        region=region,
        rooms=rooms,
        floor=floor,
        floors_total=floors_total,
        area=area,
        price=price,
        address=fields.get("address"),
        landmark=fields.get("landmark"),
        source_listing_id=fields.get("source_id"),
    )


def looks_like_joyestate(text: str) -> bool:
    """
    Быстрая проверка: похож ли присланный текст на объявление JoyEstate,
    чтобы бот не пытался парсить случайные сообщения админа.
    """
    if not text:
        return False
    markers = ["Район:", "район:", "Pайон:", "Комнат:", "Этаж:", "Цена:"]
    hits = sum(1 for m in markers if m.lower() in text.lower())
    return hits >= 3
