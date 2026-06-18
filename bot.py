import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config_data import REGIONS, ROOMS_OPTIONS, FLOOR_RANGES, PRICE_RANGES, KIND_OPTIONS

# ==================== НАСТРОЙКА ====================

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "Не найден BOT_TOKEN. Задайте переменную окружения BOT_TOKEN "
        "(в Railway это делается в разделе Variables)."
    )

# ID владельца бота — единственный, кому будут видны номера телефонов
# и доступны команды добавления/удаления квартир.
ADMIN_ID_RAW = os.getenv("ADMIN_ID")
if not ADMIN_ID_RAW:
    raise RuntimeError(
        "Не найден ADMIN_ID. Задайте переменную окружения ADMIN_ID "
        "(ваш личный numeric Telegram ID, узнать можно у бота @userinfobot)."
    )
ADMIN_ID = int(ADMIN_ID_RAW)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ==================== СОСТОЯНИЯ (FSM) ====================
# Для пошагового добавления квартиры владельцем

class AddApartment(StatesGroup):
    region = State()
    rooms = State()
    floor = State()
    price = State()
    kind = State()
    phone = State()
    description = State()
    photo = State()


# Для пошагового поиска пользователем
class SearchApartment(StatesGroup):
    region = State()
    rooms = State()
    floor = State()
    price = State()
    kind = State()


# ==================== КЛАВИАТУРЫ ====================

def kb_regions(prefix: str):
    builder = InlineKeyboardBuilder()
    for region in REGIONS:
        builder.button(text=region, callback_data=f"{prefix}_region:{region}")
    builder.button(text="🔙 Без фильтра по региону", callback_data=f"{prefix}_region:skip")
    builder.adjust(2)
    return builder.as_markup()


def kb_rooms(prefix: str):
    builder = InlineKeyboardBuilder()
    for r in ROOMS_OPTIONS:
        builder.button(text=f"{r} комн.", callback_data=f"{prefix}_rooms:{r}")
    if prefix == "search":
        builder.button(text="🔙 Без фильтра", callback_data=f"{prefix}_rooms:skip")
    builder.adjust(3)
    return builder.as_markup()


def kb_floor(prefix: str):
    builder = InlineKeyboardBuilder()
    for label in FLOOR_RANGES:
        builder.button(text=label, callback_data=f"{prefix}_floor:{label}")
    if prefix == "search":
        builder.button(text="🔙 Без фильтра", callback_data=f"{prefix}_floor:skip")
    builder.adjust(2)
    return builder.as_markup()


def kb_price(prefix: str):
    builder = InlineKeyboardBuilder()
    for label in PRICE_RANGES:
        builder.button(text=label, callback_data=f"{prefix}_price:{label}")
    if prefix == "search":
        builder.button(text="🔙 Без фильтра", callback_data=f"{prefix}_price:skip")
    builder.adjust(2)
    return builder.as_markup()


def kb_kind(prefix: str):
    builder = InlineKeyboardBuilder()
    for cb, label in KIND_OPTIONS.items():
        builder.button(text=label, callback_data=f"{prefix}_kind:{cb}")
    if prefix == "search":
        builder.button(text="🔙 Без фильтра", callback_data=f"{prefix}_kind:skip")
    builder.adjust(2)
    return builder.as_markup()


def kb_main_menu(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Найти квартиру", callback_data="start_search")
    if is_admin(user_id):
        builder.button(text="➕ Добавить квартиру", callback_data="start_add")
        builder.button(text="📋 Все квартиры", callback_data="admin_list")
    builder.adjust(1)
    return builder.as_markup()


def kb_skip_description():
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить (без описания)", callback_data="add_description:skip")
    return builder.as_markup()


def kb_skip_photo():
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить (без фото)", callback_data="add_photo:skip")
    return builder.as_markup()


# ==================== СТАРТ / ГЛАВНОЕ МЕНЮ ====================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "👋 Здравствуйте!\n\n"
        "Это бот для поиска квартир в аренду.\n"
        "Нажмите кнопку ниже, чтобы начать поиск."
    )
    await message.answer(text, reply_markup=kb_main_menu(message.from_user.id))


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=kb_main_menu(callback.from_user.id),
    )
    await callback.answer()


