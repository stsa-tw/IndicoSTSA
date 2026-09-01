"""Lookups, provisioning, and the bridge to the group registration plugin."""

from flask import has_request_context, session

from indico.core.db import db
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.items import RegistrationFormSection

from indico_stsa.constants import (GROUP_MODES_WITH_GROUP, GROUP_PLAN_FIELD, GROUP_PLUGIN, MEMBER_DISCOUNT_FIELD,
                                  MEMBER_DISCOUNT_FIELD_TITLE, MEMBER_DISCOUNT_SECTION_TITLE)


# -- settings ----------------------------------------------------------------

def get_settings(regform):
    """The plugin's configuration for a registration form, or ``None``."""
    return regform.stsa_settings


def is_member_discount_enabled(regform):
    settings = get_settings(regform)
    return settings is not None and settings.member_discount_enabled


def is_group_login_required(regform):
    """Whether group registration on this form is restricted to members.

    Always ``False`` without the group registration plugin: the setting is
    about that plugin's field, so on its own it would gate nothing.
    """
    if not is_group_plugin_installed():
        return False
    settings = get_settings(regform)
    return settings is not None and settings.group_login_required


# -- the group registration plugin -------------------------------------------
#
# It is an optional companion, so nothing here imports it.  Everything we need
# from it -- whether it is loaded, and what the participant answered in its
# field -- is reachable without doing so.

def is_group_plugin_installed():
    from indico.core.plugins import plugin_engine
    return plugin_engine.get_plugin(GROUP_PLUGIN) is not None


def get_group_choice(registration):
    """What the participant answered in the group plugin's field.

    An empty dict when the field is absent, unanswered, or the plugin is not
    installed at all.
    """
    field = find_field(registration.registration_form, GROUP_PLAN_FIELD)
    if field is None:
        return {}
    data = registration.data_by_field.get(field.id)
    return (data.data if data else None) or {}


def wants_group(registration):
    """Whether this registration is trying to create or join a group."""
    return get_group_choice(registration).get('mode') in GROUP_MODES_WITH_GROUP


def get_group_membership(registration):
    """The registration's group membership, or ``None`` without the plugin."""
    return getattr(registration, 'group_membership', None)


def reprice_group_of(registration):
    """Let the group plugin recompute its own discount for a whole group.

    Both plugins write a discount line, and the group plugin's is calculated
    from everything billable *except its own line* -- which includes ours.  So
    whenever we change our line, its line is one registration out of date.

    Our own amount never depends on theirs (see `indico_stsa.pricing`), so this
    only ever has to run one way round, and it cannot loop.
    """
    membership = get_group_membership(registration)
    if membership is None or membership.group is None:
        return False
    try:
        from indico_group_registration.pricing import apply_group_pricing
    except ImportError:
        return False
    apply_group_pricing(membership.group)
    return True


# -- membership --------------------------------------------------------------

def registration_is_member(registration, *, management=False):
    """Whether this registration earns the member discount.

    An STSA membership is an account on this site, so the test is "is this
    registration the account holder's own?".  Both halves matter:

    * ``registration.user`` is set from the *e-mail address* -- core looks it
      up with `get_user_by_email` -- so on its own it would hand the discount
      to anybody who types a member's address into an anonymous registration.
    * ``session.user`` on its own would hand it to a signed-in organizer
      registering somebody else.

    Registrations created from the management area are trusted: an organizer
    adding a participant, or applying the discount to registrations made before
    it was switched on, has made that decision deliberately.
    """
    if registration.user is None:
        return False
    if management or registration.created_by_manager:
        return True
    return has_request_context() and session.user is not None and session.user == registration.user


# -- field provisioning ------------------------------------------------------
#
# The discount has to exist on the form as a real item, because a
# `RegistrationData` row must point at a `RegistrationFormFieldData`.  We
# create it on demand and put it back if an organizer removes it.

def find_field(regform, input_type):
    """Find a field on a form by its input type, including disabled ones."""
    return next((item for item in regform.form_items
                 if item.input_type == input_type and not item.is_deleted), None)


def _create_section(regform, title, *, manager_only):
    section = RegistrationFormSection(registration_form=regform, title=title, is_manager_only=manager_only)
    db.session.add(section)
    db.session.flush()
    return section


def _create_field(regform, section, input_type, title):
    # `parent=` rather than `section.children.append(field)`.  Appending forces
    # the section's `children` collection to load, and that query autoflushes
    # the half-built field -- which at that point still has no `parent_id` and
    # so trips the `ck_form_items_top_level_sections` check constraint.  Setting
    # the many-to-one side never loads the collection, which is also how core's
    # own `RHRegistrationFormAddField` does it.
    field = RegistrationFormField(parent=section, registration_form=regform, input_type=input_type,
                                  title=title, is_required=False)
    field.data, field.versioned_data = field.field_impl.process_field_data({})
    db.session.add(field)
    db.session.flush()
    return field


def provision_discount_field(regform):
    """Make sure the invoice line item exists.

    It lives in a manager-only section, which keeps it out of the participant's
    form and out of their answer summary while still letting it appear on the
    invoice -- the invoice table iterates billable data flat, without looking
    at sections.
    """
    field = find_field(regform, MEMBER_DISCOUNT_FIELD)
    if field is not None:
        if not field.is_enabled:
            field.is_enabled = True
        return field
    section = _create_section(regform, MEMBER_DISCOUNT_SECTION_TITLE, manager_only=True)
    return _create_field(regform, section, MEMBER_DISCOUNT_FIELD, MEMBER_DISCOUNT_FIELD_TITLE)


def get_discount_data(registration):
    """The `RegistrationData` row holding this registration's discount."""
    field = find_field(registration.registration_form, MEMBER_DISCOUNT_FIELD)
    if field is None:
        return None
    return registration.data_by_field.get(field.id)


def set_discount_data(registration, value):
    """Write the discount value, creating the data row if it is missing.

    Core never creates this row for us: the field is locked, and locked fields
    are skipped in both `create_registration` and `modify_registration`.
    """
    from indico.modules.events.registration.models.registrations import RegistrationData

    field = provision_discount_field(registration.registration_form)
    data = registration.data_by_field.get(field.id)
    if data is None:
        # Passing `registration=` already puts the row into `registration.data`
        # through the backref.  Appending it again would leave the same object
        # in the collection twice, and every in-session price calculation --
        # the confirmation e-mail's included -- would then count it twice.
        data = RegistrationData(registration=registration, field_data=field.current_data)
    else:
        # Point at the current version so the row does not pin an old one.
        data.field_data = field.current_data
    data.data = value
    return data
