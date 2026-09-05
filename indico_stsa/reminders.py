"""Who is owed a payment reminder, and what it says.

Split from `indico_stsa.payments` the same way `indico_stsa.discount` is split
from `indico_stsa.pricing`: everything here is decided from plain values, so it
is the half that can be tested without a database.  Going and *finding* the
registrations those values belong to is the other half's job.

The wording is a Python string rather than a Jinja e-mail template on purpose.
It is a starting point, not a template: the organizer reads and edits it in the
dialog before anything is sent, and core's own placeholder machinery
(`{first_name}`, `{event_title}`, `{link}`, and our `{amount}`) fills it in per
recipient at send time -- so there is nothing left for a template module to do
except make the default harder to test.
"""

from decimal import Decimal

from indico.util.i18n import _

from indico_stsa.constants import AMOUNT_PLACEHOLDER, UNPAID_STATE


def needs_reminder(*, state, price, is_paid):
    """Whether a registration in this condition still owes money.

    ``state`` is the *name* of core's `RegistrationState`, which is what keeps
    this module free of Indico imports.

    All three halves are load-bearing:

    * ``unpaid`` -- "Awaiting payment" -- is the only state that means a fee is
      outstanding.  A `complete` registration has either paid or was never
      asked to, and `pending`, `rejected` and `withdrawn` are not waiting on
      money.
    * ``is_paid`` is not the opposite of the state.  A transaction that is
      still `pending` -- a bank transfer nobody has confirmed yet -- counts as
      paid while deliberately leaving the registration `unpaid`, and somebody
      who has already sent the money must not be chased for it.
    * a fee of zero in the `unpaid` state is what core leaves behind when an
      organizer removes the fee from registrations that had not paid it
      (`Update Registration Fee` -> *Remove fee*).  It stops asking for the
      money without moving the state, so the price is the only thing that says
      there is nothing left to pay.
    """
    return state == UNPAID_STATE and not is_paid and price > 0


def outstanding_total(prices):
    """What a set of registrations owes between them."""
    total = Decimal(0)
    for price in prices:
        total += Decimal(str(price or 0))
    return total


def default_subject():
    """The subject the reminder dialog opens with."""
    return str(_('Payment reminder: {event_title}'))


def default_body():
    """The reminder an organizer starts from.

    HTML, because the dialog's editor is a rich text one, and every name in
    braces is a placeholder core replaces per recipient -- so this one string
    becomes a different mail for each person it goes to.

    Every piece is forced to `str` as it goes in.  Indico's `_` hands back a
    lazy string that only picks a translation when it is rendered, which is
    exactly right for a form label defined at import time and exactly wrong
    here: this is called inside the event's locale, and the answer has to be a
    real string that a text field can hold and an organizer can edit.
    """
    amount = '{' + AMOUNT_PLACEHOLDER + '}'
    parts = (
        '<p>', _('Dear {first_name},'), '</p>',
        '<p>', _('We have not yet received the payment for your registration for '
                 '<strong>{event_title}</strong>.'), '</p>',
        '<p>', _('Amount outstanding:'), ' <strong>', amount, '</strong></p>',
        '<p>', _('You can pay from your registration page:'), '<br>{link}</p>',
        '<p>', _('If you have paid already, or if you no longer wish to attend, please reply to this e-mail and '
                 'let us know.'), '</p>',
    )
    return ''.join(str(part) for part in parts)
