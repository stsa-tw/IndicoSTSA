"""The organizer's and the administrator's settings forms."""

from decimal import Decimal

from wtforms.fields import BooleanField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import NumberRange, Optional, ValidationError

from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget

from indico_stsa.constants import AMOUNT, APPLIES_TO_BASE, APPLIES_TO_TOTAL, PERCENT


class STSASettingsForm(IndicoForm):
    """The site-wide settings, on the plugin's admin page."""

    rewrite_email_subjects = BooleanField(
        _('Rewrite e-mail subject prefixes'), widget=SwitchWidget(),
        description=_('Replaces the "[Indico]" prefix on every outgoing e-mail. Mails that deliberately carry no '
                      'prefix, such as the room booking ones, are left alone.'))

    email_subject_prefix = StringField(
        _('Subject prefix'),
        description=_('What "[Indico]" is replaced with. Leave empty to strip the prefix entirely.'))

    wallet_badges = BooleanField(
        _('Use the Apple and Google wallet badges'), widget=SwitchWidget(),
        description=_('Replaces the "Add to Wallet" dropdown on the registration summary with the standard Apple '
                      'and Google badges. Only has an effect where an organizer has configured the passes.'))

    wallet_pass_design = BooleanField(
        _('STSA colours on Apple Wallet passes'), widget=SwitchWidget(),
        description=_("Paints the pass in STSA's colours and puts the emblem on it, instead of Indico's blue. "
                      'Only has an effect where an organizer has configured Apple Wallet passes.'))

    cjk_badge_fonts = BooleanField(
        _('Chinese-capable fonts on tickets and badges'), widget=SwitchWidget(),
        description=_('Draws badge and ticket text in Noto Sans/Serif CJK, which Indico already ships but does '
                      'not offer. Without it, Chinese names come out as empty boxes in every font except the '
                      'two Japanese ones and UMing. Applies to every template in the instance.'))

    payment_reminders = BooleanField(
        _('Payment reminders'), widget=SwitchWidget(),
        description=_('Adds a "Remind unpaid" button to the registrant list that writes to everybody whose fee is '
                      'still outstanding, and an {amount} placeholder to the registration e-mail dialogs. Switch it '
                      'off if another plugin claims that placeholder name.'))

    def validate_email_subject_prefix(self, field):
        if field.data and len(field.data) > 60:
            raise ValidationError(_('That prefix is too long for an e-mail subject.'))


class RegFormSettingsForm(IndicoForm):
    """The per-registration-form settings."""

    member_discount_enabled = BooleanField(
        _('Enable the member discount'), widget=SwitchWidget(),
        description=_('Participants who register while signed in with their STSA membership get money off. '
                      'Registrations that already exist are not touched; use "Apply to existing registrations" '
                      'below for those.'))

    discount_type = SelectField(
        _('Discount'),
        choices=[(PERCENT, _('Percentage off')), (AMOUNT, _('Fixed amount off'))])

    discount_value = DecimalField(
        _('Amount'), [Optional(), NumberRange(min=0)], places=2,
        description=_("A percentage, or an amount in the registration form's currency."))

    applies_to = SelectField(
        _('Discount applies to'),
        choices=[(APPLIES_TO_BASE, _('The registration fee only')),
                 (APPLIES_TO_TOTAL, _('The whole price, including paid options'))],
        description=_('Choosing the registration fee keeps paid extras such as the dinner at full price, which is '
                      'usually what an organizer can explain.'))

    notice_text = TextAreaField(
        _('Sign-in notice'), render_kw={'rows': 3},
        description=_('Shown above the registration form to participants who are not signed in. Leave empty to use '
                      'the built-in wording, which names the discount itself.'))

    group_login_required = BooleanField(
        _('Group registration is members only'), widget=SwitchWidget(),
        description=_('Only signed-in STSA members may create or join a group. Needs the group registration '
                      'plugin; without it there is no group registration to restrict.'))

    def __init__(self, *args, group_plugin_installed=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not group_plugin_installed:
            # The setting is stored either way, so switching it on before
            # installing the group plugin is not lost -- but an organizer
            # should not be offered a switch that currently does nothing.
            del self.group_login_required

    def validate_discount_value(self, field):
        if not self.member_discount_enabled.data:
            return
        value = field.data if field.data is not None else Decimal(0)
        if value <= 0:
            raise ValidationError(_('Set a discount above zero, or leave the member discount switched off.'))
        if self.discount_type.data == PERCENT and value > 100:
            raise ValidationError(_('A percentage cannot be above 100.'))
