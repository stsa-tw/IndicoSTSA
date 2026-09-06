#!/usr/bin/env python
"""Render the images an Apple Wallet pass carries, from the association's marks.

A `.pkpass` takes three colours and a handful of images, and that is the whole
of its design surface -- there is no typeface to set and nothing to position.
These are the images:

* `logo` -- the emblem at the top of the pass, in colour.  Not the full lockup:
  Apple caps the logo at 160x50pt, and a wordmark that wide arrives as type too
  small to read, sitting low in its box because the box is wider than the mark
  is tall.  The emblem is square, so it fills the 50 points it is given and sits
  where Wallet puts it.  Core would otherwise take this from `WALLET_LOGO_URL`,
  one URL for the whole instance, pointing at the white mark the printed ticket
  uses -- which on a parchment pass arrives invisible.
* `icon` -- required for the pass to be valid at all, and what shows on the lock
  screen and in notifications.

Nothing else, deliberately.  A `strip` makes Wallet draw the event title in
white instead of in `foregroundColor` -- illegible on a light pass; a
`thumbnail` crowds the second column until the date and venue touch; a
`footer` is ignored on event tickets.  All three were tried on a signed pass;
the reasoning is with the image list in `indico_stsa/wallet_pass.py`.

Apple picks the density it wants, so each is written at 1x, 2x and 3x.

    python scripts/build-wallet-artwork.py
"""

import sys
from pathlib import Path

from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap

ROOT = _bootstrap.ROOT

BRAND = ROOT / 'indico_stsa' / 'static' / 'brand'
OUT = ROOT / 'indico_stsa' / 'static' / 'wallet' / 'pass'

#: Apple's maxima, in points, from the Wallet pass design guidance.
LOGO = (160, 50)
ICON = (29, 29)

DENSITIES = (1, 2, 3)


def write(image, name, density):
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = '' if density == 1 else f'@{density}x'
    path = OUT / f'{name}{suffix}.png'
    image.save(path)
    return path


def fit(mark, box, density, *, left=False):
    """The mark scaled to fit `box` at `density`, on a transparent canvas.

    Wallet puts the logo box where it puts it, so the only way to move the mark
    is to move it inside the image.  `left` pins it to the left edge, which is
    what lines it up with the fields underneath -- centred in a 160-point box, a
    square mark floats inward and agrees with nothing.
    """
    width, height = box[0] * density, box[1] * density
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    scale = min(width / mark.width, height / mark.height)
    resized = mark.resize((max(1, int(mark.width * scale)), max(1, int(mark.height * scale))))

    x = 0 if left else (width - resized.width) // 2
    canvas.paste(resized, (x, (height - resized.height) // 2), resized)
    return canvas


def main():
    emblem = Image.open(BRAND / 'emblem.png').convert('RGBA')

    written = []
    for density in DENSITIES:
        # Square in a 160x50 box, so it fits by height and sits as high as
        # Wallet will place it.
        written.append(write(fit(emblem, LOGO, density, left=True), 'logo', density))
        written.append(write(fit(emblem, ICON, density), 'icon', density))

    for path in written:
        print(f'Wrote {path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
