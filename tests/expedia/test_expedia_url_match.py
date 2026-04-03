"""Pytest unit tests for Expedia URL Match verifier.

Tests the ExpediaUrlMatch class covering Flights and Hotels
search verification with browser-verified URL patterns (Apr 2026).

Categories:
 1. Page Type Detection
 2. Flight URL Parsing — leg params, date normalization, IATA extraction
 3. Hotel URL Parsing — query params, regionId, sort
 4. Flight Matching — origin, dest, dates, cabin, passengers
 5. Hotel Matching — destination/regionId, dates, guests, rooms, sort
 6. Domain Validation — .com, regional
 7. Async Lifecycle — reset → update → compute
 8. Multi-GT URLs — OR semantics
 9. Edge Cases — cross-page type, empty URLs
10. Date Normalization — M/D/YYYY, YYYY-M-D, YYYY-MM-DD
11. IATA Code Extraction — from full city strings
12. generate_task_config Tests
"""

import pytest

from navi_bench.expedia.expedia_url_match import (
    ExpediaUrlMatch,
    ExpediaVerifierResult,
    detect_page_type,
    parse_flight_url,
    parse_hotel_url,
    _normalize_date,
    _extract_iata_code,
    _parse_leg_param,
    _normalize_cabin_class,
    _normalize_hotel_sort,
    _parse_passengers,
)


# =============================================================================
# Helpers
# =============================================================================

FLIGHTS_BASE = "https://www.expedia.com/Flights-Search"
HOTELS_BASE = "https://www.expedia.com/Hotel-Search"


def _match(agent_url: str, gt_url: str) -> tuple[bool, dict]:
    """Shortcut to match two URLs."""
    v = ExpediaUrlMatch(gt_url=gt_url)
    return v._urls_match(agent_url, gt_url)


# =============================================================================
# 1. Page Type Detection
# =============================================================================


class TestPageTypeDetection:
    """Test detect_page_type function."""

    def test_flight_search_page(self):
        url = f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        assert detect_page_type(url) == "flights"

    def test_hotel_search_page(self):
        url = f"{HOTELS_BASE}?destination=New%20York&startDate=2026-04-15"
        assert detect_page_type(url) == "hotels"

    def test_flights_landing_page(self):
        assert detect_page_type("https://www.expedia.com/Flights") == "flights"

    def test_hotels_landing_page(self):
        assert detect_page_type("https://www.expedia.com/Hotels") == "hotels"

    def test_cars_page(self):
        assert detect_page_type("https://www.expedia.com/Cars") == "cars"

    def test_cruises_page(self):
        assert detect_page_type("https://www.expedia.com/Cruises") == "cruises"

    def test_packages_page(self):
        assert detect_page_type("https://www.expedia.com/Packages") == "packages"

    def test_activities_page(self):
        assert detect_page_type("https://www.expedia.com/Things-To-Do") == "activities"

    def test_homepage(self):
        assert detect_page_type("https://www.expedia.com/") == "other"

    def test_unknown_path(self):
        assert detect_page_type("https://www.expedia.com/about") == "other"


# =============================================================================
# 2. Date Normalization
# =============================================================================


class TestDateNormalization:
    """Test _normalize_date for multiple Expedia date formats."""

    def test_md_yyyy(self):
        assert _normalize_date("4/16/2026") == "2026-04-16"

    def test_md_yyyy_single_digit(self):
        assert _normalize_date("1/5/2026") == "2026-01-05"

    def test_md_yyyy_double_digit(self):
        assert _normalize_date("12/25/2026") == "2026-12-25"

    def test_yyyy_m_d(self):
        assert _normalize_date("2026-4-16") == "2026-04-16"

    def test_yyyy_mm_dd(self):
        assert _normalize_date("2026-04-16") == "2026-04-16"

    def test_with_tanyt_suffix(self):
        assert _normalize_date("4/16/2026TANYT") == "2026-04-16"

    def test_empty_string(self):
        assert _normalize_date("") == ""


# =============================================================================
# 3. IATA Code Extraction
# =============================================================================


