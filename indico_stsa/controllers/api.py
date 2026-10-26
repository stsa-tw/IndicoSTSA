"""Participant-facing API endpoints."""

import pytz
from flask import jsonify, request, session
from werkzeug.exceptions import BadRequest

from indico.core.config import config
from indico.web.rh import RHProtected, json_errors, oauth_scope

from indico_stsa.attendance import parse_statuses, parse_window
from indico_stsa.registered_events import describe, find_registered


@json_errors
@oauth_scope('read:user')
class RHSTSARegisteredEvents(RHProtected):
    """The events the signed-in participant has registered for.

    Always the caller's own: there is no way to name somebody else, so there is
    nothing here for an organizer's token to be used for either.  It answers to
    a session or to an OAuth token or personal token with the ``read:user``
    scope -- core's scope for information about the signed-in user, and the
    narrowest it has that this is a fair description of.  Without a scope of its
    own, core would have asked for ``read:everything``, which it reserves for
    things that are not meant as an API.

    * ``from`` / ``to`` -- keep the events that take place, even in part, in
      this window.  ISO 8601 dates or date-times; a date alone is the whole day,
      so ``to=2026-11-30`` includes the 30th.  No UTC offset means Indico's own
      timezone.
    * ``status`` -- which of `indico_stsa.attendance.STATUSES` to list, once or
      comma-separated.  Everything but ``withdrawn`` and ``rejected`` if absent.

    A malformed value is a 400 saying which one, and never an empty list.
    """

    def _process(self):
        try:
            statuses = parse_statuses(request.args.getlist('status'))
            window = parse_window(request.args.get('from'), request.args.get('to'),
                                  tz=pytz.timezone(config.DEFAULT_TIMEZONE))
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
        found = find_registered(session.user, statuses=statuses, window=window)
        return jsonify(registrations=[describe(registration, status) for registration, status in found])
