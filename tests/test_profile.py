"""A member's registration form is filled in from what their account says.

Everything decided from plain values lives in `indico_stsa.profile`: what a claim
reads as, which claims there are, and what the form data has to say for a field
to arrive filled in and locked.  *Whose* claims they are -- the identity the
session signed in with, and whether this request is the member's own -- needs a
request and a database, and is `indico_stsa.util.member_profile`.

The claims are the ones authentik sends, and what is pinned hardest is that a
claim which did not arrive leaves its field alone: a form that locks four fields
because an account has one answer would turn every member without a major into
somebody who cannot register.
"""

import json

from werkzeug.datastructures import MultiDict

from indico_stsa.constants import PROFILE_FIELDS
from indico_stsa.profile import autofill_profile_fields, claim_text, lock_reason, profile_values


CHINESE_NAME = 'ext__stsa_chinese_name'
ENGLISH_NAME = 'ext__stsa_english_name'
MAJOR = 'ext__stsa_major'
YEAR_OF_STUDY = 'ext__stsa_year_of_study'


def identity_data(**claims):
    """What ``Identity.data`` is: a multidict whose values arrive as lists."""
    data = MultiDict()
    for claim, value in claims.items():
        for single in value if isinstance(value, list) else [value]:
            data.add(claim, single)
    return data


class TestTheFields:
    def test_each_field_is_filled_in_from_its_own_claim(self):
        assert PROFILE_FIELDS == {
            CHINESE_NAME: 'chinese_name',
            ENGLISH_NAME: 'english_name',
            MAJOR: 'major',
            YEAR_OF_STUDY: 'year_of_study',
        }

    def test_the_names_are_ones_core_will_register(self):
        # Core's client registry refuses a plugin field without the prefix, and
        # the whole registration form with it.
        assert all(name.startswith('ext__') for name in PROFILE_FIELDS)


class TestClaimText:
    def test_a_claim_that_arrived(self):
        assert claim_text(identity_data(major='資訊工程'), 'major') == '資訊工程'

    def test_padding_is_not_part_of_the_answer(self):
        assert claim_text(identity_data(major='  Computer Science \n'), 'major') == 'Computer Science'

    def test_a_claim_that_did_not_arrive(self):
        assert claim_text(identity_data(english_name='Mei Lin'), 'major') is None

    def test_an_empty_claim_is_not_an_answer(self):
        # authentik sends the key with an empty string for an attribute nobody
        # has set, which must unlock the field rather than lock it to nothing.
        assert claim_text(identity_data(major=''), 'major') is None
        assert claim_text(identity_data(major='   '), 'major') is None

    def test_a_number_is_an_answer(self):
        assert claim_text(identity_data(year_of_study=2), 'year_of_study') == '2'

    def test_a_boolean_is_not(self):
        # `True` is an `int`; it must not become the literal word in somebody's
        # registration.
        assert claim_text(identity_data(year_of_study=True), 'year_of_study') is None

    def test_structured_values_are_not(self):
        assert claim_text(identity_data(major={'name': 'CS'}), 'major') is None
        assert claim_text({'major': {'name': 'CS'}}, 'major') is None

    def test_a_double_major_is_one_answer_with_both_in_it(self):
        data = identity_data(major=['資訊工程', '數學'])
        assert claim_text(data, 'major') == '資訊工程 / 數學'

    def test_the_same_value_twice_is_said_once(self):
        assert claim_text(identity_data(major=['數學', '數學']), 'major') == '數學'

    def test_a_blank_value_beside_a_real_one_is_dropped(self):
        assert claim_text(identity_data(major=['', '數學']), 'major') == '數學'

    def test_a_plain_dict_reads_like_a_multidict(self):
        assert claim_text({'major': '數學'}, 'major') == '數學'
        assert claim_text({'major': ['數學', '物理']}, 'major') == '數學 / 物理'

    def test_no_data_at_all(self):
        # An identity without claims is not an error: it is every local
        # password login there is.
        assert claim_text(None, 'major') is None
        assert claim_text({}, 'major') is None
        assert claim_text(MultiDict(), 'major') is None