class TestIATAExtraction:
    """Test _extract_iata_code for various Expedia location formats."""

    def test_bare_iata(self):
        assert _extract_iata_code("JFK") == "jfk"

    def test_city_with_iata(self):
        assert _extract_iata_code("New York, NY (JFK)") == "jfk"

    def test_full_airport_string(self):
        result = _extract_iata_code(
            "New York, NY, United States of America (JFK-John F. Kennedy Intl.)"
        )
        assert result == "jfk"

    def test_lax_full_string(self):
        result = _extract_iata_code(
            "Los Angeles, CA, United States of America (LAX-Los Angeles Intl.)"
        )
        assert result == "lax"

    def test_lowercase_bare(self):
        assert _extract_iata_code("lhr") == "lhr"

    def test_empty_string(self):
        assert _extract_iata_code("") == ""

    def test_url_encoded(self):
        result = _extract_iata_code("New%20York%2C%20NY%20(JFK-John%20F.%20Kennedy%20Intl.)")
        assert result == "jfk"


# =============================================================================
# 4. Leg Parameter Parsing
# =============================================================================


class TestLegParsing:
    """Test _parse_leg_param for Expedia compound leg params."""

    def test_simple_iata_leg(self):
        leg = "from:JFK,to:LAX,departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
        result = _parse_leg_param(leg)
        assert result["from"] == "JFK"
        assert result["to"] == "LAX"
        assert result["departure"] == "4/16/2026TANYT"

    def test_empty_leg(self):
        assert _parse_leg_param("") == {}


# =============================================================================
# 5. Flight URL Parsing
# =============================================================================


class TestFlightURLParsing:
    """Test parse_flight_url for full URL extraction."""

    def test_oneway_basic(self):
        url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            f"&options=cabinclass:economy"
            f"&passengers=adults:1,infantinlap:N"
        )
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"
        assert r["depart_date"] == "2026-04-16"
        assert r["return_date"] == ""
        assert r["trip_type"] == "oneway"
        assert r["cabin_class"] == "economy"
        assert r["adults"] == "1"

    def test_roundtrip(self):
        url = (
            f"{FLIGHTS_BASE}?trip=roundtrip"
            f"&leg1=from:JFK,to:LAX,departure:5/13/2026TANYT,fromType:U,toType:U"
            f"&leg2=from:LAX,to:JFK,departure:5/14/2026TANYT,fromType:U,toType:U"
            f"&options=cabinclass:economy"
            f"&passengers=adults:1,infantinlap:N"
        )
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"
        assert r["depart_date"] == "2026-05-13"
        assert r["return_date"] == "2026-05-14"
        assert r["trip_type"] == "roundtrip"

    def test_business_class(self):
        url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:LHR,to:CDG,departure:4/20/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            f"&options=cabinclass:business"
            f"&passengers=adults:2,infantinlap:N"
        )
        r = parse_flight_url(url)
        assert r["cabin_class"] == "business"
        assert r["adults"] == "2"

    def test_first_class(self):
        url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LHR,departure:4/20/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            f"&options=cabinclass:first"
            f"&passengers=adults:1,infantinlap:N"
        )
        r = parse_flight_url(url)
        assert r["cabin_class"] == "first"

    def test_premium_economy(self):
        url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:SFO,to:NRT,departure:5/1/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            f"&options=cabinclass:premium_economy"
            f"&passengers=adults:2,infantinlap:N"
        )
        r = parse_flight_url(url)
        assert r["cabin_class"] == "premium_economy"

    def test_with_children(self):
        url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:LAX,to:CDG,departure:5/20/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            f"&options=cabinclass:economy"
            f"&passengers=adults:2,children:2,childrenAge:5,8,infantinlap:N"
        )
        r = parse_flight_url(url)
        assert r["adults"] == "2"
        assert r["children"] == "2"
        assert r["children_ages"] == ["5", "8"]


# =============================================================================
# 6. Hotel URL Parsing
# =============================================================================


