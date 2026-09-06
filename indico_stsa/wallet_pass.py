"""The Apple Wallet pass, in the association's colours and marks.

Indico builds a perfectly good pass and paints it `#007cac`, its own blue,
hardcoded in `AppleWalletManager.build_pass_object`.  That is the right default
for an instance that has never been told what it looks like, and the wrong one
for an association with a red mark of its own.

This module says what the pass should look like, and nothing else.  It takes no
Indico import and touches no database, which is what lets every decision here
be tested without an instance; `plugin.py` holds the two handlers that apply it
to a real pass.  The printed 門票 in `indico_stsa.ticket` is navy on paper and
this is ink on parchment -- deliberate rather than drift: the stub is an object
you are handed, and the pass sits in a stack of dark boarding cards where a
light one is the one you can find.  Both draw from the palette in `constants`.

**A pass takes a palette, not a design.**  Three colours, a logo, an icon, and
fields Apple lays out itself: no typeface, no per-field icons, no rules, no
bands.  Everything below was settled by signing a real pass and opening it,
because three of the format's apparent levers cost more than they gave, and no
drawing predicted any of it:

* `strip.png` puts a band across the top -- and makes Wallet render the event
  title in **white** rather than in `foregroundColor`, because it assumes the
  strip behind it is dark.  On parchment that is a title nobody can read.
* `thumbnail.png` renders the emblem beside the title -- and takes its width
  from the second column, until the date and the venue touch.
* `footer.png` is silently ignored on an event ticket.

**The images ship with the plugin.**  Core takes `logo.png` and `icon.png`
from `WALLET_LOGO_URL`, one URL for the whole instance, pointing at whichever
mark was chosen for Indico's blue -- on a parchment pass a white lockup arrives
invisible, in a way no code here could detect.  `scripts/build-wallet-artwork.py`
renders the emblem for both and `images()` reads them off disk.  They are
attached through `Pass._files`, where `IndicoPass.add_file_from_url` also puts
them, rather than through that method: it fetches over HTTP, so a pass would
cost a round trip from Indico to itself per image, and when a fetch fails it
substitutes **Indico's logo**, which is worse than no image.  `_files` is a
private attribute of a third-party library, so it is touched defensively: no
dict, no images, and a pass that keeps its colours.
"""

from pathlib import Path

from indico_stsa.constants import FORMOSA, INK, PARCHMENT


#: Where `scripts/build-wallet-artwork.py` writes what it renders.
IMAGE_ROOT = Path(__file__).parent / 'static' / 'wallet' / 'pass'

#: The names Apple looks for, at the densities it may ask for.  A pass with a
#: missing density simply uses one it has, so a partial set is safe.
IMAGE_NAMES = tuple(
    f'{name}{"" if density == 1 else f"@{density}x"}.png'
    for name in ('logo', 'icon')
    for density in (1, 2, 3)
)


#: What Apple calls the three colours of a pass.
#:
#: `backgroundColor` is the field; `foregroundColor` is the values printed on
#: it; `labelColor` is the small caption above each value.  Indico sets all
#: three, so all three are replaced -- setting only the background would leave
#: white labels chosen against a blue that is no longer there.
PASS_COLORS = {
    #: Warm off-white, not the ticket's navy and not pure white either.  A pass
    #: sits in a stack of boarding cards and loyalty cards, most of them dark,
    #: so a light one is the one you can find; and paper is what a ticket is,
    #: which system white is not.
    'backgroundColor': PARCHMENT,
    #: Ink, not red.  Apple gives a pass three colours and not one per field, so
    #: red on the values means red on *every* value -- the venue, the date, the
    #: address, all of it shouting equally.  Read side by side against a signed
    #: pass, the quiet version is the one that looks like a ticket somebody
    #: designed.
    'foregroundColor': INK,
    #: The red lives here instead.  A label is small, repeated and read past, so
    #: it can carry the association's colour without any of it competing with
    #: what the member actually came to read.
    'labelColor': FORMOSA,
}

#: The line Apple prints beside the logo at the top of the pass.
#:
#: Empty.  Core fills it from the `O` field of the Pass Type ID certificate --
#: whatever the Apple Developer account is registered as, a legal name and not
#: one anybody at a door would recognise.  The header row is the emblem on the
#: left and the ticket number on the right, and nothing between them; `'STSA'`
#: beside the emblem is the one-word change if that ever reads as too bare.
PASS_LOGO_TEXT = ''


#: The line under the barcode.
#:
#: Wallet has exactly one text slot there and it is the barcode's `altText`,
#: meant for the code in readable form so a broken scanner is not a dead end.
#: Indico leaves it empty, and an STSA check-in code is a UUID nobody would read
#: out — so the space goes to the one instruction a ticket needs instead.
PASS_BARCODE_CAPTION = 'Show at check-in'

