from datetime import datetime

def format_date(date_str: str) -> str:
    if not date_str:
        return "—"
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_str