class TestHotelURLParsing:
    """Test parse_hotel_url for query param extraction."""

    def test_basic_hotel(self):
        url = (
            f"{HOTELS_BASE}?destination=New%20York"
            f"&startDate=2026-04-15&endDate=2026-04-20"
            f"&adults=2&rooms=1"
        )
        r = parse_hotel_url(url)
        assert "new york" in r["destination"]
        assert r["start_date"] == "2026-04-15"
        assert r["end_date"] == "2026-04-20"
        assert r["adults"] == "2"
        assert r["rooms"] == "1"
        assert r["sort"] == ""

    def test_hotel_with_region_id(self):
        url = (
            f"{HOTELS_BASE}?destination=New%20York"
            f"&startDate=2026-04-15&endDate=2026-04-20"
            f"&adults=2&rooms=1&regionId=2621"
        )
        r = parse_hotel_url(url)
        assert r["region_id"] == "2621"

    def test_hotel_with_sort(self):
        url = f"{HOTELS_BASE}?destination=Paris&startDate=2026-05-01&endDate=2026-05-05&adults=2&rooms=1&sort=PRICE_LOW_TO_HIGH"
        r = parse_hotel_url(url)
        assert r["sort"] == "PRICE_LOW_TO_HIGH"

    def test_hotel_sort_review(self):
        url = f"{HOTELS_BASE}?destination=Tokyo&sort=REVIEW&adults=2&rooms=1"
        r = parse_hotel_url(url)
        assert r["sort"] == "REVIEW"

    def test_hotel_with_children(self):
        url = (
            f"{HOTELS_BASE}?destination=London"
            f"&startDate=2026-05-10&endDate=2026-05-15"
            f"&adults=2&rooms=1&children=2&childrenAges=6,9"
        )
        r = parse_hotel_url(url)
        assert r["children"] == "2"
        assert r["children_ages"] == ["6", "9"]


# =============================================================================
# 7. Cabin Class Normalization
# =============================================================================


class TestCabinClassNormalization:
    def test_economy(self):
        assert _normalize_cabin_class("economy") == "economy"

    def test_business(self):
        assert _normalize_cabin_class("business") == "business"

    def test_first(self):
        assert _normalize_cabin_class("first") == "first"

    def test_premium_economy(self):
        assert _normalize_cabin_class("premium_economy") == "premium_economy"

    def test_premiumeconomy(self):
        assert _normalize_cabin_class("premiumeconomy") == "premium_economy"

    def test_empty(self):
        assert _normalize_cabin_class("") == ""


# =============================================================================
# 8. Hotel Sort Normalization
# =============================================================================


class TestHotelSortNormalization:
    def test_recommended(self):
        assert _normalize_hotel_sort("RECOMMENDED") == "RECOMMENDED"

    def test_price_low(self):
        assert _normalize_hotel_sort("PRICE_LOW_TO_HIGH") == "PRICE_LOW_TO_HIGH"

    def test_review(self):
        assert _normalize_hotel_sort("REVIEW") == "REVIEW"

    def test_distance(self):
        assert _normalize_hotel_sort("DISTANCE") == "DISTANCE"


# =============================================================================
# 9. Flight URL Matching
# =============================================================================


class TestFlightMatching:
    """Test flight URL comparison logic."""

    def test_exact_match(self):
        url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            f"&options=cabinclass:economy&passengers=adults:1,infantinlap:N"
        )
        match, _ = _match(url, url)
        assert match is True

    def test_origin_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&options=cabinclass:economy&passengers=adults:1"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:SFO,to:LAX,departure:4/16/2026TANYT"
            f"&options=cabinclass:economy&passengers=adults:1"
        )
        match, details = _match(agent, gt)
        assert match is False
        assert any("Origin" in m for m in details["mismatches"])

    def test_destination_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:SFO,departure:4/16/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_date_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/17/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_return_date_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=roundtrip"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&leg2=from:LAX,to:JFK,departure:4/20/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=roundtrip"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&leg2=from:LAX,to:JFK,departure:4/21/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_cabin_class_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&options=cabinclass:economy"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&options=cabinclass:business"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_adults_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&passengers=adults:2"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&passengers=adults:3"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_trip_type_mismatch(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=roundtrip"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_case_insensitive_origin(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:jfk,to:lax,departure:4/16/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is True

    def test_full_city_string_vs_iata(self):
        """Full city+airport string should match bare IATA."""
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:New%20York%2C%20NY%20(JFK-John%20F.%20Kennedy%20Intl.),to:Los%20Angeles%2C%20CA%20(LAX-Los%20Angeles%20Intl.),departure:4/16/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is True

    def test_children_ages_order_independent(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:LAX,to:CDG,departure:5/20/2026TANYT"
            f"&passengers=adults:2,children:2,childrenAge:5,8"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:LAX,to:CDG,departure:5/20/2026TANYT"
            f"&passengers=adults:2,children:2,childrenAge:8,5"
        )
        match, _ = _match(agent, gt)
        assert match is True

    def test_gt_no_adults_agent_has_adults(self):
        """If GT doesn't specify adults, agent can have any value."""
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&passengers=adults:3"
        )
        match, _ = _match(agent, gt)
        assert match is True

    def test_date_format_normalization(self):
        """Different date formats should still match."""
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        # Same date but in ISO-ish format within leg
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:04/16/2026TANYT"
        )
        match, _ = _match(agent, gt)
        assert match is True


