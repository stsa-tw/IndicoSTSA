"""Every field type this plugin names has to exist in the client-side registry.

Core's form editor does not treat an unknown input type as a degraded case.  The
"show this field if" dropdown reads `fieldRegistry[inputType].showIfOptions` for
*every* item on the form, with no guard for a type nobody registered
(`form/fields/ShowIfInput.jsx`), so a field the plugin adds and the client does
not know about does not render badly -- it throws, and takes the whole editor
React tree with it.  The organizer who clicked "Configure field" gets a blank
page.

There is no JS test runner here, and `fields.py` cannot be imported without
Indico, so both sides are read as text.  The parsers are crude on purpose and
each has a test of its own; what is worth catching is a *new* field type that
nobody remembered to register.
"""

import re
from pathlib import Path

from indico_stsa.constants import MEMBER_DISCOUNT_FIELD, PROFILE_FIELDS


ROOT = Path(__file__).parents[1] / 'indico_stsa'
INDEX_JSX = ROOT / 'client' / 'js' / 'index.jsx'
FIELDS_PY = ROOT / 'fields.py'

#: Every field type this plugin adds.  The group plugin's are its own to
#: register, and are rightly not in this list.
OURS = {MEMBER_DISCOUNT_FIELD, *PROFILE_FIELDS}

#: A string literal in ``ext__stsa_*`` form, anywhere in the file.  The profile
#: fields are registered from a list rather than one call each, so a pattern
#: anchored on `registerPluginObject(` would find only the discount.
NAME_RE = re.compile(r"'(ext__stsa_\w+)'")

#: ``name = CHINESE_NAME_FIELD`` -- how each field class says what it is.
CLASS_NAME_RE = re.compile(r'^\s+name = (\w+)$', re.MULTILINE)


def named_in_client():
    return set(NAME_RE.findall(INDEX_JSX.read_text(encoding='utf-8')))


def implemented_in_python():
    return set(CLASS_NAME_RE.findall(FIELDS_PY.read_text(encoding='utf-8')))


def test_the_names_are_found():
    """Guard the parser: a rename must not turn this suite into a no-op."""
    assert len(PROFILE_FIELDS) == 4
    assert MEMBER_DISCOUNT_FIELD in named_in_client()


def test_every_field_type_is_registered_client_side():
    missing = OURS - named_in_client()
    assert not missing, (
        f'{", ".join(sorted(missing))} goes onto registration forms but is not registered in index.jsx; '
        'core crashes the form editor on an input type its React field registry does not have'
    )


def test_the_client_registers_nothing_the_server_does_not_know():
    # A type registered in JS that Python has no class for is an entry in the
    # "Add field" dropdown that ends in a server error.
    unknown = named_in_client() - OURS
    assert not unknown, f'index.jsx registers {", ".join(sorted(unknown))}, which constants.py does not name'


def test_every_profile_field_has_an_implementation():
    # `fields.py` names each class's type through the constants, so what is
    # looked for are the constants' own identifiers.
    constants = Path(ROOT / 'constants.py').read_text(encoding='utf-8')
    wanted = {
        identifier for identifier, value in re.findall(r"^(\w+_FIELD) = '(ext__stsa_\w+)'$", constants, re.MULTILINE)
        if value in PROFILE_FIELDS
    }
    assert len(wanted) == len(PROFILE_FIELDS)
    assert wanted <= implemented_in_python()