# ==================== ПОИСК (для всех пользователей) ====================

@dp.callback_query(F.data == "start_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchApartment.region)
    await callback.message.edit_text(
        "Шаг 1 из 5: выберите регион 👇",
        reply_markup=kb_regions("search"),
    )
    await callback.answer()


@dp.callback_query(SearchApartment.region, F.data.startswith("search_region:"))
async def search_region_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(region=None if value == "skip" else value)
    await state.set_state(SearchApartment.rooms)
    await callback.message.edit_text(
        "Шаг 2 из 5: количество комнат 👇",
        reply_markup=kb_rooms("search"),
    )
    await callback.answer()


@dp.callback_query(SearchApartment.rooms, F.data.startswith("search_rooms:"))
async def search_rooms_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(rooms=None if value == "skip" else value)
    await state.set_state(SearchApartment.floor)
    await callback.message.edit_text(
        "Шаг 3 из 5: этаж 👇",
        reply_markup=kb_floor("search"),
    )
    await callback.answer()


@dp.callback_query(SearchApartment.floor, F.data.startswith("search_floor:"))
async def search_floor_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(floor=None if value == "skip" else value)
    await state.set_state(SearchApartment.price)
    await callback.message.edit_text(
        "Шаг 4 из 5: цена 👇",
        reply_markup=kb_price("search"),
    )
    await callback.answer()


@dp.callback_query(SearchApartment.price, F.data.startswith("search_price:"))
async def search_price_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(price=None if value == "skip" else value)
    await state.set_state(SearchApartment.kind)
    await callback.message.edit_text(
        "Шаг 5 из 5: тип помещения 👇",
        reply_markup=kb_kind("search"),
    )
    await callback.answer()


@dp.callback_query(SearchApartment.kind, F.data.startswith("search_kind:"))
async def search_kind_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    kind_label = None if value == "skip" else KIND_OPTIONS.get(value)
    data = await state.get_data()
    await state.clear()

    price_min, price_max = (None, None)
    if data.get("price"):
        price_min, price_max = PRICE_RANGES[data["price"]]

    floor_min, floor_max = (None, None)
    floor_label = data.get("floor")

    results = db.search_apartments(
        region=data.get("region"),
        rooms=data.get("rooms"),
        floor=floor_label,
        price_min=price_min,
        price_max=price_max,
        kind=kind_label,
    )

    if not results:
        await callback.message.edit_text(
            "😔 По вашим критериям ничего не найдено.\n\n"
            "Попробуйте изменить фильтры — например, выбрать «Без фильтра» для одного из шагов.",
            reply_markup=kb_main_menu(callback.from_user.id),
        )
        await callback.answer()
        return

    await callback.message.edit_text(f"✅ Найдено квартир: {len(results)}")

    # Отправляем каждую квартиру отдельным сообщением (без номера телефона!)
    for apt in results[:30]:  # ограничение, чтобы не заспамить чат при больших базах
        text = format_apartment_card(apt)
        if apt["photo_id"]:
            await callback.message.answer_photo(apt["photo_id"], caption=text)
        else:
            await callback.message.answer(text)

    if len(results) > 30:
        await callback.message.answer(f"Показаны первые 30 из {len(results)}. Уточните фильтры для более точного поиска.")

    await callback.message.answer("Меню:", reply_markup=kb_main_menu(callback.from_user.id))
    await callback.answer()


def format_apartment_card(apt) -> str:
    """Карточка квартиры для обычного пользователя — БЕЗ номера телефона."""
    return (
        f"🏠 Квартира #{apt['id']}\n"
        f"📍 Регион: {apt['region']}\n"
        f"🚪 Комнат: {apt['rooms']}\n"
        f"🏢 Этаж: {apt['floor']}\n"
        f"💰 Цена: {apt['price']}$\n"
        f"🏷 Тип: {apt['kind']}\n"
        + (f"📝 {apt['description']}\n" if apt["description"] else "")
        + "\n☎️ Чтобы узнать номер для связи, напишите администратору бота."
    )


# ==================== ДОБАВЛЕНИЕ КВАРТИРЫ (только владелец) ====================

@dp.callback_query(F.data == "start_add")
async def start_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Эта функция доступна только владельцу бота.", show_alert=True)
        return
    await state.set_state(AddApartment.region)
    await callback.message.edit_text(
        "➕ Добавление квартиры\nШаг 1 из 7: выберите регион 👇",
        reply_markup=kb_regions("add"),
    )
    await callback.answer()


@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddApartment.region)
    await message.answer(
        "➕ Добавление квартиры\nШаг 1 из 7: выберите регион 👇",
        reply_markup=kb_regions("add"),
    )