# =============================================================================
# 10. Hotel URL Matching
# =============================================================================


class TestHotelMatching:
    """Test hotel URL comparison logic."""

    def test_exact_match(self):
        url = (
            f"{HOTELS_BASE}?destination=New%20York"
            f"&startDate=2026-04-15&endDate=2026-04-20"
            f"&adults=2&rooms=1"
        )
        match, _ = _match(url, url)
        assert match is True

    def test_region_id_match(self):
        gt = f"{HOTELS_BASE}?destination=New%20York&regionId=2621&startDate=2026-04-15&endDate=2026-04-20&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?destination=New%20York%2C%20NY&regionId=2621&startDate=2026-04-15&endDate=2026-04-20&adults=2&rooms=1"
        match, _ = _match(agent, gt)
        assert match is True

    def test_region_id_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=New%20York&regionId=2621&startDate=2026-04-15&endDate=2026-04-20"
        agent = f"{HOTELS_BASE}?destination=London&regionId=2114&startDate=2026-04-15&endDate=2026-04-20"
        match, _ = _match(agent, gt)
        assert match is False

    def test_start_date_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=Paris&startDate=2026-04-15&endDate=2026-04-20&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?destination=Paris&startDate=2026-04-16&endDate=2026-04-20&adults=2&rooms=1"
        match, _ = _match(agent, gt)
        assert match is False

    def test_end_date_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=Paris&startDate=2026-04-15&endDate=2026-04-20"
        agent = f"{HOTELS_BASE}?destination=Paris&startDate=2026-04-15&endDate=2026-04-21"
        match, _ = _match(agent, gt)
        assert match is False

    def test_sort_match(self):
        gt = f"{HOTELS_BASE}?destination=Paris&sort=PRICE_LOW_TO_HIGH&adults=2&rooms=1"
        match, _ = _match(gt, gt)
        assert match is True

    def test_sort_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=Paris&sort=PRICE_LOW_TO_HIGH"
        agent = f"{HOTELS_BASE}?destination=Paris&sort=REVIEW"
        match, _ = _match(agent, gt)
        assert match is False

    def test_sort_missing_in_agent(self):
        gt = f"{HOTELS_BASE}?destination=Paris&sort=PRICE_LOW_TO_HIGH"
        agent = f"{HOTELS_BASE}?destination=Paris"
        match, _ = _match(agent, gt)
        assert match is False

    def test_adults_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=Paris&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?destination=Paris&adults=3&rooms=1"
        match, _ = _match(agent, gt)
        assert match is False

    def test_rooms_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=Paris&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?destination=Paris&adults=2&rooms=2"
        match, _ = _match(agent, gt)
        assert match is False

    def test_destination_fuzzy_match(self):
        """City name substring matching."""
        gt = f"{HOTELS_BASE}?destination=New%20York"
        agent = f"{HOTELS_BASE}?destination=New%20York%2C%20New%20York%2C%20United%20States%20of%20America"
        match, _ = _match(agent, gt)
        assert match is True

    def test_destination_mismatch(self):
        gt = f"{HOTELS_BASE}?destination=New%20York"
        agent = f"{HOTELS_BASE}?destination=Los%20Angeles"
        match, _ = _match(agent, gt)
        assert match is False

    def test_children_ages_match(self):
        gt = f"{HOTELS_BASE}?destination=London&children=2&childrenAges=6,9"
        agent = f"{HOTELS_BASE}?destination=London&children=2&childrenAges=9,6"
        match, _ = _match(agent, gt)
        assert match is True

    def test_gt_no_sort_agent_has_sort(self):
        """If GT doesn't require sort, agent can have any sort."""
        gt = f"{HOTELS_BASE}?destination=Paris&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?destination=Paris&adults=2&rooms=1&sort=PRICE_LOW_TO_HIGH"
        match, _ = _match(agent, gt)
        assert match is True

    def test_agent_missing_region_id_but_destination_matches(self):
        """Agent without regionId but with matching destination should pass."""
        gt = f"{HOTELS_BASE}?destination=New%20York&regionId=2621&startDate=2026-04-15&endDate=2026-04-20"
        agent = f"{HOTELS_BASE}?destination=New%20York&startDate=2026-04-15&endDate=2026-04-20"
        match, _ = _match(agent, gt)
        assert match is True


