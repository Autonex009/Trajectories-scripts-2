"""
Pytest unit tests for Booking.com URL Match verifier.

Covers:
1. Domain validation
2. Hotel URL parsing
3. Hotel matching (destination, dates, guests, filters, price)
4. Flight URL parsing + matching
5. Cars URL parsing + matching
6. Async lifecycle (update/compute/reset)
7. Edge cases
"""

import pytest

from navi_bench.booking.booking_url_match import (
    BookingUrlMatch,
    BookingVerifierResult,
)

# =============================================================================
# Helpers
# =============================================================================

BASE_HOTEL = "https://www.booking.com/searchresults.en-gb.html"
BASE_FLIGHT = "https://www.booking.com/flights/results/"
BASE_CAR = "https://cars.booking.com/search-results"


def _v(gt_url):
    return BookingUrlMatch(gt_url=gt_url)


def _match(agent, gt):
    return _v(gt)._urls_match(agent, gt)


# =============================================================================
# 1. DOMAIN VALIDATION
# =============================================================================

class TestDomainValidation:

    def test_valid_domains(self):
        v = _v(BASE_HOTEL)
        assert v._is_valid_booking_domain("booking.com")
        assert v._is_valid_booking_domain("www.booking.com")
        assert v._is_valid_booking_domain("cars.booking.com")

    def test_invalid_domains(self):
        v = _v(BASE_HOTEL)
        assert not v._is_valid_booking_domain("google.com")
        assert not v._is_valid_booking_domain("fake-booking.com")


# =============================================================================
# 2. HOTEL URL PARSING
# =============================================================================

class TestHotelParsing:

    def test_destination_parsed(self):
        url = f"{BASE_HOTEL}?ss=Paris"
        r = _v(url)._parse_hotel_url(url)
        assert r["destination"] == "paris"

    def test_dates_parsed(self):
        url = f"{BASE_HOTEL}?checkin=2026-04-01&checkout=2026-04-05"
        r = _v(url)._parse_hotel_url(url)
        assert r["checkin"] == "2026-04-01"
        assert r["checkout"] == "2026-04-05"

    def test_guests_parsed(self):
        url = f"{BASE_HOTEL}?group_adults=2&group_children=1&no_rooms=1"
        r = _v(url)._parse_hotel_url(url)
        assert r["adults"] == "2"
        assert r["children"] == "1"
        assert r["rooms"] == "1"

    def test_ages_parsed(self):
        url = f"{BASE_HOTEL}?age=5&age=10"
        r = _v(url)._parse_hotel_url(url)
        assert sorted(r["ages"]) == ["10", "5"]

    def test_filters_parsed(self):
        url = f"{BASE_HOTEL}?nflt=class%3D5%3Bmealplan%3D1"
        r = _v(url)._parse_hotel_url(url)
        assert "class" in r["filters"]
        assert "mealplan" in r["filters"]

    def test_price_parsed(self):
        url = f"{BASE_HOTEL}?nflt=price%3DINR-min-1000-5000"
        r = _v(url)._parse_hotel_url(url)
        assert r["price_min"] == 1000
        assert r["price_max"] == 5000


# =============================================================================
# 3. HOTEL MATCHING
# =============================================================================