@dp.callback_query(AddApartment.region, F.data.startswith("add_region:"))
async def add_region_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "skip":
        await callback.answer("Для добавления квартиры регион обязателен.", show_alert=True)
        return
    await state.update_data(region=value)
    await state.set_state(AddApartment.rooms)
    await callback.message.edit_text(
        "Шаг 2 из 7: количество комнат 👇",
        reply_markup=kb_rooms("add"),
    )
    await callback.answer()


@dp.callback_query(AddApartment.rooms, F.data.startswith("add_rooms:"))
async def add_rooms_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(rooms=value)
    await state.set_state(AddApartment.floor)
    await callback.message.edit_text(
        "Шаг 3 из 7: этаж 👇",
        reply_markup=kb_floor("add"),
    )
    await callback.answer()


@dp.callback_query(AddApartment.floor, F.data.startswith("add_floor:"))
async def add_floor_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await state.update_data(floor=value)
    await state.set_state(AddApartment.price)
    await callback.message.edit_text(
        "Шаг 4 из 7: введите точную цену числом (например: 350)\n\n"
        "Просто отправьте число в чат 👇"
    )
    await callback.answer()


@dp.message(AddApartment.price)
async def add_price_entered(message: Message, state: FSMContext):
    text = message.text.strip().replace("$", "").replace(" ", "")
    if not text.isdigit():
        await message.answer("⚠️ Нужно отправить просто число, например: 350. Попробуйте ещё раз:")
        return
    await state.update_data(price=int(text))
    await state.set_state(AddApartment.kind)
    await message.answer(
        "Шаг 5 из 7: тип помещения 👇",
        reply_markup=kb_kind("add"),
    )


