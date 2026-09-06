"""The plugin class: everything this plugin hooks into, in one place."""

import json

from flask import before_render_template, request, session
from markupsafe import escape

from indico.core import signals
from indico.core.notifications import make_email
from indico.core.plugins import IndicoPlugin, get_plugin_template_module, url_for_plugin
from indico.modules.auth.util import url_for_login
from indico.modules.events.registration.fields.base import RegistrationFormFieldBase
from indico.modules.events.registration.util import get_flat_section_submission_data
from indico.modules.events.registration.views import WPManageRegistration
from indico.modules.events.views import WPConferenceDisplayBase, WPSimpleEventDisplayBase
from indico.util.i18n import _
from indico.util.signals import interceptable_sender
from indico.web.menu import SideMenuItem

from indico_stsa.blueprint import blueprint
from indico_stsa.constants import DEFAULT_SUBJECT_PREFIX
from indico_stsa.discount import format_rate
from indico_stsa.emails import rewrite_subject
from indico_stsa.fields import MemberDiscountField
from indico_stsa.forms import STSASettingsForm
from indico_stsa.group_preview import quote_member_price
from indico_stsa.handlers import (get_locked_field_reason, handle_registration_created, handle_registration_updated)
from indico_stsa.emoji import draw_item_on_badge
from indico_stsa.fonts import update_badge_style
from indico_stsa.payments import OutstandingAmountPlaceholder, find_unpaid
from indico_stsa.pricing import preview_base_price
from indico_stsa.reglist import REGLIST_FILTER_TEMPLATE, hide_internal_columns
from indico_stsa.ticket_email import add_wallet_badges
from indico_stsa.util import get_settings, is_group_login_required, is_group_plugin_installed
from indico_stsa.wallet import VENDORS, badge_url
from indico_stsa.wallet_pass import refined as refine_wallet_ticket
from indico_stsa.wallet_pass import styled as style_wallet_pass


