"""The STSA ticket template and the CJK font mapping."""

import pytest

from indico_stsa.fonts import FAMILIES, FONT_PREFIX, font_name
from indico_stsa.install_ticket import BACKGROUND
from indico_stsa.ticket import HEIGHT, WIDTH, build_data, build_items


#: A4 in the designer's units, where 50px is 1cm.
A4_WIDTH, A4_HEIGHT = 1050, 1485

#: Every placeholder the ticket asks core for.  A typo here is not a crash: the
#: item is skipped and the ticket prints with a hole in it.
USED_PLACEHOLDERS = {
    'fixed', 'event_title', 'event_dates', 'event_venue',
    'full_name_b', 'affiliation', 'registration_friendly_id', 'ticket_qr_code',
}


def test_fits_on_the_page():
    assert WIDTH == A4_WIDTH, 'the ticket is drawn full-bleed across A4'
    assert HEIGHT <= A4_HEIGHT


def test_every_item_is_inside_the_ticket():
    for item in build_items():
        assert item['x'] >= 0, item
        assert item['y'] >= 0, item
        assert item['x'] + item['width'] <= WIDTH, item
        # `height` is only set on images; text grows downwards from `y`
        if item.get('height'):
            assert item['y'] + item['height'] <= HEIGHT, item


def test_item_ids_are_unique():
    """Core keys items by id in the designer UI; duplicates make edits land on
    the wrong one."""
    ids = [item['id'] for item in build_items()]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)


def test_only_known_placeholders():
    assert {item['type'] for item in build_items()} <= USED_PLACEHOLDERS


def test_has_exactly_one_qr_code():
    """The QR is the whole point of the stub, and two would be a copy-paste."""
    qrs = [i for i in build_items() if i['type'] == 'ticket_qr_code']
    assert len(qrs) == 1
    # Big enough to scan across a doorway: 290px at 50px/cm is 5.8cm.
    assert qrs[0]['width'] >= 250
    assert qrs[0]['width'] == qrs[0]['height'], 'a QR code has to stay square'


def test_the_stub_names_its_holder():
    """A stub torn off at the door still has to say whose it was."""
    names = [i for i in build_items() if i['type'] == 'full_name_b']
    qr_y = next(i['y'] for i in build_items() if i['type'] == 'ticket_qr_code')
    assert len(names) == 2, 'the holder is named above the tear line and on the stub'
    assert any(n['y'] > qr_y - 60 for n in names), 'one of them belongs on the stub'


def test_nothing_asks_for_bold():
    """ReportLab renders the default instance of a variable font, so a bold
    request would silently come out at regular weight.  See `indico_stsa.fonts`.
    """
    assert not any(item['bold'] or item['italic'] for item in build_items())


def test_no_item_uses_resize():
    """`resize` measures the string with the pre-swap font, so it mis-measures
    every Chinese glyph.  See `indico_stsa.ticket`."""
    assert all(item.get('text_overflow') == 'wrap'
               for item in build_items() if item['type'] != 'ticket_qr_code')


def test_data_is_shaped_the_way_core_reads_it():
    data = build_data()
    assert set(data) == {'items', 'width', 'height', 'background_position'}
    assert data['background_position'] == 'stretch'


def test_the_artwork_ships():
    """The furniture layer carries every rule and both logos; without it the
    ticket is text on blank paper."""
    assert BACKGROUND.is_file(), 'run scripts/build-ticket-artwork.py'
    assert BACKGROUND.stat().st_size > 10_000


@pytest.mark.parametrize('family', sorted(FAMILIES))
def test_font_families_match_indicos_own(family):
    """The mapping keys have to be the family names core puts in a template, or
    the swap silently never happens."""
    assert family in {'serif', 'sans-serif', 'courier'}
    assert font_name(family).startswith(FONT_PREFIX)


def test_the_ticket_only_uses_mapped_families():
    assert {item['font_family'] for item in build_items()} <= set(FAMILIES)
