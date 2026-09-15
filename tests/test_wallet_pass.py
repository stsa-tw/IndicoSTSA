"""What the Apple Wallet pass is drawn from, and what survives the drawing."""

import json
from dataclasses import replace

import pytest

from indico_stsa.wallet_pass import (ICON_FALLBACK, PassTicket, images, pass_json,
                                     style_key, styled, template)


TICKET = PassTicket(
    title='2026 STSA 中秋烤肉',
    start='2026-09-25T18:00:00+08:00',
    end='2026-09-25T22:00:00+08:00',
    venue='East Coast Park · Area D',
    venue_name='East Coast Park',
    room_name='Area D',
    address='920 East Coast Parkway, Singapore 449875',
    event_url='https://event.stsa.tw/event/42/',
    holder='陳小美',
    friendly_id='7',
    qr_message='{"i":[2,"event.stsa.tw","AAAAAAAAQACAAAAAAAAAAw=="]}',
)

#: What core sets on the pass from the certificate's subject before the signal
#: fires.  Wallet checks these against the signature.
#:
#: Deliberately *not* the values in the template: the point of
#: `test_identity_overrides_whatever_the_template_was_saved_with` is that the
#: certificate wins, and a fixture that agreed with the template would prove
#: nothing.  The real pass type is `pass.tw.stsa.event`.
IDENTITY = {
    'passTypeIdentifier': 'pass.example.not-the-template',
    'teamIdentifier': 'FJX3SGU9AL',
    'serialNumber': '11111111-2222-4333-8444-555555555555',
    'formatVersion': 1,
}


class FakePass:
    """Stands in for `wallet.models.Pass`, which needs a certificate to build.

    Only what this module reads or writes; anything else it touched would show
    up here as an `AttributeError` rather than silently in production.

    The camelCase is Apple's, via the `wallet` library, and is what the real
    object is named -- spelling it our way here would test the wrong thing.
    """

    def __init__(self):
        self._files = {'icon.png': b'indico', 'logo.png': b'indico'}
        self.passTypeIdentifier = IDENTITY['passTypeIdentifier']
        self.teamIdentifier = IDENTITY['teamIdentifier']
        self.serialNumber = IDENTITY['serialNumber']


@pytest.fixture
def design():
    return template()


@pytest.fixture
def built(design):
    return pass_json(TICKET, IDENTITY, design)


@pytest.fixture
def style(design):
    return style_key(design)


def fields_of(built, style):
    return {f['key']: f for bucket in built[style].values() for f in bucket}


# -- the design comes from the template, not from here ------------------------

def test_style_key_is_found_by_shape_not_by_name(design):
    """Switching the style in Pass Designer renames the key.

    `posterGeneric` today; whatever Apple calls the layout after that later.
    Naming it in code would mean a silent revert to core's `eventTicket` the
    first time somebody changed the design.
    """
    assert style_key(design) in design
    assert any(k.endswith('Fields') for k in design[style_key(design)])


def test_a_design_with_no_style_key_is_an_error():
    with pytest.raises(ValueError):
        style_key({'formatVersion': 1, 'description': 'nothing to draw'})


@pytest.mark.parametrize('key', ('backgroundColor', 'foregroundColor', 'labelColor',
                                 'logoText', 'description', 'organizationName',
                                 'sharingProhibited'))
def test_the_template_supplies_the_design(built, design, key):
    """Every appearance key is quoted, so redesigning is not a commit here.

    `sharingProhibited` is in the list for a second reason: a ticket QR *is* the
    credential -- whoever holds it can be checked in as that member -- so Wallet
    must not offer to pass it along.
    """
    assert built.get(key) == design.get(key)


def test_static_copy_stays_editable_in_pass_designer(built, design, style):
    """Fields with nothing registration-specific keep the template's words.

    The organiser line and the door notice are copy, not data.  Burying them in
    Python would mean a release to fix a typo.
    """
    quoted = fields_of(design, style)
    written = fields_of(built, style)
    for key in ('organiser', 'notice'):
        assert written[key]['value'] == quoted[key]['value']


# -- what belongs to one registration -----------------------------------------

def test_registration_values_are_substituted(built, style):
    written = fields_of(built, style)
    assert written['event']['value'] == TICKET.title
    assert written['holder']['value'] == TICKET.holder
    assert written['venue']['value'] == TICKET.venue
    assert written['registration']['value'] == '#7'


def test_the_primary_caption_is_the_template_s_for_every_category():
    """One caption whatever the event is -- a lecture and a meetup read alike.

    The value is substituted and the label deliberately is not, so recaptioning
    the ticket stays a Pass Designer edit.
    """
    built = pass_json(TICKET, IDENTITY)
    style = style_key(template())
    field = fields_of(built, style)['event']
    assert field['value'] == TICKET.title
    assert field['label'] == fields_of(template(), style)['event']['label']


def test_date_styles_are_the_template_s(built, style):
    """Wallet formats a date for the member's locale, given a real date and a
    style.  Which style is a design decision, so it stays in the template."""
    written = fields_of(built, style)
    assert written['time']['timeStyle'] == 'PKDateStyleShort'
    assert written['date']['dateStyle'] == 'PKDateStyleMedium'
    assert written['time']['value'] == TICKET.start


def test_identity_overrides_whatever_the_template_was_saved_with(built):
    """The template carries a proposal; the certificate carries the truth.

    A pass whose `passTypeIdentifier` disagrees with the signature is one iOS
    refuses with nothing but "cannot install" to go on.
    """
    for key, value in IDENTITY.items():
        assert built[key] == value


