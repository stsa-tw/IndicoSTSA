"""Check that a built wheel carries everything the plugin needs -- and nothing it may not.

A wheel missing its assets, templates or migrations installs cleanly and then
fails on the first request that touches them, which is a much worse way to find
out.  The asset check is the one that matters most: `static/dist/manifest.json`
is what `IndicoPlugin.inject_bundle` looks `main.js` and `main.css` up in, and
without it Indico raises `Assets for plugin stsa have not been built` on every
registration page in the instance.

The last check runs the other way round.  Apple's "Add to Apple Wallet" artwork
is licensed to whoever downloaded it, under a non-transferable licence covering
only their own passes, so it must never leave a maintainer's machine inside a
package.  It is gitignored and excluded in `pyproject.toml`; this is the gate
that stops a release if both of those are ever undone.
"""

import json
import sys
import zipfile
from pathlib import Path


PKG = 'indico_stsa'

REQUIRED_FILES = [
    f'{PKG}/templates/settings.html',
    f'{PKG}/templates/overview.html',
    f'{PKG}/templates/_regform_settings.html',
    f'{PKG}/templates/_missing_tables.html',
    f'{PKG}/static/dist/manifest.json',
    # Google's button artwork is redistributable and the plugin is useless
    # without at least the fallback locale.
    f'{PKG}/static/wallet/google/enGB.svg',
    f'{PKG}/static/wallet/google/enGB.png',
    # The instructions for the artwork that is *not* here.
    f'{PKG}/static/wallet/apple/README.md',
    # The ticket: its furniture layer and the marks it is built from.
    f'{PKG}/static/ticket/background.png',
    f'{PKG}/static/brand/logo-white.png',
    f'{PKG}/static/brand/emblem.png',
    # Without this a ticket whose title has an emoji prints a crossed box.
    f'{PKG}/static/fonts/NotoEmoji.ttf',
    f'{PKG}/static/fonts/OFL.txt',
]

# Filenames here carry a date or a content hash, so match on directory and
# extension rather than on a name that changes every build.
REQUIRED_PATTERNS = [
    (f'{PKG}/migrations/', '.py'),
    (f'{PKG}/static/dist/', '.js'),
    (f'{PKG}/static/dist/', '.css'),
]

# The exact keys `plugin.py` passes to `inject_bundle`.
REQUIRED_BUNDLES = ['main.js', 'main.css']

# Nothing matching these may be in the wheel.  See the module docstring.
FORBIDDEN_PATTERNS = [
    (f'{PKG}/static/wallet/apple/', '.svg'),
    (f'{PKG}/static/wallet/apple/', '.png'),
]


def main(dist_dir):
    wheel = next(Path(dist_dir).glob('*.whl'), None)
    if wheel is None:
        sys.exit(f'no wheel in {dist_dir}')

    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        problems = [f'missing {name}' for name in REQUIRED_FILES if name not in names]
        for prefix, suffix in REQUIRED_PATTERNS:
            if not any(n.startswith(prefix) and n.endswith(suffix) for n in names):
                problems.append(f'missing {prefix}*{suffix}')

        for prefix, suffix in FORBIDDEN_PATTERNS:
            found = sorted(n for n in names if n.startswith(prefix) and n.endswith(suffix))
            if found:
                problems.append("Apple's badge artwork is not redistributable and must not be packaged: "
                                + ', '.join(found))

        if f'{PKG}/static/dist/manifest.json' in names:
            manifest = json.loads(zf.read(f'{PKG}/static/dist/manifest.json'))
            problems += [f'manifest.json has no {bundle!r} entry'
                         for bundle in REQUIRED_BUNDLES if bundle not in manifest]

    if problems:
        sys.exit('{}:\n  {}'.format(wheel.name, '\n  '.join(problems)))
    print(f'{wheel.name} looks good')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'dist')
