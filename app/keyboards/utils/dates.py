from datetime import datetime


def format_date(date_str: str) -> str:
    """YYYY-MM-DD → DD.MM.YYYY"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return date_str  # на случай кривых данных


def format_datetime(date_str: str, time_str: str) -> str:
    """YYYY-MM-DD + HH:MM → DD.MM.YYYY HH:MM"""
    try:
        return f"{format_date(date_str)} {time_str}"
    except Exception:
        return f"{date_str} {time_str}"