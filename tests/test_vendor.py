"""Scalar's browser bundle is vendored, and has to be what it says it is.

`scripts/update-scalar.py` takes the file out of the npm tarball whose SHA-512 the
registry vouched for and records the SHA-256 of what it took.  This is the other
end of that: a file that was edited, or turned into something else by a
line-ending conversion -- `.gitattributes` makes the whole repository LF, which is
why the bundle is marked as not text -- no longer matches.
"""

import hashlib
import json
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parent.parent / 'indico_stsa'
VENDOR = PLUGIN / 'vendor' / 'scalar'


@pytest.fixture(scope='module')
def manifest():
    return json.loads((VENDOR / 'scalar.json').read_text(encoding='utf-8'))


def test_the_file_is_the_one_that_was_vendored(manifest):
    assert hashlib.sha256((VENDOR / manifest['file']).read_bytes()).hexdigest() == manifest['sha256']


def test_the_manifest_says_what_it_is(manifest):
    assert manifest['package'] == '@scalar/api-reference'
    assert manifest['version'].count('.') == 2
    assert manifest['integrity'].startswith('sha512-')


def test_the_file_is_the_browser_build_and_has_no_windows_line_endings(manifest):
    script = (VENDOR / manifest['file']).read_bytes()
    assert b'\r' not in script
    assert b'createApiReference' in script


def test_the_licence_travels_with_it():
    licence = (VENDOR / 'LICENSE').read_text(encoding='utf-8')
    assert licence.startswith('MIT License')
    assert 'Scalar' in licence


def test_it_is_not_in_the_public_static_folder():
    # `/static/plugins/stsa/` serves everything under `static/` to anybody.  The
    # API reference is for administrators, so its script is served by a handler
    # that checks, from somewhere that folder does not reach.
    assert not (PLUGIN / 'static' / 'scalar').exists()
    assert PLUGIN / 'static' not in VENDOR.parents
