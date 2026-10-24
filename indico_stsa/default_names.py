"""Switching off First name and Last name -- the part that has to talk to core.

`indico_stsa.names` says why they cannot simply be disabled and what is done
instead; this is the half that makes the editor offer the switch, makes it work,
and keeps the registration's name what the membership fields say.

Core gives no hook for any of it, so two things in it are wrapped.  Both
wrappers answer "as if this plugin were not installed" for everything that is
not one of the two fields on a form that has the field that stands in for them,
and both are installed once, at start-up, and left alone.

* `RegistrationFormPersonalDataField.view_data` is what the editor reads to
  decide whether a field gets a *Disable* button (``fieldIsRequired``) and where
  it is drawn (``isEnabled``).  Reporting a switched-off field as disabled is
  all the editor needs to show it where Address and Phone are, greyed out, with
  an *Enable* button.
* `RHRegistrationFormToggleFieldState._process` is the endpoint that button
  calls, and it refuses a required personal data field outright.  This one
  records the switch in the plugin's settings instead of on the field.

The field itself is never touched.  It stays enabled and required in the
database, which is what core -- and the check constraint under it -- insists on.
"""

from flask import has_request_context, jsonify, request, session
from marshmallow import ValidationError

from indico.core import signals
from indico.core.db import db
from indico.core.logger import Logger
from indico.modules.events.registration.controllers.management.fields import RHRegistrationFormToggleFieldState
from indico.modules.events.registration.models.form_fields import RegistrationFormPersonalDataField
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.items import RegistrationFormItemType
from indico.modules.events.registration.util import (RegistrationSchemaBase, get_flat_section_positions_setup_data,
                                                    update_regform_item_positions)
from indico.modules.logs import EventLogRealm, LogKind
from indico.util.i18n import _

from indico_stsa.constants import NAME_SOURCES
from indico_stsa.models.settings import STSASettings
from indico_stsa.names import inject_names
from indico_stsa.util import NAME_COLUMNS, default_name_state, disabled_names, get_settings, name_source


logger = Logger.get('plugin.stsa')


def name_sources(regform):
    """``{default field's name: the HTML name of the field supplying it}`` for the ones that are off."""
    return {name: source.html_field_name for name, source in disabled_names(regform).items()}


def _name_of(item):
    """The name of the default field this item is, if it is First or Last name."""
    if item.type == RegistrationFormItemType.field_pd and item.personal_data_type.name in NAME_COLUMNS:
        return item.personal_data_type.name
    return None


# -- wrapping core ------------------------------------------------------------

def install():
    """Wrap the two things in core that stand between an organizer and the switch.

    Safe to call more than once: a wrapper marks itself, because the plugin is
    initialised again for every app a test run creates and a wrapper wrapped in
    itself would do its work twice.
    """
    view_data = RegistrationFormPersonalDataField.view_data
    if not hasattr(view_data.fget, 'stsa_wraps'):
        RegistrationFormPersonalDataField.view_data = property(_showing_the_switch(view_data.fget))
    process = RHRegistrationFormToggleFieldState._process
    if not hasattr(process, 'stsa_wraps'):
        RHRegistrationFormToggleFieldState._process = _taking_the_switch(process)


def _showing_the_switch(fget):
    def view_data(self):
        data = fget(self)
        try:
            name = _name_of(self)
            state = default_name_state(self.registration_form, name) if name else None
        except Exception:
            logger.exception('Could not tell whether %r can be switched off', self)
            return data
        if state is not None:
            # No longer "cannot be disabled", and disabled once it is.
            data['fieldIsRequired'] = False
            data['isEnabled'] = not state
        return data

    view_data.stsa_wraps = fget
    return view_data


