#!/usr/bin/env python
"""Install Apple's "Add to Apple Wallet" badges from the pack Apple gives you.

The artwork cannot ship with this plugin: Apple's Wallet Marketing Artwork
License Agreement is non-transferable and covers only the licensee's own passes,
so a public package has no right to pass it on.  Every operator downloads their
own copy instead -- a formality for anyone already issuing Apple passes, since
that needs an Apple Developer account anyway.

    1. https://developer.apple.com/wallet/add-to-apple-wallet-guidelines/
       -> "Download badge files", and accept the agreement.
    2. python scripts/install-apple-badges.py ~/Downloads/Add-to-Apple-Wallet.zip

What this does, and deliberately does not do: it copies Apple's RGB SVGs in
under their own market codes, and rasterizes a PNG of each because Apple ships
none and e-mail needs one -- Gmail and Outlook do not render SVG at all.  The
raster keeps the artwork's proportions and colours exactly; nothing is redrawn,
recoloured or restyled, which Apple's guidelines forbid.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path


TARGET = Path(__file__).resolve().parent.parent / 'indico_stsa' / 'static' / 'wallet' / 'apple'

#: Apple's pack is `Add to Apple Wallet Badges/<MARKET>/RGB/<name>.svg`, with a
#: CMYK sibling for print that is no use on a screen.
SVG_RE = re.compile(r'Add to Apple Wallet Badges/(?P<market>[^/]+)/RGB/[^/]+\.svg$')

#: Three times the 48px the badge is rendered at, so it stays sharp on a phone.
PNG_HEIGHT = 144


def rasterize(svg_path, png_path):
    try:
        import cairosvg
    except ImportError:
        sys.exit('rasterizing the PNGs needs cairosvg:\n    pip install cairosvg')
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_height=PNG_HEIGHT)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('archive', type=Path, help="Apple's Add-to-Apple-Wallet.zip")
    parser.add_argument('--markets', help='comma-separated market codes to install (default: all)')
    args = parser.parse_args()

    if not args.archive.is_file():
        sys.exit(f'no such file: {args.archive}')

    wanted = {m.strip() for m in args.markets.split(',')} if args.markets else None
    TARGET.mkdir(parents=True, exist_ok=True)

    installed = []
    with zipfile.ZipFile(args.archive) as zf:
        for name in zf.namelist():
            match = SVG_RE.search(name)
            if not match:
                continue
            market = match.group('market')
            if wanted is not None and market not in wanted:
                continue
            svg_path = TARGET / f'{market}.svg'
            svg_path.write_bytes(zf.read(name))
            rasterize(svg_path, TARGET / f'{market}.png')
            installed.append(market)

    if not installed:
        sys.exit(f'{args.archive.name} contains no Add to Apple Wallet badges -- is it the right zip?')
    print(f'installed {len(installed)} badges into {TARGET}:')
    print('  ' + ' '.join(sorted(installed)))


if __name__ == '__main__':
    main()
