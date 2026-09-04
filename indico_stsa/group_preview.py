"""Quoting the member price in the group registration plugin's plan picker.

That plugin's picker shows what one person pays under each group plan -- "45.00
SGD each" -- and shows the same number again when somebody pastes a code to
preview the group they are about to join.  Both are worked out in the browser
from the fee in its field data, with the plan's own rate applied to it.  The
member discount never reached that fee, so a signed-in member was quoted the
full price and then charged less.

The picker carries two fees, which is what makes an exact quote possible:
``basePrice`` is the form's standard fee, and ``payerBasePrice`` is what the
person in front of it actually pays before a group plan is applied.  Only the
second is ours to write.  Leaving the standard fee alone is the whole point --
the group plugin works its own rate out from whichever of the two its
``applies_to`` setting names, exactly as it does on the server, so a percentage
plan set against the fee does not quietly start compounding with our discount.

Against a group plugin too old to offer ``payerBasePrice`` the standard fee is
written instead, which is the best that can be done from here: the quote then
carries the discount but works the plan's percentage out from the discounted
fee, leaving it high by the plan's percentage of the discount.  High rather
than low is the direction to be wrong in -- nobody is charged more than they
were shown -- and upgrading that plugin makes it exact.

The fee is what gets rewritten, never the plan list.  The join preview looks the
group's plan up over AJAX and prices it against the same fee, so changing the
fee reaches both quotes, while a rewritten plan list would reach only the first.
It also keeps this from having an opinion about what a group plan is worth,
which is the group plugin's business and not ours.

No quote can include the paid options nobody has chosen yet, so a member who
then picks one pays a little more than the quote -- which is the picker's own
long-standing approximation, and visible to whoever is choosing the option.
"""

from indico_stsa.constants import GROUP_PLAN_FIELD


#: What the person in front of the picker pays before a group plan is applied.
#: The group plugin offers this for exactly this purpose.
PAYER_FEE = 'payerBasePrice'
#: The form's standard fee.  Written only where the group plugin is too old to
#: know about `PAYER_FEE`, since it is also what that plugin works a plan's own
#: rate out from.
STANDARD_FEE = 'basePrice'


def quote_member_price(form_data, base_price):
    """Point the group plan picker at the fee a member actually pays.

    `form_data` is the flat submission data the registration form is rendered
    from, whose ``items`` are camelized field data -- so the fee is a `float`
    like the group plugin's own, because that is what its React prop expects and
    what survives the trip through JSON.

    :return: how many pickers were re-quoted, which is zero on every form that
             does not have the group plugin's field on it.
    """
    items = (form_data or {}).get('items') or {}
    quoted = 0
    for item in items.values():
        if not isinstance(item, dict) or item.get('inputType') != GROUP_PLAN_FIELD:
            continue
        item[PAYER_FEE if PAYER_FEE in item else STANDARD_FEE] = float(base_price)
        quoted += 1
    return quoted
