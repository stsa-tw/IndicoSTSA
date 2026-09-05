"""Finding the registrations that still owe money, and saying how much.

The other half of `indico_stsa.reminders`: everything here needs the database
or Indico's own locale-aware formatting, so none of it is unit-tested -- see
the layering note in CLAUDE.md.
"""

from sqlalchemy.orm import joinedload

from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.util.date_time import format_currency
from indico.util.i18n import _
from indico.util.placeholders import Placeholder

from indico_stsa.constants import AMOUNT_PLACEHOLDER
from indico_stsa.reminders import needs_reminder, outstanding_total


def find_unpaid(regform):
    """Every active registration on this form that still owes money.

    The state narrows the query, and the rest of `needs_reminder` is decided in
    Python because neither of the other two facts can be asked of the database:
    `price` is summed from the registration's billable answers and `is_paid`
    comes off its latest transaction.  Both are eager-loaded for exactly that
    reason -- without it, reading them is a fresh query per registration, and
    the price alone walks three relationships deep.

    Ordered the way core orders the registrant list, which is what decides
    whose registration the *Preview email* button quotes the mail against.
    """
    registrations = (Registration.query
                     .with_parent(regform)
                     .filter(~Registration.is_deleted,
                             Registration.state == RegistrationState.unpaid)
                     .options(joinedload('data').joinedload('field_data').joinedload('field'),
                              joinedload('transaction'))
                     .order_by(*Registration.order_by_name)
                     .all())
    return [registration for registration in registrations
            if needs_reminder(state=registration.state.name, price=registration.price,
                              is_paid=registration.is_paid)]


def format_outstanding(registrations, currency):
    """What the whole set owes, formatted for the organizer."""
    return format_currency(outstanding_total(r.price for r in registrations), currency)


class OutstandingAmountPlaceholder(Placeholder):
    """``{amount}`` -- what this registrant still has to pay.

    A reminder that cannot name the amount is barely a reminder, and the body
    is one string sent to everybody, so the figure can only reach the mail as a
    placeholder: core replaces it per recipient in `_send_emails`.

    It is offered to every ``registration-email``, not just ours, because that
    is the only context there is -- placeholders are registered per context for
    the whole instance.  So it also turns up in core's own *E-mail* dialog,
    which is a fair trade for it working in the reminder at all.  The name is
    the reason the whole feature has a switch: two plugins claiming ``amount``
    would make `named_objects_from_signal` raise, and it raises for *every*
    registration e-mail, not just the ones that use the placeholder.
    """

    name = AMOUNT_PLACEHOLDER
    description = _('The amount the registrant still has to pay')

    @classmethod
    def render(cls, regform, registration):
        # `registration` is `None` while the dialog is only *describing* the
        # available placeholders, which is the one call that has nobody to
        # quote a price for.
        if registration is None:
            return ''
        return format_currency(registration.price, registration.currency)
