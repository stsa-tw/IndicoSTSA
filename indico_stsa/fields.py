"""The registration field that carries the member discount.

The value is written by the plugin, never by a participant or a manager: the
plugin locks the field through ``is_field_data_locked``, which makes core skip
it when creating and modifying registrations.

Note the asymmetry this class is built around.  ``calculate_price`` is handed
only the stored value and the versioned data -- it cannot reach the
registration -- so the amount has to be written into the value beforehand, by
`indico_stsa.pricing`.  The ``render_*`` methods do get the whole
`RegistrationData`, so they can name the rate as it is configured right now.
"""

from decimal import Decimal

from marshmallow import fields

from indico.modules.events.registration.custom import RegistrationListColumn
from indico.modules.events.registration.fields.base import RegistrationFormFieldBase
from indico.util.i18n import _

from indico_stsa.constants import MEMBER_DISCOUNT_FIELD
from indico_stsa.discount import format_rate, to_decimal


class MemberDiscountField(RegistrationFormFieldBase):
    """A named discount line for participants who are signed-in members."""

    name = MEMBER_DISCOUNT_FIELD
    mm_field_class = fields.Dict
    versioned_data_fields = frozenset()
    not_empty_if_required = False

    @property
    def default_value(self):
        return {}

    @property
    def empty_value(self):
        return {}

    def calculate_price(self, reg_data, versioned_data):
        if not reg_data:
            return Decimal(0)
        # Never let a malformed value turn into a positive charge.
        return min(to_decimal(reg_data.get('amount', 0)), Decimal(0))

    def _describe(self, data):
        """The Value column: what the discount is, and on what terms."""
        value = data.data or {}
        if not value:
            return ''
        currency = data.registration.currency if data.registration else ''
        rate = format_rate(value.get('rate_type'), value.get('rate'), currency)
        if not rate:
            return str(_('Member'))
        return str(_('Member · {rate} off').format(rate=rate))

    def get_friendly_data(self, registration_data, for_humans=False, for_search=False):
        return self._describe(registration_data)

    def render_summary_data(self, data):
        return self._describe(data)

    def render_invoice_data(self, data):
        return self._describe(data)

    def render_email_data(self, data):
        return self._describe(data)

    def render_reglist_column(self, data):
        text = self._describe(data)
        return RegistrationListColumn(text, text)

    def render_spreadsheet_data(self, data):
        return self._describe(data)
