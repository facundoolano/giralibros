import datetime

from django import template

register = template.Library()


@register.filter(name="timeago")
def humanize_date(dt):
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
        return f"{dt.day}/{dt.month}"
    return f"{dt.day}/{dt.month}/{dt.year}"
