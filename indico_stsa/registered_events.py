"""Finding the events a participant has registered for, and describing them.

The other half of `indico_stsa.attendance`: everything here needs the database,
so none of it is unit-tested -- see the layering note in CLAUDE.md.
"""

from sqlalchemy.orm import contains_eager

from indico.core.db import db
from indico.modules.events.models.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.util.date_time import now_utc

from indico_stsa.attendance import STATUSES, overlaps, registration_status
from indico_stsa.constants import EVENTS_API_BY_DEFAULT
from indico_stsa.models.settings import STSASettings
from indico_stsa.util import tables_exist


def find_registered(user, *, statuses, window=(None, None), now=None):
    """``[(registration, status)]`` for `user`, soonest event first.

    Only registrations made with a form that is listed in the events API
    (`STSASettings.include_in_events_api`) are looked at.  A form nobody has
    configured has no settings row, so the join is an outer one and the row's
    absence reads as `EVENTS_API_BY_DEFAULT` -- the same answer the column gives
    a row that is created later.  An install whose tables were never upgraded
    lists nothing instead, whatever the default is.  Registrations of events and
    forms that have been deleted are out as well, and so is anything that is not
    `user`'s -- nobody is ever asked for somebody else's.

    The status and the window are applied to what that leaves, in Python and not
    in SQL.  There is one participant's worth of rows here, and it keeps the
    meaning of both in the one place `indico_stsa.attendance` that is tested.
    """
    if not tables_exist():
        return []
    now = now or now_utc()
    registrations = (Registration.query
                     .join(Registration.event)
                     .join(Registration.registration_form)
                     .outerjoin(STSASettings, STSASettings.registration_form_id == RegistrationForm.id)
                     .filter(Registration.user == user,
                             ~Registration.is_deleted,
                             ~Event.is_deleted,
                             ~RegistrationForm.is_deleted,
                             db.func.coalesce(STSASettings.include_in_events_api, EVENTS_API_BY_DEFAULT))
                     .options(contains_eager(Registration.event),
                              contains_eager(Registration.registration_form))
                     .order_by(Event.start_dt, Registration.id)
                     .all())
    found = []
    for registration in registrations:
        event = registration.event
        status = registration_status(state=registration.state.name, checked_in=registration.checked_in,
                                     start=event.start_dt, end=event.end_dt, now=now)
        if status in statuses and overlaps(event.start_dt, event.end_dt, *window):
            found.append((registration, status))
    return found


def describe(registration, status):
    """One registration as the API shows it: the event, the registration, the status.

    Times are the event's own -- local to where it happens, with the UTC offset
    on them -- because that is the hour the organizer announced; the moments
    that belong to the registration itself are UTC.  One entry per
    *registration*, since the status is the registration's: a participant who
    registered on two forms of one event is listed twice.
    """
    event = registration.event
    regform = registration.registration_form
    return {
        'status': status,
        'event': {
            'id': event.id,
            'title': event.title,
            'url': event.external_url,
            'start_dt': event.start_dt_local.replace(microsecond=0).isoformat(),
            'end_dt': event.end_dt_local.replace(microsecond=0).isoformat(),
            'timezone': event.timezone,
            'venue': event.venue_name or None,
            'room': event.room_name or None,
            'address': event.address or None,
        },
        'registration': {
            'id': registration.id,
            'friendly_id': registration.friendly_id,
            'state': registration.state.name,
            'registered_dt': registration.submitted_dt.replace(microsecond=0).isoformat(),
            'checked_in': registration.checked_in,
            'checked_in_dt': (registration.checked_in_dt.replace(microsecond=0).isoformat()
                              if registration.checked_in_dt else None),
            'form': {'id': regform.id, 'title': regform.title},
        },
    }


def _nullable(kind, **extra):
    return {'type': [kind, 'null'], **extra}


#: What `describe` returns, as JSON Schema, for the API reference.  Kept beside
#: the function it describes so that changing one is changing the other.
ENTRY_SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': list(STATUSES)},
        'event': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'title': {'type': 'string'},
                'url': {'type': 'string', 'format': 'uri'},
                'start_dt': {'type': 'string', 'format': 'date-time',
                             'description': "In the event's own timezone."},
                'end_dt': {'type': 'string', 'format': 'date-time'},
                'timezone': {'type': 'string', 'example': 'Asia/Singapore'},
                'venue': _nullable('string'),
                'room': _nullable('string'),
                'address': _nullable('string'),
            },
        },
        'registration': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'friendly_id': {'type': 'integer'},
                'state': {'type': 'string', 'enum': ['complete', 'pending', 'unpaid', 'rejected', 'withdrawn']},
                'registered_dt': {'type': 'string', 'format': 'date-time'},
                'checked_in': {'type': 'boolean'},
                'checked_in_dt': _nullable('string', format='date-time'),
                'form': {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'title': {'type': 'string'}}},
            },
        },
    },
}
RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {'registrations': {'type': 'array', 'items': ENTRY_SCHEMA}},
}
