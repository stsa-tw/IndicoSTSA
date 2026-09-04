"""Writing the member discount onto a registration.

The discount is stored as a value on our own billable field rather than as a
``price_adjustment``, so it shows up on the invoice as a named line with a
rate next to it instead of an unlabelled "Price adjustment" row.

Core hands `calculate_price` only the stored value and the versioned field
data -- not the registration -- so the amount has to be computed here and
written into the value beforehand.  Everything that renders the line does get
the whole `RegistrationData`, which is how `indico_stsa.fields` can describe
the discount as it stands right now.

`will_be_discounted` and `preview_base_price` read the same decision forwards,
for prices that have to be quoted before there is a registration to price --
see `indico_stsa.group_preview`.
"""

from decimal import Decimal

from flask import has_request_context, session

from indico.core.db import db

from indico_stsa.constants import GROUP_DISCOUNT_FIELD, MEMBER_DISCOUNT_FIELD
from indico_stsa.discount import discount_for, discountable_amount, member_base_price, quantize, to_decimal
from indico_stsa.util import (find_field, get_discount_data, get_settings, registration_is_member,
                              reprice_group_of, set_discount_data)


#: Input types whose price must never be part of what a discount is calculated
#: from.  Ours is excluded for the obvious reason -- otherwise the discount
#: would change its own basis.  The group registration plugin's is excluded so
#: that the two plugins cannot chase each other: its line is calculated from
#: everything except itself, *including* ours, so if ours were calculated from
#: its line too, each recomputation would move both.  Excluding it here makes
#: our amount depend only on the fee and the paid options, and leaves the group
#: discount free to stack on top.
DISCOUNT_FIELDS = frozenset({MEMBER_DISCOUNT_FIELD, GROUP_DISCOUNT_FIELD})


def _other_items_total(registration):
    """Everything billable on the registration except the discount lines."""
    excluded_ids = set()
    for input_type in DISCOUNT_FIELDS:
        field = find_field(registration.registration_form, input_type)
        if field is not None:
            excluded_ids.add(field.id)
    total = Decimal(0)
    for data in registration.data:
        if data.field_data.field_id in excluded_ids:
            continue
        total += Decimal(str(data.price or 0))
    return total


def compute_discount(registration, settings):
    """What this registration's member discount is worth, as a negative amount."""
    base_price = Decimal(str(registration.base_price or 0))
    discountable = discountable_amount(base_price, _other_items_total(registration), settings.applies_to)
    return discount_for(settings.discount_type, settings.discount_value, discountable)


def is_member_discounted(registration):
    """Whether this registration already carries the member discount.

    Read from the stored value rather than recomputed, because that is what
    makes the discount stick: someone who earned it while signed in keeps it
    when they later edit their registration through the link in their
    confirmation e-mail, signed out.
    """
    data = get_discount_data(registration)
    return bool(data and data.data and data.data.get('member'))


def will_be_discounted(registration, *, management=False):
    """Whether the discount is going to land on the registration being filled in.

    This is the same decision `apply_member_discount` makes, read forwards: it
    is what lets a price be quoted before there is anything to price.  A
    registration that is being edited answers for itself; a new one answers for
    whoever is filling it in, and being signed in is exactly what the notice
    above the form promises is enough.
    """
    if registration is not None:
        if is_member_discounted(registration):
            return True
        if registration.is_paid:
            # `apply_member_discount(upgrade_only=True)` will not grant it now:
            # there would be no way to give the difference back.
            return False
        return registration_is_member(registration, management=management)
    # In the management area the fee belongs to somebody who is not in the
    # room, and whether their address turns out to be an account's is not
    # knowable from here.  The standard fee is the honest quote.
    return not management and has_request_context() and session.user is not None


def preview_base_price(regform, *, management=False, registration=None):
    """The registration fee to quote to whoever is looking at the form.

    ``None`` when the standard fee is already the right answer -- the discount
    is off, or this visitor is not going to get it -- which is what keeps the
    plugin invisible on every form it is not configured for.
    """
    settings = get_settings(regform)
    if settings is None or not settings.member_discount_enabled:
        return None
    if not will_be_discounted(registration, management=management):
        return None
    return member_base_price(regform.base_price, settings.discount_type, settings.discount_value)


def apply_member_discount(registration, *, management=False, upgrade_only=False):
    """Write (or clear) this registration's member discount line.

    :param management: the caller is an organizer acting deliberately, which is
                       what lets the discount be applied to a registration made
                       before it was switched on.
    :param upgrade_only: never take an earned discount away.  Used when a
                         registration is modified, so that editing an answer
                         cannot cost somebody a discount they already have --
                         the modification may well be happening from a link in
                         an e-mail, with nobody signed in.
    :return: the amount written, as a negative `Decimal` (zero if none).
    """
    if registration is None or registration.is_deleted:
        return Decimal(0)

    settings = get_settings(registration.registration_form)
    enabled = settings is not None and settings.member_discount_enabled

    if not enabled:
        # Switching the discount off has to take it back off the invoices;
        # leaving stale lines behind would quietly keep charging the old price.
        return _write(registration, {})

    already = is_member_discounted(registration)
    if upgrade_only and not already and registration.is_paid:
        # Somebody who signs in and edits a registration they have already paid
        # for would otherwise end up over-paid, with no way for Indico to give
        # the difference back: a transaction is one amount against one
        # registration, and there is no partial-payment concept to net it off.
        # An organizer can still grant it deliberately, with "Apply to existing
        # registrations", and refund the difference themselves.
        return Decimal(0)

    member = (already if upgrade_only else False) or registration_is_member(registration, management=management)
    if not member:
        return _write(registration, {})

    amount = compute_discount(registration, settings)
    if amount == 0:
        # An empty value keeps the row out of `billable_data`, so no zero-value
        # "Member discount" line clutters the invoice.  `member` is still
        # recorded, so a later change that makes the discount worth something
        # picks it up.
        return _write(registration, {'member': True})

    return _write(registration, {
        'member': True,
        'rate': str(settings.discount_value),
        'rate_type': settings.discount_type,
        'applies_to': settings.applies_to,
        'amount': str(quantize(amount)),
    })


def clear_member_discount(registration):
    """Drop the discount from a registration entirely."""
    return _write(registration, {})


def _write(registration, value):
    """Store `value`, then let everything downstream catch up."""
    amount = to_decimal(value.get('amount', 0)) if value else Decimal(0)
    previous = get_discount_data(registration)
    if previous is None and not value:
        # Nothing stored and nothing to store: do not provision a field, and do
        # not touch the registration at all.
        return amount
    if previous is not None and (previous.data or {}) == value:
        return amount

    set_discount_data(registration, value)
    db.session.flush()
    # Our line just changed what the group plugin's line is calculated from.
    reprice_group_of(registration)
    if not registration.is_deleted:
        registration.sync_state()
    return amount