def _taking_the_switch(process):
    def toggle(self):
        try:
            name = _name_of(self.field)
            state = default_name_state(self.regform, name) if name else None
        except Exception:
            logger.exception('Could not tell whether %r can be switched off', self.field)
            return process(self)
        if state is not None:
            return _switch(self, name)
        if name and request.args.get('enable') == 'true':
            # An editor that was opened before the field that stood in for this
            # one was removed still offers *Enable*, for a field that was
            # switched back on when that happened.  Core would call that a
            # duplicate title; it is a request that is already true.
            return jsonify(view_data=self.field.view_data,
                           positions=get_flat_section_positions_setup_data(self.regform))
        return process(self)

    toggle.stsa_wraps = process
    return toggle


def _switch(rh, name):
    """What core's toggle does, for a field it would refuse, and the plugin's settings for the switch."""
    field, regform = rh.field, rh.regform
    enable = request.args.get('enable') == 'true'
    settings = get_settings(regform)
    if settings is None:
        settings = STSASettings(registration_form=regform)
        db.session.add(settings)
    setattr(settings, NAME_COLUMNS[name], not enable)
    if not enable:
        _move_to_the_end(field)
    db.session.flush()
    signals.event.registration_form_field_toggled.send(field)
    logger.info('Field %s %s by %s', field, 'enabled' if enable else 'disabled', session.user)
    if enable:
        field.log(EventLogRealm.management, LogKind.positive, 'Registration',
                  f'Field "{field.title}" in "{regform.title}" enabled', session.user)
    else:
        field.log(EventLogRealm.management, LogKind.negative, 'Registration',
                  f'Field "{field.title}" in "{regform.title}" disabled', session.user)
    return jsonify(view_data=field.view_data, positions=get_flat_section_positions_setup_data(regform))


def _move_to_the_end(field):
    """Put a switched-off field after the ones that are on, where core puts a disabled one.

    The editor draws it with the disabled fields and counts positions without
    it, so a gap where it used to be would put every drag one place out.  Core's
    own renumbering keeps the order it finds, and what it finds is the list it
    loaded before the field moved -- hence the refresh.
    """
    section = field.parent
    field.position = max(child.position for child in section.children) + 1
    db.session.flush()
    db.session.expire(section, ['children'])
    update_regform_item_positions(field.registration_form)


# -- keeping the invariants --------------------------------------------------

def release_names(field, *, deleting=False):
    """Switch a name field back on when the field that stood in for it is no more.

    Without this the switch would stay set, waiting for the next English name
    anybody added to the form -- which would then switch First name off again
    without anybody having asked.

    :param deleting: whether `field` is about to be deleted; core announces that
                     *before* it happens.
    """
    if field.input_type not in NAME_SOURCES.values():
        return 0
    regform = field.registration_form
    settings = get_settings(regform)
    if settings is None:
        return 0
    released = 0
    for name, column in NAME_COLUMNS.items():
        if getattr(settings, column) and name_source(regform, name, ignoring=field.id if deleting else None) is None:
            setattr(settings, column, False)
            released += 1
    return released


def unconditional(field):
    """Take a *show if* off First or Last name, wherever it came from.

    Core hides the setting for them because a registration needs a name; the
    switch is what takes that hiding away, and without it an organizer could
    make a name field depend on another and leave a registration with none.
    """
    name = _name_of(field)
    if name is None or field.show_if_id is None or default_name_state(field.registration_form, name) is None:
        return False
    field.show_if_id = None
    field.show_if_values = None
    return True


# -- the submission ----------------------------------------------------------

def supply_names(sender, data):
    """Fill in the names core requires from the fields that stand in for them.

    Receiver for the schema's *pre-load* signal, which sees every schema in the
    instance and answers only for the registration form's.  The form being
    submitted is found from the URL, because the schema class is built per
    request and does not know which form it was built for.
    """
    if not (isinstance(sender, type) and issubclass(sender, RegistrationSchemaBase) and isinstance(data, dict)):
        return
    if not has_request_context() or not (regform_id := (request.view_args or {}).get('reg_form_id')):
        return
    regform = RegistrationForm.get(regform_id)
    if regform is None or not (sources := name_sources(regform)):
        return
    if blank := inject_names(data, sources):
        # The error goes on the field that is on the page.
        raise ValidationError({source: [str(_('This field is required.'))] for source in blank})
