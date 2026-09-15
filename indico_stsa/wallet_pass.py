"""The Apple Wallet pass, drawn in Xcode's Pass Designer rather than in Python.

Indico builds a perfectly good pass and paints it `#007cac`, its own blue,
hardcoded in `AppleWalletManager.build_pass_object`.  That is the right default
for an instance that has never been told what it looks like, and the wrong one
for an association with marks of its own.

This module says what the pass should look like, and nothing else.  It takes no
Indico import and touches no database, which is what lets every decision here
be tested without an instance; `plugin.py` holds the handler that reads a
registration and applies it.

**The design is not in this file.**  It is `EventTicket.pkpasstemplate/`, an Xcode
Pass Designer bundle -- `pass.json`, the artwork, and the `.lproj` strings --
which is the thing somebody opens and edits.  Everything below starts from that
`pass.json` and substitutes only what belongs to one registration: the field
values, the barcode, the dates, and the identity keys that have to match the
certificate.  Labels, colours, the style key and the static copy are quoted, so
changing them is a Pass Designer job and not a commit here.

**Why the whole of pass.json is replaced, rather than a few attributes set.**
Indico builds passes with `wallet-py3k`, whose `Pass.json_dict()` is a fixed
whitelist: it emits only the keys it was written to know about.  Setting an
attribute it does not know is silently dropped, which rules out `semantics`,
`sharingProhibited`, `useAutomaticColors`, the plural `barcodes` -- and the
style key, which is always `eventTicket` because that is the class Indico
instantiates.  So the pass object is handed a `json_dict` of our own;
`Pass._createPassJson` calls it through `PassHandler`, and what it returns *is*
pass.json.

**The style key is `posterGeneric`, and it is read rather than assumed.**  The
poster *event ticket* scheme is limited to NFC-enabled passes, which wants an
entitlement Apple issues case by case.  A poster *generic* pass does not.
Switching the style in Pass Designer renames that key, so hard-coding it here
would quietly undo the thing that keeps this pass issuable.  For the same
reason `preferredStyleSchemes` is stripped: Pass Designer writes
`posterEventTicket` back into the template on every save, and shipping it would
ask for the entitlement-gated scheme again.

**One field per bucket is all the face draws.**  Settled by signing real
passes and looking at them, because none of it is documented and no amount of
reading predicted it: `posterGeneric` renders `headerFields[0]`,
`primaryFields[0]` and `footerFields[0]` -- the *first* entry of each, and
nothing after it.  A second entry in a bucket is a field nobody will ever see.

* `secondaryFields` and `auxiliaryFields` are **not drawn at all**.  The holder
  sat in `secondaryFields` for a while and simply never appeared on a ticket.
* `backFields` is the exception and draws all of them, so anything that does
  not fit the three face slots belongs there.
* That leaves the face with exactly three lines of text plus the barcode's
  `altText`, and the template spends them on when, what, and who.

Date and time therefore share one field rather than taking two: `dateStyle`
and `timeStyle` on a single entry get both onto the one line the header draws.

**The images ship with the template.**  Core takes `logo.png` and `icon.png`
from `WALLET_LOGO_URL`, one URL for the whole instance, and fetches them over
HTTP -- a round trip from Indico to itself per image, substituting *Indico's*
logo when a fetch fails, which is worse than no image.  These are read off disk
instead and attached through `Pass._files`, a private attribute of a
third-party library, so it is touched defensively: no dict, no images, and a
pass that still carries its design.
"""

# PEP 604 annotations on the dataclass below, evaluated lazily so this module
# imports on the Python that ships with macOS as well as on the 3.12 the plugin
# targets.  `scripts/_bootstrap.py` exists so these modules run on a laptop with
# no Indico; running on a laptop with no pyenv is the same promise.
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path


#: The Pass Designer bundle, shipped whole and under its own extension -- so the
#: thing the plugin reads is the same folder somebody double-clicks to edit.
TEMPLATE_ROOT = Path(__file__).parent / 'EventTicket.pkpasstemplate'

#: Pass Designer's own bookkeeping, which no issued pass should carry.
DESIGNER_KEYS = ('_id',)

#: Wallet still looks for the unscaled name on older systems, and a pass without
#: an icon is invalid; the 2x art stands in when the template ships no 1x.
ICON_FALLBACK = 'icon@2x.png'

#: Asking for this would want an NFC entitlement -- see the module docstring.
STRIPPED_KEYS = ('preferredStyleSchemes',)

#: Apple's own constant, spelled out rather than imported from `wallet.models`,
#: so this module stays importable -- and testable -- without the library.
BARCODE_QR = 'PKBarcodeFormatQR'

#: The label over the event title, keyed by Indico's event type.
#:
#: Design rather than glue, so it lives here: these strings are the keys the
#: template's `.lproj` files translate, and they mirror `IndicoEvent.kicker` in
#: the member app, so a member reads the same word on the pass and on the app's
#: ticket screen.
PASS_KICKERS = {'conference': '活動', 'meeting': '聚會', 'lecture': '講座'}

#: What an event of an unrecognised type is called.
PASS_KICKER_DEFAULT = '活動'


@dataclass(frozen=True)
class PassTicket:
    """One registration, flattened to the strings the pass needs.

    A dataclass rather than the `Registration` itself, because everything in
    this module is then testable without an Indico: `plugin.py` is the only
    place that knows what a registration looks like.
    """

    title: str
    kicker: str                 # 活動 / 聚會 / 講座 -- the label over the title
    start: str                  # ISO 8601 with offset
    end: str
    venue: str | None           # `location · room`
    venue_name: str | None
    room_name: str | None
    address: str | None
    event_url: str | None
    holder: str
    friendly_id: str
    qr_message: str


