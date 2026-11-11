"""
Обработчики всех сообщений и нажатий на кнопки.
"""
from datetime import date, datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import config
import database as db
import keyboards as kb

router = Router()


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_master = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()


def generate_slots() -> list[str]:
    """Все возможные слоты времени за рабочий день, например ['10:00', '11:00', ...]."""
    slots = []
    hour = config.WORK_START_HOUR
    while hour < config.WORK_END_HOUR:
        slots.append(f"{hour:02d}:00")
        hour += config.SLOT_STEP_MIN // 60
    return slots


async def get_free_slots(master_name: str, booking_date: str) -> list[str]:
    all_slots = generate_slots()
    booked = await db.get_booked_times(master_name, booking_date)
    free = [s for s in all_slots if s not in booked]

    # Если дата — сегодня, убираем слоты, которые уже прошли
    if booking_date == date.today().isoformat():
        now = datetime.now()
        free = [
            s for s in free
            if datetime.strptime(s, "%H:%M").time() > now.time()
        ]
    return free


# ---------- Старт и главное меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Здравствуйте! Это бот записи в {config.SHOP_NAME}.\n"
        "Выберите действие:",
        reply_markup=kb.main_menu_kb(),
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"Это бот записи в {config.SHOP_NAME}.\nВыберите действие:",
        reply_markup=kb.main_menu_kb(),
    )
    await callback.answer()


# ---------- Запись: выбор услуги ----------

@router.callback_query(F.data == "book_start")
async def book_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.choosing_service)
    await callback.message.edit_text(
        "💬Выберите услугу:",
        reply_markup=kb.services_kb(),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_service, F.data.startswith("service_"))
async def choose_service(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[1])
    name, price, duration = config.SERVICES[idx]
    await state.update_data(service_idx=idx)

    if len(config.MASTERS) == 1:
        # Мастер один — выбираем автоматически и сразу идём к выбору даты
        await state.update_data(master_idx=0)
        await state.set_state(BookingStates.choosing_date)
        await callback.message.edit_text(
            f"Услуга: {name} — {price}₽\n\nВыберите дату:",
            reply_markup=kb.dates_kb(),
        )
    else:
        await state.set_state(BookingStates.choosing_master)
        await callback.message.edit_text(
            f"Услуга: {name} — {price}₽\n\nВыберите мастера:",
            reply_markup=kb.masters_kb(),
        )
    await callback.answer()


# ---------- Запись: выбор мастера (если их больше одного) ----------

@router.callback_query(BookingStates.choosing_master, F.data.startswith("master_"))
async def choose_master(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[1])
    await state.update_data(master_idx=idx)
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        f"Мастер: {config.MASTERS[idx]}\n\nВыберите дату:",
        reply_markup=kb.dates_kb(),
    )
    await callback.answer()


# ---------- Запись: выбор даты ----------

