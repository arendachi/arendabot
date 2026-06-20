"""
Telegram-бот: каталог объявлений недвижимости с фильтрацией по 7 категориям.

Категории фильтрации:
1. Регион
2. Количество комнат
3. Этаж
4. Этажность дома
5. Площадь
6. Цена
7. Тип: Жилой / Нежилой

Кроме поиска, бот умеет принимать от админа текст объявления в формате
JoyEstate (без команды, просто как обычное сообщение) и автоматически:
  - распознавать поля (район, комнаты, этаж, этажность, площадь, цена, ID),
  - добавлять объявление в базу,
  - публиковать готовый пост в Telegram-канал.

Запуск:
    export BOT_TOKEN="ваш_токен_от_BotFather"
    export ADMIN_IDS="123456789"
    export CHANNEL_USERNAME="@ваш_канал"
    python bot.py
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import database as db
import parser as listing_parser

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Шаги диалога фильтрации
STEP_REGION = "region"
STEP_ROOMS = "rooms"
STEP_FLOOR = "floor"
STEP_FLOORS_TOTAL = "floors_total"
STEP_AREA = "area"
STEP_PRICE = "price"
STEP_TYPE = "type"
STEP_RESULTS = "results"

TOTAL_STEPS = 7
PAGE_SIZE = 5


# ---------- Вспомогательные функции построения клавиатур ----------

def kb_regions() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(region, callback_data=f"region:{region}")]
        for region in config.REGIONS
    ]
    buttons.append([InlineKeyboardButton("⏭ Любой регион", callback_data="region:any")])
    return InlineKeyboardMarkup(buttons)


def kb_rooms() -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(r, callback_data=f"rooms:{r}") for r in config.ROOM_OPTIONS
    ]
    rows = [row[i:i + 3] for i in range(0, len(row), 3)]
    rows.append([InlineKeyboardButton("⏭ Любое количество", callback_data="rooms:any")])
    rows.append([InlineKeyboardButton("⬅ Назад", callback_data="back:region")])
    return InlineKeyboardMarkup(rows)


def kb_floor() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"floor:{idx}")]
        for idx, (label, _, _) in enumerate(config.FLOOR_RANGES)
    ]
    rows.append([InlineKeyboardButton("⏭ Любой этаж", callback_data="floor:any")])
    rows.append([InlineKeyboardButton("⬅ Назад", callback_data="back:rooms")])
    return InlineKeyboardMarkup(rows)


def kb_floors_total() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"floors_total:{idx}")]
        for idx, (label, _, _) in enumerate(config.FLOORS_TOTAL_RANGES)
    ]
    rows.append([InlineKeyboardButton("⏭ Любая этажность", callback_data="floors_total:any")])
    rows.append([InlineKeyboardButton("⬅ Назад", callback_data="back:floor")])
    return InlineKeyboardMarkup(rows)


def kb_area() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"area:{idx}")]
        for idx, (label, _, _) in enumerate(config.AREA_RANGES)
    ]
    rows.append([InlineKeyboardButton("⏭ Любая площадь", callback_data="area:any")])
    rows.append([InlineKeyboardButton("⬅ Назад", callback_data="back:floors_total")])
    return InlineKeyboardMarkup(rows)


def kb_price() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"price:{idx}")]
        for idx, (label, _, _) in enumerate(config.PRICE_RANGES)
    ]
    rows.append([InlineKeyboardButton("⏭ Любая цена", callback_data="price:any")])
    rows.append([InlineKeyboardButton("⬅ Назад", callback_data="back:area")])
    return InlineKeyboardMarkup(rows)


def kb_type() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"type:{value}")]
        for value, label in config.PROPERTY_TYPES
    ]
    rows.append([InlineKeyboardButton("⏭ Любой тип", callback_data="type:any")])
    rows.append([InlineKeyboardButton("⬅ Назад", callback_data="back:price")])
    return InlineKeyboardMarkup(rows)


def kb_results_nav(has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    nav_row = []
    if has_prev:
        nav_row.append(InlineKeyboardButton("⬅ Назад", callback_data="page:prev"))
    if has_next:
        nav_row.append(InlineKeyboardButton("Вперёд ➡", callback_data="page:next"))
    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")])
    return InlineKeyboardMarkup(rows)


# ---------- Хендлеры команд ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["filters"] = {}
    await update.message.reply_text(
        "👋 Добро пожаловать в каталог объявлений недвижимости!\n\n"
        "Я помогу найти подходящий вариант по фильтрам.\n"
        f"Шаг 1 из {TOTAL_STEPS}: выберите регион 👇",
        reply_markup=kb_regions(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — начать новый поиск по фильтрам\n"
        "/help — это сообщение"
    )


# ---------- Обработка нажатий на кнопки ----------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    filters = context.user_data.setdefault("filters", {})

    if data.startswith("region:"):
        value = data.split(":", 1)[1]
        filters["region"] = None if value == "any" else value
        await query.edit_message_text(
            f"Шаг 2 из {TOTAL_STEPS}: выберите количество комнат 👇",
            reply_markup=kb_rooms(),
        )

    elif data.startswith("rooms:"):
        value = data.split(":", 1)[1]
        filters["rooms"] = None if value == "any" else value
        await query.edit_message_text(
            f"Шаг 3 из {TOTAL_STEPS}: выберите этаж 👇",
            reply_markup=kb_floor(),
        )

    elif data.startswith("floor:"):
        value = data.split(":", 1)[1]
        filters["floor_idx"] = None if value == "any" else int(value)
        await query.edit_message_text(
            f"Шаг 4 из {TOTAL_STEPS}: выберите этажность дома 👇",
            reply_markup=kb_floors_total(),
        )

    elif data.startswith("floors_total:"):
        value = data.split(":", 1)[1]
        filters["floors_total_idx"] = None if value == "any" else int(value)
        await query.edit_message_text(
            f"Шаг 5 из {TOTAL_STEPS}: выберите площадь 👇",
            reply_markup=kb_area(),
        )

    elif data.startswith("area:"):
        value = data.split(":", 1)[1]
        filters["area_idx"] = None if value == "any" else int(value)
        await query.edit_message_text(
            f"Шаг 6 из {TOTAL_STEPS}: выберите диапазон цены 👇",
            reply_markup=kb_price(),
        )

    elif data.startswith("price:"):
        value = data.split(":", 1)[1]
        filters["price_idx"] = None if value == "any" else int(value)
        await query.edit_message_text(
            f"Шаг 7 из {TOTAL_STEPS}: выберите тип недвижимости 👇",
            reply_markup=kb_type(),
        )

    elif data.startswith("type:"):
        value = data.split(":", 1)[1]
        filters["property_type"] = None if value == "any" else value
        context.user_data["offset"] = 0
        await show_results(query, context)

    elif data.startswith("back:"):
        target = data.split(":", 1)[1]
        if target == "region":
            await query.edit_message_text(f"Шаг 1 из {TOTAL_STEPS}: выберите регион 👇", reply_markup=kb_regions())
        elif target == "rooms":
            await query.edit_message_text(f"Шаг 2 из {TOTAL_STEPS}: выберите количество комнат 👇", reply_markup=kb_rooms())
        elif target == "floor":
            await query.edit_message_text(f"Шаг 3 из {TOTAL_STEPS}: выберите этаж 👇", reply_markup=kb_floor())
        elif target == "floors_total":
            await query.edit_message_text(f"Шаг 4 из {TOTAL_STEPS}: выберите этажность дома 👇", reply_markup=kb_floors_total())
        elif target == "area":
            await query.edit_message_text(f"Шаг 5 из {TOTAL_STEPS}: выберите площадь 👇", reply_markup=kb_area())
        elif target == "price":
            await query.edit_message_text(f"Шаг 6 из {TOTAL_STEPS}: выберите диапазон цены 👇", reply_markup=kb_price())

    elif data == "page:next":
        context.user_data["offset"] = context.user_data.get("offset", 0) + PAGE_SIZE
        await show_results(query, context)

    elif data == "page:prev":
        context.user_data["offset"] = max(0, context.user_data.get("offset", 0) - PAGE_SIZE)
        await show_results(query, context)

    elif data == "restart":
        context.user_data["filters"] = {}
        context.user_data["offset"] = 0
        await query.edit_message_text(
            f"🔄 Новый поиск.\nШаг 1 из {TOTAL_STEPS}: выберите регион 👇",
            reply_markup=kb_regions(),
        )


def _resolve_filters(filters: dict) -> dict:
    """Превращает индексы диапазонов из user_data в реальные параметры для запроса к БД."""
    resolved = {"region": filters.get("region"), "property_type": filters.get("property_type")}

    rooms = filters.get("rooms")
    if rooms and rooms != "5+":
        resolved["rooms"] = int(rooms)
    elif rooms == "5+":
        resolved["rooms"] = None  # отдельная обработка ниже через floor_min аналог не нужен, фильтруем после
    else:
        resolved["rooms"] = None

    floor_idx = filters.get("floor_idx")
    if floor_idx is not None:
        _, fmin, fmax = config.FLOOR_RANGES[floor_idx]
        resolved["floor_min"] = fmin
        resolved["floor_max"] = fmax
    else:
        resolved["floor_min"] = None
        resolved["floor_max"] = None

    floors_total_idx = filters.get("floors_total_idx")
    if floors_total_idx is not None:
        _, ftmin, ftmax = config.FLOORS_TOTAL_RANGES[floors_total_idx]
        resolved["floors_total_min"] = ftmin
        resolved["floors_total_max"] = ftmax
    else:
        resolved["floors_total_min"] = None
        resolved["floors_total_max"] = None

    area_idx = filters.get("area_idx")
    if area_idx is not None:
        _, amin, amax = config.AREA_RANGES[area_idx]
        resolved["area_min"] = amin
        resolved["area_max"] = amax
    else:
        resolved["area_min"] = None
        resolved["area_max"] = None

    price_idx = filters.get("price_idx")
    if price_idx is not None:
        _, pmin, pmax = config.PRICE_RANGES[price_idx]
        resolved["price_min"] = pmin
        resolved["price_max"] = pmax
    else:
        resolved["price_min"] = None
        resolved["price_max"] = None

    return resolved


def _filters_summary(filters: dict) -> str:
    parts = []
    parts.append(f"Регион: {filters.get('region') or 'любой'}")
    parts.append(f"Комнат: {filters.get('rooms') or 'любое'}")
    floor_idx = filters.get("floor_idx")
    parts.append(f"Этаж: {config.FLOOR_RANGES[floor_idx][0] if floor_idx is not None else 'любой'}")
    floors_total_idx = filters.get("floors_total_idx")
    parts.append(f"Этажность: {config.FLOORS_TOTAL_RANGES[floors_total_idx][0] if floors_total_idx is not None else 'любая'}")
    area_idx = filters.get("area_idx")
    parts.append(f"Площадь: {config.AREA_RANGES[area_idx][0] if area_idx is not None else 'любая'}")
    price_idx = filters.get("price_idx")
    parts.append(f"Цена: {config.PRICE_RANGES[price_idx][0] if price_idx is not None else 'любая'}")
    ptype = filters.get("property_type")
    type_label = "любой"
    for value, label in config.PROPERTY_TYPES:
        if value == ptype:
            type_label = label
    parts.append(f"Тип: {type_label}")
    return "\n".join(parts)


async def show_results(query, context: ContextTypes.DEFAULT_TYPE):
    filters = context.user_data.get("filters", {})
    resolved = _resolve_filters(filters)
    offset = context.user_data.get("offset", 0)

    rooms_raw = filters.get("rooms")

    db_kwargs = {
        "region": resolved["region"],
        "floor_min": resolved["floor_min"],
        "floor_max": resolved["floor_max"],
        "floors_total_min": resolved["floors_total_min"],
        "floors_total_max": resolved["floors_total_max"],
        "area_min": resolved["area_min"],
        "area_max": resolved["area_max"],
        "price_min": resolved["price_min"],
        "price_max": resolved["price_max"],
        "property_type": resolved["property_type"],
    }
    if rooms_raw and rooms_raw != "5+":
        db_kwargs["rooms"] = int(rooms_raw)

    all_matches = db.search_listings(**db_kwargs, limit=100000, offset=0)

    if rooms_raw == "5+":
        all_matches = [row for row in all_matches if row["rooms"] >= 5]

    total = len(all_matches)
    page_items = all_matches[offset:offset + PAGE_SIZE]

    summary = _filters_summary(filters)

    if not page_items:
        text = (
            f"🔎 Результаты поиска:\n{summary}\n\n"
            f"😕 По заданным фильтрам ничего не найдено.\n"
            f"Попробуйте изменить параметры."
        )
        await query.edit_message_text(text, reply_markup=kb_results_nav(False, False))
        return

    lines = [f"🔎 Результаты поиска ({total} найдено):", summary, ""]
    for row in page_items:
        type_label = "🏠 Жилой" if row["property_type"] == "residential" else "🏢 Нежилой"
        title = row["title"] or "Без названия"
        floors_total = row["floors_total"] if row["floors_total"] is not None else "?"
        area = f"{row['area']:.0f} м²" if row["area"] is not None else "—"
        lines.append(
            f"#{row['id']} {title}\n"
            f"📍 {row['region']} | 🚪 {row['rooms']} комн. | 🏢 этаж {row['floor']}/{floors_total} | "
            f"📐 {area} | 💰 {row['price']:,} | {type_label}".replace(",", " ")
        )
        lines.append("")

    has_prev = offset > 0
    has_next = offset + PAGE_SIZE < total

    await query.edit_message_text(
        "\n".join(lines).strip(),
        reply_markup=kb_results_nav(has_prev, has_next),
    )


def _format_channel_post(parsed: listing_parser.ParsedListing, listing_id: int) -> str:
    """Формирует красивый пост для канала на основе распознанного объявления."""
    type_label = "🏠 Жилой" if parsed.property_type == "residential" else "🏢 Нежилой"
    area_line = f"📐 Площадь: {parsed.area:.0f} м²\n" if parsed.area is not None else ""
    floors_total_line = f"🏢 Этажность: {parsed.floors_total}\n" if parsed.floors_total is not None else ""
    address_line = f"🏬 Адрес: {parsed.address}\n" if parsed.address else ""
    landmark_line = f"📍 Ориентир: {parsed.landmark}\n" if parsed.landmark else ""

    text = (
        f"🆕 Новое объявление\n\n"
        f"⚜️ Район: {parsed.region}\n"
        f"{address_line}"
        f"{landmark_line}\n"
        f"🔻 Комнат: {parsed.rooms}\n"
        f"🔻 Этаж: {parsed.floor}\n"
        f"{floors_total_line}"
        f"{area_line}"
        f"🏷 Тип: {type_label}\n\n"
        f"💰 Цена: ${parsed.price:,}".replace(",", " ") + "\n\n"
        f"🆔 #{listing_id}"
    )
    return text


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает обычное текстовое сообщение от админа.
    Если текст похож на объявление JoyEstate — парсит его, добавляет в базу
    и публикует готовый пост в канал. Иначе сообщение игнорируется (это не наша
    зона ответственности — админ мог просто написать что-то другое боту).
    """
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_IDS:
        return  # обычные пользователи не должны автоматически добавлять объявления

    text = update.message.text or ""
    if not listing_parser.looks_like_joyestate(text):
        return  # это не похоже на объявление — не мешаем остальной логике бота

    try:
        parsed = listing_parser.parse_joyestate_text(text)
    except listing_parser.ParseError as e:
        await update.message.reply_text(
            f"⚠️ Не удалось распознать объявление: {e}\n\n"
            f"Проверьте формат текста (район, комнаты, этаж, цена — обязательны)."
        )
        return

    # Защита от дублей: если объявление с таким ID из источника уже было добавлено
    if parsed.source_listing_id:
        existing = db.get_listing_by_source_id(parsed.source_listing_id)
        if existing:
            await update.message.reply_text(
                f"⚠️ Объявление с ID {parsed.source_listing_id} уже было добавлено "
                f"ранее (запись #{existing['id']}). Пропускаю, чтобы не дублировать."
            )
            return

    title_parts = [parsed.region, f"{parsed.rooms} комн."]
    title = ", ".join(title_parts)

    listing_id = db.add_listing(
        region=parsed.region,
        rooms=parsed.rooms,
        floor=parsed.floor,
        price=parsed.price,
        property_type=parsed.property_type,
        floors_total=parsed.floors_total,
        area=parsed.area,
        title=title,
        description=parsed.landmark or "",
        contact="",
        source_listing_id=parsed.source_listing_id,
    )

    await update.message.reply_text(f"✅ Объявление добавлено в базу (запись #{listing_id}).")

    post_text = _format_channel_post(parsed, listing_id)
    try:
        await context.bot.send_message(chat_id=config.CHANNEL_USERNAME, text=post_text)
        await update.message.reply_text(f"📣 Объявление опубликовано в канале {config.CHANNEL_USERNAME}.")
    except Exception as e:
        logger.exception("Не удалось опубликовать объявление в канал")
        await update.message.reply_text(
            f"⚠️ Объявление сохранено в базе, но не удалось опубликовать в канал: {e}\n\n"
            f"Проверьте, что бот добавлен в канал {config.CHANNEL_USERNAME} как администратор "
            f"с правом публикации сообщений."
        )


def main():
    if config.BOT_TOKEN == "ВСТАВЬТЕ_СЮДА_ТОКЕН_ОТ_BOTFATHER":
        raise SystemExit(
            "Не задан токен бота. Установите переменную окружения BOT_TOKEN "
            "или впишите токен прямо в config.py"
        )
    if not config.ADMIN_IDS:
        logger.warning(
            "ADMIN_IDS не настроен — автодобавление объявлений из текста JoyEstate "
            "работать не будет. Установите переменную окружения ADMIN_IDS."
        )
    if config.CHANNEL_USERNAME == "@ваш_канал":
        logger.warning(
            "CHANNEL_USERNAME не настроен — публикация в канал не будет работать. "
            "Установите переменную окружения CHANNEL_USERNAME."
        )

    db.init_db()
    db.seed_demo_data()  # удалите эту строку, если не нужны тестовые объявления

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    logger.info("Бот запущен и ожидает сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