class TestHotelMatching:

    def test_exact_match(self):
        gt = f"{BASE_HOTEL}?ss=Paris&checkin=2026-04-01&checkout=2026-04-05&group_adults=2&no_rooms=1&group_children=0"
        match, _ = _match(gt, gt)
        assert match is True

    def test_destination_mismatch(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        agent = f"{BASE_HOTEL}?ss=London"
        match, _ = _match(agent, gt)
        assert match is False

    def test_date_mismatch(self):
        gt = f"{BASE_HOTEL}?checkin=2026-04-01&checkout=2026-04-05"
        agent = f"{BASE_HOTEL}?checkin=2026-04-02&checkout=2026-04-05"
        match, _ = _match(agent, gt)
        assert match is False

    def test_missing_guest(self):
        gt = f"{BASE_HOTEL}?group_adults=2"
        agent = f"{BASE_HOTEL}?"
        match, _ = _match(agent, gt)
        assert match is False

    def test_filters_subset_allowed(self):
        gt = f"{BASE_HOTEL}?nflt=class%3D5"
        agent = f"{BASE_HOTEL}?nflt=class%3D5%3Bmealplan%3D1"
        match, _ = _match(agent, gt)
        assert match is True

    def test_missing_filter_fails(self):
        gt = f"{BASE_HOTEL}?nflt=class%3D5"
        agent = f"{BASE_HOTEL}?"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 4. FLIGHT MATCHING
# =============================================================================

class TestFlightMatching:

    def test_exact_match(self):
        gt = f"{BASE_FLIGHT}?from=DEL.AIRPORT&to=PAR.CITY&depart=2026-04-01&type=ONEWAY&adults=1"
        match, _ = _match(gt, gt)
        assert match is True

    def test_origin_mismatch(self):
        gt = f"{BASE_FLIGHT}?from=DEL.AIRPORT"
        agent = f"{BASE_FLIGHT}?from=BOM.AIRPORT"
        match, _ = _match(agent, gt)
        assert match is False

    def test_date_mismatch(self):
        gt = f"{BASE_FLIGHT}?depart=2026-04-01"
        agent = f"{BASE_FLIGHT}?depart=2026-04-02"
        match, _ = _match(agent, gt)
        assert match is False

    def test_stops_filter(self):
        gt = f"{BASE_FLIGHT}?stops=0"
        match, _ = _match(gt, gt)
        assert match is True


# =============================================================================
# 5. CAR MATCHING
# =============================================================================

class TestCarMatching:

    def test_exact_match(self):
        gt = f"{BASE_CAR}?locationName=Paris&puDay=1&puMonth=4&puYear=2026"
        match, _ = _match(gt, gt)
        assert match is True

    def test_location_mismatch(self):
        gt = f"{BASE_CAR}?locationName=Paris"
        agent = f"{BASE_CAR}?locationName=London"
        match, _ = _match(agent, gt)
        assert match is False

    def test_filter_mismatch(self):
        gt = f"{BASE_CAR}?filterCriteria_transmission=AUTOMATIC"
        agent = f"{BASE_CAR}?filterCriteria_transmission=MANUAL"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 6. ASYNC LIFECYCLE
# =============================================================================

class TestAsyncLifecycle:

    @pytest.mark.asyncio
    async def test_match_scores_1(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=gt)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_scores_0(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=f"{BASE_HOTEL}?ss=London")
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_reset(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=gt)
        assert (await v.compute()).score == 1.0

        await v.reset()
        assert (await v.compute()).score == 0.0

    @pytest.mark.asyncio
    async def test_first_match_sticks(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=gt)
        await v.update(url=f"{BASE_HOTEL}?ss=London")
        assert (await v.compute()).score == 1.0

    @pytest.mark.asyncio
    async def test_compute_detailed(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=gt)
        result = await v.compute_detailed()

        assert isinstance(result, BookingVerifierResult)
        assert result.match is True


# =============================================================================
# 7. EDGE CASES
# =============================================================================

class TestEdgeCases:

    def test_empty_url(self):
        v = _v(f"{BASE_HOTEL}?ss=Paris")
        match, _ = v._urls_match("", f"{BASE_HOTEL}?ss=Paris")
        assert match is False

    def test_unknown_url_type(self):
        v = _v("https://www.booking.com/unknown")
        match, details = v._urls_match("https://www.booking.com/unknown", "https://www.booking.com/unknown")
        assert match is False

    def test_multiple_gt_urls(self):
        gt = [
            f"{BASE_HOTEL}?ss=Paris",
            f"{BASE_HOTEL}?ss=London"
        ]
        v = BookingUrlMatch(gt_url=gt)
        match, _ = v._urls_match(f"{BASE_HOTEL}?ss=London", gt[1])
        assert match is True