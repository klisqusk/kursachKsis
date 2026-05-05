from datetime import datetime


def format_size(size):
    try:
        size = float(size)
    except (TypeError, ValueError):
        size = 0

    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def format_datetime(value):
    if not value:
        return ""

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value

    return parsed.strftime("%d.%m.%Y %H:%M")