def test_an_event_with_no_venue_drops_the_row(design, style):
    """Rather than shipping a labelled blank, which reads as a mistake."""
    bare = pass_json(replace(TICKET, venue=None, venue_name=None, room_name=None),
                     IDENTITY, design)
    assert 'venue' not in fields_of(bare, style)
    assert 'venueName' not in bare['semantics']


# -- hygiene ------------------------------------------------------------------

def test_preferred_style_schemes_is_stripped(built, design):
    """Pass Designer writes `posterEventTicket` back on every save.

    That is the scheme limited to NFC-enabled passes, which wants an entitlement
    Apple issues case by case -- and asking for it while the style key says
    `posterGeneric` is incoherent besides.  Deleting it from the template does
    not stick, so it is removed here instead.

    The first assertion is deliberate: if the template ever stops carrying the
    key, the second one stops proving anything.
    """
    assert 'preferredStyleSchemes' in design, 'template no longer carries it -- this test is now vacuous'
    assert 'preferredStyleSchemes' not in built


def test_designer_bookkeeping_does_not_ship(built, style):
    """`_id` is how Pass Designer tracks a field between saves."""
    assert not any('_id' in field for field in fields_of(built, style).values())


def test_the_barcode_is_the_plural_form(built):
    """`barcode` singular is deprecated; `barcodes` is what Wallet reads now.

    `wallet-py3k` only emits the singular, which is one of the reasons the whole
    of pass.json is replaced rather than a few attributes set.
    """
    assert 'barcode' not in built
    assert built['barcodes'][0]['message'] == TICKET.qr_message
    assert built['barcodes'][0]['format'] == 'PKBarcodeFormatQR'


def test_the_barcode_caption_is_the_ticket_number(built):
    """Wallet has exactly one text slot under the code.  Indico leaves it empty;
    the ticket number is what a door asks for when a scanner will not read."""
    assert built['barcodes'][0]['altText'] == '#7'


def test_sample_coordinates_do_not_ship(built):
    """The template's are its sample event's, and Indico holds no latitude or
    longitude for a real one.  A pass claiming every event happens at one park
    would wake on the Lock Screen in the wrong place."""
    assert 'locations' not in built
    assert 'venueLocation' not in built['semantics']


def test_empty_semantic_tags_do_not_ship(built):
    """Pass Designer leaves empty collections behind for slots it offers and the
    design does not use.  An empty tag says nothing."""
    assert all(value not in (None, '', [], {}) for value in built['semantics'].values())


def test_semantics_describe_this_event(built):
    assert built['semantics']['eventName'] == TICKET.title
    assert built['semantics']['eventStartDate'] == TICKET.start
    assert built['semantics']['venueRoom'] == TICKET.room_name


def test_a_ticket_outlives_its_event(built):
    """`RHTicketDownload`'s four access checks say nothing about the date, so a
    pass for an event already attended is a record worth keeping."""
    assert 'expirationDate' not in built
    assert 'voided' not in built


# -- the artwork --------------------------------------------------------------

def test_the_template_ships_its_own_images():
    found = images()
    assert {'icon@2x.png', 'icon@3x.png', 'artwork@2x.png', 'primaryLogo@2x.png'} <= found.keys()
    assert 'pass.json' not in found


def test_an_unscaled_icon_is_synthesised():
    """A pass without `icon.png` is invalid, and Pass Designer exports no 1x."""
    found = images()
    assert found['icon.png'] == found[ICON_FALLBACK]


def test_localisations_ship_under_their_directory():
    """`.lproj` entries keep their path inside the bundle, which is how Wallet
    finds the strings for the member's own language."""
    found = images()
    assert {'en.lproj/pass.strings', 'zh-Hant.lproj/pass.strings'} <= found.keys()


# -- applying it to a real pass object ----------------------------------------

def test_styled_replaces_indico_s_images():
    """Core fetches its logo over HTTP before this runs, and substitutes
    *Indico's* mark when the fetch fails.  Neither belongs on an STSA pass."""
    result = styled(FakePass(), TICKET)
    assert result._files['icon.png'] != b'indico'
    assert 'artwork@2x.png' in result._files


def test_styled_installs_the_pass_json(built):
    """`PassHandler` calls `json_dict()` if it exists, so what it returns is
    pass.json -- that is the whole of how the whitelist is worked around."""
    result = styled(FakePass(), TICKET)
    assert result.json_dict() == built


def test_styled_survives_a_pass_without_files():
    """`_files` is a private attribute of a third-party library.  A pass that
    keeps Indico's images is a working ticket; an exception here is a download
    that fails."""
    class Bare:
        def __init__(self):
            self.passTypeIdentifier = self.teamIdentifier = self.serialNumber = 'x'

    bare = Bare()
    styled(bare, TICKET)
    assert bare.json_dict()['description']


def test_the_serialiser_emits_what_we_built(built):
    """The library this works around, driven for real rather than reasoned about.

    Skipped where `wallet-py3k` is absent: it is Indico's dependency, not ours,
    so a checkout without Indico installed has no copy of it.
    """
    models = pytest.importorskip('wallet.models')
    # The same identity `built` was made with: `styled` reads it off the pass
    # object, so a fake carrying different ids would differ for an uninteresting
    # reason and hide whether the serialiser kept everything else.
    passfile = models.Pass(models.EventTicket(),
                           passTypeIdentifier=IDENTITY['passTypeIdentifier'],
                           organizationName='y',
                           teamIdentifier=IDENTITY['teamIdentifier'])
    passfile.serialNumber = IDENTITY['serialNumber']
    styled(passfile, TICKET)
    emitted = json.loads(passfile._createPassJson().decode())

    assert emitted == built
    # The keys the whitelist would otherwise have dropped.
    assert 'semantics' in emitted
    assert 'sharingProhibited' in emitted
    assert style_key(emitted) != 'eventTicket'
