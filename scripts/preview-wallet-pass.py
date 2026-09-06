#!/usr/bin/env python
"""Draw what the Apple Wallet pass will look like, before issuing one.

This renders the front of the pass from the same constants the plugin paints
it with, so the picture cannot drift from what ships: change
`indico_stsa/constants.py` or `wallet_pass.py` and run this again.  It needs
nothing but Pillow, which is what it is for -- the real thing needs the signing
certificate, and `sign-preview-pass.py` is the script for anybody who has it.

    python scripts/preview-wallet-pass.py [--out preview.png] [--title "..."]

**It is a mock-up, not a pass.**  Wallet refuses an unsigned pass -- on a
device and in the Simulator alike -- so nothing here can render what iOS will,
and Apple does not publish the metrics it lays fields out by.  This answers "do
these colours work", not "where exactly will that word sit".  What is faithful:
the palette, the images, the labels, the caption and the field order, all read
from the plugin rather than redrawn here.  What is not: type, spacing, and how
a long value gets truncated.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap

ROOT = _bootstrap.ROOT

from indico_stsa.constants import FORMOSA, INK, PAPER, PARCHMENT
from indico_stsa.wallet_pass import (IMAGE_ROOT, PASS_BARCODE_CAPTION, PASS_FIELD_LABELS,
                                    PASS_HEADER_LABEL, PASS_LOGO_TEXT)


#: Apple's pass is 3:4-ish on screen; this is a comfortable render of the front.
WIDTH, HEIGHT = 640, 570
SCALE = 2
MARGIN = 28
RADIUS = 36

#: Fonts that can draw both Latin and Chinese, most preferred first.  A preview
#: is worth having even where none of them exist, so a miss falls back to
#: Pillow's built-in bitmap face rather than failing.
FONT_CANDIDATES = [
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Medium.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]


def font(size, *, bold=False):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size * SCALE, index=1 if bold else 0)
            except OSError:
                continue
    return ImageFont.load_default()


def tracked(draw, xy, text, *, face, fill, tracking=1.6):
    """Draw `text` letter by letter, which is the only way Pillow tracks type.

    Apple sets pass labels in caps with a little tracking; without it they read
    as shouting rather than as captions.
    """
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=face, fill=fill)
        x += draw.textlength(char, font=face) + tracking * SCALE


def field(draw, x, y, label, value, *, value_size=17):
    """One label/value pair, laid out the way Apple stacks them."""
    tracked(draw, (x * SCALE, y * SCALE), label, face=font(10), fill=FORMOSA)
    draw.text((x * SCALE, (y + 15) * SCALE), value, font=font(value_size, bold=True), fill=INK)
    return y + 15 + value_size + 12


def render(title, date, venue, name, ticket_number):
    image = Image.new('RGB', (WIDTH * SCALE, HEIGHT * SCALE), '#0B0B0C')
    draw = ImageDraw.Draw(image)

    # The pass itself, inset so the rounded corner is visible against a screen.
    card = [MARGIN * SCALE, MARGIN * SCALE, (WIDTH - MARGIN) * SCALE, (HEIGHT - MARGIN) * SCALE]
    draw.rounded_rectangle(card, radius=RADIUS * SCALE, fill=PARCHMENT)

    x = MARGIN + 26
    y = MARGIN + 26

    # The very files the pass carries, so the preview cannot flatter it.
    logo = IMAGE_ROOT / 'logo@3x.png'
    if logo.exists():
        mark = Image.open(logo).convert('RGBA')
        # Apple caps the logo at 160x50pt.  The card here is wider than a real
        # pass, so the box is scaled by the same ratio rather than to a height
        # that happens to look right -- a preview that draws the mark larger
        # than Wallet will is worse than no preview.
        height = int(50 * (WIDTH - 2 * MARGIN) / 375) * SCALE
        mark = mark.resize((int(mark.width * height / mark.height), height))
        image.paste(mark, (x * SCALE, y * SCALE), mark)
        after = x + mark.width // SCALE + 12
        header_bottom = y + mark.height // SCALE
    else:
        after = x
        header_bottom = y + 24

    # Empty by default; drawn anyway so that somebody who sets it can see what
    # it does to the header row.
    if PASS_LOGO_TEXT:
        draw.text((after * SCALE, (y + 7) * SCALE), PASS_LOGO_TEXT, font=font(15, bold=True), fill=FORMOSA)

    # The header field, top right, which is what Wallet shows in a stack.
    tracked(draw, ((WIDTH - MARGIN - 120) * SCALE, (MARGIN + 26) * SCALE),
            PASS_HEADER_LABEL.upper(), face=font(10), fill=FORMOSA)
    draw.text(((WIDTH - MARGIN - 120) * SCALE, (MARGIN + 41) * SCALE),
              ticket_number, font=font(20, bold=True), fill=INK)

    y = header_bottom + 26
    y = field(draw, x, y, PASS_FIELD_LABELS['event-title'], title, value_size=24)

    y += 20
    field(draw, x, y, PASS_FIELD_LABELS['event-date'], date)
    field(draw, x + 250, y, PASS_FIELD_LABELS['event-venue'], venue)
    y += 56

    field(draw, x, y, PASS_FIELD_LABELS['registration-name'], name)
    y += 56

    barcode(draw, y)
    return image.resize((WIDTH, HEIGHT), Image.LANCZOS)


def barcode(draw, y):
    """The QR, on its own white panel and centred, the way Wallet draws it.

    The modules are a fixed pattern, not an encoding of anything: this is a
    picture of where the barcode goes, and a preview that scanned would only
    invite somebody to scan it.
    """
    size = 150
    left = (WIDTH - size) // 2

    panel = [(left - 14) * SCALE, (y - 14) * SCALE,
             (left + size + 14) * SCALE, (y + size + 36) * SCALE]
    draw.rounded_rectangle(panel, radius=10 * SCALE, fill=PAPER)

    modules = 25
    step = size / modules
    ink = '#1C1C1E'

    def cell(row, col):
        cx, cy = (left + col * step) * SCALE, (y + row * step) * SCALE
        draw.rectangle([cx, cy, cx + step * SCALE, cy + step * SCALE], fill=ink)

    # The three finders, drawn as the concentric squares they actually are: a
    # 7x7 ring and a 3x3 centre. Deriving them from a modulo, as an earlier
    # pass here did, produced shapes no scanner has ever seen.
    finders = ((0, 0), (0, modules - 7), (modules - 7, 0))
    for top, leftmost in finders:
        for row in range(7):
            for col in range(7):
                edge = min(row, col, 6 - row, 6 - col)
                if edge == 0 or edge >= 2:
                    cell(top + row, leftmost + col)

    def inside_finder(row, col):
        return any(top <= row < top + 8 and leftmost <= col < leftmost + 8 for top, leftmost in finders)

    for row in range(modules):
        for col in range(modules):
            if not inside_finder(row, col) and ((row * 7 + col * 11 + (row * col) % 5) % 3) == 0:
                cell(row, col)

    # Wallet prints this from the barcode's `altText`, which the plugin sets --
    # so unlike an earlier version of this drawing, the line is really there.
    caption = PASS_BARCODE_CAPTION
    face = font(11)
    width = draw.textlength(caption, font=face)
    draw.text(((WIDTH * SCALE - width) / 2, (y + size + 12) * SCALE),
              caption, font=face, fill=INK)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # `preview/` is gitignored and is where the ticket's own renders go.
    parser.add_argument('--out', type=Path, default=ROOT / 'preview' / 'wallet-pass.png')
    parser.add_argument('--title', default='2026 STSA Boba Chat | Back to School Edition')
    parser.add_argument('--date', default='30 Aug 2026, 13:00')
    parser.add_argument('--venue', default='Wushiland Boba')
    parser.add_argument('--name', default='楊晨諺')
    parser.add_argument('--ticket', default='#1042')
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(args.title, args.date, args.venue, args.name, args.ticket).save(args.out)
    print(f'Wrote {args.out}')
    print(f'Background {PARCHMENT}  ·  values {INK}  ·  labels {FORMOSA}  ·  logo text {PASS_LOGO_TEXT!r}')


if __name__ == '__main__':
    main()
