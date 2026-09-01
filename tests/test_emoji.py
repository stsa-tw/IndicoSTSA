"""Emoji on printed tickets: which lines change path, and how they are split."""

import pytest

from indico_stsa.emoji import (EMOJI_FONT, INVISIBLE, needs_image, split_runs, strip_undrawable)


SERIF = 'serif'

#: Nothing here needs a second font, so none of it may leave the vector text
#: path -- that is what keeps ordinary tickets byte-for-byte what they were.
PLAIN = [
    '2026 STSA 秋季迎新晚會 Welcome Night',
    '昱辰 林',
    # The en dash is the character Indico's own date formatter emits, and that
    # is the point: it must survive, not be taken for something undrawable.
    'Oct 1 – 2, 2026',  # ruff: ignore[ambiguous-unicode-character-string]
    '國立新加坡大學 文化中心',
    '持票人  ATTENDEE',
    '',
]

WITH_EMOJI = [
    '秋季迎新晚會 🎉',
    '昱辰 🐻',
    '🎉🎊🥳',
    '2026 STSA 迎新 🎉 Welcome 🇹🇼',
]


def test_the_emoji_font_ships():
    assert EMOJI_FONT.is_file(), 'the emoji font is what makes any of this work'
    assert EMOJI_FONT.stat().st_size > 500_000


@pytest.mark.parametrize('text', PLAIN)
def test_plain_text_is_left_alone(text):
    assert not needs_image(text, SERIF)


@pytest.mark.parametrize('text', WITH_EMOJI)
def test_emoji_text_needs_composing(text):
    assert needs_image(text, SERIF)


def test_runs_are_split_by_which_font_can_draw_them():
    runs = split_runs('秋季 🎉 Night', SERIF)
    assert [text for text, _ in runs] == ['秋季 ', '🎉', ' Night']
    assert [is_emoji for _, is_emoji in runs] == [False, True, False]


def test_adjacent_emoji_share_one_run():
    """One run means one `draw.text` call, and no seam between the glyphs."""
    runs = split_runs('🎉🎊🥳', SERIF)
    assert len(runs) == 1
    assert runs[0] == ('🎉🎊🥳', True)


def test_a_flag_stays_in_one_run():
    """A flag is two regional indicators; split apart they stop being a flag."""
    runs = split_runs('🇹🇼', SERIF)
    assert len(runs) == 1
    assert runs[0][1] is True


def test_joiners_do_not_start_a_run():
    """A ZWJ has no glyph of its own, so it must not be mistaken for text the
    font cannot draw."""
    assert INVISIBLE.match('‍')
    assert INVISIBLE.match('️')
    runs = split_runs('a‍b', SERIF)
    assert ''.join(text for text, _ in runs) == 'a‍b'


def test_nothing_is_lost_from_ordinary_text():
    text = '2026 STSA 秋季迎新晚會 Welcome Night'
    assert strip_undrawable(text, SERIF) == text


def test_stripping_keeps_the_words_and_drops_the_boxes():
    """The fallback for when the emoji font is unavailable: a clean line."""
    out = strip_undrawable('秋季迎新晚會 \U000fffff Welcome', SERIF)
    assert '\U000fffff' not in out
    assert '秋季迎新晚會' in out
    assert 'Welcome' in out
    assert '  ' not in out, 'the gap the dropped character left is closed up'


def test_emoji_survive_stripping_while_the_font_is_there():
    assert '🎉' in strip_undrawable('迎新 🎉', SERIF)
