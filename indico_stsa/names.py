"""A registrant's name, taken from the membership fields when First and Last name are off.

A form that asks for 英文姓名 and 中文姓名 has no use for *First name* and *Last
name* beside them, and Indico will not let an organizer switch those two off:
every registration needs a name, so they are required and always enabled -- down
to a constraint in the database.  So they are switched off *here*, on the
plugin's side of the line.  They stay on the form as far as core is concerned,
which keeps every registration with a name and every core feature that reads one
working; what changes is that the participant is not asked for them, and the
registration's name is the English name followed by the Chinese one.

This module is the part that needs neither Indico nor a database: what a name
is, what the form data has to say for the two fields to disappear, and how the
submitted names reach the fields core insists on.  Which fields are off, and
whether they can be, is `indico_stsa.util.disabled_names`.
"""


def clean_name(value):
    """A submitted name as text, or ``None`` when it is not one.

    Anything but a string is not a name, and a string that is only blanks is
    nobody's.
    """
    if not isinstance(value, str):
        return None
    return value.strip() or None


def hide_default_names(form_data, sources):
    """Take the switched-off name fields out of the form a participant is shown.

    :param form_data: the flat submission data, whose ``items`` are the
                      camelized field data each form item is rendered from.
    :param sources: ``{default field's HTML name: HTML name of the field that
                   supplies it}`` for the fields that are off.
    :return: how many were taken out.

    The field that supplies the name is marked required in what it is shown,
    so that the participant is told so before they press the button rather
    than after.  It is not changed on the form: the server is what insists.

    A field taken out is not rendered, which is all it takes -- the form's
    values for it still go back with the rest, and are replaced by
    `inject_names` on the way in.
    """
    items = (form_data or {}).get('items') or {}
    hidden = 0
    for item_id, item in list(items.items()):
        if not isinstance(item, dict):
            continue
        if item.get('fieldIsPersonalData') and item.get('htmlName') in sources:
            del items[item_id]
            hidden += 1
        elif item.get('htmlName') in sources.values():
            item['isRequired'] = True
    return hidden


def inject_names(data, sources):
    """Put the names the participant did give where core expects to find them.

    :param data: the raw submission, changed in place.
    :param sources: as for `hide_default_names`.
    :return: the HTML names of the supplying fields that were submitted blank.

    Core still requires First and Last name, and the form no longer sends them
    -- or sends what it was prefilled with, from an account that may not say
    what the membership does.  Whatever arrived is replaced: the membership
    fields are the answer, and a hand-built request does not get to disagree
    with them.

    A supplying field that is *absent* is left alone, which is what a
    modification that did not touch it looks like.  One that is present and
    blank is the participant having emptied a name the registration needs, and
    is returned so that the error can be put on the field they can see.
    """
    blank = []
    for name, source in sources.items():
        if source not in data:
            continue
        text = clean_name(data[source])
        if text is None:
            blank.append(source)
        else:
            data[name] = text
    return blank
