"""Who gets chased for a registration fee, and what the chasing letter says.

`indico_stsa.payments` narrows the query to the `unpaid` state and then asks
`needs_reminder` about each row it got back, so these are the tests for the two
conditions the database cannot express -- a fee of zero, and a payment that has
been made but not yet confirmed.
"""

from decimal import Decimal

import pytest

from indico_stsa.constants import AMOUNT_PLACEHOLDER
from indico_stsa.reminders import default_body, default_subject, needs_reminder, outstanding_total


class TestNeedsReminder:
    def test_an_unpaid_registration_with_a_fee(self):
        assert needs_reminder(state='unpaid', price=Decimal('40.00'), is_paid=False)

    @pytest.mark.parametrize('state', ('complete', 'pending', 'rejected', 'withdrawn'))
    def test_only_the_unpaid_state_owes_anything(self, state):
        # `complete` has either paid or was never asked to; the other three are
        # not waiting on money at all.
        assert not needs_reminder(state=state, price=Decimal('40.00'), is_paid=False)

    def test_a_pending_transaction_counts_as_paid(self):
        # A bank transfer nobody has confirmed yet leaves the registration
        # `unpaid` while `is_paid` is already true.  Chasing somebody who has
        # sent the money is exactly the mail this must not send.
        assert not needs_reminder(state='unpaid', price=Decimal('40.00'), is_paid=True)

    @pytest.mark.parametrize('price', (Decimal(0), Decimal('0.00'), 0))
    def test_nothing_left_to_pay(self, price):
        # What core leaves behind when an organizer removes the fee from the
        # registrations that had not paid it: the state stays `unpaid`.
        assert not needs_reminder(state='unpaid', price=price, is_paid=False)


class TestOutstandingTotal:
    def test_adds_the_prices_up(self):
        assert outstanding_total([Decimal('40.00'), Decimal('12.50')]) == Decimal('52.50')

    def test_nobody_owes_nothing(self):
        assert outstanding_total([]) == Decimal(0)

    def test_survives_a_missing_price(self):
        assert outstanding_total([Decimal('40.00'), None]) == Decimal('40.00')

    def test_floats_do_not_drift(self):
        # `Decimal(0.1)` is not `Decimal('0.1')`, and a total shown to an
        # organizer must not end in fourteen decimal places.
        assert outstanding_total([0.1, 0.2]) == Decimal('0.3')


class TestDefaultMessage:
    def test_the_subject_names_the_event(self):
        # Placeholders are replaced in the subject as well as the body.
        assert '{event_title}' in default_subject()

    @pytest.mark.parametrize('placeholder', ('{first_name}', '{event_title}', '{link}'))
    def test_the_body_uses_core_placeholders(self, placeholder):
        assert placeholder in default_body()

    def test_the_body_asks_for_the_amount_we_provide(self):
        # The one placeholder that is ours; `indico_stsa.payments` answers to
        # this name and the two have to agree.
        assert '{' + AMOUNT_PLACEHOLDER + '}' in default_body()

    def test_the_body_is_html(self):
        # The dialog's editor is a rich text one, and core sanitizes rather
        # than escapes the body, so paragraphs have to be markup.
        assert default_body().startswith('<p>')
