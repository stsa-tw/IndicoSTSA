"""Names shared across modules that must not import each other."""

#: Our billable field.  The ``ext__`` prefix is mandatory for plugin-provided
#: registration fields -- Indico's frontend registry rejects anything else.
MEMBER_DISCOUNT_FIELD = 'ext__stsa_member_discount'

#: Titles of the auto-provisioned section and field.  We find them by input
#: type, not by title, so an organizer may rename them.
MEMBER_DISCOUNT_FIELD_TITLE = 'Member discount'
MEMBER_DISCOUNT_SECTION_TITLE = 'Member discount (internal)'

#: The member's own details, as registration field types, each mapped to the
#: claim of the signed-in account it is filled in from.  Same ``ext__`` rule as
#: the discount field.  The claim names are the ones the identity provider
#: emits (see `indico_stsa.profile`); the titles an organizer sees are the
#: client's business, in `client/js/index.jsx`, and every name here has to be
#: registered there too or core's form editor crashes on it.
CHINESE_NAME_FIELD = 'ext__stsa_chinese_name'
ENGLISH_NAME_FIELD = 'ext__stsa_english_name'
MAJOR_FIELD = 'ext__stsa_major'
YEAR_OF_STUDY_FIELD = 'ext__stsa_year_of_study'

PROFILE_FIELDS = {
    CHINESE_NAME_FIELD: 'chinese_name',
    ENGLISH_NAME_FIELD: 'english_name',
    MAJOR_FIELD: 'major',
    YEAR_OF_STUDY_FIELD: 'year_of_study',
}

#: The default name fields an organizer may switch off once the form has the
#: member-detail field that stands in for them, by the personal data type's name
#: -- which is also the field's HTML name -- and mapped to that field's type.  A
#: registrant's English name is their first name and their Chinese name their
#: last, so the full name reads English first, the way it does on the membership.
NAME_SOURCES = {
    'first_name': ENGLISH_NAME_FIELD,
    'last_name': CHINESE_NAME_FIELD,
}

#: The group registration plugin, which this one integrates with when it is
#: installed.  Referred to by name rather than imported: it is an optional
#: companion, not a dependency.
GROUP_PLUGIN = 'group_registration'
#: The participant-facing field that plugin adds, and the shape of its answer.
GROUP_PLAN_FIELD = 'ext__group_plan'
#: Its own discount line, which our pricing has to ignore; see
#: `indico_stsa.pricing` for why.
GROUP_DISCOUNT_FIELD = 'ext__group_discount'
#: Values of the ``mode`` key in the group plan answer that mean "I want a
#: group".  ``none`` means the participant is registering on their own.
GROUP_MODES_WITH_GROUP = frozenset({'create', 'join'})

#: Discount kinds.
PERCENT = 'percent'
AMOUNT = 'amount'
DISCOUNT_TYPES = frozenset({PERCENT, AMOUNT})

#: What the discount is calculated against.
APPLIES_TO_BASE = 'base'
APPLIES_TO_TOTAL = 'total'
APPLIES_TO = frozenset({APPLIES_TO_BASE, APPLIES_TO_TOTAL})

#: Whether the events API lists a registration form's registrations when nobody
#: has said either way.  On, so that a participant who asks is answered: off
#: made every form -- and every form nobody had opened the STSA settings of --
#: read as "no events" with nothing to say why.  It is the default of the column
#: *and* the answer for a form with no settings row at all, which is why it is
#: spelled out once here.
EVENTS_API_BY_DEFAULT = True

#: The subject prefix Indico ships with, and which this plugin replaces.
#: ``[Indico@somehost]`` is the error-report variant of the same thing.
DEFAULT_SUBJECT_PREFIX = '[STSA 活動]'

#: The name of the `RegistrationState` that means "Awaiting payment".  Spelled
#: out so that `indico_stsa.reminders` can decide who owes money without
#: importing the enum -- and so that the string the pure half compares against
#: is the same one `indico_stsa.payments` filters the query by.
UNPAID_STATE = 'unpaid'

#: The STSA palette, sampled from the emblem: the merlion half and the bear
#: half.  Here rather than in `indico_stsa.ticket` because the printed 門票 and
#: the artwork script both draw from it, and neither has any business importing
#: the other.  The Apple Wallet pass used to share it; it takes its colours from
#: `EventTicket.pkpasstemplate/pass.json` now, where they are edited by hand.
STRAIT = '#2F5478'
FORMOSA = '#8A2424'
INK = '#1C2733'
GRAPHITE = '#6B7683'
PAPER = '#FFFFFF'
STRAIT_PALE = '#9DB4CC'

#: Our addition to core's ``registration-email`` placeholders: what the
#: registrant still owes.  Shared because the default reminder body writes it
#: and the placeholder class answers to it.
AMOUNT_PLACEHOLDER = 'amount'
