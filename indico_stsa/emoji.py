"""Getting emoji onto printed tickets and badges.

An event called "秋季迎新晚會 🎉" printed a crossed box where the emoji should
be.  Noto Sans/Serif CJK has no emoji glyphs, ReportLab draws `.notdef` for a
codepoint a font does not have, and there is no way to ask it for a second font
when the first one comes up short: a `Paragraph` is drawn in exactly one face,
and Indico strips any inline markup out of the text before it gets there.

So an item whose text needs two fonts is not drawn as text at all.  It is
composed here -- run by run, each run in the font that actually has the glyphs
-- and handed back to Indico as an image, which the badge renderer already knows
how to place.  Everything else stays on the normal text path; this only touches
the lines that would otherwise be boxes.

If the emoji font is missing, or anything here goes wrong, the characters are
dropped instead.  A title reading "秋季迎新晚會" is a small loss.  One reading
"秋季迎新晚會 ⊠" looks broken, and is the thing being fixed.
"""

import re
import unicodedata
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from indico_stsa.fonts import FAMILIES, cjk_font_path


#: Shipped alongside the plugin; see `static/fonts/README.md`.
EMOJI_FONT = Path(__file__).parent / 'static' / 'fonts' / 'NotoEmoji.ttf'

#: The designer canvas is 50px to the centimetre; a point is 1/72 inch.
PX_PER_CM = 50
PT_PER_CM = 72 / 2.54
PX_PER_PT = PX_PER_CM / PT_PER_CM

#: The image is composed at this multiple of its final size, so the result is
#: still crisp on paper next to the vector text around it.
SUPERSAMPLE = 4

#: Zero-width joiners, variation selectors and the like: they carry no glyph of
#: their own and must never count as "text this font cannot draw".
INVISIBLE = re.compile(r'[‍︎️\U000e0020-\U000e007f]')


@lru_cache(maxsize=8)
def _coverage(path):
    """The set of codepoints a font actually has a glyph for."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True) as font:
        return frozenset(font.getBestCmap())


def emoji_font_available():
    return EMOJI_FONT.is_file()


def _is_drawable(char, primary, emoji):
    """Whether *some* font we have can draw this character."""
    point = ord(char)
    return point in primary or point in emoji


def needs_image(text, family):
    """Whether this text has characters the item's own font cannot draw."""
    if not text or not emoji_font_available():
        return False
    primary = _coverage(cjk_font_path(family))
    return any(ord(c) not in primary and not INVISIBLE.match(c) and not c.isspace()
               for c in str(text))


def strip_undrawable(text, family):
    """Drop what nothing we have can draw, so a box is never printed."""
    primary = _coverage(cjk_font_path(family))
    emoji = _coverage(EMOJI_FONT) if emoji_font_available() else frozenset()
    kept = [c for c in str(text)
            if c.isspace() or _is_drawable(c, primary, emoji) or unicodedata.combining(c)]
    return re.sub(r'\s{2,}', ' ', ''.join(kept)).strip()


def split_runs(text, family):
    """Break the text into runs, each tagged with the font that can draw it.

    Invisible joiners travel with the run before them, so a sequence like a
    flag or a skin-tone modifier is handed to the emoji font in one piece
    rather than being split down the middle.
    """
    primary = _coverage(cjk_font_path(family))
    emoji = _coverage(EMOJI_FONT)
    runs = []
    for char in str(text):
        if not _is_drawable(char, primary, emoji) and not char.isspace():
            continue
        if INVISIBLE.match(char) and runs:
            runs[-1][0].append(char)
            continue
        use_emoji = ord(char) not in primary and ord(char) in emoji
        if runs and runs[-1][1] == use_emoji:
            runs[-1][0].append(char)
        else:
            runs.append(([char], use_emoji))
    return [(''.join(chars), use_emoji) for chars, use_emoji in runs]


def _wrap(runs, fonts, max_width, draw):
    """Greedy wrap, breaking between characters.

    Between characters rather than between words because half of this text is
    Chinese, which has no spaces to break on, and a title that refuses to wrap
    runs off the side of the ticket.
    """
    lines, line, width = [], [], 0.0
    for text, use_emoji in runs:
        font = fonts[use_emoji]
        for char in text:
            advance = draw.textlength(char, font=font)
            if width + advance > max_width and line:
                lines.append(line)
                line, width = [], 0.0
            if not line and char.isspace():
                # The space that caused the break belongs to neither line; kept,
                # it indents the new one by a space nobody asked for.
                continue
            if line and line[-1][1] is use_emoji:
                line[-1] = (line[-1][0] + char, use_emoji)
            else:
                line.append((char, use_emoji))
            width += advance
    if line:
        lines.append(line)
    return lines


def render(text, *, family, font_size_pt, width_px, color, align='left'):
    """Compose the text as an image, and say how tall it came out.

    :return: ``(BytesIO, height_px)`` in the designer's pixels, so the caller
             can size the item's box to match and keep the aspect ratio.
    """
    from PIL import Image, ImageDraw, ImageFont

    runs = split_runs(text, family)
    if not runs:
        return None, 0

    scale = PX_PER_PT * SUPERSAMPLE
    fonts = {
        False: ImageFont.truetype(str(cjk_font_path(family)), round(font_size_pt * scale)),
        True: ImageFont.truetype(str(EMOJI_FONT), round(font_size_pt * scale)),
    }
    canvas_width = round(width_px * SUPERSAMPLE)
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    lines = _wrap(runs, fonts, canvas_width, probe)

    # Match the badge renderer, which sets leading equal to the font size.
    leading = round(font_size_pt * scale)
    height = max(leading * len(lines), leading)
    image = Image.new('RGBA', (canvas_width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for row, line in enumerate(lines):
        line_width = sum(draw.textlength(t, font=fonts[e]) for t, e in line)
        if align == 'right':
            x = canvas_width - line_width
        elif align == 'center':
            x = (canvas_width - line_width) / 2
        else:
            x = 0
        for chunk, use_emoji in line:
            font = fonts[use_emoji]
            # `anchor='ls'` puts the baseline where ReportLab puts it, so a
            # line of emoji sits on the same baseline as the text beside it.
            draw.text((x, row * leading + leading * 0.82), chunk, font=font,
                      fill=color, anchor='ls')
            x += draw.textlength(chunk, font=font)

    out = BytesIO()
    image.save(out, format='PNG')
    out.seek(0)
    return out, round(height / SUPERSAMPLE)


def draw_item_on_badge(sender, data=None, **kwargs):
    """Swap in an image for any item the badge fonts cannot draw.

    Connected to `designer.draw_item_on_badge`, which lets a receiver replace
    the item and the content core is about to draw.
    """
    item = data['item']
    text = data['text']
    if isinstance(text, BytesIO) or not text:
        return None                       # already an image, or nothing to draw
    family = item.get('font_family')
    if family not in FAMILIES or not needs_image(text, family):
        return None

    from indico_stsa.ticket import parse_font_size

    if not emoji_font_available():
        return {'text': strip_undrawable(text, family)}

    image, height = render(
        text,
        family=family,
        font_size_pt=parse_font_size(item['font_size']),
        width_px=item['width'],
        color=item.get('color') or '#000000',
        align=item.get('text_align', 'left'),
    )
    if image is None:
        return {'text': strip_undrawable(text, family)}
    # The renderer needs a height to place an image, and sizing the box to what
    # was actually composed is what stops it being stretched.
    return {'item': dict(item, height=height), 'text': image}
