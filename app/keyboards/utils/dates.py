from datetime import datetime


def format_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d.%m.%Y")