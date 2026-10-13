"""Filling a registration form in from the signed-in member's own account.

Four field types -- 中文姓名, 英文姓名, 就讀科系 and 目前身分 -- are filled in
from the claims the identity provider (authentik) sent when the member signed
in.  A claim that arrived is the answer: the field is locked to it, so what a
member's registrations say about them is what their membership says.  Nobody
signed in, or a claim the account does not have, leaves the field an ordinary
text box.

Indico already keeps every claim.  Its authlib identity provider hands the whole
userinfo response to the identity, and `process_identity` writes it into
``Identity.data`` on every login -- so no second round trip to the provider is
needed, and none is made.  What this module does is the part that needs neither
Indico nor a database: which claims there are, what text a claim reads as, and
what the form data has to say for a field to come out locked.  *Whose* claims
those are, and whether they apply to this request at all, is
`indico_stsa.util.member_profile`.

Like the e-mail address's padlock, and for the same reason, the lock is not
``is_field_data_locked``: core skips a locked field when a registration is
created or modified, which would leave the stored value to be whatever this
plugin wrote and nothing at all where it did not.  The padlock is drawn from
the form data, and the value is written over the submission afterwards -- see
`indico_stsa.handlers.apply_member_profile`.
"""

from indico.util.i18n import _

from indico_stsa.constants import PROFILE_FIELDS


#: Two values for one claim -- a double major arrives as a list -- are shown as
#: one answer.  Dropping the second would be a quiet loss of data, and a slash
#: reads the same in either script.
JOIN = ' / '


def lock_reason():
    """What the padlock on a filled-in field says when it is pointed at.

    A real `str` rather than the lazy string Indico hands back outside a
    request, because this one is serialized into the page with the rest of the
    form data and `json.dumps` refuses a lazy string.
    """
    return str(_('Filled in from your STSA membership. Sign out to enter something else.'))


def _raw_values(data, claim):
    """Every value stored under `claim`, whatever shape `data` is.

    ``Identity.data`` is a werkzeug ``MultiDict``, which is what ``getlist`` is
    for; a plain dict is accepted as well so that this stays testable without
    one.
    """
    if not data:
        return []
    getlist = getattr(data, 'getlist', None)
    if getlist is not None:
        return list(getlist(claim))
    value = data.get(claim)
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _as_text(value):
    """A claim value as the text to put in a field, or ``None``.

    A number is a legitimate answer -- a year of study may well be sent as
    ``2`` -- while a ``bool``, which is also an ``int`` in Python, or anything
    structured is not an answer to a text question and must not turn into the
    literal ``True`` or ``{...}`` in somebody's registration.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip() or None
    return None


def claim_text(data, claim):
    """What an identity's data says under `claim`, as text -- or ``None``."""
    seen = []
    for value in _raw_values(data, claim):
        text = _as_text(value)
        if text and text not in seen:
            seen.append(text)
    return JOIN.join(seen) or None


def profile_values(data):
    """The member's details by field type, leaving out every one not sent.

    Only a claim with an answer is in the result, which is what makes "locked if
    it was filled in" a plain membership test: a form asking for all four, of a
    member whose account has no major, locks three.
    """
    values = {}
    for input_type, claim in PROFILE_FIELDS.items():
        if (text := claim_text(data, claim)) is not None:
            values[input_type] = text
    return values


def autofill_profile_fields(form_data, values):
    """Fill in and lock the fields of a form about to be rendered.

    `form_data` is the flat submission data, whose ``items`` are the camelized
    field data each form item is rendered from.  The value goes in as
    ``autofillValue``, which the field's input component writes into the form,
    and the padlock is the same ``lockedReason`` core's own padlock reads --
    which is also what disables the input.

    A reason somebody else already wrote is left alone, and the field with it:
    something that locked a field for its own reasons is saying more than we
    are, and only one reason is shown.

    :return: how many fields were filled in.
    """
    items = (form_data or {}).get('items') or {}
    filled = 0
    for item in items.values():
        if not isinstance(item, dict):
            continue
        value = values.get(item.get('inputType'))
        if value is None or item.get('lockedReason'):
            continue
        item['autofillValue'] = value
        item['lockedReason'] = lock_reason()
        filled += 1
    return filled