@dp.callback_query(AddApartment.kind, F.data.startswith("add_kind:"))
async def add_kind_chosen(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    label = KIND_OPTIONS.get(value)
    await state.update_data(kind=label)
    await state.set_state(AddApartment.phone)
    await callback.message.edit_text(
        "Шаг 6 из 7: введите номер телефона для связи\n\n"
        "⚠️ Этот номер будет виден только вам (владельцу бота). "
        "Отправьте его в формате, например: +998901234567"
    )
    await callback.answer()


@dp.message(AddApartment.phone)
async def add_phone_entered(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(AddApartment.description)
    await message.answer(
        "Шаг 7 из 7: добавьте краткое описание квартиры (текстом)\n"
        "Например: «Свежий ремонт, мебель, рядом метро»\n\n"
        "Или нажмите «Пропустить».",
        reply_markup=kb_skip_description(),
    )


@dp.callback_query(AddApartment.description, F.data == "add_description:skip")
async def add_description_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(AddApartment.photo)
    await callback.message.edit_text(
        "Отправьте фото квартиры (одно фото) или нажмите «Пропустить».",
        reply_markup=kb_skip_photo(),
    )
    await callback.answer()


@dp.message(AddApartment.description)
async def add_description_entered(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddApartment.photo)
    await message.answer(
        "Отправьте фото квартиры (одно фото) или нажмите «Пропустить».",
        reply_markup=kb_skip_photo(),
    )


@dp.callback_query(AddApartment.photo, F.data == "add_photo:skip")
async def add_photo_skip(callback: CallbackQuery, state: FSMContext):
    await finalize_add_apartment(callback.message, state, photo_id=None, edit=True, user_id=callback.from_user.id)
    await callback.answer()


@dp.message(AddApartment.photo, F.photo)
async def add_photo_entered(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await finalize_add_apartment(message, state, photo_id=photo_id, edit=False, user_id=message.from_user.id)


@dp.message(AddApartment.photo)
async def add_photo_wrong_type(message: Message):
    await message.answer("⚠️ Пришлите фото как изображение, или нажмите «Пропустить» выше.")


async def finalize_add_apartment(message: Message, state: FSMContext, photo_id, edit: bool, user_id: int):
    data = await state.get_data()
    apt_id = db.add_apartment(
        region=data["region"],
        rooms=data["rooms"],
        floor=data["floor"],
        price=data["price"],
        kind=data["kind"],
        phone=data["phone"],
        description=data.get("description"),
        photo_id=photo_id,
    )
    await state.clear()

    text = (
        f"✅ Квартира успешно добавлена! Номер в базе: #{apt_id}\n\n"
        f"📍 {data['region']}\n"
        f"🚪 {data['rooms']} комн.\n"
        f"🏢 {data['floor']}\n"
        f"💰 {data['price']}$\n"
        f"🏷 {data['kind']}\n"
        f"☎️ {data['phone']} (виден только вам)"
    )

    if edit:
        await message.edit_text(text)
    else:
        await message.answer(text)

    await message.answer("Что дальше?", reply_markup=kb_main_menu(user_id))


# ==================== АДМИНСКИЕ КОМАНДЫ ====================

@dp.callback_query(F.data == "admin_list")
async def admin_list_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недоступно.", show_alert=True)
        return
    await send_apartment_list(callback.message)
    await callback.answer()


@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    await send_apartment_list(message)


async def send_apartment_list(message: Message):
    total = db.count_apartments()
    if total == 0:
        await message.answer("База пуста. Добавьте первую квартиру через /add")
        return

    apartments = db.get_all_apartments()
    await message.answer(f"📋 Всего квартир в базе: {total}\n\nПоказываю последние 20 (с номерами телефонов):")

    for apt in apartments[:20]:
        text = (
            f"#{apt['id']} | {apt['region']} | {apt['rooms']} комн. | "
            f"{apt['floor']} | {apt['price']}$ | {apt['kind']}\n"
            f"☎️ {apt['phone']}"
        )
        await message.answer(text)

    if total > 20:
        await message.answer(
            f"Показаны последние 20 из {total}.\n"
            f"Чтобы посмотреть конкретную квартиру — /find ID\n"
            f"Чтобы удалить квартиру — /delete ID"
        )


@dp.message(Command("find"))
async def cmd_find(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /find ID  (например: /find 5)")
        return

    apt = db.get_apartment(int(parts[1]))
    if not apt:
        await message.answer("Квартира с таким ID не найдена.")
        return

    text = (
        f"#{apt['id']}\n"
        f"📍 {apt['region']}\n"
        f"🚪 {apt['rooms']} комн.\n"
        f"🏢 {apt['floor']}\n"
        f"💰 {apt['price']}$\n"
        f"🏷 {apt['kind']}\n"
        f"☎️ {apt['phone']}\n"
        + (f"📝 {apt['description']}\n" if apt["description"] else "")
    )
    if apt["photo_id"]:
        await message.answer_photo(apt["photo_id"], caption=text)
    else:
        await message.answer(text)


@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /delete ID  (например: /delete 5)")
        return

    success = db.delete_apartment(int(parts[1]))
    if success:
        await message.answer(f"✅ Квартира #{parts[1]} удалена.")
    else:
        await message.answer("Квартира с таким ID не найдена.")


@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    """Вспомогательная команда — узнать свой Telegram ID."""
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    total = db.count_apartments()
    await message.answer(f"📊 Всего квартир в базе: {total}")


# ==================== ЗАПУСК ====================

async def main():
    db.init_db()
    logging.info("База данных готова. Запускаю бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