@router.callback_query(BookingStates.choosing_date, F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    booking_date = callback.data.split("_", 1)[1]
    data = await state.get_data()
    master_name = config.MASTERS[data["master_idx"]]

    free_slots = await get_free_slots(master_name, booking_date)
    if not free_slots:
        await callback.answer("На эту дату свободных слотов нет 🙁", show_alert=True)
        return

    await state.update_data(booking_date=booking_date)
    await state.set_state(BookingStates.choosing_time)
    d = date.fromisoformat(booking_date)
    await callback.message.edit_text(
        f"Дата: {d.strftime('%d.%m.%Y')}\n\nВыберите время:",
        reply_markup=kb.times_kb(free_slots),
    )
    await callback.answer()


# ---------- Запись: выбор времени ----------

@router.callback_query(BookingStates.choosing_time, F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    booking_time = callback.data.split("_", 1)[1]
    await state.update_data(booking_time=booking_time)
    await state.set_state(BookingStates.confirming)

    data = await state.get_data()
    name, price, _duration = config.SERVICES[data["service_idx"]]
    master_name = config.MASTERS[data["master_idx"]]
    d = date.fromisoformat(data["booking_date"])

    summary = (
        "Проверьте данные записи😅:\n\n"
        f"Услуга: {name} — {price}₽\n"
        f"Мастер: {master_name}\n"
        f"Дата: {d.strftime('%d.%m.%Y')}\n"
        f"Время: {booking_time}\n"
    )
    await callback.message.edit_text(summary, reply_markup=kb.confirm_kb())
    await callback.answer()


# ---------- Запись: подтверждение ----------

@router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    name, price, _duration = config.SERVICES[data["service_idx"]]
    master_name = config.MASTERS[data["master_idx"]]
    booking_date = data["booking_date"]
    booking_time = data["booking_time"]

    # Проверяем, что слот всё ещё свободен (на случай гонки записей)
    free_slots = await get_free_slots(master_name, booking_date)
    if booking_time not in free_slots:
        await callback.answer(
            "Увы, это время только что заняли. Выберите другое.", show_alert=True
        )
        await state.set_state(BookingStates.choosing_time)
        await callback.message.edit_text(
            "Выберите другое время:",
            reply_markup=kb.times_kb(free_slots),
        )
        return

    user = callback.from_user
    user_name = f"{user.full_name} (@{user.username})" if user.username else user.full_name

    booking_id = await db.add_booking(
        user_id=user.id,
        user_name=user_name,
        service_name=name,
        service_price=price,
        master_name=master_name,
        booking_date=booking_date,
        booking_time=booking_time,
    )

    d = date.fromisoformat(booking_date)
    await callback.message.edit_text(
        "✅ Запись подтверждена!\n\n"
        f"Услуга: {name} — {price}₽\n"
        f"Мастер: {master_name}\n"
        f"Дата: {d.strftime('%d.%m.%Y')}\n"
        f"Время: {booking_time}\n\n"
        "Ждём вас! Отменить запись можно в разделе «Мои записи».",
        reply_markup=kb.main_menu_kb(),
    )
    await state.clear()
    await callback.answer()

    # Уведомление администратору
    if config.ADMIN_ID:
        try:
            await bot.send_message(
                config.ADMIN_ID,
                "🆕 Новая запись!\n\n"
                f"Клиент: {user_name}\n"
                f"Услуга: {name} — {price}₽\n"
                f"Мастер: {master_name}\n"
                f"Дата: {d.strftime('%d.%m.%Y')}\n"
                f"Время: {booking_time}\n"
                f"ID записи: {booking_id}",
            )
        except Exception:
            pass  # админ мог не запустить бота (/start) — не роняем бота из-за этого


# ---------- Мои записи и отмена ----------

@router.callback_query(F.data == "my_bookings")
async def my_bookings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    bookings = await db.get_user_bookings(callback.from_user.id)
    if not bookings:
        await callback.message.edit_text(
            "У вас пока нет активных записей.",
            reply_markup=kb.main_menu_kb(),
        )
    else:
        await callback.message.edit_text(
            "Ваши записи (нажмите, чтобы отменить):",
            reply_markup=kb.my_bookings_kb(bookings),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_"))
async def cancel_booking(callback: CallbackQuery, bot: Bot):
    booking_id = int(callback.data.split("_")[1])
    booking = await db.get_booking_by_id(booking_id)

    if not booking or booking[1] != callback.from_user.id:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    (_id, _user_id, user_name, service_name, service_price,
     master_name, booking_date, booking_time, status) = booking

    if status == "cancelled":
        await callback.answer("Эта запись уже отменена.", show_alert=True)
        return

    await db.cancel_booking(booking_id)
    await callback.answer("Запись отменена.")

    bookings = await db.get_user_bookings(callback.from_user.id)
    if not bookings:
        await callback.message.edit_text(
            "У вас пока нет активных записей.",
            reply_markup=kb.main_menu_kb(),
        )
    else:
        await callback.message.edit_text(
            "Ваши записи (нажмите, чтобы отменить):",
            reply_markup=kb.my_bookings_kb(bookings),
        )

    if config.ADMIN_ID:
        try:
            d = date.fromisoformat(booking_date)
            await bot.send_message(
                config.ADMIN_ID,
                "❌ Запись отменена клиентом\n\n"
                f"Клиент: {user_name}\n"
                f"Услуга: {service_name} — {service_price}₽\n"
                f"Мастер: {master_name}\n"
                f"Дата: {d.strftime('%d.%m.%Y')}\n"
                f"Время: {booking_time}",
            )
        except Exception:
            pass