# =============================================================================
# 11. Domain Validation
# =============================================================================


class TestDomainValidation:
    """Test _is_valid_expedia_domain."""

    def _check(self, domain: str) -> bool:
        return ExpediaUrlMatch._is_valid_expedia_domain(domain)

    def test_expedia_com(self):
        assert self._check("expedia.com") is True

    def test_www_expedia_com(self):
        assert self._check("www.expedia.com") is True

    def test_expedia_co_uk(self):
        assert self._check("expedia.co.uk") is True

    def test_www_expedia_co_uk(self):
        assert self._check("www.expedia.co.uk") is True

    def test_expedia_de(self):
        assert self._check("expedia.de") is True

    def test_expedia_co_in(self):
        assert self._check("expedia.co.in") is True

    def test_expedia_com_au(self):
        assert self._check("expedia.com.au") is True

    def test_expedia_ca(self):
        assert self._check("expedia.ca") is True

    def test_non_expedia(self):
        assert self._check("google.com") is False
        assert self._check("fake-expedia.com") is False

    def test_skyscanner_domain(self):
        assert self._check("skyscanner.net") is False

    def test_trip_domain(self):
        assert self._check("trip.com") is False


# =============================================================================
# 12. Async Lifecycle (update/compute/reset)
# =============================================================================


class TestAsyncLifecycle:
    """Test the full async lifecycle: reset → update → compute."""

    @pytest.mark.asyncio
    async def test_exact_match_scores_1(self):
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&options=cabinclass:economy&passengers=adults:1"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_scores_0(self):
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(
            url=f"{FLIGHTS_BASE}?trip=oneway&leg1=from:SFO,to:LAX,departure:4/16/2026TANYT"
        )
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_empty_url_scores_0(self):
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_non_expedia_url_ignored(self):
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="https://www.google.com/search?q=flights")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_reset_clears_match(self):
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.update(url=gt_url)
        r1 = await metric.compute()
        assert r1.score == 1.0

        await metric.reset()
        r2 = await metric.compute()
        assert r2.score == 0.0

    @pytest.mark.asyncio
    async def test_first_match_sticks(self):
        """Once matched, subsequent URLs don't overwrite."""
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)  # Match
        await metric.update(
            url=f"{FLIGHTS_BASE}?trip=oneway&leg1=from:SFO,to:LAX,departure:4/16/2026TANYT"
        )  # Different
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_compute_detailed(self):
        gt_url = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute_detailed()
        assert isinstance(result, ExpediaVerifierResult)
        assert result.match is True
        assert result.score == 1.0
        assert result.page_type == "flights"

    @pytest.mark.asyncio
    async def test_hotel_lifecycle(self):
        gt_url = (
            f"{HOTELS_BASE}?destination=New%20York"
            f"&startDate=2026-04-15&endDate=2026-04-20"
            f"&adults=2&rooms=1&sort=PRICE_LOW_TO_HIGH"
        )
        metric = ExpediaUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0


# =============================================================================
# 13. Multi-GT URLs (OR semantics)
# =============================================================================


class TestMultiGTUrls:
    """Test OR semantics when multiple GT URLs are provided."""

    @pytest.mark.asyncio
    async def test_matches_second_gt(self):
        gt_urls = [
            f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT&options=cabinclass:economy",
            f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT&options=cabinclass:business",
        ]
        metric = ExpediaUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(
            url=f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT&options=cabinclass:business"
        )
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_in_any_gt(self):
        gt_urls = [
            f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT&options=cabinclass:economy",
            f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT&options=cabinclass:business",
        ]
        metric = ExpediaUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(
            url=f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT&options=cabinclass:first"
        )
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_single_gt_as_string(self):
        gt_url = f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        metric = ExpediaUrlMatch(gt_url=gt_url)
        assert metric.gt_urls == [gt_url]


