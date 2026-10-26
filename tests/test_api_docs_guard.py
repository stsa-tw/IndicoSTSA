"""Everything the API reference serves is for administrators, and nobody else.

The three handlers -- the page, the OpenAPI document and Scalar's script -- are the
whole of it.  Anything that did not check who was asking would leave a hole that
looks exactly like the rest of the feature from the outside, so this holds the
module to it: every handler in it is an administrator-only one, and none of them
has loosened the check it got from there.  The behaviour itself was exercised
against a running Indico, with an administrator, a member, and nobody.
"""

import inspect

import pytest

from indico.modules.admin.controllers.base import RHAdminBase
from indico.web.rh import RH

from indico_stsa.controllers import docs


HANDLERS = [cls for _, cls in inspect.getmembers(docs, inspect.isclass)
            if issubclass(cls, RH) and cls.__module__ == docs.__name__]


def test_there_are_handlers_to_check():
    assert {cls.__name__ for cls in HANDLERS} == {'RHSTSAAPIDocs', 'RHSTSAOpenAPI', 'RHSTSAScalarScript'}


@pytest.mark.parametrize('handler', HANDLERS, ids=lambda cls: cls.__name__)
def test_only_an_administrator_gets_in(handler):
    assert issubclass(handler, RHAdminBase)
    # Not overridden to be more permissive on the way down.
    assert handler._check_access is RHAdminBase._check_access


def test_the_script_is_not_somewhere_the_public_can_fetch_it():
    assert docs.SCALAR_SCRIPT.parent.parent.name == 'vendor'


def test_the_page_may_only_talk_to_this_server():
    directives = dict(part.split(' ', 1) for part in docs.CONTENT_SECURITY_POLICY.split('; '))
    assert directives['default-src'] == "'none'"
    assert directives['connect-src'] == "'self'"
    assert directives['script-src'] == "'self'"
    assert 'unsafe-eval' not in docs.CONTENT_SECURITY_POLICY


def test_scalar_is_told_not_to_phone_home():
    assert docs.SCALAR_CONFIGURATION['telemetry'] is False
    assert docs.SCALAR_CONFIGURATION['agent'] == {'disabled': True}
    assert docs.SCALAR_CONFIGURATION['withDefaultFonts'] is False
