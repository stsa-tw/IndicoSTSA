"""What the plugin does when Indico tells it something happened."""

from indico.core.errors import UserValueError
from indico.util.i18n import _

from indico_stsa.constants import GROUP_MODES_WITH_GROUP, GROUP_PLAN_FIELD, MEMBER_DISCOUNT_FIELD
from indico_stsa.pricing import apply_member_discount
from indico_stsa.util import find_field, is_group_login_required, registration_is_member


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
    """
    if management or registration.created_by_manager:
        return
    if not is_group_login_required(registration.registration_form):
        return
    if _submitted_group_mode(registration, data) not in GROUP_MODES_WITH_GROUP:
        return
    if registration_is_member(registration):
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
