"""The subject prefix rewriting, which every outgoing mail goes through."""

import pytest

from indico_stsa.constants import DEFAULT_SUBJECT_PREFIX
from indico_stsa.emails import rewrite_subject


@pytest.mark.parametrize(('subject', 'expected'), (
    ('[Indico] Registration confirmation', '[STSA 活動] Registration confirmation'),
    ('[Indico] Reset your password', '[STSA 活動] Reset your password'),
    # The error report mail carries the server name inside the prefix.
    ('[Indico@indico.example.com] Error', '[STSA 活動] Error'),
    # Core normalizes whitespace after rendering the subject macro, but the
    # macro itself emits a leading newline, so be tolerant of both.
    ('  [Indico]   Spaced out  ', '[STSA 活動] Spaced out  '),
))
def test_rewrites_indico_prefix(subject, expected):
    assert rewrite_subject(subject, DEFAULT_SUBJECT_PREFIX) == expected


@pytest.mark.parametrize('subject', (
    # The room booking mails set the prefix block to empty on purpose.
    'Booking confirmed for Room 42',
    # A prefix that is not at the start is part of the subject.
    'Re: [Indico] Registration confirmation',
    # Another system's prefix is not ours to touch.
    '[Sentry] New issue',
    '',
))
def test_leaves_everything_else_alone(subject):
    assert rewrite_subject(subject, DEFAULT_SUBJECT_PREFIX) == subject


def test_empty_prefix_strips():
    assert rewrite_subject('[Indico] Hello', '') == 'Hello'
    assert rewrite_subject('[Indico] Hello', None) == 'Hello'


def test_prefix_is_stripped_of_stray_whitespace():
    assert rewrite_subject('[Indico] Hello', '  [STSA]  ') == '[STSA] Hello'


def test_subject_that_is_only_a_prefix():
    assert rewrite_subject('[Indico]', '[STSA]') == '[STSA]'


def test_none_subject_survives():
    assert rewrite_subject(None, '[STSA]') is None
