"""What the plugin does when Indico tells it something happened."""

from indico.core.errors import UserValueError
from indico.modules.events.registration.models.items import PersonalDataType
from indico.modules.events.registration.models.registrations import RegistrationData
from indico.util.i18n import _

from indico_stsa.constants import GROUP_MODES_WITH_GROUP, GROUP_PLAN_FIELD, MEMBER_DISCOUNT_FIELD
from indico_stsa.names import clean_name
from indico_stsa.pricing import apply_member_discount
from indico_stsa.util import (disabled_names, find_field, find_profile_fields, is_group_login_required,
                              registration_is_member)


def handle_registration_created(registration, data=None, management=False):
    """Gate group registration, then price the registration.

    Order matters: the gate has to raise before anything is priced, and raising
    here rolls the whole registration back -- which is the right outcome, since
    the alternative is registering somebody into a group they were not allowed
    to form.
    """
    enforce_group_login(registration, data, management=management)
    apply_member_discount(registration, management=management)


def handle_registration_updated(registration, data=None, management=False):
    """Re-price a modified registration, and gate a group chosen while editing.

    The discount is only ever added here, never taken away: a participant may
    well be editing their registration from the link in their confirmation
    e-mail with nobody signed in, and losing a discount over a changed phone
    number would be indefensible.
    """
    enforce_group_login(registration, data, management=management)
    apply_member_discount(registration, management=management, upgrade_only=True)


def enforce_group_login(registration, data, *, management=False):
    """Refuse a group chosen by somebody who is not a signed-in member.

    The check reads the *submitted* answer rather than the stored one, which
    makes it independent of whether the group registration plugin's own signal
    handler has already run and created the membership.  Reading the stored
    answer instead would either block every later edit of a registration that
    is already in a group, or -- depending on which plugin's handler ran first
    -- let the very thing this is meant to stop straight through.

    Organizers are never gated: adding a participant to a group from the
    management area is a deliberate act by somebody who is signed in already.
    That carve-out is core's ``management`` flag, which describes the action in
    front of us, and deliberately *not* ``registration.created_by_manager``,
    which only records who first created the row.  A registration an organizer
    made is still editable from the link in its confirmation e-mail, by
    somebody who need not be signed in at all, so keying on the stored flag
    would wave exactly the choice this is meant to stop straight through --
    hence ``trust_manager=False`` below as well.
    """
    if management:
        return
    if not is_group_login_required(registration.registration_form):
        return
    if _submitted_group_mode(registration, data) not in GROUP_MODES_WITH_GROUP:
        return
    if registration_is_member(registration, trust_manager=False):
        return
    raise UserValueError(_('Group registration on this form is only open to STSA members. Please sign in with '
                           'your STSA membership and register again -- your answers are kept while you sign in.'))


def _submitted_group_mode(registration, data):
    """The ``mode`` of the group plan answer in this submission, if any.

    ``None`` when the group plugin's field is absent, or when this submission
    did not touch it -- modifying a registration sends only what changed.
    """
    if not data:
        return None
    field = find_field(registration.registration_form, GROUP_PLAN_FIELD)
    if field is None:
        return None
    value = data.get(field.html_field_name)
    return value.get('mode') if isinstance(value, dict) else None


def get_locked_field_reason(form_item, registration):
    """Keep our field out of core's read/write paths.

    Core skipping it is what lets the plugin own the `RegistrationData` row:
    locked fields are not written when a registration is created or modified,
    so nothing but `indico_stsa.pricing` ever touches the value.
    """
    if form_item.input_type == MEMBER_DISCOUNT_FIELD:
        return _('This is set automatically by the STSA plugin.')
    return None


def apply_member_profile(registration, profile):
    """Write the member's own details over what was submitted for them.

    This is the half of the lock that enforces it: the padlock on the form is a
    courtesy, and a hand-built request can carry anything.  So whatever
    arrived for a field the account has an answer for is replaced with that
    answer, on creation and on every later modification -- a member who edits
    their registration signed in gets their membership as it is now, and the
    notification's diff says so.

    Only a value core has already decided to keep is touched.  A field that has
    no row on this registration is one core left out on purpose -- hidden by a
    condition, purged, or never answered because it was added afterwards -- and
    writing one here would put an answer on the registration that the form did
    not ask for.

    :param profile: ``{input type: text}``, from `indico_stsa.util.member_profile`.
    :return: how many values were changed.
    """
    if not profile:
        return 0
    changed = 0
    data_by_field = registration.data_by_field
    for field in find_profile_fields(registration.registration_form):
        value = profile.get(field.input_type)
        row = data_by_field.get(field.id)
        if value is None or row is None or field.is_purged or row.data == value:
            continue
        # Point at the current version as core's own `process_form_data` does,
        # so the row does not go on pinning an old one.
        row.field_data = field.current_data
        row.data = value
        changed += 1
    return changed


def sync_default_names(registration):
    """Make First and Last name what the membership fields say, where they are switched off.

    The names arrive in the submission already -- `indico_stsa.default_names`
    puts them there before core reads it -- so this is not what *gets* them
    onto the registration.  It is what keeps them right afterwards: it runs
    after `apply_member_profile`, which may have replaced the English or the
    Chinese name with the account's, and it runs on every modification, where
    a request that left a name out would otherwise leave an old one in.

    The registration's own columns and the answer rows are both written, since
    core reads the first for the name it shows and the second for everything
    else, and they must not disagree.

    :return: how many of the two fields were changed.
    """
    regform = registration.registration_form
    sources = disabled_names(regform)
    if not sources:
        return 0
    data_by_field = registration.data_by_field
    changed = 0
    for name, source in sources.items():
        answer = data_by_field.get(source.id)
        text = clean_name(answer.data if answer else None)
        field = regform.get_personal_data_field(PersonalDataType[name])
        if text is None or field is None:
            continue
        touched = False
        if getattr(registration, name) != text:
            setattr(registration, name, text)
            touched = True
        row = data_by_field.get(field.id)
        if row is None:
            # Passing `registration=` already puts the row into
            # `registration.data`; appending it as well would list it twice.
            row = RegistrationData(registration=registration, field_data=field.current_data)
            row.data = text
            touched = True
        elif row.data != text:
            row.field_data = field.current_data
            row.data = text
            touched = True
        changed += touched
    return changed