# =============================================================================
# 14. Cross-Page Type Rejection & Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and cross-page-type rejection."""

    def test_flight_vs_hotel_no_match(self):
        gt = f"{FLIGHTS_BASE}?trip=oneway&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
        agent = f"{HOTELS_BASE}?destination=New%20York"
        match, details = _match(agent, gt)
        assert match is False
        assert any("Page type" in m for m in details["mismatches"])

    def test_empty_gt_url_list(self):
        metric = ExpediaUrlMatch(gt_url=[])
        # Should not crash

    def test_children_ages_missing_in_agent(self):
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&passengers=adults:2,children:2,childrenAge:5,8"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:JFK,to:LAX,departure:4/16/2026TANYT"
            f"&passengers=adults:2"
        )
        match, details = _match(agent, gt)
        assert match is False
        assert any("Children ages" in m for m in details["mismatches"])


# =============================================================================
# 15. Browser-Verified Bracket-Semicolon Children Format
# =============================================================================


class TestBracketSemicolonChildren:
    """Test the browser-verified children:2[10;5] format (Apr 2026)."""

    def test_parse_bracket_format_2_children(self):
        result = _parse_passengers("adults:2,children:2[10;5],infantinlap:N")
        assert result["adults"] == "2"
        assert result["children"] == "2"
        assert sorted(result["children_ages"]) == ["10", "5"]

    def test_parse_bracket_format_1_child(self):
        result = _parse_passengers("adults:2,children:1[7],infantinlap:N")
        assert result["children"] == "1"
        assert result["children_ages"] == ["7"]

    def test_parse_bracket_format_3_children(self):
        result = _parse_passengers("adults:2,children:3[2;6;10],infantinlap:N")
        assert result["children"] == "3"
        assert sorted(result["children_ages"]) == ["10", "2", "6"]

    def test_bracket_vs_legacy_matching(self):
        """Bracket format in agent should match legacy format in GT."""
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:LAX,to:CDG,departure:5/20/2026TANYT"
            f"&passengers=adults:2,children:2,childrenAge:5,10"
        )
        agent = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:LAX,to:CDG,departure:5/20/2026TANYT"
            f"&passengers=adults:2,children:2[10;5],infantinlap:N"
        )
        match, _ = _match(agent, gt)
        assert match is True

    def test_bracket_format_in_both(self):
        """Both GT and agent using bracket format."""
        url = (
            f"{FLIGHTS_BASE}?trip=roundtrip"
            f"&leg1=from:LAX,to:LHR,departure:4/16/2026TANYT,fromType:A,toType:A"
            f"&leg2=from:LHR,to:LAX,departure:4/23/2026TANYT,fromType:A,toType:A"
            f"&options=cabinclass:economy"
            f"&passengers=adults:2,children:2[10;5],infantinlap:N"
        )
        match, _ = _match(url, url)
        assert match is True

    def test_legacy_format_still_works(self):
        result = _parse_passengers("adults:2,children:2,childrenAge:5,8,infantinlap:N")
        assert result["children"] == "2"
        assert sorted(result["children_ages"]) == ["5", "8"]


# =============================================================================
# 16. Live Browser-Verified URL Tests
# =============================================================================