class STSAPlugin(IndicoPlugin):
    """STSA

    Customizations for the Singapore Taiwanese Student Association.

    Replaces the "[Indico]" prefix on outgoing e-mail with STSA's own, and adds
    a member discount that organizers can switch on per registration form:
    money off for anyone who registers while signed in with their STSA
    membership. Participants who are not signed in are told what the discount
    is worth and offered a button that brings them back to the form with
    everything they had already typed still in place.

    An STSA membership is an account on this site, so a member is anyone signed
    in. Where the group registration plugin is also installed, group
    registration can be restricted to signed-in members too.

    It also swaps Indico's "Add to Wallet" dropdown for the standard Apple and
    Google wallet badges, which is what participants actually look for, gives
    tickets and badges a Chinese-capable font and an STSA ticket design, and
    puts a one-click payment reminder for everybody who still owes money in the
    registrant list.
    """

    configurable = True
    settings_form = STSASettingsForm
    default_settings = {
        'rewrite_email_subjects': True,
        'email_subject_prefix': DEFAULT_SUBJECT_PREFIX,
        'wallet_badges': True,
        'wallet_pass_design': True,
        'cjk_badge_fonts': True,
        'payment_reminders': True,
    }

    def init(self):
        super().init()

        # -- e-mail subject prefixes ----------------------------------------
        #
        # `make_email` is the one function every outgoing mail is built by, and
        # it is decorated with `@make_interceptable` precisely so a plugin can
        # step in.  See `indico_stsa.emails` for why this rather than a
        # template override.
        self.connect(signals.plugin.interceptable_function, self._intercept_make_email,
                     sender=interceptable_sender(make_email))

        # -- the member discount --------------------------------------------
        #
        # `get_fields` is connected via the base class, which is how core
        # discovers every registration field implementation.
        self.connect(signals.core.get_fields, self._get_fields, sender=RegistrationFormFieldBase)
        self.connect(signals.event.registration_created, self._registration_created)
        self.connect(signals.event.registration_updated, self._registration_updated)
        self.connect(signals.event.is_field_data_locked, self._is_field_data_locked)

        # The group registration plugin's plan picker quotes a price per member
        # from the form's standard fee, which knows nothing about the member
        # discount.  `get_flat_section_submission_data` builds the field data
        # the whole registration form is rendered from and is decorated with
        # `@make_interceptable` so a plugin can step in -- see
        # `indico_stsa.group_preview`.
        self.connect(signals.plugin.interceptable_function, self._intercept_submission_data,
                     sender=interceptable_sender(get_flat_section_submission_data))

        # -- management UI ---------------------------------------------------
        self.connect(signals.menu.items, self._sidemenu_items, sender='event-management-sidemenu')
        self.template_hook('extra-regform-settings', self._inject_regform_settings)

        # The "Customize list" dialog builds its column list from the form
        # itself and core has no hook for leaving a field out, so the internal
        # member discount field is filtered out of the template's context
        # instead.  See `indico_stsa.reglist` for why that is Flask's signal.
        self.connect(before_render_template, self._before_render_template)

        # -- payment reminders -----------------------------------------------
        #
        # `registration-status-action-button` is core's own hook for an extra
        # button in the registrant list toolbar, and nothing in core uses it,
        # so there is no ordering to negotiate with anybody.  The *Actions*
        # dropdown next to it was the obvious alternative and does not work:
        # both the dropdown itself and every entry in it are rendered with the
        # `disabled` class, which only `js-requires-selected-row` ever takes
        # off again -- so an action that deliberately ignores the selection
        # cannot be reached there at all.
        self.template_hook('registration-status-action-button', self._reglist_action_button)
        # `{amount}`, so the reminder can name the sum it is asking for.
        self.connect(signals.core.get_placeholders, self._get_email_placeholders, sender='registration-email')

        # -- the participant-facing form -------------------------------------
        #
        # Everything the React side needs travels as one `data-stsa` attribute
        # on the regform root; unknown `data-*` there land in `extraData`,
        # which is the sanctioned way to feed a plugin's own data into the
        # registration form.
        self.template_hook('regform-container-attrs', self._regform_container_attrs, markup=False)
        self.template_hook('html-head', self._wallet_head_meta)
        self.connect(signals.core.before_notification_send, self._before_notification_send,
                     sender='notify-registration')

        # -- the Apple Wallet pass -------------------------------------------
        #
        # Core fires these while building a pass, before `passfile.create(...)`
        # signs anything, so what is set here is what ends up in the member's
        # Wallet.  There is no other way in: the background colour is a literal
        # in `build_pass_object`, and a signed pass cannot be repainted
        # afterwards, by us or by the app.
        self.connect(signals.event.registration.apple_wallet_ticket_object, self._refine_apple_wallet_ticket)
        self.connect(signals.event.registration.apple_wallet_object, self._style_apple_wallet_pass)

        # -- printed tickets and badges --------------------------------------
        #
        # Core computes each item's style and then asks whether anything wants
        # to change it, which is where the Chinese-capable font goes in.
        self.connect(signals.event.designer.update_badge_style, self._update_badge_style)
        self.connect(signals.event.designer.draw_item_on_badge, self._draw_item_on_badge)
        self.connect(signals.plugin.cli, self._get_cli)

        # The wallet badges replace server-rendered markup, so the bundle has to
        # reach the pages that carry it as well as the registration form: the
        # "Get ticket" dropdown also appears on a conference home page and in a
        # meeting's header.
        #
        # Only the two display *bases* are listed, not the regform views under
        # them.  `inject_bundle` matches subclasses, so naming both a base and
        # its subclass puts the bundle in the page twice, and the second copy
        # runs the wallet enhancement over the badges the first one made.
        for view_class in (WPConferenceDisplayBase, WPSimpleEventDisplayBase, WPManageRegistration):
            self.inject_bundle('main.js', view_class)
            self.inject_bundle('main.css', view_class)

    def get_blueprints(self):
        return blueprint

    def _draw_item_on_badge(self, sender, data=None, **kwargs):
        """Compose any line the badge fonts cannot draw, rather than boxing it.

        Same setting as the fonts: turning the CJK faces off means core's own
        font is in use, and second-guessing what it can draw is then our
        business no longer.
        """
        try:
            if not self.settings.get('cjk_badge_fonts'):
                return None
            return draw_item_on_badge(sender, data=data, **kwargs)
        except Exception:
            self.logger.exception('Could not compose an emoji item on a badge')
            return None

    def _get_cli(self, sender, **kwargs):
        from indico_stsa.cli import cli
        return cli

    def _update_badge_style(self, sender, item=None, styles=None, **kwargs):
        """Draw badge text in a font that has Chinese in it.

        Off is a real option: it changes the face on *every* template in the
        instance, and an organizer who has tuned a badge to Liberation's
        metrics should be able to keep it.
        """
        try:
            if not self.settings.get('cjk_badge_fonts'):
                return None
            return update_badge_style(sender, item=item, styles=styles, **kwargs)
        except Exception:
            self.logger.exception('Could not apply the CJK badge font')
            return None

    # -- wallet badges -------------------------------------------------------

    def _wallet_head_meta(self, **kwargs):
        """Tell the page where the badge artwork is, or say nothing at all.

        This goes in the document head rather than through `get_vars_js`, which
        would look like the natural home for it.  `vars.js` is generated once
        and written to a cache file keyed on the Indico version, so a setting
        changed in the admin area would not take effect until that file was
        deleted -- a switch that appears to do nothing is worse than no switch.

        The markup this replaces is rendered by templates the plugin does not
        touch, on pages that are not the registration form, so there is no
        `data-` attribute of ours to hang it off either.
        """
        try:
            if not self.settings.get('wallet_badges'):
                return ''
        except Exception:
            self.logger.exception('Could not read the wallet badge setting')
            return ''
        # One tag per vendor whose artwork is actually installed, in the
        # visitor's language.  Apple's badge has to be downloaded by hand, so
        # its tag is usually absent -- and a wallet with no tag simply keeps the
        # button Indico rendered, which is what Apple's guidelines require of
        # anybody who does not have their artwork.
        tags = []
        for vendor in VENDORS:
            if url := badge_url(vendor):
                tags.append(f'<meta name="stsa-wallet-{vendor}" content="{escape(url)}">')
        return ''.join(tags)

    def _style_apple_wallet_pass(self, registration, obj=None, **kwargs):
        """Repaint the pass in STSA's colours.

        Wrapped like every other handler here, and for a sharper reason than
        most: this runs while a participant is downloading their ticket, and an
        exception would turn a working pass into an error page.  Indico's own
        blue is a perfectly good pass, so that is what a failure leaves behind.
        """
        try:
            if not self.settings.get('wallet_pass_design') or obj is None:
                return
            style_wallet_pass(obj)
        except Exception:
            self.logger.exception('Could not apply the STSA design to an Apple Wallet pass')

    def _refine_apple_wallet_ticket(self, event, obj=None, **kwargs):
        """Relabel the fields core put on the pass, and thin them out.

        Same failure rule as the colours: a pass with core's own labels and
        fields is a working ticket, and an exception here would be a download
        that fails.
        """
        try:
            if not self.settings.get('wallet_pass_design') or obj is None:
                return
            refine_wallet_ticket(obj)
        except Exception:
            self.logger.exception('Could not apply the STSA labels to an Apple Wallet ticket')

    def _before_notification_send(self, sender, email=None, registration=None, template_name=None,
                                  to_managers=False, **kwargs):
        """Put the badges into the mail the participant's ticket arrives with.

        The mail is already rendered by the time this runs, so the badges are
        spliced into it rather than templated -- see `indico_stsa.ticket_email`
        for why that is the lesser evil.  A failure here must not stop the mail:
        a ticket that arrives without a wallet button is a small loss, a
        confirmation that never arrives is not.
        """
        try:
            if not self.settings.get('wallet_badges'):
                return
            add_wallet_badges(email, registration, template_name, to_managers)
        except Exception:
            self.logger.exception('Could not add the wallet badges to a registration e-mail')

    # -- e-mail --------------------------------------------------------------

    def _intercept_make_email(self, sender, func=None, args=None, **kwargs):
        """Build the mail as usual, then rewrite its subject prefix.

        Returning a value here means the original function is not called, so we
        call it ourselves -- which is exactly what this signal is for.

        Every failure path ends with Indico building the mail as if this plugin
        were not installed.  A subject prefix is cosmetic; a registration
        confirmation that never went out is not.
        """
        try:
            if not self.settings.get('rewrite_email_subjects'):
                return None
            prefix = self.settings.get('email_subject_prefix')
        except Exception:
            self.logger.exception('Could not read the e-mail subject prefix settings')
            return None
        args.apply_defaults()
        email = func(*args.args, **args.kwargs)
        try:
            email['subject'] = rewrite_subject(email['subject'], prefix)
        except Exception:
            self.logger.exception('Could not rewrite the subject of %r', email.get('subject'))
        return email

    # -- registration --------------------------------------------------------

    def _get_fields(self, sender, **kwargs):
        yield MemberDiscountField

    def _registration_created(self, registration, data=None, management=False, **kwargs):
        handle_registration_created(registration, data, management=management)

    def _registration_updated(self, registration, data=None, management=False, **kwargs):
        handle_registration_updated(registration, data, management=management)

    def _is_field_data_locked(self, sender, registration=None, **kwargs):
        return get_locked_field_reason(sender, registration)

    def _intercept_submission_data(self, sender, func=None, args=None, **kwargs):
        """Quote the member price in the group plugin's plan picker.

        Building the form data is the original function's job, so it is called
        first and its result handed back whatever happens next: this is the
        participant's own registration form, and a picker quoting the standard
        fee is a far smaller thing to lose than the form itself.
        """
        args.apply_defaults()
        form_data = func(*args.args, **args.kwargs)
        try:
            base_price = preview_base_price(args.arguments['regform'],
                                            management=args.arguments['management'],
                                            registration=args.arguments['registration'])
            if base_price is not None:
                quote_member_price(form_data, base_price)
        except Exception:
            self.logger.exception('Could not quote the member price in the group plan picker')
        return form_data

    # -- management UI -------------------------------------------------------

    def _sidemenu_items(self, sender, event, **kwargs):
        if not event.can_manage(session.user, permission='registration'):
            return
        return SideMenuItem('stsa', _('STSA'), url_for_plugin('stsa.manage_overview', event),
                            section='organization', weight=-9)

    def _before_render_template(self, sender, template=None, context=None, **kwargs):
        """Filter the registrant-list column dialog just before it renders.

        This receiver sees *every* template in the instance, so it does as
        little as possible before recognising its own, and it swallows whatever
        goes wrong: a column an organizer should not have been offered is worth
        far less than the page it is on.
        """
        if context is None or getattr(template, 'name', None) != REGLIST_FILTER_TEMPLATE:
            return
        try:
            hide_internal_columns(context)
        except Exception:
            self.logger.exception('Could not filter the registration list column dialog')

    def _reglist_action_button(self, regform, **kwargs):
        """The "remind everybody who has not paid" button, or nothing at all.

        Four things have to be true before it is worth showing, and none of
        them is checked for us.  The hook sits *outside* the surrounding
        `can_manage_registration` block in core's template, so the permission
        is ours to check; an event with no payment feature has nowhere for
        anybody to pay; and a button that opens a dialog saying "nobody owes
        anything" is a button that should not have been drawn.

        Rendering nothing is the failure mode, as everywhere else here: this
        runs in the middle of the registrant list, which an organizer needs far
        more than they need this button.
        """
        try:
            if not self.settings.get('payment_reminders'):
                return ''
            event = regform.event
            if not event.can_manage(session.user, permission='registration'):
                return ''
            if not event.has_feature('payment'):
                return ''
            if not (count := len(find_unpaid(regform))):
                return ''
            tpl = get_plugin_template_module('_reglist_button.html')
            return tpl.render_reminder_button(regform=regform, count=count)
        except Exception:
            self.logger.exception('Could not render the STSA payment reminder button')
            return ''

    def _get_email_placeholders(self, sender, **kwargs):
        """Offer `{amount}` to every registration e-mail, not just the reminder.

        Placeholders are registered per context for the whole instance, so
        there is no way to offer one only to our own dialog -- it turns up in
        core's *E-mail* action too, which is no bad thing.

        The setting is what makes that safe to live with: `{amount}` is a
        short, obvious name, and two plugins claiming it would make
        `named_objects_from_signal` raise on *every* registration e-mail rather
        than only the ones using the placeholder.  Reading the setting is
        guarded separately because the rest of this is a generator, whose body
        does not run until the signal's result is iterated -- which is halfway
        through building somebody's mail.
        """
        try:
            enabled = self.settings.get('payment_reminders')
        except Exception:
            self.logger.exception('Could not read the payment reminder setting')
            return
        if enabled:
            yield OutstandingAmountPlaceholder

    def _inject_regform_settings(self, regform, **kwargs):
        """A row in the registration form's settings box.

        Rendering nothing is the failure mode: this hook sits in the middle of
        a core page that has to keep working whatever state the plugin is in.
        """
        try:
            tpl = get_plugin_template_module('_regform_settings.html')
            return tpl.render_settings_row(regform=regform, settings=get_settings(regform),
                                           group_plugin=is_group_plugin_installed())
        except Exception:
            self.logger.exception('Could not render the STSA registration form settings row')
            return ''

    # -- the participant-facing form -----------------------------------------

    def _regform_container_attrs(self, event, regform, management, registration=None, **kwargs):
        """Hand the React side everything it needs, or nothing at all.

        This one is on the participant's path: the registration form itself
        renders through this hook, so a failure here would cost somebody a
        registration.  No attribute means the React side finds no `data-stsa`
        and leaves the form exactly as core rendered it.
        """
        try:
            return self._build_regform_attrs(event, regform, management, registration)
        except Exception:
            self.logger.exception('Could not build the STSA registration form data')
            return None

    def _build_regform_attrs(self, event, regform, management, registration):
        """The `data-stsa` attribute, or ``None`` when neither feature is on.

        Returning no attribute when neither feature is on keeps this plugin
        entirely invisible on the forms it is not configured for.
        """
        settings = get_settings(regform)
        discount_on = settings is not None and settings.member_discount_enabled
        group_gate_on = is_group_login_required(regform)
        if not discount_on and not group_gate_on:
            return None

        anonymous = not management and session.user is None
        config = {
            # Whether the *visitor* is signed out.  Drives the notices, and
            # decides whether a draft is worth saving.
            'anonymous': anonymous,
            # Whether a draft may be restored.  Deliberately independent of
            # `anonymous`: the whole point is to restore it once the visitor
            # has come back signed *in*.  Off in the management area, where
            # nobody is being asked to sign in for anything.
            'draft': not management,
            'eventId': event.id,
            'regformId': regform.id,
            # Part of the draft's key, so that a draft of a *new* registration
            # can never be restored over somebody editing an existing one.
            'registrationId': registration.id if registration else None,
            'loginUrl': url_for_login(request.relative_url) if anonymous else None,
            'memberDiscount': discount_on,
            'discountRate': (format_rate(settings.discount_type, settings.discount_value, regform.currency)
                             if discount_on else ''),
            'discountAppliesTo': settings.applies_to if discount_on else None,
            'noticeText': (settings.notice_text or '') if discount_on else '',
            'groupLoginRequired': group_gate_on,
        }
        return {'data-stsa': json.dumps(config)}
