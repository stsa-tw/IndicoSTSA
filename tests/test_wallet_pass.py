"""What the Apple Wallet pass is repainted in, and how its fields are tidied."""

import pytest

from indico_stsa import constants, ticket
from indico_stsa.constants import FORMOSA, INK, PARCHMENT
from indico_stsa.wallet_pass import (ALIGN_RIGHT, IMAGE_NAMES, PASS_BARCODE_CAPTION, PASS_COLORS,
                                    PASS_FIELD_LABELS, PASS_HEADER_LABEL, PASS_LOGO_TEXT, images, refined,
                                    styled)


class FakePass:
    """Stands in for `wallet.models.Pass`, which needs a certificate to build.

    Only the four attributes this module writes; anything else it touched would
    show up here as an `AttributeError` rather than silently in production.

    The camelCase is Apple's, via the `wallet` library, and is what the real
    object is named -- spelling it our way here would test the wrong thing.
    """

    class FakeBarcode:
        def __init__(self):
            self.altText = ''

    def __init__(self):
        self._files = {}
        self.barcode = FakePass.FakeBarcode()
        self.backgroundColor = '#007cac'
        self.foregroundColor = '#ffffff'
        self.labelColor = '#ffffff'
        self.logoText = 'Some Legal Entity Pte Ltd'


def test_repaints_every_colour_indico_sets():
    """Core sets all three, so all three have to be replaced.

    Replacing only the background would leave labels that were chosen against a
    blue which is no longer there.
    """
    result = styled(FakePass())

    assert result.backgroundColor == PARCHMENT
    assert result.foregroundColor == INK
    assert result.labelColor == FORMOSA


def test_replaces_the_certificate_derived_logo_text():
    """Indico fills this from the certificate's `O` field.

    That is whatever the Apple Developer account is registered as -- a legal
    name, and not necessarily one anybody at the door would recognise.
    """
    assert styled(FakePass()).logoText == PASS_LOGO_TEXT


def test_styles_in_place_and_returns_the_same_object():
    """The caller in `plugin.py` reads as one line and relies on this."""
    passfile = FakePass()
    assert styled(passfile) is passfile


def test_draws_from_the_same_palette_as_the_printed_ticket():
    """One association, one palette, two media.

    The pass is light where the stub is navy, which is a choice about where each
    one is looked at -- but both come out of `constants`, and somebody
    hardcoding a hex into either is the drift this is here to catch.
    """
    assert PASS_COLORS['backgroundColor'] == constants.PARCHMENT
    assert PASS_COLORS['foregroundColor'] == ticket.INK
    assert PASS_COLORS['labelColor'] == ticket.FORMOSA


@pytest.mark.parametrize('colour', PASS_COLORS.values())
def test_colours_are_hex_apple_accepts(colour):
    """PassKit takes `#rrggbb` or `rgb(...)`; the library passes ours through."""
    assert colour.startswith('#')
    assert len(colour) == 7
    int(colour[1:], 16)


class TestImages:
    def test_ships_a_logo_and_an_icon(self):
        """Both are load-bearing.

        Without the logo a pass falls back to whatever `WALLET_LOGO_URL` points
        at, which on a light pass is usually the white lockup and therefore
        nothing; without the icon it is not a valid pass at all.
        """
        found = images()

        assert 'logo.png' in found
        assert 'icon.png' in found
        assert all(data for data in found.values())

    def test_every_name_is_one_apple_looks_for(self):
        """A file under a name Apple does not know is dead weight in the pass.

        `strip.png` in particular is not merely unused: supplying one makes
        Wallet render the event title in white rather than in `foregroundColor`,
        which on a light pass is a title nobody can read.
        """
        for name in IMAGE_NAMES:
            stem = name.removesuffix('.png').split('@')[0]
            assert stem in {'logo', 'icon'}

    def test_attaches_them_where_indico_puts_its_own(self):
        passfile = styled(FakePass())

        assert 'logo.png' in passfile._files
        assert passfile._files['logo.png'].startswith(b'\x89PNG')

    def test_a_pass_without_the_files_dict_still_gets_its_colours(self):
        """`_files` is a private attribute of a third-party library.

        If it is ever renamed, a pass in Indico's blue is the right outcome and
        an exception during a ticket download is not.
        """
        class Older(FakePass):
            def __init__(self):
                super().__init__()
                del self._files

        result = styled(Older())

        assert result.backgroundColor == PARCHMENT
        assert not hasattr(result, '_files')