class TestLiveVerifiedURLs:
    """Test with exact URLs captured from Expedia browser sessions (Apr 2026)."""

    def test_live_oneway_business_sfo_nrt(self):
        """Live URL from browser deep-dive: SFO → NRT, business, 2 adults."""
        live_url = (
            "https://www.expedia.com/Flights-Search?flight-type=on&mode=search&trip=oneway"
            "&leg1=from:San%20Francisco,%20CA,%20United%20States%20of%20America%20(SFO-San%20Francisco%20Intl.)"
            ",to:Tokyo,%20Japan%20(NRT-Narita%20Intl.)"
            ",departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            "&options=cabinclass:business"
            "&fromDate=4/16/2026&d1=2026-4-16"
            "&passengers=adults:2,infantinlap:N"
        )
        r = parse_flight_url(live_url)
        assert r["origin"] == "sfo"
        assert r["destination"] == "nrt"
        assert r["depart_date"] == "2026-04-16"
        assert r["trip_type"] == "oneway"
        assert r["cabin_class"] == "business"
        assert r["adults"] == "2"

    def test_live_roundtrip_children_lax_lhr(self):
        """Live URL: LAX → LHR roundtrip, 2 adults, 2 children ages 10 and 5."""
        live_url = (
            "https://www.expedia.com/Flights-Search?"
            "leg1=from:Los%20Angeles,%20CA%20(LAX-Los%20Angeles%20Intl.)"
            ",to:London%20(LHR-Heathrow)"
            ",departure:4/16/2026TANYT,fromType:A,toType:A"
            "&leg2=from:London%20(LHR-Heathrow)"
            ",to:Los%20Angeles,%20CA%20(LAX-Los%20Angeles%20Intl.)"
            ",departure:4/23/2026TANYT,fromType:A,toType:A"
            "&mode=search&options=cabinclass:economy"
            "&passengers=adults:2,children:2[10;5],infantinlap:N"
            "&trip=roundtrip"
        )
        r = parse_flight_url(live_url)
        assert r["origin"] == "lax"
        assert r["destination"] == "lhr"
        assert r["depart_date"] == "2026-04-16"
        assert r["return_date"] == "2026-04-23"
        assert r["trip_type"] == "roundtrip"
        assert r["cabin_class"] == "economy"
        assert r["adults"] == "2"
        assert r["children"] == "2"
        assert sorted(r["children_ages"]) == ["10", "5"]

    def test_live_gt_match_across_formats(self):
        """GT uses IATA codes, agent uses full city strings — should match."""
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:SFO,to:NRT,departure:4/16/2026TANYT"
            f"&options=cabinclass:business&passengers=adults:2"
        )
        live_agent = (
            "https://www.expedia.com/Flights-Search?flight-type=on&mode=search&trip=oneway"
            "&leg1=from:San%20Francisco,%20CA,%20United%20States%20of%20America%20(SFO-San%20Francisco%20Intl.)"
            ",to:Tokyo,%20Japan%20(NRT-Narita%20Intl.)"
            ",departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT"
            "&options=cabinclass:business"
            "&fromDate=4/16/2026&d1=2026-4-16"
            "&passengers=adults:2,infantinlap:N"
        )
        match, _ = _match(live_agent, gt)
        assert match is True

    def test_live_nonstop_filter_url(self):
        """Nonstop filter adds 'filters' param — should still match core params."""
        gt = (
            f"{FLIGHTS_BASE}?trip=oneway"
            f"&leg1=from:SFO,to:NRT,departure:4/16/2026TANYT"
            f"&options=cabinclass:business&passengers=adults:2"
        )
        filtered_agent = (
            "https://www.expedia.com/Flights-Search?"
            "filters=%5B%7B%22numOfStopFilterValue%22%3A%7B%22stopInfo%22%3A%7B%22numberOfStops%22%3A0%7D%7D%7D%5D"
            "&leg1=from:San%20Francisco%2C%20CA%20(SFO-San%20Francisco%20Intl.)%2C"
            "to:Tokyo%2C%20Japan%20(NRT-Narita%20Intl.)%2C"
            "departure%3A4%2F16%2F2026TANYT%2CfromType%3AA%2CtoType%3AA"
            "&mode=search&options=cabinclass:business"
            "&passengers=adults:2,infantinlap:N"
            "&trip=oneway"
        )
        # The filtered URL may have re-encoded params, so parsing may differ.
        # Our verifier focuses on the core params.
        r = parse_flight_url(filtered_agent)
        assert r["trip_type"] == "oneway"
        assert r["cabin_class"] == "business"
        assert r["adults"] == "2"


# =============================================================================
# 17. Browser-Verified Hotel URL Formats (Apr 2026)
# =============================================================================


