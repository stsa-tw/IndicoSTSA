"""The Google Wallet class is made before a mail carrying its link goes out.

Indico makes the class on the first click on a Google link, and a mail full of
those links is clicked by a link scanner all at once -- so the first mail of an
event is what makes the class instead.  Core's `GoogleWalletManager` is replaced
here by a stand-in, because making a class is a call to Google; what is tested is
when it is made, how often, and that nothing it does can stop the mail.
"""

import sys
from types import ModuleType, SimpleNamespace

import pytest
from flask import Flask

from indico_stsa import ticket_email
from indico_stsa.ticket_email import add_wallet_badges, ensure_google_wallet_class


GOOGLE_MODULE = 'indico.modules.events.registration.wallets.google'


class _Wallet:
    """A `GoogleWalletManager` that remembers what was asked of it."""

    stored = set()
    created = []
    fail_with = None
    refuse_to_load = False

    def __init__(self, event):
        if self.refuse_to_load:
            raise ValueError('bad credentials')
        self.event = event

    @staticmethod
    def event_uses_google_wallet_tickets(event):
        return event.id in _Wallet.stored

    def create_ticket_class(self, *, update=False):
        _Wallet.created.append(self.event.id)
        if _Wallet.fail_with is not None:
            raise _Wallet.fail_with
        _Wallet.stored.add(self.event.id)
        return f'Indico-Event-{self.event.id}'


class _Log:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args, **kwargs):
        self.warnings.append((message, args, kwargs))


@pytest.fixture(autouse=True)
def wallet(monkeypatch):
    _Wallet.stored = set()
    _Wallet.created = []
    _Wallet.fail_with = None
    _Wallet.refuse_to_load = False
    module = ModuleType(GOOGLE_MODULE)
    module.GoogleWalletManager = _Wallet
    monkeypatch.setitem(sys.modules, GOOGLE_MODULE, module)
    return _Wallet


@pytest.fixture(autouse=True)
def request_context():
    with Flask('test').app_context():
        yield


@pytest.fixture
def log(monkeypatch):
    log = _Log()
    monkeypatch.setattr(ticket_email, 'logger', log)
    return log


def event(id=1):
    return SimpleNamespace(id=id)


class TestEnsureGoogleWalletClass:
    def test_the_class_is_made_when_the_event_has_none(self, wallet):
        ensure_google_wallet_class(event(7))
        assert wallet.created == [7]
        assert 7 in wallet.stored

    def test_an_event_that_has_one_is_left_alone(self, wallet):
        wallet.stored.add(7)
        ensure_google_wallet_class(event(7))
        assert wallet.created == []

    def test_a_bulk_mail_makes_it_once(self, wallet):
        for __ in range(20):
            ensure_google_wallet_class(event(7))
        assert wallet.created == [7]

    def test_each_event_gets_its_own(self, wallet):
        ensure_google_wallet_class(event(7))
        ensure_google_wallet_class(event(8))
        assert wallet.created == [7, 8]

    def test_the_next_request_looks_again(self, wallet):
        wallet.fail_with = RuntimeError('Google is down')
        ensure_google_wallet_class(event(7))
        wallet.fail_with = None
        with Flask('test').app_context():
            ensure_google_wallet_class(event(7))
        assert wallet.created == [7, 7]
        assert 7 in wallet.stored

    def test_a_failure_is_logged_and_does_not_escape(self, wallet, log):
        wallet.fail_with = RuntimeError('Google is down')
        ensure_google_wallet_class(event(7))
        assert len(log.warnings) == 1
        assert log.warnings[0][2]['exc_info'] is True

    def test_a_failure_is_not_retried_for_the_rest_of_the_request(self, wallet, log):
        # Without this, a bulk approval while Google is unreachable would wait
        # on it once per registrant.
        wallet.fail_with = RuntimeError('Google is down')
        for __ in range(20):
            ensure_google_wallet_class(event(7))
        assert wallet.created == [7]
        assert len(log.warnings) == 1

    def test_credentials_that_do_not_load_do_not_escape_either(self, wallet, log):
        wallet.refuse_to_load = True
        ensure_google_wallet_class(event(7))
        assert wallet.created == []
        assert len(log.warnings) == 1


class _Registration:
    id = 5
    locator = SimpleNamespace(registrant='registrant')

    def __init__(self, event):
        self.event = event
        self.registration_form = SimpleNamespace(event=event)


@pytest.fixture
def mail(monkeypatch, tmp_path):
    """`add_wallet_badges` with the parts that need a database or artwork stubbed."""
    artwork = tmp_path / 'badge.png'
    artwork.write_bytes(b'\x89PNG')
    monkeypatch.setattr(ticket_email, 'carries_ticket', lambda *args: True)
    monkeypatch.setattr(ticket_email, 'available_vendors', lambda regform: ('google', 'apple'))
    monkeypatch.setattr(ticket_email, 'badge_path', lambda vendor, extension: artwork)
    monkeypatch.setattr(ticket_email, 'url_for', lambda endpoint, *args, **kwargs: f'https://example.test/{endpoint}')
    # The labels are lazy strings, which want Indico's translations to be read.
    monkeypatch.setattr(ticket_email, 'VENDOR_LABELS', {'apple': 'Apple', 'google': 'Google'})
    monkeypatch.setattr(ticket_email, '_', lambda text: text)
    return {'attachments': [], 'body': '<p>Your ticket</p>'}


class TestAddWalletBadges:
    def test_the_class_exists_before_the_mail_is_done(self, wallet, mail):
        assert add_wallet_badges(mail, _Registration(event(7)), 'any.html', False)
        assert wallet.created == [7]
        assert len(mail['attachments']) == 2

    def test_the_mail_goes_out_when_the_class_could_not_be_made(self, wallet, mail, log):
        wallet.fail_with = RuntimeError('Google is down')
        assert add_wallet_badges(mail, _Registration(event(7)), 'any.html', False)
        assert len(mail['attachments']) == 2
        assert 'ticket_google_wallet' in str(mail['body'])
        assert len(log.warnings) == 1

    def test_no_google_artwork_means_no_class(self, wallet, mail, monkeypatch, tmp_path):
        apple = tmp_path / 'apple.png'
        apple.write_bytes(b'\x89PNG')
        monkeypatch.setattr(ticket_email, 'badge_path', lambda vendor, extension: apple if vendor == 'apple' else None)
        assert add_wallet_badges(mail, _Registration(event(7)), 'any.html', False)
        assert wallet.created == []

    def test_a_form_without_google_makes_none(self, wallet, mail, monkeypatch):
        monkeypatch.setattr(ticket_email, 'available_vendors', lambda regform: ('apple',))
        assert add_wallet_badges(mail, _Registration(event(7)), 'any.html', False)
        assert wallet.created == []

    def test_a_mail_that_carries_no_ticket_makes_none(self, wallet, mail, monkeypatch):
        monkeypatch.setattr(ticket_email, 'carries_ticket', lambda *args: False)
        assert not add_wallet_badges(mail, _Registration(event(7)), 'any.html', False)
        assert wallet.created == []
