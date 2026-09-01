"""Organizer-facing endpoints."""

from decimal import Decimal

from flask import flash, redirect, session

from indico.core.db import db
from indico.core.plugins import WPJinjaMixinPlugin, url_for_plugin
from indico.modules.events.registration.controllers.management import RHManageRegFormBase, RHManageRegFormsBase
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.views import WPManageRegistration
from indico.modules.logs import EventLogRealm, LogKind
from indico.util.i18n import _, ngettext
from indico.web.forms.base import FormDefaults
from indico.web.util import jsonify_data

from indico_stsa.constants import APPLIES_TO_BASE, PERCENT
from indico_stsa.discount import format_rate
from indico_stsa.forms import RegFormSettingsForm
from indico_stsa.models.settings import STSASettings
from indico_stsa.pricing import apply_member_discount, is_member_discounted
from indico_stsa.util import (get_discount_data, get_settings, is_group_plugin_installed, provision_discount_field,
                              tables_exist)


class WPSTSA(WPJinjaMixinPlugin, WPManageRegistration):
    """Renders our management pages inside the registration management area.

    ``WPJinjaMixinPlugin`` has to come first.  ``WPManageRegistration`` sets
    ``template_prefix = 'events/registration/'`` for core templates, and that
    prefix is prepended verbatim -- turning ``stsa:overview.html`` into
    ``events/registration/stsa:overview.html``, which exists nowhere.  Listing
    the mixin first clears the prefix and swaps in the plugin template loader,
    so ``stsa:<name>`` resolves to this plugin's ``templates/`` directory.
    """

    sidemenu_option = 'stsa'


class RHSTSAOverview(RHManageRegFormsBase):
    """Every registration form in the event, and what is switched on."""

    def _process(self):
        regforms = (RegistrationForm.query
                    .with_parent(self.event)
                    .filter(~RegistrationForm.is_deleted)
                    .order_by(RegistrationForm.title)
                    .all())
        rows = []
        for regform in regforms:
            settings = get_settings(regform)
            rows.append({
                'regform': regform,
                'settings': settings,
                # Formatted here rather than in the template so that an
                # organizer reads the same "20%" the participant is shown.
                'rate': (format_rate(settings.discount_type, settings.discount_value, regform.currency)
                         if settings else ''),
            })
        return WPSTSA.render_template('stsa:overview.html', self.event, rows=rows,
                                      group_plugin=is_group_plugin_installed(),
                                      tables_missing=not tables_exist())


class RHSTSARegFormBase(RHManageRegFormBase):
    """Base for pages scoped to one registration form."""

    def _process_args(self):
        RHManageRegFormBase._process_args(self)
        self.settings = get_settings(self.regform)


class RHSTSASettings(RHSTSARegFormBase):
    """Configure the member discount and the group login gate."""

    def _process(self):
        group_plugin = is_group_plugin_installed()
        if not tables_exist():
            # There is nothing to read and nowhere to write: saving would fail
            # on the INSERT, and a form that quietly does not save is worse
            # than no form.  The page says what is missing instead.
            return WPSTSA.render_template('stsa:settings.html', self.event, regform=self.regform, form=None,
                                          settings=None, group_plugin=group_plugin, discounted=0,
                                          tables_missing=True)

        settings = self.settings
        defaults = FormDefaults(
            member_discount_enabled=settings.member_discount_enabled if settings else False,
            discount_type=settings.discount_type if settings else PERCENT,
            discount_value=settings.discount_value if settings else Decimal(0),
            applies_to=settings.applies_to if settings else APPLIES_TO_BASE,
            notice_text=settings.notice_text if settings else '',
            group_login_required=settings.group_login_required if settings else False,
        )
        form = RegFormSettingsForm(obj=defaults, group_plugin_installed=group_plugin)

        if form.validate_on_submit():
            if settings is None:
                settings = STSASettings(registration_form=self.regform)
                db.session.add(settings)

            settings.member_discount_enabled = form.member_discount_enabled.data
            settings.discount_type = form.discount_type.data
            settings.discount_value = form.discount_value.data or Decimal(0)
            settings.applies_to = form.applies_to.data
            settings.notice_text = form.notice_text.data or ''
            if group_plugin:
                settings.group_login_required = form.group_login_required.data

            if settings.member_discount_enabled:
                provision_discount_field(self.regform)

            db.session.flush()
            self.event.log(EventLogRealm.management, LogKind.change, 'Registration',
                           f'STSA settings for "{self.regform.title}"', session.user)
            db.session.commit()
            flash(_('STSA settings saved.'), 'success')
            return redirect(url_for_plugin('stsa.manage_settings', self.regform))

        return WPSTSA.render_template('stsa:settings.html', self.event, regform=self.regform, form=form,
                                      settings=settings, group_plugin=group_plugin,
                                      discounted=_count_discounted(self.regform), tables_missing=False)


class RHRecalculateDiscounts(RHSTSARegFormBase):
    """Apply the current settings to every registration on the form.

    This is the retroactive path, and it is deliberately a button rather than
    something that happens on save: every registration linked to a membership
    account gets the discount, including ones made before the discount existed
    and ones made without anybody signing in.  That is an organizer's decision
    to make, not a side effect of editing a rate.
    """

    def _process(self):
        if not tables_exist():
            # Without the settings there is nothing to reprice *to*, and going
            # ahead would strip the discount off every registration that has
            # one.
            flash(_('STSA has no tables in this database, so there are no settings to apply. Run '
                    '`indico db --plugin stsa upgrade` on the server and restart Indico.'), 'error')
            return jsonify_data()

        registrations = (Registration.query
                         .with_parent(self.regform)
                         .filter(~Registration.is_deleted)
                         .all())
        changed = 0
        for registration in registrations:
            before = _stored_discount(registration)
            apply_member_discount(registration, management=True)
            changed += _stored_discount(registration) != before
        db.session.commit()
        if changed:
            self.event.log(EventLogRealm.management, LogKind.change, 'Registration',
                           f'Recalculated STSA member discounts for "{self.regform.title}"', session.user)
            flash(ngettext('One registration was repriced.',
                           '{n} registrations were repriced.', changed).format(n=changed), 'success')
        else:
            flash(_('Every registration already had the right price.'), 'info')
        return jsonify_data(flash=False)


def _stored_discount(registration):
    """A snapshot of the discount value, for telling what actually changed."""
    data = get_discount_data(registration)
    return dict(data.data) if data and data.data else {}


def _count_discounted(regform):
    """How many registrations currently carry the discount."""
    return sum(1 for registration in regform.registrations
               if not registration.is_deleted and is_member_discounted(registration))
