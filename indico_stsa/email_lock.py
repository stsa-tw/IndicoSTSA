"""Holding a signed-in member's registration to the address on their membership.

An STSA membership is an account on this site, so the membership's e-mail
address is the account's.  Core already fills the registration form's *E-mail*
field in from the account of whoever is signed in; all that is missing is that
it stays that way, so that every registration a member makes can be matched
back to the member who made it -- and so that the member discount, which is
decided from exactly that link, is never quietly lost to a typed-over address.

The padlock and the rule that enforces it come from two different places, which
looks like an inconsistency and is not.

`is_field_data_locked` is the signal a plugin reaches for, and the one the
member discount field uses -- but it means far more than "the participant may
not edit this".  Core *skips* a locked field when a registration is created or
modified, leaving its data empty; that is precisely why the discount field can
have the plugin as its only writer.  Doing the same to the e-mail field would
be fatal: `Registration.email` is not nullable and is written from that same
loop, so every registration would end in an integrity error long before any
handler of ours could put the address back.

So the padlock is drawn by writing `lockedReason` into the flat submission data
the form is rendered from -- the same key core's own `get_locked_reason` fills
in there, so the participant gets core's disabled input and core's padlock with
our wording under it, and none of core's write-side behaviour changes.  The rule
itself is enforced on the address that actually arrives, through
`before_check_registration_email`: that is the one check both the form's live
"is this address all right?" request and the submitted registration go through,
so a hand-built POST meets it too.
"""

from indico.util.i18n import _


#: Core's personal-data e-mail field.  Personal-data fields are named after
#: their type rather than ``field_<id>``, so this is its name on every form.
EMAIL_FIELD = 'email'

#: The conflict we answer `before_check_registration_email` with, and it is one
#: of core's own on purpose.  The registration form renders a *known* conflict
#: as a sentence and an unknown one as whichever branch happens to fall
#: through -- for a dictionary shaped like ours, "the registration will not be
#: associated with any Indico account", which is both wrong and alarming.
#: `email-other-user` at error status is rendered as "This email address is not
#: associated with your Indico account", which is exactly what we mean by it.
FOREIGN_EMAIL_CONFLICT = 'email-other-user'


def lock_reason():
    """What the padlock on the e-mail field says when it is pointed at.

    A real `str`, not the lazy string Indico hands back outside a request:
    this one is serialized into the page with the rest of the form data, and
    `json.dumps` refuses a lazy string -- which would cost the whole
    registration form, not just the padlock.
    """
    return str(_('Your STSA membership is registered under this address. Sign out to register with another one.'))


def lock_email_field(form_data):
    """Draw the padlock on the e-mail field of a form about to be rendered.

    `form_data` is the flat submission data, whose ``items`` are the camelized
    field data each form item is rendered from.  The membership's field is the
    one named after its personal-data type and marked as personal data, which
    is exactly how core's own form recognises it -- a form is free to carry
    other e-mail questions, and an organizer's *Parent's e-mail* is not the
    membership's.

    A reason somebody else already wrote is left alone.  Nothing in core locks
    this field today, but whatever did would be saying something more specific
    than we are about a field that is already disabled, and only one reason is
    shown.

    :return: how many fields were locked -- one on any form whose e-mail field
             was not already locked by somebody else.
    """
    items = (form_data or {}).get('items') or {}
    locked = 0
    for item in items.values():
        if not isinstance(item, dict):
            continue
        if item.get('htmlName') != EMAIL_FIELD or not item.get('fieldIsPersonalData'):
            continue
        if item.get('lockedReason'):
            continue
        item['lockedReason'] = lock_reason()
        locked += 1
    return locked


def is_membership_address(email, member_emails):
    """Whether an address submitted for a registration is the member's own.

    Every address on the account counts, not just the one the profile leads
    with: core looks a registration's user up with `get_user_by_email`, which
    matches secondary addresses too, so a member who registered under one of
    theirs is already linked to the same membership.  Refusing it here would
    mean a registration nobody could edit afterwards -- the address it already
    holds would be one the form would no longer accept.

    Comparison is on the trimmed lower-case address, which is the form Indico
    stores and the form `check_registration_email` has already reduced its
    argument to.
    """
    if not email:
        return False
    return _normalize(email) in {_normalize(known) for known in member_emails or () if known}


def _normalize(email):
    return email.strip().lower()


def foreign_email_error():
    """The answer that turns an address that is not the member's away."""
    return {'status': 'error', 'conflict': FOREIGN_EMAIL_CONFLICT}
