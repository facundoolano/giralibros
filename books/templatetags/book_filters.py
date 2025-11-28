import datetime

from django import template

register = template.Library()


@register.filter(name="timeago")
def humanize_date(dt):
    SPANISH_MONTHS = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }

    delta = datetime.datetime.now(datetime.UTC) - dt

    if delta < datetime.timedelta(seconds=60):
        return f"{delta.seconds}s"
    elif delta < datetime.timedelta(hours=1):
        return f"{delta.seconds // 60}m"
    elif delta < datetime.timedelta(days=1):
        return f"{delta.seconds // 60 // 60}h"
    elif delta < datetime.timedelta(days=8):
        return f"{delta.days}d"
    elif delta < datetime.timedelta(days=365):
        month = SPANISH_MONTHS[dt.month]
        return f"{dt.day} {month}"

    month = SPANISH_MONTHS[dt.month]
    return f"{dt.day} {month}, {dt.year}"
