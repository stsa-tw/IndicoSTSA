"""Making ticket and badge PDFs render Chinese properly.

Indico draws badges with ReportLab, and offers the organizer a fixed list of
font families: Liberation Serif/Sans/Mono, Linux Libertine, and -- for CJK --
Kochi Mincho, Kochi Gothic and AR PL UMing.  For Traditional Chinese that list
is poor: the Liberation faces have no CJK glyphs at all and drop out to tofu,
the Kochi faces are Japanese, and UMing is a dated Ming face whose Latin is
noticeably worse than its Chinese.

Indico already ships Noto Sans CJK and Noto Serif CJK -- they sit unused in
`indico_fonts`, registered nowhere.  They cover Traditional Chinese, Japanese
and Korean *and* have a good Latin, so one family can set a bilingual line
without switching fonts mid-sentence.

So this backs Indico's three generic families with those faces.  Every badge
and ticket in the instance gets CJK support, not only the STSA one, and a
template that was set in `sans-serif` keeps working -- it just stops producing
tofu the moment somebody's name is in Chinese.
"""

import os
from importlib.resources import as_file, files

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


#: Indico's generic family names mapped onto the CJK faces it already ships.
#: `courier` is the utility face; the Mono CJK keeps Latin digits monospaced
#: while still having the ideographs.
FAMILIES = {
    'serif': 'NotoSerifCJKjp-VF.ttf',
    'sans-serif': 'NotoSansCJKjp-VF.ttf',
    'courier': 'NotoSansMonoCJKjp-VF.ttf',
}

#: The name each face is registered under.  Prefixed so it can never collide
#: with the names core registers.
FONT_PREFIX = 'STSA-CJK-'

_registered = False


def font_name(family):
    return f'{FONT_PREFIX}{family}'


def register_fonts():
    """Register the CJK faces with ReportLab.  Idempotent and cheap to re-call.

    These are variable fonts, and ReportLab has no variable-axis support, so
    what gets embedded is each file's default instance -- Regular.  That is why
    nothing in the STSA ticket asks for bold: it would silently render at
    regular weight, and a hierarchy built on a weight that does not arrive is
    worse than one built on size and colour, which do.
    """
    global _registered
    if _registered:
        return
    with as_file(files('indico_fonts')) as font_dir:
        for family, filename in FAMILIES.items():
            path = os.path.join(font_dir, filename)
            if not os.path.exists(path):
                # A future Indico could stop shipping these; a badge in the
                # wrong font beats a traceback on the ticket download.
                continue
            pdfmetrics.registerFont(TTFont(font_name(family), path))
    _registered = True


def update_badge_style(sender, item=None, styles=None, **kwargs):
    """Swap the font ReportLab was about to use for the CJK one.

    Connected to `designer.update_badge_style`, which core sends for every item
    it is about to draw, with the styles it computed.  Whatever we return is
    merged over them.
    """
    register_fonts()
    name = font_name(item['font_family'])
    if name not in pdfmetrics.getRegisteredFontNames():
        return None
    return {'fontName': name}
