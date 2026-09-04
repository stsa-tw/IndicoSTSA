"""The group plan picker has to quote the price a member actually pays.

The picker is the group registration plugin's, and it works out "45.00 SGD
each" in the browser from two fees in its field data: the form's standard fee,
which a plan's own rate is worked out from, and what the person in front of it
pays before a group plan.  `quote_member_price` writes the second in the flat
submission data the registration form is rendered from -- and falls back to the
first against a group plugin too old to offer it, which is the case these tests
pin hardest, because getting it the wrong way round would silently compound two
discounts.  Nothing here needs a database: the data is a plain dict by the time
it reaches this module.
"""

import json
from decimal import Decimal

from indico_stsa.constants import GROUP_PLAN_FIELD, MEMBER_DISCOUNT_FIELD
from indico_stsa.group_preview import PAYER_FEE, STANDARD_FEE, quote_member_price


def field(id, input_type, **extra):
    """One camelized field entry, as `get_flat_section_submission_data` makes it."""
    return {'id': id, 'inputType': input_type, 'htmlName': f'field_{id}', **extra}


def form_data(*items):
    return {'sections': {1: {'id': 1, 'title': 'Registration'}},
            'items': {item['id']: item for item in items}}


class TestQuoteMemberPrice:
    def test_requotes_the_picker(self):
        data = form_data(field(7, GROUP_PLAN_FIELD, basePrice=50.0, payerBasePrice=50.0, currency='SGD'))
        assert quote_member_price(data, Decimal('45.00')) == 1
        assert data['items'][7][PAYER_FEE] == 45.0

    def test_the_standard_fee_is_not_ours_to_move(self):
        # It is what the group plugin works a plan's own rate out from when the
        # organizer has set that rate against the fee.  Moving it would make a
        # percentage plan compound with the member discount, which is the one
        # thing the server does not do.
        data = form_data(field(7, GROUP_PLAN_FIELD, basePrice=50.0, payerBasePrice=50.0))
        quote_member_price(data, Decimal('45.00'))
        assert data['items'][7][STANDARD_FEE] == 50.0

    def test_an_older_group_plugin_still_gets_the_discount(self):
        # Nothing to write the payer's fee into, so the standard fee carries it:
        # a quote that is a little high beats one that ignores the discount.
        data = form_data(field(7, GROUP_PLAN_FIELD, basePrice=50.0))
        assert quote_member_price(data, Decimal('45.00')) == 1
        assert data['items'][7][STANDARD_FEE] == 45.0
        assert PAYER_FEE not in data['items'][7]

    def test_leaves_everything_else_alone(self):
        picker = field(7, GROUP_PLAN_FIELD, basePrice=50.0, payerBasePrice=50.0)
        other = field(8, 'single_choice', price=10, basePrice=50.0)
        internal = field(9, MEMBER_DISCOUNT_FIELD)
        data = form_data(picker, other, internal)
        quote_member_price(data, Decimal('45.00'))
        assert data['items'][8] == other
        assert data['items'][8]['basePrice'] == 50.0
        assert data['items'][9] == internal
        assert data['sections'] == {1: {'id': 1, 'title': 'Registration'}}

    def test_a_form_without_the_group_plugin(self):
        # By far the most common case: the group registration plugin is
        # optional, and most forms have no picker to re-quote.
        data = form_data(field(7, 'text'), field(8, 'number', price=5))
        before = json.dumps(data, sort_keys=True)
        assert quote_member_price(data, Decimal('45.00')) == 0
        assert json.dumps(data, sort_keys=True) == before

    def test_the_quote_survives_the_trip_through_json(self):
        # The form data is serialized into the page, and `json.dumps` refuses a
        # Decimal -- which would take the whole registration form down with it.
        data = form_data(field(7, GROUP_PLAN_FIELD, basePrice=50.0, payerBasePrice=50.0))
        quote_member_price(data, Decimal('45.00'))
        assert json.loads(json.dumps(data))['items']['7'][PAYER_FEE] == 45.0

    def test_every_picker_on_the_form(self):
        data = form_data(field(7, GROUP_PLAN_FIELD, basePrice=50.0, payerBasePrice=50.0),
                         field(8, GROUP_PLAN_FIELD, basePrice=50.0, payerBasePrice=50.0))
        assert quote_member_price(data, Decimal('45.00')) == 2
        assert [item[PAYER_FEE] for item in data['items'].values()] == [45.0, 45.0]

    def test_nothing_to_quote_is_not_a_failure(self):
        # This runs on the participant's own registration form, so an
        # unfamiliar shape has to be nothing worth doing rather than an error.
        assert quote_member_price(None, Decimal('45.00')) == 0
        assert quote_member_price({}, Decimal('45.00')) == 0
        assert quote_member_price({'items': None}, Decimal('45.00')) == 0
        assert quote_member_price({'items': {1: None, 2: 'label'}}, Decimal('45.00')) == 0