class TestProfileValues:
    def test_every_field_the_account_has_an_answer_for(self):
        data = identity_data(chinese_name='林美玲', english_name='Mei-Ling Lin', major='資訊工程',
                             year_of_study='大三')
        assert profile_values(data) == {
            CHINESE_NAME: '林美玲',
            ENGLISH_NAME: 'Mei-Ling Lin',
            MAJOR: '資訊工程',
            YEAR_OF_STUDY: '大三',
        }

    def test_a_claim_that_did_not_arrive_leaves_its_field_out(self):
        values = profile_values(identity_data(chinese_name='林美玲', major=''))
        assert values == {CHINESE_NAME: '林美玲'}

    def test_other_claims_are_none_of_our_business(self):
        # `sub`, `email`, `groups` and the rest are in the identity too.
        values = profile_values(identity_data(sub='abc', email='mei@example.com', groups=['members'],
                                              major='數學'))
        assert values == {MAJOR: '數學'}

    def test_an_identity_with_no_claims(self):
        assert profile_values(MultiDict()) == {}
        assert profile_values(None) == {}


def field(id, input_type, **extra):
    """One camelized field entry, as `get_flat_section_submission_data` makes it."""
    return {'id': id, 'htmlName': f'field_{id}', 'inputType': input_type, 'lockedReason': None, **extra}


def form_data(*items):
    return {'sections': {1: {'id': 1, 'title': 'About you'}}, 'items': {item['id']: item for item in items}}


class TestAutofillProfileFields:
    def test_fills_in_and_locks_the_field(self):
        data = form_data(field(5, CHINESE_NAME))
        assert autofill_profile_fields(data, {CHINESE_NAME: '林美玲'}) == 1
        assert data['items'][5]['autofillValue'] == '林美玲'
        assert data['items'][5]['lockedReason'] == lock_reason()

    def test_the_reason_is_worth_reading(self):
        # Shown to the participant, under the padlock on a field they have just
        # found they cannot type in.
        assert 'STSA' in lock_reason()
        assert lock_reason().endswith('.')

    def test_each_field_gets_its_own_answer(self):
        data = form_data(field(5, CHINESE_NAME), field(6, ENGLISH_NAME), field(7, MAJOR))
        values = {CHINESE_NAME: '林美玲', ENGLISH_NAME: 'Mei-Ling Lin', MAJOR: '數學'}
        assert autofill_profile_fields(data, values) == 3
        assert [data['items'][i]['autofillValue'] for i in (5, 6, 7)] == ['林美玲', 'Mei-Ling Lin', '數學']

    def test_a_field_the_account_has_no_answer_for_stays_open(self):
        # The manual-entry fallback: neither locked nor given a value, so it is
        # exactly the text box core drew.
        data = form_data(field(5, CHINESE_NAME), field(7, MAJOR))
        assert autofill_profile_fields(data, {CHINESE_NAME: '林美玲'}) == 1
        assert data['items'][7] == field(7, MAJOR)

    def test_a_form_without_our_fields_is_left_alone(self):
        text = field(1, 'text')
        data = form_data(text, field(2, 'email', fieldIsPersonalData=True))
        assert autofill_profile_fields(data, {CHINESE_NAME: '林美玲'}) == 0
        assert data['items'][1] == text

    def test_a_reason_somebody_else_already_wrote_is_not_overwritten(self):
        # Something that locked the field for its own reasons is saying more
        # than we are, and a value under somebody else's padlock is a claim we
        # cannot back.
        data = form_data(field(5, CHINESE_NAME, lockedReason='Purged'))
        assert autofill_profile_fields(data, {CHINESE_NAME: '林美玲'}) == 0
        assert data['items'][5]['lockedReason'] == 'Purged'
        assert 'autofillValue' not in data['items'][5]

    def test_nothing_to_fill_in(self):
        data = form_data(field(5, CHINESE_NAME))
        assert autofill_profile_fields(data, {}) == 0
        assert data['items'][5] == field(5, CHINESE_NAME)

    def test_the_result_survives_the_trip_through_json(self):
        # The form data is serialized into the page; a reason or a value that
        # cannot be would take the whole registration form with it.
        data = form_data(field(5, CHINESE_NAME))
        autofill_profile_fields(data, {CHINESE_NAME: '林美玲'})
        item = json.loads(json.dumps(data))['items']['5']
        assert item['autofillValue'] == '林美玲'
        assert item['lockedReason'] == lock_reason()

    def test_an_unfamiliar_shape_is_nothing_worth_doing(self):
        # This runs on the participant's own registration form, so it has to be
        # a no-op rather than an error.
        assert autofill_profile_fields(None, {CHINESE_NAME: 'x'}) == 0
        assert autofill_profile_fields({}, {CHINESE_NAME: 'x'}) == 0
        assert autofill_profile_fields({'items': None}, {CHINESE_NAME: 'x'}) == 0
        assert autofill_profile_fields({'items': {1: None, 2: 'label'}}, {CHINESE_NAME: 'x'}) == 0
