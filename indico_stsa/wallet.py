"""Finding the right wallet badge artwork for the page or mail being built.

Both vendors ship their badge as localized artwork and both forbid recreating
it, so this does not draw anything: it looks for the file, and says nothing when
there is not one.  See `static/wallet/README.md` for where the files come from.

Two formats, for two places:

* **SVG** on the web, which is what the vendors' own guidelines assume.
* **PNG** in e-mail, because Gmail and Outlook do not render SVG at all -- an
  SVG badge in a mail is an empty box, or a broken-image icon.
"""

from pathlib import Path

from flask import session

from indico.web.flask.util import url_for


#: Indico's locales mapped onto the codes Google names its button files with.
#: Google's codes are its own -- `cz` rather than `cs`, `jp` rather than `ja`,
#: `br` rather than `pt_BR` -- so this cannot be derived, only written down.
GOOGLE_LOCALES = {
    'cs_CZ': 'cz',
    'de_DE': 'de',
    'en_AU': 'enAU',
    'en_CA': 'enCA',
    'en_GB': 'enGB',
    'en_IN': 'enIN',
    'en_SG': 'enSG',
    'en_US': 'enUS',
    'es_ES': 'esES',
    'fr_FR': 'frFR',
    'hu_HU': 'hu',
    'id_ID': 'id',
    'it_IT': 'it',
    'ja_JP': 'jp',
    'mn_MN': 'mn',
    'nl_NL': 'nl',
    'pl_PL': 'pl',
    'pt_BR': 'br',
    'pt_PT': 'pt',
    'ru_RU': 'ru',
    'sv_SE': 'se',
    'th_TH': 'th',
    'tr_TR': 'tr',
    'uk_UA': 'uk',
    'vi_VN': 'vi',
    'zh_Hant_TW': 'zhTW',
    'zh_Hant_HK': 'zhHK',
}

#: What a visitor whose language Google has no button for is shown.  English
#: rather than nothing: a badge in the wrong language is still the badge people
#: are looking for, and Google ships no neutral artwork.
GOOGLE_FALLBACK = 'enGB'

#: The same, for Apple, whose badge pack is organized by market rather than by
#: language: one folder covers every English-speaking one, `TWTC` is Traditional
#: Chinese for Taiwan, `PTBR` is Brazilian Portuguese.
APPLE_LOCALES = {
    'cs_CZ': 'CZ',
    'de_DE': 'DE',
    'en_AU': 'US_UK',
    'en_CA': 'US_UK',
    'en_GB': 'US_UK',
    'en_IN': 'US_UK',
    'en_SG': 'US_UK',
    'en_US': 'US_UK',
    'es_ES': 'ES',
    'fi_FI': 'FI',
    'fr_FR': 'FR',
    'hu_HU': 'HU',
    'id_ID': 'ID',
    'it_IT': 'IT',
    'ja_JP': 'JP',
    'ko_KR': 'KR',
    'nl_NL': 'NL',
    'pl_PL': 'PL',
    'pt_BR': 'PTBR',
    'pt_PT': 'PT',
    'ru_RU': 'RU',
    'sv_SE': 'SE',
    'th_TH': 'TH',
    'tr_TR': 'TR',
    'uk_UA': 'UA',
    'vi_VN': 'VN',
    'zh_Hans_CN': 'CN',
    'zh_Hant_HK': 'HK',
    'zh_Hant_TW': 'TWTC',
}

APPLE_FALLBACK = 'US_UK'

VENDORS = ('apple', 'google')

STATIC_ROOT = Path(__file__).parent / 'static'
WALLET_ROOT = STATIC_ROOT / 'wallet'


def current_locale():
    return (session.lang if session else None) or 'en_GB'


def badge_path(vendor, extension, locale=None):
    """The artwork file for a vendor, or ``None`` if it is not installed.

    ``None`` rather than a stand-in: both vendors' guidelines say to use their
    own artwork and not to make your own, so the honest answer when a file is
    missing is "no badge" and the caller leaves Indico's own button alone.
    """
    locale = locale or current_locale()
    if vendor == 'google':
        locales, fallback = GOOGLE_LOCALES, GOOGLE_FALLBACK
    elif vendor == 'apple':
        locales, fallback = APPLE_LOCALES, APPLE_FALLBACK
    else:
        raise ValueError(f'unknown wallet vendor: {vendor!r}')

    for code in (locales.get(locale, fallback), fallback):
        path = WALLET_ROOT / vendor / f'{code}.{extension}'
        if path.is_file():
            return path
    return None


def badge_url(vendor, locale=None):
    """The URL the vendor's SVG badge is served at, for use on a web page."""
    path = badge_path(vendor, 'svg', locale)
    if path is None:
        return None
    relative = path.relative_to(STATIC_ROOT).as_posix()
    stem, _dot, extension = relative.rpartition('.')
    return url_for('assets.plugin_file', plugin='stsa', filename=stem, fileext=extension)
