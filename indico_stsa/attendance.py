"""Where a registration stands, and which ones the events API was asked for.

Split from `indico_stsa.registered_events` the same way `indico_stsa.reminders`
is split from `indico_stsa.payments`: everything here is decided from plain
values, so it is the half that can be tested without a database, and it is the
only place that has an opinion about what "no show" means.  The query that goes
and finds the registrations those values belong to is the other half's job --
and it deliberately does *not* repeat any of this in SQL, so the status a
registration is listed under and the status it is filtered by cannot disagree.
"""

from datetime import date, datetime, time, timedelta


#: What a registration is listed under.  One of these per registration, decided
#: by `registration_status`; ``unpaid`` is not among them because it says
#: nothing about whether somebody came -- the payload carries the registration's
#: own state for a client that wants to flag it.
UPCOMING = 'upcoming'
ONGOING = 'ongoing'
CHECKED_IN = 'checked_in'
NO_SHOW = 'no_show'
PENDING = 'pending'
WITHDRAWN = 'withdrawn'
REJECTED = 'rejected'

STATUSES = (UPCOMING, ONGOING, CHECKED_IN, NO_SHOW, PENDING, WITHDRAWN, REJECTED)

#: What is listed when the caller does not say.  A registration that was
#: withdrawn or turned down is not an event somebody is going to, so it has to
#: be asked for by name.
DEFAULT_STATUSES = frozenset(STATUSES) - {WITHDRAWN, REJECTED}

#: The names of core's `RegistrationState` that decide a status without looking
#: at the clock.  Spelled out, like `constants.UNPAID_STATE`, so this module
#: stays free of Indico imports.
_CANCELLED_STATES = frozenset({WITHDRAWN, REJECTED})
_PENDING_STATE = 'pending'


def registration_status(*, state, checked_in, start, end, now):
    """What a registration should be listed as.

    ``state`` is the *name* of core's `RegistrationState`.  In the order they
    are decided:

    * a withdrawn or rejected registration is that, whatever the calendar says;
    * one still waiting for an organizer's approval is ``pending`` -- the place
      is not theirs yet, so calling it ``upcoming`` would promise one;
    * somebody who has checked in has, whether or not the event is over;
    * otherwise it is the clock.  ``no_show`` needs the event to be *over*: while
      it is on, somebody who has not arrived yet is merely ``ongoing``.

    Awaiting payment is not a status.  Such a registration holds a place and can
    be checked in, so it is ``upcoming`` or ``no_show`` like any other.
    """
    if state in _CANCELLED_STATES:
        return state
    if state == _PENDING_STATE:
        return PENDING
    if checked_in:
        return CHECKED_IN
    if now >= end:
        return NO_SHOW
    if now >= start:
        return ONGOING
    return UPCOMING


def overlaps(start, end, window_from, window_to):
    """Whether an event running from `start` to `end` falls into the window.

    The window is half-open, ``[window_from, window_to)``, and either end may be
    ``None`` for "no limit".  An event is in it if any of it is: a three-day
    conference is part of the week it ends in as well as the one it starts in.

    An event that ends at the very moment the window opens is *not* in it -- a
    party that runs until midnight belongs to the day before -- except that an
    event of no length at all, which core allows, is in the window it starts in.
    """
    if window_from is not None and not (end > window_from or start >= window_from):
        return False
    return window_to is None or start < window_to


def parse_statuses(values):
    """The set of statuses asked for, from every ``status`` in the query string.

    Each may carry several, comma-separated, so ``?status=upcoming,ongoing`` and
    ``?status=upcoming&status=ongoing`` mean the same.  Nothing asked for is
    `DEFAULT_STATUSES`; a name that is not a status is an error rather than
    quietly matching nothing, because a typo that returns an empty list looks
    exactly like a participant with no events.
    """
    asked = {part.strip().lower() for value in values for part in value.split(',') if part.strip()}
    if not asked:
        return DEFAULT_STATUSES
    if unknown := asked - set(STATUSES):
        raise ValueError(f"Unknown status {', '.join(sorted(unknown))}. It has to be one of: {', '.join(STATUSES)}.")
    return frozenset(asked)


def parse_window(window_from, window_to, *, tz):
    """The ``from`` and ``to`` of the query string, as ``(start, end)``.

    Both optional.  ``tz`` is where a date, or a time with no UTC offset, is
    read -- the instance's own timezone, which is the one an organizer meant when
    they wrote the event's dates down.
    """
    start = _parse_moment(window_from, 'from', tz) if window_from else None
    end = _parse_moment(window_to, 'to', tz, upper=True) if window_to else None
    if start is not None and end is not None and end <= start:
        raise ValueError('`to` has to be later than `from`.')
    return start, end


def _parse_moment(value, name, tz, *, upper=False):
    """Read an ISO 8601 date or date and time.

    A date alone stands for the whole of that day, so as the upper bound it means
    the *end* of it: ``to=2026-11-30`` includes the 30th, which is what anybody
    who writes it expects.
    """
    value = value.strip()
    try:
        try:
            day = date.fromisoformat(value)
        except ValueError:
            moment = datetime.fromisoformat(value)
        else:
            moment = datetime.combine(day, time.min)
            if upper:
                moment += timedelta(days=1)
    except ValueError:
        # The `+` of a UTC offset is a space by the time it gets here when a
        # client did not percent-encode it, and the likeliest reason for a
        # perfectly good timestamp to be refused.
        raise ValueError(f'`{name}` is not an ISO 8601 date or time: {value!r}. A + in an offset has to be written '
                         '%2B in a URL.') from None
    return moment if moment.tzinfo is not None else _attach(moment, tz)


def _attach(moment, tz):
    # pytz's zones have to be asked to `localize`; `replace(tzinfo=...)` would
    # give a pytz zone its first, long-obsolete offset.  Anything else (a fixed
    # offset, `zoneinfo`) is what `replace` is for.
    if hasattr(tz, 'localize'):
        return tz.localize(moment)
    return moment.replace(tzinfo=tz)
