"""What a registration is listed as, and how the events API reads its query string.

`indico_stsa.registered_events` finds one participant's registrations and hands
each to `registration_status`, so these are the tests for the decisions the
database cannot make: whether somebody who has not turned up is late or gone,
and which events a window takes in.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from indico_stsa.attendance import (CHECKED_IN, DEFAULT_STATUSES, NO_SHOW, ONGOING, PENDING, REJECTED, STATUSES,
                                    UPCOMING, WITHDRAWN, overlaps, parse_statuses, parse_window,
                                    registration_status)


SGT = timezone(timedelta(hours=8))
START = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
END = datetime(2026, 11, 14, 18, 0, tzinfo=UTC)


def status(*, state='complete', checked_in=False, now):
    return registration_status(state=state, checked_in=checked_in, start=START, end=END, now=now)


class TestRegistrationStatus:
    def test_not_started_yet(self):
        assert status(now=START - timedelta(days=3)) == UPCOMING

    def test_the_moment_it_starts(self):
        assert status(now=START) == ONGOING

    def test_under_way_and_not_arrived(self):
        # Not a no-show yet: they may still come.
        assert status(now=START + timedelta(hours=1)) == ONGOING

    def test_the_moment_it_ends(self):
        assert status(now=END) == NO_SHOW

    def test_over_and_never_arrived(self):
        assert status(now=END + timedelta(days=30)) == NO_SHOW

    @pytest.mark.parametrize('offset', (timedelta(days=-3), timedelta(hours=1), timedelta(days=30)))
    def test_checking_in_wins_over_the_clock(self, offset):
        assert status(checked_in=True, now=START + offset) == CHECKED_IN

    @pytest.mark.parametrize('state', ('withdrawn', 'rejected'))
    @pytest.mark.parametrize('now', (START - timedelta(days=3), END + timedelta(days=3)))
    def test_a_cancelled_registration_stays_cancelled(self, state, now):
        assert status(state=state, now=now) == state

    def test_a_cancelled_registration_is_not_checked_in(self):
        # Somebody who checked in and was withdrawn afterwards is not attending.
        assert status(state='withdrawn', checked_in=True, now=END + timedelta(days=1)) == WITHDRAWN

    @pytest.mark.parametrize('now', (START - timedelta(days=3), START + timedelta(hours=1), END + timedelta(days=3)))
    def test_waiting_for_approval_has_no_place_yet(self, now):
        assert status(state='pending', now=now) == PENDING

    def test_awaiting_payment_still_holds_a_place(self):
        # `unpaid` says nothing about whether anybody came.
        assert status(state='unpaid', now=START - timedelta(days=3)) == UPCOMING
        assert status(state='unpaid', checked_in=True, now=END + timedelta(days=3)) == CHECKED_IN
        assert status(state='unpaid', now=END + timedelta(days=3)) == NO_SHOW

    def test_every_status_is_reachable(self):
        reached = {
            status(now=START - timedelta(days=1)), status(now=START), status(now=END),
            status(checked_in=True, now=END), status(state='pending', now=END),
            status(state='withdrawn', now=END), status(state='rejected', now=END),
        }
        assert reached == set(STATUSES)


class TestParseStatuses:
    def test_nothing_asked_lists_the_live_ones(self):
        assert parse_statuses([]) == DEFAULT_STATUSES
        assert parse_statuses(['']) == DEFAULT_STATUSES
        assert {WITHDRAWN, REJECTED}.isdisjoint(DEFAULT_STATUSES)

    def test_one(self):
        assert parse_statuses(['checked_in']) == {CHECKED_IN}

    def test_comma_separated_and_repeated_mean_the_same(self):
        assert parse_statuses(['upcoming,ongoing']) == parse_statuses(['upcoming', 'ongoing']) == {UPCOMING, ONGOING}

    def test_a_cancelled_one_can_be_asked_for_by_name(self):
        assert parse_statuses(['withdrawn,rejected']) == {WITHDRAWN, REJECTED}

    def test_case_and_spaces_do_not_matter(self):
        assert parse_statuses([' No_Show , upcoming']) == {NO_SHOW, UPCOMING}

    def test_a_typo_is_an_error_and_not_an_empty_list(self):
        with pytest.raises(ValueError, match=r'Unknown status noshow.*no_show'):
            parse_statuses(['upcoming,noshow'])


class TestParseWindow:
    def test_no_window(self):
        assert parse_window(None, None, tz=SGT) == (None, None)
        assert parse_window('', '', tz=SGT) == (None, None)

    def test_either_end_may_be_left_open(self):
        start, end = parse_window('2026-11-01', None, tz=SGT)
        assert start == datetime(2026, 11, 1, tzinfo=SGT)
        assert end is None
        assert parse_window(None, '2026-11-01', tz=SGT)[0] is None

    def test_a_date_is_read_in_the_given_timezone(self):
        start = parse_window('2026-11-01', None, tz=SGT)[0]
        assert start == datetime(2026, 10, 31, 16, 0, tzinfo=UTC)

    def test_a_date_as_the_end_includes_that_day(self):
        end = parse_window(None, '2026-11-30', tz=SGT)[1]
        assert end == datetime(2026, 12, 1, tzinfo=SGT)

    def test_one_day(self):
        start, end = parse_window('2026-11-14', '2026-11-14', tz=SGT)
        assert end - start == timedelta(days=1)

    def test_a_time_with_no_offset_is_read_in_the_given_timezone(self):
        start, end = parse_window('2026-11-14T09:30', '2026-11-14T12:00:00', tz=SGT)
        assert start == datetime(2026, 11, 14, 9, 30, tzinfo=SGT)
        assert end == datetime(2026, 11, 14, 12, 0, tzinfo=SGT)

    @pytest.mark.parametrize('value', ('2026-11-14T09:30:00+00:00', '2026-11-14T09:30:00Z'))
    def test_an_explicit_offset_is_kept(self, value):
        start = parse_window(value, None, tz=SGT)[0]
        assert start == datetime(2026, 11, 14, 9, 30, tzinfo=UTC)

    def test_a_time_as_the_end_is_not_extended(self):
        end = parse_window(None, '2026-11-14T12:00', tz=SGT)[1]
        assert end == datetime(2026, 11, 14, 12, 0, tzinfo=SGT)

    @pytest.mark.parametrize('value', ('tomorrow', '14/11/2026', '2026-13-01', '2026-11-14T25:00'))
    def test_garbage_names_the_parameter(self, value):
        with pytest.raises(ValueError, match='`from` is not an ISO 8601'):
            parse_window(value, None, tz=SGT)
        with pytest.raises(ValueError, match='`to` is not an ISO 8601'):
            parse_window(None, value, tz=SGT)

    def test_an_unencoded_plus_is_explained(self):
        # `+08:00` in a URL arrives as ` 08:00`.
        with pytest.raises(ValueError, match='%2B'):
            parse_window('2026-11-14T09:30:00 08:00', None, tz=SGT)

    @pytest.mark.parametrize(('start', 'end'), (('2026-11-14T12:00', '2026-11-14T12:00'),
                                                ('2026-11-14T12:00', '2026-11-14T11:00')))
    def test_an_empty_or_backwards_window(self, start, end):
        with pytest.raises(ValueError, match='later than'):
            parse_window(start, end, tz=SGT)


class TestOverlaps:
    # An event from 14:00 to 18:00.
    @staticmethod
    def hours(frm, to):
        base = datetime(2026, 11, 14, tzinfo=UTC)
        return (None if frm is None else base + timedelta(hours=frm),
                None if to is None else base + timedelta(hours=to))

    @pytest.mark.parametrize(('frm', 'to'), ((None, None), (0, 24), (14, 18), (15, 16), (10, 15), (17, 24),
                                             (None, 15), (17, None)))
    def test_in(self, frm, to):
        assert overlaps(*self.hours(14, 18), *self.hours(frm, to))

    @pytest.mark.parametrize(('frm', 'to'), ((0, 14), (18, 24), (None, 14), (18, None), (0, 10), (20, 24)))
    def test_out(self, frm, to):
        # The window is half-open: one that closes as the event opens, or opens
        # as it closes, has nothing of it in it.
        assert not overlaps(*self.hours(14, 18), *self.hours(frm, to))

    def test_a_multi_day_event_is_in_every_window_it_touches(self):
        base = datetime(2026, 11, 14, tzinfo=UTC)
        start, end = base, base + timedelta(days=3)
        assert overlaps(start, end, base - timedelta(days=5), base + timedelta(days=1))
        assert overlaps(start, end, base + timedelta(days=2), base + timedelta(days=9))
        assert overlaps(start, end, base + timedelta(days=1), base + timedelta(days=2))

    def test_an_event_of_no_length_is_in_the_window_it_starts_in(self):
        # Core's check constraint is `end_dt >= start_dt`, so these exist.
        at = datetime(2026, 11, 14, 12, tzinfo=UTC)
        assert overlaps(at, at, at, at + timedelta(days=1))
        assert overlaps(at, at, at - timedelta(days=1), at + timedelta(days=1))
        assert not overlaps(at, at, at - timedelta(days=1), at)
        assert not overlaps(at, at, at + timedelta(seconds=1), None)
