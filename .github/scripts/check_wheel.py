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

It also refuses a wheel that carries Scalar's script in the public static folder.
The API reference is for administrators and serves that script through a handler
that checks; `/static/plugins/stsa/` serves everything under `static/` to anybody.
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
    # The payment reminder button renders on every registrant list, so a wheel
    # without it breaks a page nobody asked this plugin about.
    f'{PKG}/templates/_reglist_button.html',
    f'{PKG}/templates/payment_reminders.html',
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
    # The Apple Wallet pass is the Pass Designer bundle, whole: pass.json *is*
    # the design, and a wheel without it raises on the first ticket download.
    # Without the icon a pass is not valid at all; without the artwork the
    # poster layout has no face.
    f'{PKG}/EventTicket.pkpasstemplate/pass.json',
    f'{PKG}/EventTicket.pkpasstemplate/icon@2x.png',
    f'{PKG}/EventTicket.pkpasstemplate/artwork@2x.png',
    f'{PKG}/EventTicket.pkpasstemplate/primaryLogo@2x.png',
    # Wallet reads these for a member whose phone is not in English.
    f'{PKG}/EventTicket.pkpasstemplate/en.lproj/pass.strings',
    f'{PKG}/EventTicket.pkpasstemplate/zh-Hant.lproj/pass.strings',
    # Without this a ticket whose title has an emoji prints a crossed box.
    f'{PKG}/static/fonts/NotoEmoji.ttf',
    f'{PKG}/static/fonts/OFL.txt',
    # The API reference: its page, and the Scalar bundle it draws with, which is
    # vendored (see `scripts/update-scalar.py`) so that nothing is fetched from a CDN.
    f'{PKG}/templates/api_docs.html',
    f'{PKG}/vendor/scalar/standalone.js',
    f'{PKG}/vendor/scalar/scalar.json',
    f'{PKG}/vendor/scalar/LICENSE',
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

# Nothing matching these may be in the wheel, each with the reason.  See the
# module docstring.
APPLE = "Apple's badge artwork is not redistributable and must not be packaged"
PUBLIC = 'the API reference must be served by its handler, not from the public static folder'
FORBIDDEN_PATTERNS = [
    (f'{PKG}/static/wallet/apple/', '.svg', APPLE),
    (f'{PKG}/static/wallet/apple/', '.png', APPLE),
    (f'{PKG}/static/', 'standalone.js', PUBLIC),
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

        for prefix, suffix, reason in FORBIDDEN_PATTERNS:
            found = sorted(n for n in names if n.startswith(prefix) and n.endswith(suffix))
            if found:
                problems.append(f'{reason}: ' + ', '.join(found))

        if f'{PKG}/static/dist/manifest.json' in names:
            manifest = json.loads(zf.read(f'{PKG}/static/dist/manifest.json'))
            problems += [f'manifest.json has no {bundle!r} entry'
                         for bundle in REQUIRED_BUNDLES if bundle not in manifest]

    if problems:
        sys.exit('{}:\n  {}'.format(wheel.name, '\n  '.join(problems)))
    print(f'{wheel.name} looks good')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'dist')
