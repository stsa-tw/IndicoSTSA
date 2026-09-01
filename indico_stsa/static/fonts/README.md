# Emoji font

`NotoEmoji.ttf` is Google's **Noto Emoji** (monochrome), from
[google/fonts](https://github.com/google/fonts/tree/main/ofl/notoemoji), under
the SIL Open Font License 1.1 — see `OFL.txt`, which the licence requires to
travel with it.

It is here because no CJK font has emoji glyphs, so an event title with an emoji
in it printed a crossed box. See `indico_stsa/emoji.py` for how a line that
needs both fonts is composed.

Monochrome rather than colour on purpose: tickets are usually printed, often in
black and white, and Noto Color Emoji is a bitmap font that ReportLab cannot
embed at all.
