"""First and Last name come from the English and Chinese name fields when they are off.

Everything decided from plain values lives in `indico_stsa.names`: what a name
is, what the form shown to a participant looks like without the two fields, and
how the submitted names reach the fields core insists on.  *Whether* the fields
are off -- the switch, and the form having what stands in for them -- needs a
database, and is `indico_stsa.util.disabled_names`.

What is pinned hardest is that the membership fields win, and that an *absent*
field is not a *blank* one: a modification that never touched the English name
must not be refused for lacking it, and a registration whose English name was
emptied must not be given a first name of nothing.
"""

import pytest

from indico_stsa.constants import CHINESE_NAME_FIELD, ENGLISH_NAME_FIELD, NAME_SOURCES
from indico_stsa.names import clean_name, hide_default_names, inject_names


#: Both fields off, with the fields that stand in for them at ids 12 and 13.
SOURCES = {'first_name': 'field_13', 'last_name': 'field_12'}


def form_data():
    """The flat submission data of a form with both name fields and the two that replace them."""
    return {'sections': {1: {}}, 'items': {
        1: {'htmlName': 'first_name', 'fieldIsPersonalData': True, 'isRequired': True},
        2: {'htmlName': 'last_name', 'fieldIsPersonalData': True, 'isRequired': True},
        3: {'htmlName': 'email', 'fieldIsPersonalData': True, 'isRequired': True},
        12: {'htmlName': 'field_12', 'fieldIsPersonalData': False, 'isRequired': False},
        13: {'htmlName': 'field_13', 'fieldIsPersonalData': False, 'isRequired': False},
        14: {'htmlName': 'field_14', 'fieldIsPersonalData': False, 'isRequired': False},
    }}


class TestTheMapping:
    def test_the_english_name_is_the_first_name(self):
        assert NAME_SOURCES['first_name'] == ENGLISH_NAME_FIELD

    def test_the_chinese_name_is_the_last_name(self):
        assert NAME_SOURCES['last_name'] == CHINESE_NAME_FIELD

    def test_only_the_two_names_can_be_switched_off(self):
        # The e-mail address is what a registration is found by; it stays.
        assert set(NAME_SOURCES) == {'first_name', 'last_name'}


class TestCleanName:
    @pytest.mark.parametrize(('value', 'expected'), (
        ('Mei-Ling Lin', 'Mei-Ling Lin'),
        ('  林美玲  ', '林美玲'),
        ('', None),
        ('   ', None),
        (None, None),
        (12, None),
        (['Mei'], None),
        ({'text': 'Mei'}, None),
    ))
    def test_a_name_is_a_string_with_something_in_it(self, value, expected):
        assert clean_name(value) == expected


class TestHideDefaultNames:
    def test_takes_the_two_fields_out(self):
        data = form_data()
        assert hide_default_names(data, SOURCES) == 2
        assert sorted(data['items']) == [3, 12, 13, 14]

    def test_leaves_every_other_field_alone(self):
        data = form_data()
        hide_default_names(data, SOURCES)
        assert data['items'][3] == {'htmlName': 'email', 'fieldIsPersonalData': True, 'isRequired': True}
        assert data['items'][14]['isRequired'] is False

    def test_the_fields_that_stand_in_are_shown_as_required(self):
        data = form_data()
        hide_default_names(data, SOURCES)
        assert data['items'][12]['isRequired'] is True
        assert data['items'][13]['isRequired'] is True

    def test_one_off_and_one_on(self):
        data = form_data()
        assert hide_default_names(data, {'first_name': 'field_13'}) == 1
        assert 1 not in data['items']
        assert 2 in data['items']
        assert data['items'][13]['isRequired'] is True
        # The Chinese name is not standing in for anything, so it stays optional.
        assert data['items'][12]['isRequired'] is False

    def test_a_field_of_the_same_name_that_is_not_personal_data_stays(self):
        # A text field somebody called `first_name` is a text field.
        data = {'items': {7: {'htmlName': 'first_name', 'fieldIsPersonalData': False}}}
        assert hide_default_names(data, SOURCES) == 0
        assert 7 in data['items']

    def test_nothing_off_changes_nothing(self):
        data = form_data()
        assert hide_default_names(data, {}) == 0
        assert data == form_data()

    @pytest.mark.parametrize('data', (None, {}, {'items': None}, {'items': {}}))
    def test_survives_a_form_with_nothing_in_it(self, data):
        assert hide_default_names(data, SOURCES) == 0

    def test_survives_an_item_that_is_not_a_dict(self):
        data = {'items': {1: None, 2: 'label'}}
        assert hide_default_names(data, SOURCES) == 0


class TestInjectNames:
    def test_the_membership_fields_become_the_name(self):
        data = {'field_12': '林美玲', 'field_13': 'Mei-Ling Lin'}
        assert inject_names(data, SOURCES) == []
        assert data['first_name'] == 'Mei-Ling Lin'
        assert data['last_name'] == '林美玲'

    def test_they_win_over_what_the_form_sent(self):
        # The form is prefilled from the Indico account, and a hand-built request
        # can say anything; neither gets to disagree with the membership.
        data = {'first_name': 'Mei', 'last_name': 'Lin', 'field_12': '林美玲', 'field_13': 'Mei-Ling Lin'}
        inject_names(data, SOURCES)
        assert (data['first_name'], data['last_name']) == ('Mei-Ling Lin', '林美玲')

    def test_a_name_is_trimmed(self):
        data = {'field_13': '  Mei-Ling Lin '}
        inject_names(data, {'first_name': 'field_13'})
        assert data['first_name'] == 'Mei-Ling Lin'

    def test_a_blank_name_is_reported_not_injected(self):
        data = {'field_12': '林美玲', 'field_13': '   '}
        assert inject_names(data, SOURCES) == ['field_13']
        assert 'first_name' not in data
        assert data['last_name'] == '林美玲'

    def test_a_blank_name_does_not_clear_the_one_the_form_sent(self):
        # The refusal is what stops the registration; clearing would only make
        # it a worse one if something let it through.
        data = {'first_name': 'Mei', 'field_13': ''}
        assert inject_names(data, {'first_name': 'field_13'}) == ['field_13']
        assert data['first_name'] == 'Mei'

    def test_an_absent_field_is_not_a_blank_one(self):
        # A modification sends only what changed.  Changing a phone number
        # must not be refused for the English name it never mentioned.
        data = {'field_14': 'Computer Science'}
        assert inject_names(data, SOURCES) == []
        assert data == {'field_14': 'Computer Science'}

    def test_only_what_changed_is_replaced(self):
        data = {'field_13': 'Mei-Ling Lin'}
        assert inject_names(data, SOURCES) == []
        assert data['first_name'] == 'Mei-Ling Lin'
        assert 'last_name' not in data

    def test_a_name_that_is_not_text_is_blank(self):
        data = {'field_13': 12}
        assert inject_names(data, {'first_name': 'field_13'}) == ['field_13']

    def test_nothing_off_changes_nothing(self):
        data = {'field_12': '林美玲', 'first_name': 'Mei'}
        assert inject_names(data, {}) == []
        assert data == {'field_12': '林美玲', 'first_name': 'Mei'}

    def test_it_is_safe_to_run_twice(self):
        # Core parses a submission twice, and the pre-load signal fires both times.
        data = {'field_12': '林美玲', 'field_13': 'Mei-Ling Lin'}
        inject_names(data, SOURCES)
        once = dict(data)
        assert inject_names(data, SOURCES) == []
        assert data == once
