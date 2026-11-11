"""
Построение inline-клавиатур для всех шагов бота.
"""
from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записаться", callback_data="book_start")
    kb.button(text="🗂 Мои записи", callback_data="my_bookings")
    kb.adjust(1)
    return kb.as_markup()


def services_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, (name, price, _duration) in enumerate(config.SERVICES):
        kb.button(text=f"{name} — {price}₽", callback_data=f"service_{i}")
    kb.button(text="⬅️ Назад", callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


def masters_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, name in enumerate(config.MASTERS):
        kb.button(text=name, callback_data=f"master_{i}")
    kb.button(text="⬅️ Назад", callback_data="book_start")
    kb.adjust(1)
    return kb.as_markup()


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def dates_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    today = date.today()
    for offset in range(config.DAYS_AHEAD):
        d = today + timedelta(days=offset)
        label = f"{d.strftime('%d.%m')} ({WEEKDAYS_RU[d.weekday()]})"
        kb.button(text=label, callback_data=f"date_{d.isoformat()}")
    kb.button(text="⬅️ Назад", callback_data="book_start")
    kb.adjust(3)
    return kb.as_markup()


def times_kb(free_slots: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in free_slots:
        kb.button(text=t, callback_data=f"time_{t}")
    kb.button(text="⬅️ Назад", callback_data="book_start")
    kb.adjust(4)
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm_booking")
    kb.button(text="❌ Отмена", callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


def my_bookings_kb(bookings: list[tuple]) -> InlineKeyboardMarkup:
    """bookings: список кортежей (id, service_name, price, master, date, time)."""
    kb = InlineKeyboardBuilder()
    for b in bookings:
        booking_id, service_name, _price, _master, b_date, b_time = b
        d = date.fromisoformat(b_date)
        label = f"❌ {d.strftime('%d.%m')} {b_time} — {service_name}"
        kb.button(text=label, callback_data=f"cancel_{booking_id}")
    kb.button(text="⬅️ Назад", callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()