def template():
    """The design, as Pass Designer last saved it."""
    return json.loads((TEMPLATE_ROOT / 'pass.json').read_text('utf-8'))


def style_key(design):
    """Whichever style the designer wrote -- `posterGeneric`, `eventTicket`, ...

    Found by shape rather than by name: the one top-level object holding
    `*Fields` lists is the style, whatever Apple calls it this year.
    """
    for key, value in design.items():
        if isinstance(value, dict) and any(k.endswith('Fields') for k in value):
            return key
    raise ValueError(f'{TEMPLATE_ROOT.name}/pass.json has no pass style key')


def _values(ticket):
    """What each template field becomes for this registration.

    A key absent from here keeps whatever the template says -- which is how the
    static copy (主辦, 注意事項) stays editable in Pass Designer instead of being
    buried in Python.  A value resolving to `None` drops the field, so an event
    with no venue ships no empty row.
    """
    return {
        'time': {'value': ticket.start},
        'event': {'value': ticket.title, 'label': ticket.kicker},
        'date': {'value': ticket.start},
        'holder': {'value': ticket.holder},
        'venue': {'value': ticket.venue},
        'registration': {'value': f'#{ticket.friendly_id}'},
        'ends': {'value': ticket.end},
        'address': {'value': ticket.address},
        'eventPage': {'value': ticket.event_url},
    }


def pass_json(ticket, identity, design=None):
    """The template verbatim, with everything registration-specific substituted.

    `identity` carries the keys Wallet checks against the signature, which Indico
    reads off the certificate's subject -- they win over whatever placeholder the
    template was saved with.
    """
    design = template() if design is None else design
    out = copy.deepcopy(design)
    style = style_key(design)
    values = _values(ticket)

    buckets = {}
    for bucket, fields in design[style].items():
        filled = []
        for field in fields:
            field = {k: v for k, v in copy.deepcopy(field).items() if k not in DESIGNER_KEYS}
            field.update(values.get(field.get('key'), {}))
            if field.get('value') in (None, ''):
                continue
            filled.append(field)
        if filled:
            buckets[bucket] = filled
    out[style] = buckets

    out.update(identity)
    for key in STRIPPED_KEYS:
        out.pop(key, None)

    out['barcodes'] = [{
        'format': BARCODE_QR,
        'message': ticket.qr_message,
        'messageEncoding': 'iso-8859-1',
        # Wallet prints this under the code, for a door that has to look
        # somebody up by hand when the scanner will not read.
        'altText': f'#{ticket.friendly_id}',
    }]
    out.pop('barcode', None)

    out['relevantDate'] = ticket.start

    semantics = dict(out.get('semantics') or {})
    semantics.update({
        'eventName': ticket.title,
        'eventStartDate': ticket.start,
        'eventEndDate': ticket.end,
    })
    for key, value in (('venueName', ticket.venue_name), ('venueRoom', ticket.room_name)):
        if value:
            semantics[key] = value
        else:
            semantics.pop(key, None)
    # The template's coordinates are its sample event's.  Indico holds no
    # latitude or longitude for an event, and a pass claiming every event
    # happens at one park would wake on the Lock Screen in the wrong place.
    semantics.pop('venueLocation', None)
    out.pop('locations', None)
    # Pass Designer leaves empty collections behind for slots it offers and the
    # design does not use.  An empty semantic tag says nothing, so it is not
    # shipped -- `seats: []` is the one it otherwise warns about.
    out['semantics'] = {k: v for k, v in semantics.items() if v not in (None, '', [], {})}

    # No expirationDate and no voided, deliberately.  `RHTicketDownload`'s four
    # access checks say nothing about the date, so a ticket outlives its event
    # and one already attended is a record worth keeping.
    return out


def images():
    """The artwork to attach, as `{filename: bytes}`.

    Missing files are skipped rather than raised on: a pass with the right
    fields and Indico's logo is a working ticket, and an incomplete template
    should not stop one being issued.
    """
    if not TEMPLATE_ROOT.is_dir():
        return {}
    found = {}
    for path in sorted(TEMPLATE_ROOT.iterdir()):
        if path.name.startswith('.') or path.name == 'pass.json':
            continue
        if path.is_dir():                                   # *.lproj
            for child in sorted(path.iterdir()):
                found[f'{path.name}/{child.name}'] = child.read_bytes()
        elif path.suffix == '.png':
            found[path.name] = path.read_bytes()
    if ICON_FALLBACK in found:
        found.setdefault('icon.png', found[ICON_FALLBACK])
    return found


def styled(pass_object, ticket):
    """Redraw `pass_object` from the template, in place, and return it.

    Deliberately tolerant of an object that does not have every attribute: the
    `wallet` library is a third-party dependency of Indico's rather than ours,
    and a pass that keeps Indico's blue is a far better outcome than a ticket
    download that fails.
    """
    identity = {
        'passTypeIdentifier': getattr(pass_object, 'passTypeIdentifier', ''),
        'teamIdentifier': getattr(pass_object, 'teamIdentifier', ''),
        'serialNumber': getattr(pass_object, 'serialNumber', ''),
        'formatVersion': 1,
    }
    built = pass_json(ticket, identity)

    files = getattr(pass_object, '_files', None)
    if isinstance(files, dict):
        files.clear()
        files.update(images())

    # An instance attribute wins over the class's, and a plain closure needs no
    # `self`.  `PassHandler` calls it if it exists, so this *is* pass.json.
    pass_object.json_dict = lambda: built
    return pass_object
