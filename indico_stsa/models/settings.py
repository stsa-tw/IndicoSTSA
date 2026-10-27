"""Per-registration-form configuration."""

from decimal import Decimal

from indico.core.db import db
from indico.util.string import format_repr

from indico_stsa.constants import APPLIES_TO_BASE, EVENTS_API_BY_DEFAULT, PERCENT
from indico_stsa.models import SCHEMA


class STSASettings(db.Model):
    """STSA's configuration for one registration form.

    A row exists only for forms an organizer has actually opened the settings
    page for; absence means every feature here is off -- bar the events API,
    which `EVENTS_API_BY_DEFAULT` leaves on -- which is why lookups go through
    `indico_stsa.util.get_settings` rather than the relationship.
    """

    __tablename__ = 'regform_settings'
    __table_args__ = (db.CheckConstraint('discount_value >= 0', name='non_negative_discount'),
                      {'schema': SCHEMA})

    registration_form_id = db.Column(
        db.Integer,
        db.ForeignKey('event_registration.forms.id'),
        primary_key=True
    )
    #: Whether signed-in participants get a discount on this form
    member_discount_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    #: ``percent`` or ``amount``
    discount_type = db.Column(
        db.String,
        nullable=False,
        default=PERCENT
    )
    #: A percentage, or an amount in the form's currency
    discount_value = db.Column(
        db.Numeric(11, 2),
        nullable=False,
        default=Decimal(0)
    )
    #: Whether the discount applies to the registration fee only, or to the
    #: whole price including paid options
    applies_to = db.Column(
        db.String,
        nullable=False,
        default=APPLIES_TO_BASE
    )
    #: The wording of the "sign in to get the discount" notice.  Empty means
    #: the built-in wording, which names the discount itself.
    notice_text = db.Column(
        db.Text,
        nullable=False,
        default=''
    )
    #: Whether creating or joining a group requires being signed in.  Only has
    #: an effect while the group registration plugin is installed.
    group_login_required = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    #: Whether the default *First name* field is switched off, so that the
    #: registrant's English name stands in for it.  Only has an effect while
    #: the form has that field -- see `indico_stsa.util.disabled_names`.
    first_name_disabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    #: Likewise for *Last name*, and the Chinese name.
    last_name_disabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    #: Whether the registrations made with this form are listed by the events
    #: API (`indico_stsa.registered_events`) when their owner asks for the
    #: events they have registered for.  On unless an organizer switched it off,
    #: which is also what a form with no row at all is.
    include_in_events_api = db.Column(
        db.Boolean,
        nullable=False,
        default=EVENTS_API_BY_DEFAULT
    )

    registration_form = db.relationship(
        'RegistrationForm',
        lazy=True,
        backref=db.backref(
            'stsa_settings',
            uselist=False,
            lazy=True
        )
    )

    @property
    def has_discount(self):
        """Whether the discount would actually take anything off."""
        return self.member_discount_enabled and (self.discount_value or 0) > 0

    def __repr__(self):
        return format_repr(self, 'registration_form_id', 'member_discount_enabled', 'group_login_required')
