"""The arithmetic that turns a configured rate into money off.

Nothing in here touches Indico or the database, which is what makes it
straightforward to test: everything that decides *whether* somebody gets the
discount lives in `indico_stsa.pricing`, and everything that decides *how much*
lives here.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from indico_stsa.constants import APPLIES_TO, APPLIES_TO_BASE, PERCENT


#: Money is always rounded to whole cents, half up.  Indico stores prices as
#: ``numeric(11, 2)``, so anything finer would be truncated by the database
#: anyway, and we would rather round where we can test it.
CENTS = Decimal('0.01')


class DiscountError(ValueError):
    """Raised when a discount configuration cannot be used."""


def quantize(value):
    """Round a money amount to whole cents."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def to_decimal(value, default=Decimal(0)):
    """Read a number out of JSON or a form without ever raising."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def discountable_amount(base_price, other_items_total, applies_to):
    """The part of a registration's price the discount is calculated against.

    `other_items_total` must exclude every discount line -- ours and the group
    registration plugin's -- or the discount would change what the discount is
    calculated from.  See `indico_stsa.pricing` for why that matters.
    """
    if applies_to not in APPLIES_TO:
        raise DiscountError(f'unknown applies_to: {applies_to!r}')
    if applies_to == APPLIES_TO_BASE:
        return max(Decimal(base_price), Decimal(0))
    return max(Decimal(base_price) + Decimal(other_items_total), Decimal(0))


def discount_for(discount_type, value, discountable):
    """What a rate is worth, as a **negative** amount in whole cents.

    Clamped to `discountable`, so a 100-dollar discount on an 80-dollar fee
    gives back 80, not 100: Indico clamps the total at zero regardless, and we
    would rather the invoice line matched the total.
    """
    value = to_decimal(value)
    if not discount_type or value <= 0:
        return Decimal(0)
    discountable = Decimal(discountable)
    if discountable <= 0:
        return Decimal(0)

    raw = discountable * value / Decimal(100) if discount_type == PERCENT else value
    return -min(quantize(raw), quantize(discountable))


def member_base_price(base_price, discount_type, discount_value):
    """The registration fee as a member is quoted it, before any group plan.

    Calculated from the fee alone whatever `applies_to` says.  A quote is read
    before anything on the form has been filled in, so there are no paid
    options to add to the basis yet -- which means a member who then picks one
    pays a little less than the quote rather than a little more.
    """
    base_price = max(to_decimal(base_price), Decimal(0))
    return quantize(base_price + discount_for(discount_type, discount_value, base_price))


def format_rate(discount_type, value, currency):
    """The rate as a participant reads it: "20% off" or "5.00 SGD off"."""
    value = to_decimal(value)
    if not discount_type or value <= 0:
        return ''
    if discount_type == PERCENT:
        return f'{_trim(value)}%'
    return f'{quantize(value)} {currency}'


def _trim(value):
    """Render a Decimal without trailing zeroes (15 rather than 15.00).

    The `f` format is what keeps this readable: ``Decimal('10.0').normalize()``
    is ``Decimal('1E+1')``, and ``str()`` on that would put "1E+1% off" on the
    invoice.
    """
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return format(normalized.to_integral_value(), 'f')
    return format(normalized, 'f')