#: Indico's key for the ticket number, which core puts on the back.  It is
#: brought forward into the header -- see `PASS_HEADER_LABEL`.
PASS_TICKET_NUMBER_FIELD = 'back-ticket-number'

#: What each of Indico's fields is called on an STSA pass.
#:
#: English only, and that is a typographic decision rather than a linguistic
#: one.  Wallet sets every label at one small size, and a bilingual label puts
#: Chinese beside Latin at that size -- two type colours and two rhythms, in a
#: caption meant to be read past.  The pass looks like one thing when the
#: labels do.  A member's own name still arrives in whatever script it is
#: written in, which is data rather than decoration.
#:
#: Keys are Indico's, from `AppleWalletManager.build_ticket_object`; a key that
#: is not here keeps the label core gave it.
PASS_FIELD_LABELS = {
    'event-title': 'Event',
    'event-date': 'Date',
    'event-venue': 'Venue',
    'registration-name': 'Attendee',
    PASS_TICKET_NUMBER_FIELD: 'Ticket',
}

#: What goes top right, beside the logo.
#:
#: The most valuable slot on the pass, and the one core leaves empty: header
#: fields are what Wallet shows while passes are **stacked**, so this is the
#: only line a member sees without opening anything.  The ticket number is
#: what belongs there -- short, unique, and what a door asks for.
PASS_HEADER_LABEL = 'Ticket'

#: Fields taken off the front of the pass.
#:
#: An e-mail address is not something a ticket needs to show, and a pass is
#: readable from a locked phone -- so it sits where core also puts it, on the
#: back, behind a tap.  Nothing is lost and a row of the front is given back.
PASS_HIDDEN_FIELDS = frozenset({'registration-email'})

#: Apple's own constant.  Spelled out rather than imported from `wallet.models`
#: so this module keeps to the plugin's own names and stays importable without
#: the library -- which is what lets it be tested without one.
ALIGN_RIGHT = 'PKTextAlignmentRight'


def refined(ticket):
    """Relabel and tidy the fields core built, in place.

    None of it is something a colour can do: the labels become ours, the e-mail
    leaves the front, the ticket number comes forward into the header, and the
    second column is right-aligned so the two columns have an edge each instead
    of both ragging right.
    """
    front = (ticket.primaryFields, ticket.secondaryFields, ticket.auxiliaryFields)

    for fields in front:
        fields[:] = [field for field in fields if field.key not in PASS_HIDDEN_FIELDS]

    for fields in (*front, ticket.backFields):
        for field in fields:
            if label := PASS_FIELD_LABELS.get(field.key):
                field.label = label

    # The header, and only the header.  The number sat in the holder's row too
    # for a while, to fill the half-row beside the name; signed and looked at,
    # the same number twice on one small card read worse than the gap.
    number = next((field for field in ticket.backFields
                   if field.key == PASS_TICKET_NUMBER_FIELD), None)
    if number is not None and not ticket.headerFields:
        ticket.headerFields.append(
            type(number)(f'header-{number.key}', number.value, PASS_HEADER_LABEL))

    # Two per row on a pass this width; the trailing one gets the right edge.
    for fields in (ticket.secondaryFields, ticket.auxiliaryFields):
        if len(fields) > 1:
            fields[-1].textAlignment = ALIGN_RIGHT

    return ticket


def images():
    """The artwork to attach, as `{filename: bytes}`.

    Missing files are skipped rather than raised on: a pass with the right
    colours and Indico's logo is a working ticket, and a wheel built before the
    artwork script was run should not stop one being issued.
    """
    found = {}
    for name in IMAGE_NAMES:
        path = IMAGE_ROOT / name
        if path.is_file():
            found[name] = path.read_bytes()
    return found


def styled(pass_object):
    """Repaint `pass_object` in STSA's colours, in place.

    Takes the `Pass` from `wallet.models` and returns it, so a caller can read
    as one line.  Deliberately tolerant of an object that does not have every
    attribute: the `wallet` library is a third-party dependency of Indico's, not
    ours, and a pass that keeps Indico's blue is a far better outcome than a
    ticket download that fails.
    """
    for name, value in PASS_COLORS.items():
        setattr(pass_object, name, value)
    pass_object.logoText = PASS_LOGO_TEXT

    # Core builds the barcode before this signal fires, so there is one to
    # caption; a pass without one is left alone rather than given a barcode.
    barcode = getattr(pass_object, 'barcode', None)
    if barcode is not None:
        barcode.altText = PASS_BARCODE_CAPTION

    files = getattr(pass_object, '_files', None)
    if isinstance(files, dict):
        files.update(images())
    return pass_object