def test_captions_the_barcode():
    """Wallet's only text slot under the QR is the barcode's `altText`.

    Indico leaves it empty and the check-in code is a UUID nobody would read
    aloud, so the space carries the instruction instead.
    """
    assert styled(FakePass()).barcode.altText == PASS_BARCODE_CAPTION
    # English only: Wallet sets it at one small size beside Latin field
    # values, and a mixed-script line there gives the pass two type colours.
    assert PASS_BARCODE_CAPTION.isascii()


def test_a_pass_without_a_barcode_is_left_alone():
    """Captioning a barcode that is not there would be inventing one."""
    class NoBarcode(FakePass):
        def __init__(self):
            super().__init__()
            del self.barcode

    assert not hasattr(styled(NoBarcode()), 'barcode')


class FakeField:
    """`wallet.models.Field`: the three things core sets and the one we set."""

    def __init__(self, key, value, label=''):
        self.key = key
        self.value = value
        self.label = label
        self.textAlignment = 'PKTextAlignmentLeft'


class FakeTicket:
    """Core's `EventTicket`, with exactly the fields `build_ticket_object` writes."""

    def __init__(self):
        self.headerFields = []
        self.primaryFields = [FakeField('event-title', '2026 STSA Boba Chat', 'Event')]
        self.secondaryFields = [FakeField('event-date', '30 Aug 2026, 13:00', 'Date'),
                                FakeField('event-venue', 'Wushiland Boba', 'Venue')]
        self.auxiliaryFields = [FakeField('registration-name', '楊晨諺', 'Name'),
                                FakeField('registration-email', 'member@u.nus.edu', 'Email')]
        self.backFields = [FakeField('back-registration-email', 'member@u.nus.edu', 'Email'),
                           FakeField('back-ticket-number', '#1042', 'Ticket number')]


def keys(fields):
    return [field.key for field in fields]


class TestRefined:
    def test_takes_the_email_off_the_front_and_leaves_it_on_the_back(self):
        """A pass is readable from a locked phone; an address is not a ticket's
        business to show. Core also keeps it on the back, so nothing is lost."""
        ticket = refined(FakeTicket())

        assert 'registration-email' not in keys(ticket.auxiliaryFields)
        assert 'back-registration-email' in keys(ticket.backFields)

    def test_relabels_with_our_words_and_nothing_else(self):
        ticket = refined(FakeTicket())

        assert ticket.primaryFields[0].label == PASS_FIELD_LABELS['event-title']
        assert ticket.auxiliaryFields[0].label == PASS_FIELD_LABELS['registration-name']
        # A key we have no word for keeps core's.
        assert ticket.backFields[0].label == 'Email'

    def test_labels_are_english(self):
        """Typographic, not linguistic: Wallet sets every label at one small
        size, and a mixed-script label there gives the pass two type colours."""
        assert all(label.isascii() for label in PASS_FIELD_LABELS.values())
        assert PASS_HEADER_LABEL.isascii()

    def test_brings_the_ticket_number_forward_into_the_header(self):
        """The header is what Wallet shows while passes are stacked -- the one
        line a member sees without opening anything."""
        ticket = refined(FakeTicket())

        assert len(ticket.headerFields) == 1
        assert ticket.headerFields[0].value == '#1042'
        assert ticket.headerFields[0].label == PASS_HEADER_LABEL
        # Forward, not duplicated: it was once in the holder's row as well, and
        # the same number twice on one small card read worse than the gap.
        assert '#1042' not in [field.value for field in ticket.auxiliaryFields]

    def test_is_idempotent(self):
        """Core may fire the signal more than once for one pass."""
        ticket = refined(refined(FakeTicket()))

        assert len(ticket.headerFields) == 1
        assert keys(ticket.auxiliaryFields) == ['registration-name']

    def test_a_ticket_with_no_number_on_the_back_gets_no_header(self):
        ticket = FakeTicket()
        ticket.backFields = [field for field in ticket.backFields if field.key != 'back-ticket-number']

        assert refined(ticket).headerFields == []

    def test_right_aligns_the_second_column_only(self):
        """Two columns with an edge each, instead of both ragging right. A row
        with one field has nothing to align against and is left alone."""
        ticket = refined(FakeTicket())

        assert ticket.secondaryFields[0].textAlignment == 'PKTextAlignmentLeft'
        assert ticket.secondaryFields[1].textAlignment == ALIGN_RIGHT
        assert ticket.auxiliaryFields[0].textAlignment == 'PKTextAlignmentLeft'

    def test_returns_the_same_object(self):
        ticket = FakeTicket()
        assert refined(ticket) is ticket
