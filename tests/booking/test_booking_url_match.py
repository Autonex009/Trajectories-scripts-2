"""
Pytest unit tests for Booking.com URL Match verifier.
"""

import pytest
from navi_bench.booking.booking_url_match import generate_task_config
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
BASE_URL = "https://www.booking.com"
BASE_FLIGHT_SEARCH = "https://www.booking.com/flights/search"
BASE_CAR_SEARCH = "https://www.booking.com/cars/search"


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

    @pytest.mark.asyncio
    async def test_non_booking_url_ignored(self):
        gt = "https://www.booking.com/hotel/fr/paris.html?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)

        await v.update(url="https://www.google.com")
        result = await v.compute()

        assert result.score == 0.0
        assert v._agent_url == ""
        assert v._matched_gt_url == ""  # ✅ FIX


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

    def test_parse_flight_url(self):
        url = f"{BASE_FLIGHT}?from=DEL.AIRPORT&to=PAR.CITY&depart=2026-04-01&type=ONEWAY&adults=2"
        parsed = _v(url)._parse_flights_url(url)

        assert parsed["origin"] == "del.airport"
        assert parsed["destination"] == "par.city"
        assert parsed["depart_date"] == "2026-04-01"

    @pytest.mark.asyncio
    async def test_flight_url_lifecycle_match(self):
        gt = f"{BASE_FLIGHT}?from=DEL.AIRPORT&to=PAR.CITY&depart=2026-04-01&type=ONEWAY&adults=1"

        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=gt)
        result = await v.compute_detailed()

        assert result.match is True


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

    def test_parse_cars_url(self):
        url = f"{BASE_CAR}?locationName=Paris&dropLocationName=Paris&puDay=1"
        parsed = _v(url)._parse_cars_url(url)

        assert parsed["location_name"] == "Paris"
        assert parsed["drop_location_name"] == "Paris"
        assert parsed["pu_day"] == "1"

    @pytest.mark.asyncio
    async def test_cars_url_lifecycle_match(self):
        gt = f"{BASE_CAR}?locationName=Paris&puDay=1"

        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=gt)
        result = await v.compute_detailed()

        assert result.match is True

    @pytest.mark.asyncio
    async def test_cars_url_lifecycle_no_match(self):
        gt = f"{BASE_CAR}?locationName=Paris&puDay=1"
        agent = f"{BASE_CAR}?locationName=Paris&puDay=2"

        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=agent)
        result = await v.compute_detailed()

        assert result.match is False


# =============================================================================
# 6. TASK CONFIG
# =============================================================================

@pytest.mark.asyncio
async def test_generate_task_config_gt_url_precedence():
    gt_url_list = [f"{BASE_URL}/hotels/list?cityName=London"]

    config = generate_task_config(
        task="Find hotels",
        location="London",
        timezone="Europe/London",
        gt_url=gt_url_list,
    )

    assert set(config.eval_config["gt_url"]) == set(gt_url_list)


@pytest.mark.asyncio
async def test_generate_task_config_placeholder_substitution():
    gt_url_template = f"{BASE_URL}/search?checkin={{checkinDate}}&checkout={{checkoutDate}}"

    config = generate_task_config(
        task="Hotels",
        location="Paris",
        timezone="Europe/Paris",
        gt_url=[gt_url_template],
        values={
            "checkinDate": "{now() + timedelta(1)}",
            "checkoutDate": "{now() + timedelta(3)}",
        },
    )

    url = config.eval_config["gt_url"][0]
    assert "checkin=" in url
    assert "checkout=" in url


@pytest.mark.asyncio
async def test_generate_task_config_raises_value_error():
    with pytest.raises(ValueError):
        generate_task_config(
            task="Find hotels",
            location="Paris",
            timezone="Europe/Paris"
        )

# =============================================================================
# 7. ASYNC LIFECYCLE
# =============================================================================
class TestAsyncLifecycle:

    @pytest.mark.asyncio
    async def test_reset(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)

        await v.update(url=gt)
        await v.reset()

        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_first_match_sticks(self):
        gt1 = f"{BASE_HOTEL}?ss=Paris"
        gt2 = f"{BASE_HOTEL}?ss=London"

        v = BookingUrlMatch(gt_url=[gt1, gt2])

        await v.update(url=gt1)
        await v.update(url=gt2)  # should be ignored

        result = await v.compute_detailed()

        assert result.match is True
        assert result.gt_url == gt1  # first match sticks


# =============================================================================
# 8. MULTIPLE GT URL SUPPORT
# =============================================================================
class TestMultipleGTUrls:

    @pytest.mark.asyncio
    async def test_multiple_gt_urls(self):
        gt1 = f"{BASE_HOTEL}?ss=Paris"
        gt2 = f"{BASE_HOTEL}?ss=London"

        v = BookingUrlMatch(gt_url=[gt1, gt2])

        await v.update(url=gt2)
        result = await v.compute_detailed()

        assert result.match is True
        assert result.gt_url == gt2

# =============================================================================
# 9. COMPUTE DETAILED OUTPUT
# =============================================================================
class TestComputeDetailed:

    @pytest.mark.asyncio
    async def test_compute_detailed_fields(self):
        gt = f"{BASE_HOTEL}?ss=Paris"
        v = BookingUrlMatch(gt_url=gt)

        await v.update(url=gt)
        result = await v.compute_detailed()

        assert isinstance(result, BookingVerifierResult)
        assert result.score == 1.0
        assert result.match is True
        assert result.agent_url == gt
        assert result.gt_url == gt
        assert isinstance(result.details, dict)

# =============================================================================
# 10. SCORING
# =============================================================================
class TestScoring:

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
        agent = f"{BASE_HOTEL}?ss=London"

        v = BookingUrlMatch(gt_url=gt)
        await v.update(url=agent)

        result = await v.compute()
        assert result.score == 0.0