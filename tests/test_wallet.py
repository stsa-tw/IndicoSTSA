"""The locale mapping and artwork lookup for the wallet badges."""

import pytest

from indico_stsa.wallet import (APPLE_FALLBACK, APPLE_LOCALES, GOOGLE_FALLBACK, GOOGLE_LOCALES, STATIC_ROOT,
                                VENDORS, WALLET_ROOT)


#: Every vendor, with its locale map and the code a language nobody has artwork
#: for falls back to.
VENDOR_MAPS = {
    'google': (GOOGLE_LOCALES, GOOGLE_FALLBACK),
    'apple': (APPLE_LOCALES, APPLE_FALLBACK),
}

#: Both formats have to be there for every code: the SVG is used on web pages
#: and the PNG in e-mail, and a badge missing one of them silently disappears
#: from half the places it belongs.
FORMATS = ('svg', 'png')

#: Vendors whose artwork this package is allowed to ship.  Apple's is not: its
#: licence is non-transferable and covers only the licensee's own passes, so
#: each operator installs their own copy with `scripts/install-apple-badges.py`.
#: Apple's artwork is therefore only checked where somebody has installed it.
SHIPPED_VENDORS = ('google',)


def installed(vendor, extension):
    return {path.stem for path in (WALLET_ROOT / vendor).glob(f'*.{extension}')}


@pytest.mark.parametrize('vendor', SHIPPED_VENDORS)
@pytest.mark.parametrize('extension', FORMATS)
def test_every_mapped_locale_has_artwork(vendor, extension):
    locales, _fallback = VENDOR_MAPS[vendor]
    missing = sorted(set(locales.values()) - installed(vendor, extension))
    assert not missing, f'no {vendor} {extension} artwork for: {", ".join(missing)}'


@pytest.mark.parametrize('vendor', SHIPPED_VENDORS)
@pytest.mark.parametrize('extension', FORMATS)
def test_fallback_artwork_exists(vendor, extension):
    _locales, fallback = VENDOR_MAPS[vendor]
    assert (WALLET_ROOT / vendor / f'{fallback}.{extension}').is_file()


@pytest.mark.parametrize('extension', FORMATS)
def test_apple_artwork_is_not_shipped(extension):
    """Apple's licence does not travel with the package; see `apple/README.md`.

    This is the test that stops a maintainer who has installed the badges on
    their own machine from publishing them to everybody by accident.
    """
    assert not installed('apple', extension), (
        'Apple badge artwork must not be committed or packaged: its licence is '
        'non-transferable. It is gitignored -- check what you are about to release.'
    )


@pytest.mark.parametrize('extension', FORMATS)
def test_installed_apple_artwork_is_complete(extension):
    """Where an operator *has* installed it, no mapped language may be missing.

    Skipped on a clean checkout; it earns its keep on a deployment, where a
    half-installed pack means some readers silently get no badge at all.
    """
    present = installed('apple', extension)
    if not present:
        pytest.skip('Apple artwork is not installed here')
    missing = sorted(set(APPLE_LOCALES.values()) - present)
    assert not missing, f'no apple {extension} artwork for: {", ".join(missing)}'


@pytest.mark.parametrize('vendor', VENDORS)
@pytest.mark.parametrize('extension', FORMATS)
def test_no_stray_artwork(vendor, extension):
    """Every file present should be reachable from the map.

    A file nobody maps to is dead weight, and usually means a locale was added
    to the directory but not to the map.
    """
    locales, _fallback = VENDOR_MAPS[vendor]
    unmapped = sorted(installed(vendor, extension) - set(locales.values()))
    assert not unmapped, f'{vendor} artwork with no locale mapped to it: {", ".join(unmapped)}'


@pytest.mark.parametrize('locale', ('en_GB', 'en_SG', 'zh_Hant_TW', 'ja_JP', 'pt_BR'))
@pytest.mark.parametrize('vendor', VENDORS)
def test_locales_stsa_cares_about(vendor, locale):
    locales, _fallback = VENDOR_MAPS[vendor]
    assert locale in locales


def test_google_artwork_is_googles_own():
    """A cheap guard against the artwork being replaced with a lookalike.

    Google's buttons are 283x50 in its own dark grey; a hand-drawn stand-in
    would not be, and both vendors forbid substituting one.
    """
    svg = (WALLET_ROOT / 'google' / 'enGB.svg').read_text(encoding='utf-8')
    assert 'viewBox="0 0 283 50"' in svg
    assert '#1F1F1F' in svg


def test_apple_artwork_is_apples_own():
    """The same guard for Apple, whose badge is 110.739x35.016 as shipped."""
    badge = WALLET_ROOT / 'apple' / 'US_UK.svg'
    if not badge.is_file():
        pytest.skip('Apple artwork is not installed here')
    assert 'viewBox="0 0 110.739 35.016"' in badge.read_text(encoding='utf-8')


def test_readmes_name_the_sources_and_apples_licence():
    readme = (WALLET_ROOT / 'README.md').read_text(encoding='utf-8')
    apple = (WALLET_ROOT / 'apple' / 'README.md').read_text(encoding='utf-8')
    assert 'developers.google.com' in readme
    assert 'Wallet Marketing Artwork' in readme
    # Apple's artwork comes with a licence, and whoever touches this directory
    # next needs to know both where it comes from and why it stays out of the
    # package.
    assert 'developer.apple.com' in apple
    assert 'non-transferable' in apple


def test_static_root_points_at_the_package():
    assert STATIC_ROOT.is_dir()
    assert STATIC_ROOT.name == 'static'
    assert STATIC_ROOT.parent.name == 'indico_stsa'
