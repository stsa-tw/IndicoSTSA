"""The arithmetic that turns a configured rate into money off."""

from decimal import Decimal

import pytest

from indico_stsa.constants import AMOUNT, APPLIES_TO_BASE, APPLIES_TO_TOTAL, PERCENT
from indico_stsa.discount import (DiscountError, discount_for, discountable_amount, format_rate, member_base_price,
                                 quantize, to_decimal)


class TestDiscountableAmount:
    def test_base_ignores_paid_options(self):
        assert discountable_amount(Decimal(100), Decimal(50), APPLIES_TO_BASE) == Decimal(100)

    def test_total_includes_them(self):
        assert discountable_amount(Decimal(100), Decimal(50), APPLIES_TO_TOTAL) == Decimal(150)

    def test_never_negative(self):
        # A registration can carry negative line items -- the group
        # registration plugin's discount is one -- and a negative basis would
        # turn a discount into a charge.
        assert discountable_amount(Decimal(100), Decimal(-500), APPLIES_TO_TOTAL) == Decimal(0)
        assert discountable_amount(Decimal(-10), Decimal(0), APPLIES_TO_BASE) == Decimal(0)

    def test_rejects_unknown_scope(self):
        with pytest.raises(DiscountError):
            discountable_amount(Decimal(100), Decimal(0), 'sideways')


class TestDiscountFor:
    def test_percentage(self):
        assert discount_for(PERCENT, Decimal(20), Decimal(100)) == Decimal('-20.00')

    def test_fixed_amount(self):
        assert discount_for(AMOUNT, Decimal(15), Decimal(100)) == Decimal('-15.00')

    def test_rounds_to_cents_half_up(self):
        assert discount_for(PERCENT, Decimal('33.333'), Decimal('10')) == Decimal('-3.33')
        assert discount_for(PERCENT, Decimal(15), Decimal('1.50')) == Decimal('-0.23')

    def test_never_exceeds_what_it_applies_to(self):
        assert discount_for(AMOUNT, Decimal(500), Decimal(80)) == Decimal('-80.00')

    @pytest.mark.parametrize(('discount_type', 'value', 'discountable'), (
        (None, Decimal(20), Decimal(100)),
        ('', Decimal(20), Decimal(100)),
        (PERCENT, Decimal(0), Decimal(100)),
        (PERCENT, Decimal(-5), Decimal(100)),
        (PERCENT, Decimal(20), Decimal(0)),
        (PERCENT, Decimal(20), Decimal(-10)),
    ))
    def test_nothing_to_take_off(self, discount_type, value, discountable):
        assert discount_for(discount_type, value, discountable) == Decimal(0)

    def test_full_percentage(self):
        assert discount_for(PERCENT, Decimal(100), Decimal('42.50')) == Decimal('-42.50')


class TestMemberBasePrice:
    """The fee a member is quoted before a group plan is applied to it."""

    def test_percentage(self):
        assert member_base_price(Decimal(100), PERCENT, Decimal(20)) == Decimal('80.00')

    def test_fixed_amount(self):
        assert member_base_price(Decimal(100), AMOUNT, Decimal(15)) == Decimal('85.00')

    def test_never_goes_below_zero(self):
        assert member_base_price(Decimal(80), AMOUNT, Decimal(500)) == Decimal('0.00')
        assert member_base_price(Decimal(-10), PERCENT, Decimal(20)) == Decimal('0.00')

    def test_no_rate_is_the_standard_fee(self):
        assert member_base_price(Decimal('42.50'), None, Decimal(20)) == Decimal('42.50')
        assert member_base_price(Decimal('42.50'), PERCENT, Decimal(0)) == Decimal('42.50')

    def test_reads_whatever_the_fee_arrives_as(self):
        # `regform.base_price` is a Decimal, but a quote is worth having even
        # if some caller hands this a float or a string.
        assert member_base_price(45.5, PERCENT, Decimal(10)) == Decimal('40.95')
        assert member_base_price('45.5', PERCENT, Decimal(10)) == Decimal('40.95')

    def test_rounds_to_cents(self):
        assert member_base_price(Decimal('33.33'), PERCENT, Decimal(10)) == Decimal('30.00')


class TestFormatRate:
    def test_percentage_drops_trailing_zeroes(self):
        assert format_rate(PERCENT, Decimal('20.00'), 'SGD') == '20%'
        assert format_rate(PERCENT, Decimal('12.50'), 'SGD') == '12.5%'

    def test_amount_carries_the_currency(self):
        assert format_rate(AMOUNT, Decimal(5), 'SGD') == '5.00 SGD'

    def test_no_rate_is_no_text(self):
        assert format_rate(None, Decimal(20), 'SGD') == ''
        assert format_rate(PERCENT, Decimal(0), 'SGD') == ''


class TestHelpers:
    def test_quantize(self):
        assert quantize(Decimal('1.005')) == Decimal('1.01')
        assert quantize('2.344') == Decimal('2.34')

    @pytest.mark.parametrize(('value', 'expected'), (
        ('12.34', Decimal('12.34')),
        (12.5, Decimal('12.5')),
        (None, Decimal(0)),
        ('nonsense', Decimal(0)),
        ({}, Decimal(0)),
    ))
    def test_to_decimal_never_raises(self, value, expected):
        assert to_decimal(value) == expected