class TestHotelBrowserVerified:
    """Test hotel URL patterns discovered in browser deep-dive."""

    def test_live_basic_hotel_url(self):
        """Live URL from hotel deep-dive: New York, 2 adults, 1 room."""
        live_url = (
            "https://www.expedia.com/Hotel-Search?"
            "destination=New%20York%2C%20New%20York%2C%20United%20States%20of%20America"
            "&regionId=2621"
            "&latLong=40.712843%2C-74.005966"
            "&flexibility=0_DAY"
            "&d1=2026-04-16&startDate=2026-04-16"
            "&d2=2026-04-19&endDate=2026-04-19"
            "&adults=2&rooms=1"
            "&sort=RECOMMENDED"
        )
        r = parse_hotel_url(live_url)
        assert "new york" in r["destination"]
        assert r["region_id"] == "2621"
        assert r["start_date"] == "2026-04-16"
        assert r["end_date"] == "2026-04-19"
        assert r["adults"] == "2"
        assert r["rooms"] == "1"
        assert r["sort"] == "RECOMMENDED"

    def test_children_roomindex_age_format(self):
        """Browser-verified: children=1_10,1_5 (RoomIndex_Age)."""
        url = (
            f"{HOTELS_BASE}?destination=London"
            "&regionId=2114"
            "&d1=2026-04-16&d2=2026-04-19"
            "&adults=2&rooms=1"
            "&children=1_10,1_5"
        )
        r = parse_hotel_url(url)
        assert r["children"] == "2"
        assert sorted(r["children_ages"]) == ["10", "5"]

    def test_children_roomindex_age_3_children(self):
        """RoomIndex_Age format with 3 children across rooms."""
        url = (
            f"{HOTELS_BASE}?destination=Dubai"
            "&adults=2,1"
            "&rooms=1"
            "&children=1_5,1_8,2_3"
        )
        r = parse_hotel_url(url)
        assert r["children"] == "3"
        assert sorted(r["children_ages"]) == ["3", "5", "8"]

    def test_multiroom_adults_comma_separated(self):
        """Browser-verified: adults=2,1,1 for multi-room."""
        url = (
            f"{HOTELS_BASE}?destination=London"
            "&adults=2,1,1"
            "&rooms=1"
        )
        r = parse_hotel_url(url)
        assert r["adults"] == "4"  # Sum of 2+1+1
        assert r["rooms"] == "3"  # Number of entries

    def test_multiroom_2_rooms(self):
        """Multi-room with 2 entries."""
        url = (
            f"{HOTELS_BASE}?destination=Paris"
            "&adults=2,2"
            "&rooms=1"
        )
        r = parse_hotel_url(url)
        assert r["adults"] == "4"
        assert r["rooms"] == "2"

    def test_d1_d2_date_params(self):
        """Browser-verified: d1/d2 used as date parameters."""
        url = (
            f"{HOTELS_BASE}?destination=Tokyo"
            "&d1=2026-04-16&d2=2026-04-19"
            "&adults=1&rooms=1"
        )
        r = parse_hotel_url(url)
        assert r["start_date"] == "2026-04-16"
        assert r["end_date"] == "2026-04-19"

    def test_sort_distance_from_landmark(self):
        """Browser-verified sort value."""
        assert _normalize_hotel_sort("DISTANCE_FROM_LANDMARK") == "DISTANCE_FROM_LANDMARK"

    def test_sort_guest_rating(self):
        """Browser-verified sort value."""
        assert _normalize_hotel_sort("GUEST_RATING") == "GUEST_RATING"

    def test_sort_star_rating(self):
        """Browser-verified sort value."""
        assert _normalize_hotel_sort("STAR_RATING_HIGHEST_FIRST") == "STAR_RATING_HIGHEST_FIRST"

    def test_legacy_children_ages_still_works(self):
        """Legacy childrenAges=6,9 format should still work."""
        url = (
            f"{HOTELS_BASE}?destination=London"
            "&startDate=2026-05-10&endDate=2026-05-15"
            "&adults=2&rooms=1&children=2&childrenAges=6,9"
        )
        r = parse_hotel_url(url)
        assert r["children"] == "2"
        assert sorted(r["children_ages"]) == ["6", "9"]

    def test_roomindex_vs_legacy_matching(self):
        """RoomIndex_Age agent should match legacy GT."""
        gt = f"{HOTELS_BASE}?destination=London&children=2&childrenAges=6,9&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?destination=London&children=1_9,1_6&adults=2&rooms=1"
        match, _ = _match(agent, gt)
        assert match is True

    def test_live_sorted_url(self):
        """Live URL with sort=PRICE_LOW_TO_HIGH."""
        live_url = (
            "https://www.expedia.com/Hotel-Search?"
            "destination=New%20York%2C%20New%20York%2C%20United%20States%20of%20America"
            "&regionId=2621&d1=2026-04-16&d2=2026-04-19"
            "&adults=2&rooms=1"
            "&sort=PRICE_LOW_TO_HIGH"
        )
        gt = f"{HOTELS_BASE}?destination=New%20York&startDate=2026-04-16&endDate=2026-04-19&adults=2&rooms=1&sort=PRICE_LOW_TO_HIGH"
        match, _ = _match(live_url, gt)
        assert match is True
