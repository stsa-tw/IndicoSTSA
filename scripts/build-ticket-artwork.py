#!/usr/bin/env python
"""Compose the STSA ticket's background layer from the association's logos.

Indico's designer canvas can position text and images and nothing else -- there
is no line or rectangle primitive -- so every band, rule and hairline on the
ticket has to arrive as part of one background image.  This draws that image
from the marks in `indico_stsa/static/brand/` and writes it next to them.

Run it after changing the layout in `indico_stsa/ticket.py`, or after replacing
a logo:

    python scripts/build-ticket-artwork.py

The geometry here and the item coordinates in `ticket.py` are two halves of one
design: a rule drawn at y=566 here sits under text placed at y=596 there. Move
one, move the other.
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / 'indico_stsa' / 'static' / 'brand'
OUT = ROOT / 'indico_stsa' / 'static' / 'ticket' / 'background.png'

# Kept in step with indico_stsa/ticket.py by hand; see the module docstring.
WIDTH, HEIGHT = 1050, 1210
SCALE = 2                       # drawn at 2x so it holds up in print

STRAIT = '#2F5478'
FORMOSA = '#8A2424'
MIST = '#EDF0F4'
PAPER = '#FFFFFF'
STRAIT_PALE = '#9DB4CC'


def _rect(draw, x, y, w, h, color):
    draw.rectangle([x * SCALE, y * SCALE, (x + w) * SCALE - 1, (y + h) * SCALE - 1], fill=color)


def _logo(im, path, x, y, width):
    from PIL import Image
    art = Image.open(path).convert('RGBA')
    height = round(art.height * (width * SCALE) / art.width)
    art = art.resize((width * SCALE, height), Image.LANCZOS)
    im.paste(art, (x * SCALE, y * SCALE), art)


def _perforation(draw, y, color=STRAIT_PALE):
    """The tear line.  A dashed rule, edge to edge."""
    dash, gap, x = 14, 10, 24
    while x < WIDTH - 24:
        draw.line([(x * SCALE, y * SCALE), (min(x + dash, WIDTH - 24) * SCALE, y * SCALE)],
                  fill=color, width=max(2, SCALE))
        x += dash + gap


def main():
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit('this needs Pillow:\n    pip install Pillow')

    for name in ('logo-white.png', 'emblem.png'):
        if not (BRAND / name).is_file():
            sys.exit(f'missing brand asset: {BRAND / name}')

    im = Image.new('RGB', (WIDTH * SCALE, HEIGHT * SCALE), PAPER)
    draw = ImageDraw.Draw(im)

    # the navy field, with the wordmark reversed out of it
    _rect(draw, 0, 0, WIDTH, 150, STRAIT)
    _logo(im, BRAND / 'logo-white.png', 60, 52, 400)

    # the hairline above the when/where pair
    _rect(draw, 60, 566, 930, 2, MIST)

    # the tear line
    _perforation(draw, 716)

    # the footer: a rule, the emblem on its own, and the oxblood underline.
    # The bear-and-merlion mark in colour rather than the wordmark: the navy
    # field at the top already spells the name out, and repeating it here would
    # be the same words twice on one page.
    _rect(draw, 60, 1078, 930, 2, MIST)
    _logo(im, BRAND / 'emblem.png', 60, 1092, 80)
    _rect(draw, 60, 1186, 930, 5, FORMOSA)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT, optimize=True)
    print(f'wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size // 1024} KB, {im.width}x{im.height})')


if __name__ == '__main__':
    main()
