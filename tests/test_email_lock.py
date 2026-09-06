"""A signed-in member registers under the address on their membership.

Two decisions live in `indico_stsa.email_lock`, and both are made from plain
values: which field on a form is *the* e-mail field, and whether an address
that has arrived belongs to the membership it claims.  Who is signed in, and
whether the lock applies to them at all, is the other half's job -- it needs a
request and a database, and lives in `indico_stsa.util` and the plugin.

The case pinned hardest here is the second address on an account.  Core links a
registration to its user with `get_user_by_email`, which matches every address
on the account, so a member who registered under one of theirs is already
linked to the right membership; a check that only accepted the first would turn
their registration into one they could no longer edit.
"""

import json

from indico_stsa.email_lock import (EMAIL_FIELD, FOREIGN_EMAIL_CONFLICT, foreign_email_error, is_membership_address,
                                    lock_email_field, lock_reason)


def field(id, html_name, **extra):
    """One camelized field entry, as `get_flat_section_submission_data` makes it."""
    return {'id': id, 'htmlName': html_name, 'inputType': 'text', 'lockedReason': None, **extra}


def email_field(id=2, **extra):
    """Core's personal-data e-mail field, which every form has."""
    return field(id, EMAIL_FIELD, inputType='email', fieldIsPersonalData=True, **extra)


def form_data(*items):
    return {'sections': {1: {'id': 1, 'title': 'Personal Data'}},
            'items': {item['id']: item for item in items}}


class TestLockEmailField:
    def test_locks_the_email_field(self):
        data = form_data(email_field())
        assert lock_email_field(data) == 1
        assert data['items'][2]['lockedReason'] == lock_reason()

    def test_the_reason_is_worth_reading(self):
        # It is shown to the participant, under the padlock on a field they
        # have just found they cannot type in.
        assert 'STSA' in lock_reason()
        assert lock_reason().endswith('.')

    def test_leaves_the_organizers_own_email_questions_alone(self):
        # A form may ask for any number of addresses -- a parent's, an
        # emergency contact's.  Only the personal-data field is the
        # membership's, and it is the one core names after its type.
        parents = field(8, 'field_8', inputType='email')
        also_email = field(9, 'field_9', inputType='email', fieldIsPersonalData=False)
        data = form_data(email_field(), parents, also_email)
        assert lock_email_field(data) == 1
        assert data['items'][8]['lockedReason'] is None
        assert data['items'][9]['lockedReason'] is None

    def test_leaves_the_rest_of_the_form_alone(self):
        first_name = field(1, 'first_name', fieldIsPersonalData=True)
        data = form_data(first_name, email_field())
        lock_email_field(data)
        assert data['items'][1] == first_name
        assert data['sections'] == {1: {'id': 1, 'title': 'Personal Data'}}

    def test_a_reason_core_already_wrote_is_not_overwritten(self):
        # Nothing in core locks the e-mail field today, but if something did,
        # its reason is the more specific one and ours would only bury it.
        data = form_data(email_field(lockedReason='Purged'))
        assert lock_email_field(data) == 0
        assert data['items'][2]['lockedReason'] == 'Purged'

    def test_the_lock_survives_the_trip_through_json(self):
        # The form data is serialized into the page; a reason that cannot be
        # serialized would take the whole registration form down with it.
        data = form_data(email_field())
        lock_email_field(data)
        assert json.loads(json.dumps(data))['items']['2']['lockedReason'] == lock_reason()

    def test_nothing_to_lock_is_not_a_failure(self):
        # This runs on the participant's own registration form, so an
        # unfamiliar shape has to be nothing worth doing rather than an error.
        assert lock_email_field(None) == 0
        assert lock_email_field({}) == 0
        assert lock_email_field({'items': None}) == 0
        assert lock_email_field({'items': {1: None, 2: 'label'}}) == 0
        assert lock_email_field(form_data(field(1, 'first_name'))) == 0


class TestIsMembershipAddress:
    def test_the_address_on_the_membership(self):
        assert is_membership_address('mei@example.com', {'mei@example.com'})

    def test_a_second_address_on_the_same_account(self):
        # Core links the registration to the same user either way, so this is
        # already a member registering as themselves.
        assert is_membership_address('mei@ntu.edu.sg', {'mei@example.com', 'mei@ntu.edu.sg'})

    def test_somebody_elses_address(self):
        assert not is_membership_address('someone@example.com', {'mei@example.com'})

    def test_case_and_padding_are_not_a_different_address(self):
        # Indico stores addresses folded and `check_registration_email` has
        # already folded the one it is asking about, but the account's are
        # whatever the database holds.
        assert is_membership_address('  Mei@Example.COM ', {'mei@example.com'})
        assert is_membership_address('mei@example.com', {'Mei@Example.com '})

    def test_a_near_miss_is_still_a_miss(self):
        assert not is_membership_address('mei@example.com.tw', {'mei@example.com'})
        assert not is_membership_address('mei@example.com', {'mei@example.com.tw'})

    def test_no_address_at_all(self):
        assert not is_membership_address('', {'mei@example.com'})
        assert not is_membership_address(None, {'mei@example.com'})

    def test_an_account_with_nothing_to_match(self):
        # Cannot happen -- an Indico account always has an address -- but the
        # answer has to be "not the member's", never "anything goes".
        assert not is_membership_address('mei@example.com', set())
        assert not is_membership_address('mei@example.com', None)
        assert not is_membership_address('mei@example.com', {None, ''})


class TestForeignEmailError:
    def test_it_is_an_error_the_form_knows_how_to_render(self):
        # The conflict is one of core's own names on purpose: the registration
        # form renders it as "This email address is not associated with your
        # Indico account", and an unknown one as a sentence about the account
        # the registration will not be linked to, which is alarming and wrong.
        assert foreign_email_error() == {'status': 'error', 'conflict': FOREIGN_EMAIL_CONFLICT}
        assert FOREIGN_EMAIL_CONFLICT == 'email-other-user'
