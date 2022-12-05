from calendar import monthrange
from app.models import *
from app import db
from datetime import datetime


def save(start, end, txt, color, bg, id=None, calendar_id=None):
    start = datetime.fromisoformat(start)
    end = datetime.fromisoformat(end)

    if id is None:
        calendar = Calendar.query.get(calendar_id)
        event = Event(**dict(
            start=start,
            end=end,
            text=txt,
            color=color,
            bg=bg
        ))
        calendar.events.append(event)
    else:
        event = Event.query.get(id)
        event.start, event.end, event.text, event.color, event.bg = start, end, txt, color, bg
    db.session.commit()
    return True


def delete(id):
    Event.query.filter_by(id=id).delete()
    db.session.commit()
    return True


def get(month, year, calendars_ids=None):
    daysInMonth = str(monthrange(year, month)[1])
    month = month if month > 10 else "0" + str(month)
    dateYM = str(year) + "-" + str(month) + "-"
    start = dateYM + "01 00:00:00"
    end = dateYM + daysInMonth + " 23:59:59"
    rows = []
    if calendars_ids:
        rows = Event.query.filter((Event.calendar_id.in_(calendars_ids)) & (Event.start.between(
            start, end) | Event.end.between(start, end) | ((Event.start <= start) & (Event.end >= end)))).all()
    else:
        rows = Event.query.all()
    if len(rows) == 0:
        return None
    data = {}
    for r in rows:
        data[r.id] = {
            "s": r.start, "e": r.end,
            "c": r.color, "b": r.bg,
            "t": r.text
        }
    return data
