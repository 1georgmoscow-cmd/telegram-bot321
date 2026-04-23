from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from app.config import Settings
from app.database.db import Database
from app.keyboards.admin import (
    admin_menu_kb,
    slots_manage_kb,
    bookings_manage_kb,
)
from app.utils.dates import format_date


router = Router()


# ---------------- ADMIN MENU ----------------

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


# ---------------- VIEW SCHEDULE ----------------

@router.callback_query(F.data == "admin_view_schedule")
async def view_schedule(callback: CallbackQuery, db: Database):
    days = db.get_month_work_days("2026-01-01", "2026-12-31")

    if not days:
        await callback.message.edit_text(
            "Нет доступных дней.",
            reply_markup=admin_menu_kb(),
        )
        await callback.answer()
        return

    text = "<b>Рабочие дни:</b>\n" + "\n".join(days)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


# ---------------- ADD SLOT (пример-заглушка) ----------------

@router.callback_query(F.data == "admin_add_slot")
async def add_slot(callback: CallbackQuery):
    await callback.message.edit_text(
        "Функция добавления слота (FSM сюда обычно ставят)",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


# ---------------- CANCEL BOOKING ----------------

@router.callback_query(F.data.startswith("admin_cancel_by_id:"))
async def cancel_booking_by_id(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
    settings: Settings,
):
    booking_id = int(callback.data.split(":")[1])

    booking = db.cancel_booking_by_id(booking_id)

    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    await bot.send_message(
        settings.admin_id,
        "<b>Запись отменена</b>\n"
        f"Дата: {format_date(booking['date'])}\n"
        f"Время: {booking['time']}",
        parse_mode="HTML",
    )

    await callback.answer("Удалено")
    await callback.message.edit_text(
        "Запись отменена",
        reply_markup=admin_menu_kb(),
    )