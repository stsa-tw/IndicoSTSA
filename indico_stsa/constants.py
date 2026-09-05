"""Names shared across modules that must not import each other."""

#: Our billable field.  The ``ext__`` prefix is mandatory for plugin-provided
#: registration fields -- Indico's frontend registry rejects anything else.
MEMBER_DISCOUNT_FIELD = 'ext__stsa_member_discount'

#: Titles of the auto-provisioned section and field.  We find them by input
#: type, not by title, so an organizer may rename them.
MEMBER_DISCOUNT_FIELD_TITLE = 'Member discount'
MEMBER_DISCOUNT_SECTION_TITLE = 'Member discount (internal)'

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

#: The subject prefix Indico ships with, and which this plugin replaces.
#: ``[Indico@somehost]`` is the error-report variant of the same thing.
DEFAULT_SUBJECT_PREFIX = '[STSA 活動]'

#: The name of the `RegistrationState` that means "Awaiting payment".  Spelled
#: out so that `indico_stsa.reminders` can decide who owes money without
#: importing the enum -- and so that the string the pure half compares against
#: is the same one `indico_stsa.payments` filters the query by.
UNPAID_STATE = 'unpaid'

#: Our addition to core's ``registration-email`` placeholders: what the
#: registrant still owes.  Shared because the default reminder body writes it
#: and the placeholder class answers to it.
AMOUNT_PLACEHOLDER = 'amount'
