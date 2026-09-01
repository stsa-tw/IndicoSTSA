"""The STSA ticket: 「門票」, a tear-off stub.

Two layers.  The **furniture** -- the navy field, the rules, the perforation
and the STSA marks -- is one background PNG built ahead of time by
`scripts/build-ticket-artwork.py`, because Indico's designer canvas has no line
or rectangle primitive: it can position text and images, and nothing else.  The
**items** below are the text and the QR code, which is all that changes from
one registration to the next.

Coordinates are the designer's pixels, where 50px is 1cm, measured from the
top-left.  A4 is 1050 wide; the ticket is 1210 tall, leaving the rest of the
sheet blank to cut or fold away.
"""

from indico_stsa import _


#: Sampled from the STSA emblem: the merlion half and the bear half.
STRAIT = '#2F5478'
FORMOSA = '#8A2424'
INK = '#1C2733'
GRAPHITE = '#6B7683'
PAPER = '#FFFFFF'
STRAIT_PALE = '#9DB4CC'

WIDTH = 1050
HEIGHT = 1210

SERIF, SANS, MONO = 'serif', 'sans-serif', 'courier'

#: The title Indico shows the template under, and how we find it again to
#: refresh it rather than installing a second copy.
TEMPLATE_TITLE = 'STSA 門票 / Ticket'


def _txt(x, y, w, type_, *, text='', size=14, font=SANS, color=INK, align='left'):
    """A positioned text item.

    `wrap`, never `resize`: the resize path measures the string with the font
    core picked *before* `indico_stsa.fonts` swaps in the CJK face, so it
    mis-measures every Chinese glyph and shrinks text that would have fitted.
    """
    return {'x': x, 'y': y, 'width': w, 'height': None, 'type': type_, 'text': text,
            'font_size': f'{size}pt', 'font_family': font, 'color': color, 'text_align': align,
            'bold': False, 'italic': False, 'background_color': None, 'selected': False,
            'text_overflow': 'wrap'}


def _qr(x, y, size):
    return {'x': x, 'y': y, 'width': size, 'height': size, 'type': 'ticket_qr_code', 'text': '',
            'font_size': '14pt', 'font_family': SANS, 'color': INK, 'text_align': 'center',
            'bold': False, 'italic': False, 'selected': False, 'preserve_aspect_ratio': True}


def build_items():
    """The ticket's items, in drawing order."""
    items = [
        # -- the navy field ---------------------------------------------------
        _txt(600, 62, 390, 'fixed', text='ADMIT ONE', size=13, font=MONO,
             color=STRAIT_PALE, align='right'),
        _txt(600, 92, 390, 'event_dates', size=15, color=PAPER, align='right'),

        # -- the event, with room for the two lines a bilingual title needs ---
        _txt(60, 208, 930, 'event_title', size=30, font=SERIF, color=INK),

        # -- the holder, who is what the ticket is actually about -------------
        _txt(60, 384, 930, 'fixed', text=str(_('持票人  ATTENDEE')), size=11, font=MONO, color=GRAPHITE),
        _txt(60, 414, 930, 'full_name_b', size=44, font=SERIF, color=INK),
        _txt(60, 494, 930, 'affiliation', size=16, color=GRAPHITE),

        _txt(60, 596, 440, 'fixed', text=str(_('日期時間  WHEN')), size=11, font=MONO, color=GRAPHITE),
        _txt(60, 624, 440, 'event_dates', size=16, color=INK),
        _txt(540, 596, 450, 'fixed', text=str(_('地點  WHERE')), size=11, font=MONO, color=GRAPHITE),
        _txt(540, 624, 450, 'event_venue', size=16, color=INK),

        # -- the stub, below the perforation ----------------------------------
        #
        # It repeats the holder and the event on purpose: a stub torn off at
        # the door and kept in a box still has to say whose it was.
        #
        # The QR is deliberately the largest thing down here.  It is what a
        # phone has to read across a crowded doorway, so it gets the space
        # rather than the text beside it.
        _qr(60, 752, 290),
        _txt(392, 768, 600, 'fixed', text=str(_('入場憑證  ENTRY PASS')), size=11, font=MONO, color=GRAPHITE),
        _txt(392, 798, 600, 'full_name_b', size=27, font=SERIF, color=INK),
        _txt(392, 854, 600, 'event_title', size=13, color=GRAPHITE),
        _txt(392, 924, 60, 'fixed', text='NO.', size=11, font=MONO, color=GRAPHITE),
        _txt(450, 914, 300, 'registration_friendly_id', size=24, font=MONO, color=FORMOSA),
        _txt(392, 986, 600, 'fixed', text=str(_('請於入場時出示此 QR code')), size=12, color=GRAPHITE),
        _txt(392, 1012, 600, 'fixed', text=str(_('Show this QR code at the door')), size=12, color=GRAPHITE),

        # -- the footer, where the association signs it off --------------------
        _txt(400, 1126, 590, 'fixed', text=str(_('此票僅限本人使用  ·  Admits the named holder only')),
             size=11, color=GRAPHITE, align='right'),
    ]
    for i, item in enumerate(items, 1):
        item['id'] = i
    return items


def build_data():
    """The complete `DesignerTemplate.data` for the ticket."""
    return {'items': build_items(), 'width': WIDTH, 'height': HEIGHT,
            'background_position': 'stretch'}
