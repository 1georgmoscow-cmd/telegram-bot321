import calendar
from datetime import date, timedelta
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

RU_MONTHS = [
    "Январь", "Февраль", "Март", "Апрель",
    "Май", "Июнь", "Июль", "Август",
    "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

IGNORE_CB = "noop"


def _month_add(base: date, offset: int) -> tuple[int, int]:
    m = (base.month - 1) + offset
    y = base.year + (m // 12)
    return y, (m % 12) + 1


def month_calendar_kb(available_days: set[str], month_offset: int = 0) -> InlineKeyboardMarkup:
    today = date.today()
    month_later = today + timedelta(days=31)

    year, month = _month_add(today, month_offset)

    cal = calendar.Calendar(firstweekday=0)

    keyboard: list[list[InlineKeyboardButton]] = []

    # header
    keyboard.append([
        InlineKeyboardButton(
            text=f"{RU_MONTHS[month - 1]} {year}",
            callback_data=IGNORE_CB
        )
    ])

    # weekdays
    keyboard.append([
        InlineKeyboardButton(text=d, callback_data=IGNORE_CB)
        for d in WEEKDAYS
    ])

    # days
    for week in cal.monthdatescalendar(year, month):
        row = []

        for day in week:
            day_str = day.strftime("%Y-%m-%d")

            in_month = day.month == month
            in_range = today <= day <= month_later
            available = day_str in available_days

            if not in_month or not in_range:
                row.append(
                    InlineKeyboardButton(text=" ", callback_data=IGNORE_CB)
                )
                continue

            if available:
                row.append(
                    InlineKeyboardButton(
                        text=str(day.day),
                        callback_data=f"pick_date|{day_str}"
                    )
                )
            else:
                row.append(
                    InlineKeyboardButton(
                        text=str(day.day),
                        callback_data=IGNORE_CB
                    )
                )

        keyboard.append(row)

    # nav
    nav = []

    if month_offset > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"cal_month|{month_offset - 1}"
            )
        )

    if month_offset < 1:
        nav.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"cal_month|{month_offset + 1}"
            )
        )

    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton(text="В меню", callback_data="back_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)