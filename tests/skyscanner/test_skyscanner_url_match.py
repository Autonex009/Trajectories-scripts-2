"""Pytest unit tests for Skyscanner URL Match verifier.

Tests the SkyscannerUrlMatch class covering Flights, Hotels, and Car Hire
search verification with browser-verified URL patterns (Mar 2026).

Categories:
 1. Page Type Detection
 2. Flight URL Parsing — path + query params
 3. Hotel URL Parsing — query params
 4. Car Hire URL Parsing — path segments
 5. Flight Matching — origin, dest, dates, cabin, stops, airlines, alliances
 6. Hotel Matching — entity_id, dates, guests, rooms, sort
 7. Car Hire Matching — locations, datetimes, driver age
 8. Domain Validation — .net, .com, regional
 9. Async Lifecycle — reset → update → compute
10. Multi-GT URLs — OR semantics
11. Filter Order & Edge Cases
12. Real-World Multi-Filter Scenarios
13. generate_task_config Tests
"""

import pytest

from navi_bench.skyscanner.skyscanner_url_match import (
    SkyscannerUrlMatch,
    SkyscannerVerifierResult,
    detect_page_type,
    generate_task_config,
    parse_carhire_url,
    parse_flight_url,
    parse_hotel_url,
)


# =============================================================================
# Helpers
# =============================================================================

FLIGHTS_BASE = "https://www.skyscanner.net/transport/flights"
HOTELS_BASE = "https://www.skyscanner.net/hotels/search"
CARHIRE_BASE = "https://www.skyscanner.net/carhire/results"


def _match(agent_url: str, gt_url: str) -> tuple[bool, dict]:
    """Shortcut to match two URLs."""
    v = SkyscannerUrlMatch(gt_url=gt_url)
    return v._urls_match(agent_url, gt_url)


# =============================================================================
# 1. Page Type Detection
# =============================================================================


class TestPageTypeDetection:
    """Test detect_page_type function."""

    def test_flight_page(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        assert detect_page_type(url) == "flights"

    def test_hotel_page(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20"
        assert detect_page_type(url) == "hotels"

    def test_carhire_page(self):
        url = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        assert detect_page_type(url) == "carhire"

    def test_browse_page(self):
        url = "https://www.skyscanner.net/transport/flights-from/edi/"
        assert detect_page_type(url) == "browse"

    def test_multicity_page(self):
        url = "https://www.skyscanner.net/transport/d/jfk/260420/lax/lax/260425/jfk/"
        assert detect_page_type(url) == "multicity"

    def test_homepage(self):
        assert detect_page_type("https://www.skyscanner.net/") == "other"

    def test_unknown_path(self):
        assert detect_page_type("https://www.skyscanner.net/about") == "other"


# =============================================================================
# 2. Flight URL Parsing
# =============================================================================


class TestFlightURLParsing:
    """Test parse_flight_url for path and query param extraction."""

    def test_oneway_basic(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?adultsv2=1&cabinclass=economy&rtn=0"
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"
        assert r["depart_date"] == "260420"
        assert r["return_date"] == ""
        assert r["rtn"] == "0"
        assert r["adults"] == "1"
        assert r["cabin_class"] == "economy"

    def test_roundtrip_with_return_date(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/260425/?adultsv2=2&cabinclass=business&rtn=1"
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"
        assert r["depart_date"] == "260420"
        assert r["return_date"] == "260425"
        assert r["rtn"] == "1"
        assert r["adults"] == "2"
        assert r["cabin_class"] == "business"

    def test_first_class(self):
        url = f"{FLIGHTS_BASE}/lhr/jfk/260415/?cabinclass=first&rtn=0"
        r = parse_flight_url(url)
        assert r["cabin_class"] == "first"

    def test_premium_economy(self):
        url = f"{FLIGHTS_BASE}/sfo/nrt/260501/?cabinclass=premiumeconomy&rtn=0"
        r = parse_flight_url(url)
        assert r["cabin_class"] == "premiumeconomy"

    def test_children_pipe_separated(self):
        url = f"{FLIGHTS_BASE}/lax/cdg/260420/?adultsv2=2&childrenv2=5|8&rtn=0"
        r = parse_flight_url(url)
        assert r["children_ages"] == ["5", "8"]

    def test_single_child(self):
        url = f"{FLIGHTS_BASE}/lax/cdg/260420/?adultsv2=2&childrenv2=3&rtn=0"
        r = parse_flight_url(url)
        assert r["children_ages"] == ["3"]

    def test_stops_exclusion_direct(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?stops=!oneStop,!twoPlusStops&rtn=0"
        r = parse_flight_url(url)
        assert r["stops"] == {"!oneStop", "!twoPlusStops"}

    def test_stops_exclusion_1stop(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?stops=!twoPlusStops&rtn=0"
        r = parse_flight_url(url)
        assert r["stops"] == {"!twoPlusStops"}

    def test_airlines_numeric_ids(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?airlines=-32593,-32596&rtn=0"
        r = parse_flight_url(url)
        assert r["airlines"] == {"-32593", "-32596"}

    def test_alliances(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=Star%20Alliance,SkyTeam&rtn=0"
        r = parse_flight_url(url)
        assert r["alliances"] == {"star alliance", "skyteam"}

    def test_alliances_oneworld(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=oneworld&rtn=0"
        r = parse_flight_url(url)
        assert r["alliances"] == {"oneworld"}

    def test_case_insensitive_origin_dest(self):
        url = f"{FLIGHTS_BASE}/JFK/LAX/260420/?rtn=0"
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"

    def test_no_query_params(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/"
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"
        assert r["depart_date"] == "260420"
        assert r["rtn"] == ""
        assert r["adults"] == ""
        assert r["cabin_class"] == ""

    def test_prefer_directs(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?preferdirects=true&rtn=0"
        r = parse_flight_url(url)
        assert r["prefer_directs"] == "true"


# =============================================================================
# 3. Hotel URL Parsing
# =============================================================================


class TestHotelURLParsing:
    """Test parse_hotel_url for query param extraction."""

    def test_basic_hotel(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&rooms=1"
        r = parse_hotel_url(url)
        assert r["entity_id"] == "27544008"
        assert r["checkin"] == "2026-04-20"
        assert r["checkout"] == "2026-04-25"
        assert r["adults"] == "2"
        assert r["rooms"] == "1"
        assert r["sort"] == ""

    def test_hotel_with_sort_price(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&rooms=1&sort=price"
        r = parse_hotel_url(url)
        assert r["sort"] == "price"

    def test_hotel_with_sort_neg_price(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&sort=-price"
        r = parse_hotel_url(url)
        assert r["sort"] == "-price"

    def test_hotel_with_sort_rating(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&sort=-hotel_rating"
        r = parse_hotel_url(url)
        assert r["sort"] == "-hotel_rating"

    def test_hotel_with_sort_distance(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&sort=distance"
        r = parse_hotel_url(url)
        assert r["sort"] == "distance"

    def test_hotel_3_adults_2_rooms(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&adults=3&rooms=2"
        r = parse_hotel_url(url)
        assert r["adults"] == "3"
        assert r["rooms"] == "2"

    def test_hotel_no_dates(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&adults=2&rooms=1"
        r = parse_hotel_url(url)
        assert r["entity_id"] == "27544008"
        assert r["checkin"] == ""
        assert r["checkout"] == ""


# =============================================================================
# 4. Car Hire URL Parsing
# =============================================================================


class TestCarHireURLParsing:
    """Test parse_carhire_url for path segment extraction."""

    def test_basic_carhire(self):
        url = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        r = parse_carhire_url(url)
        assert r["pickup_location"] == "bcn"
        assert r["dropoff_location"] == "bcn"
        assert r["pickup_datetime"] == "2026-04-20T10:00"
        assert r["dropoff_datetime"] == "2026-04-25T10:00"
        assert r["driver_age"] == "30"

    def test_numeric_location_ids(self):
        """Browser-verified: Skyscanner uses numeric IDs not IATA codes."""
        url = f"{CARHIRE_BASE}/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30"
        r = parse_carhire_url(url)
        assert r["pickup_location"] == "95565085"
        assert r["dropoff_location"] == "95565085"
        assert r["pickup_datetime"] == "2026-04-20T10:00"
        assert r["dropoff_datetime"] == "2026-04-25T10:00"
        assert r["driver_age"] == "30"

    def test_different_numeric_ids(self):
        """Different numeric pickup and dropoff IDs (LHR to LGW)."""
        url = f"{CARHIRE_BASE}/95565050/95565051/2026-05-01T08:00/2026-05-05T18:00/35"
        r = parse_carhire_url(url)
        assert r["pickup_location"] == "95565050"
        assert r["dropoff_location"] == "95565051"

    def test_no_driver_age(self):
        url = f"{CARHIRE_BASE}/CDG/CDG/2026-04-25T12:00/2026-04-28T12:00"
        r = parse_carhire_url(url)
        assert r["pickup_location"] == "cdg"
        assert r["dropoff_location"] == "cdg"
        assert r["pickup_datetime"] == "2026-04-25T12:00"
        assert r["dropoff_datetime"] == "2026-04-28T12:00"
        assert r["driver_age"] == ""

    def test_case_insensitive_location(self):
        url = f"{CARHIRE_BASE}/bcn/bcn/2026-04-20T10:00/2026-04-25T10:00/30"
        r = parse_carhire_url(url)
        assert r["pickup_location"] == "bcn"


# =============================================================================
# 5. Flight URL Matching
# =============================================================================


class TestFlightMatching:
    """Test flight URL comparison logic."""

    def test_exact_match(self):
        url = f"{FLIGHTS_BASE}/jfk/lax/260420/?adultsv2=1&cabinclass=economy&rtn=0"
        match, _ = _match(url, url)
        assert match is True

    def test_origin_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{FLIGHTS_BASE}/sfo/lax/260420/?rtn=0"
        match, details = _match(agent, gt)
        assert match is False
        assert any("Origin" in m for m in details["mismatches"])

    def test_destination_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/sfo/260420/?rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_date_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260421/?rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_return_date_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/260425/?rtn=1"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/260426/?rtn=1"
        match, _ = _match(agent, gt)
        assert match is False

    def test_cabin_class_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=economy&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=business&rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_stops_match(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?stops=!oneStop,!twoPlusStops&rtn=0"
        match, _ = _match(gt, gt)
        assert match is True

    def test_stops_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?stops=!oneStop,!twoPlusStops&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?stops=!twoPlusStops&rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_stops_missing_in_agent(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?stops=!oneStop,!twoPlusStops&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_airlines_match(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?airlines=-32593,-32596&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?airlines=-32596,-32593&rtn=0"
        match, _ = _match(agent, gt)
        assert match is True  # Set comparison, order independent

    def test_airlines_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?airlines=-32593&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?airlines=-32596&rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_alliances_match_case_insensitive(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=Star%20Alliance,SkyTeam&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=star%20alliance,skyteam&rtn=0"
        match, _ = _match(agent, gt)
        assert match is True

    def test_alliances_with_spaces(self):
        """Browser-verified: Star Alliance has a space."""
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=Star%20Alliance&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=Star Alliance&rtn=0"
        match, _ = _match(agent, gt)
        assert match is True

    def test_alliances_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=Star%20Alliance&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?alliances=oneworld&rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_children_order_independent(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?childrenv2=5|8&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?childrenv2=8|5&rtn=0"
        match, _ = _match(agent, gt)
        assert match is True

    def test_adults_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?adultsv2=2&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?adultsv2=3&rtn=0"
        match, _ = _match(agent, gt)
        assert match is False

    def test_rtn_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=1"
        match, _ = _match(agent, gt)
        assert match is False

    def test_case_insensitive_origin(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{FLIGHTS_BASE}/JFK/LAX/260420/?rtn=0"
        match, _ = _match(agent, gt)
        assert match is True

    def test_gt_no_adults_agent_has_adults(self):
        """If GT doesn't specify adults, agent can have any value."""
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?adultsv2=3&rtn=0"
        match, _ = _match(agent, gt)
        assert match is True

    def test_prefer_directs_mismatch(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?preferdirects=true&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lax/260420/?preferdirects=false&rtn=0"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 6. Hotel URL Matching
# =============================================================================


class TestHotelMatching:
    """Test hotel URL comparison logic."""

    def test_exact_match(self):
        url = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&rooms=1"
        match, _ = _match(url, url)
        assert match is True

    def test_entity_id_mismatch(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20"
        agent = f"{HOTELS_BASE}?entity_id=12345678&checkin=2026-04-20"
        match, _ = _match(agent, gt)
        assert match is False

    def test_checkin_mismatch(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25"
        agent = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-21&checkout=2026-04-25"
        match, _ = _match(agent, gt)
        assert match is False

    def test_checkout_mismatch(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25"
        agent = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-26"
        match, _ = _match(agent, gt)
        assert match is False

    def test_sort_match_price(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&sort=price"
        match, _ = _match(gt, gt)
        assert match is True

    def test_sort_match_neg_rating(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&sort=-hotel_rating"
        match, _ = _match(gt, gt)
        assert match is True

    def test_sort_mismatch(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&sort=price"
        agent = f"{HOTELS_BASE}?entity_id=27544008&sort=-hotel_rating"
        match, _ = _match(agent, gt)
        assert match is False

    def test_sort_missing_in_agent(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&sort=price"
        agent = f"{HOTELS_BASE}?entity_id=27544008"
        match, _ = _match(agent, gt)
        assert match is False

    def test_adults_mismatch(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?entity_id=27544008&adults=3&rooms=1"
        match, _ = _match(agent, gt)
        assert match is False

    def test_rooms_mismatch(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008&adults=2&rooms=1"
        agent = f"{HOTELS_BASE}?entity_id=27544008&adults=2&rooms=2"
        match, _ = _match(agent, gt)
        assert match is False

    def test_entity_id_missing_in_agent(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008"
        agent = f"{HOTELS_BASE}?checkin=2026-04-20"
        match, details = _match(agent, gt)
        assert match is False
        assert any("entity_id" in m for m in details["mismatches"])

    def test_gt_no_sort_agent_has_sort(self):
        """If GT doesn't require sort, agent can have any sort."""
        gt = f"{HOTELS_BASE}?entity_id=27544008"
        agent = f"{HOTELS_BASE}?entity_id=27544008&sort=price"
        match, _ = _match(agent, gt)
        assert match is True


# =============================================================================
# 7. Car Hire URL Matching
# =============================================================================


class TestCarHireMatching:
    """Test car hire URL comparison logic."""

    def test_exact_match(self):
        url = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(url, url)
        assert match is True

    def test_numeric_id_match(self):
        """Browser-verified: car hire uses numeric IDs."""
        url = f"{CARHIRE_BASE}/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(url, url)
        assert match is True

    def test_numeric_pickup_location_mismatch(self):
        gt = f"{CARHIRE_BASE}/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/95565050/95565085/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_iata_vs_numeric_id_mismatch(self):
        """IATA code and numeric ID are NOT interchangeable."""
        gt = f"{CARHIRE_BASE}/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_pickup_location_mismatch(self):
        gt = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/MAD/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_dropoff_location_mismatch(self):
        gt = f"{CARHIRE_BASE}/LHR/LGW/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/LHR/STN/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_pickup_datetime_mismatch(self):
        gt = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T12:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_dropoff_datetime_mismatch(self):
        gt = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-26T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_driver_age_mismatch(self):
        gt = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/42"
        match, _ = _match(agent, gt)
        assert match is False

    def test_driver_age_optional(self):
        """If GT has no age, agent's age doesn't matter."""
        gt = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/42"
        match, _ = _match(agent, gt)
        assert match is True

    def test_case_insensitive_location(self):
        gt = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        agent = f"{CARHIRE_BASE}/bcn/bcn/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is True


# =============================================================================
# 8. Domain Validation
# =============================================================================


class TestDomainValidation:
    """Test _is_valid_skyscanner_domain."""

    def _check(self, domain: str) -> bool:
        return SkyscannerUrlMatch._is_valid_skyscanner_domain(domain)

    def test_skyscanner_net(self):
        assert self._check("skyscanner.net") is True

    def test_www_skyscanner_net(self):
        assert self._check("www.skyscanner.net") is True

    def test_skyscanner_com(self):
        assert self._check("skyscanner.com") is True

    def test_www_skyscanner_com(self):
        assert self._check("www.skyscanner.com") is True

    def test_skyscanner_co_in(self):
        assert self._check("skyscanner.co.in") is True

    def test_www_skyscanner_co_in(self):
        assert self._check("www.skyscanner.co.in") is True

    def test_skyscanner_co_uk(self):
        assert self._check("skyscanner.co.uk") is True

    def test_skyscanner_de(self):
        assert self._check("skyscanner.de") is True

    def test_skyscanner_jp(self):
        assert self._check("skyscanner.jp") is True

    def test_skyscanner_com_au(self):
        assert self._check("skyscanner.com.au") is True

    def test_non_skyscanner(self):
        assert self._check("google.com") is False
        assert self._check("fake-skyscanner.net") is False

    def test_kayak_domain(self):
        assert self._check("kayak.com") is False

    def test_trip_domain(self):
        assert self._check("trip.com") is False


# =============================================================================
# 9. Async Lifecycle (update/compute/reset)
# =============================================================================


class TestAsyncLifecycle:
    """Test the full async lifecycle: reset → update → compute."""

    @pytest.mark.asyncio
    async def test_exact_match_scores_1(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?adultsv2=1&cabinclass=economy&rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_scores_0(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=f"{FLIGHTS_BASE}/sfo/lax/260420/?rtn=0")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_empty_url_scores_0(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_non_skyscanner_url_ignored(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="https://www.google.com/search?q=flights")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_reset_clears_match(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.update(url=gt_url)
        r1 = await metric.compute()
        assert r1.score == 1.0

        await metric.reset()
        r2 = await metric.compute()
        assert r2.score == 0.0

    @pytest.mark.asyncio
    async def test_first_match_sticks(self):
        """Once matched, subsequent URLs don't overwrite."""
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)  # Match
        await metric.update(url=f"{FLIGHTS_BASE}/sfo/lax/260420/?rtn=0")  # Different
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_multiple_updates_before_match(self):
        """Multiple non-matching updates followed by eventual match."""
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=business&rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=economy&rtn=0")
        await metric.update(url=f"{FLIGHTS_BASE}/sfo/lax/260420/?rtn=0")
        await metric.update(url=gt_url)  # Match!
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_compute_detailed(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute_detailed()
        assert isinstance(result, SkyscannerVerifierResult)
        assert result.match is True
        assert result.score == 1.0
        assert result.page_type == "flights"

    @pytest.mark.asyncio
    async def test_hotel_lifecycle(self):
        gt_url = f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&sort=price"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_carhire_lifecycle(self):
        gt_url = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0


# =============================================================================
# 10. Multi-GT URLs (OR semantics)
# =============================================================================


class TestMultiGTUrls:
    """Test OR semantics when multiple GT URLs are provided."""

    @pytest.mark.asyncio
    async def test_matches_second_gt(self):
        gt_urls = [
            f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=economy&rtn=0",
            f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=business&rtn=0",
        ]
        metric = SkyscannerUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=business&rtn=0")
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_in_any_gt(self):
        gt_urls = [
            f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=economy&rtn=0",
            f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=business&rtn=0",
        ]
        metric = SkyscannerUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=f"{FLIGHTS_BASE}/jfk/lax/260420/?cabinclass=first&rtn=0")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_single_gt_as_string(self):
        gt_url = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        metric = SkyscannerUrlMatch(gt_url=gt_url)
        assert metric.gt_urls == [gt_url]


# =============================================================================
# 11. Cross-Page Type Rejection & Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and cross-page-type rejection."""

    def test_flight_vs_hotel_no_match(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{HOTELS_BASE}?entity_id=27544008"
        match, details = _match(agent, gt)
        assert match is False
        assert any("Page type" in m for m in details["mismatches"])

    def test_flight_vs_carhire_no_match(self):
        gt = f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_hotel_vs_carhire_no_match(self):
        gt = f"{HOTELS_BASE}?entity_id=27544008"
        agent = f"{CARHIRE_BASE}/BCN/BCN/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(agent, gt)
        assert match is False

    def test_empty_gt_url_list(self):
        metric = SkyscannerUrlMatch(gt_url=[])
        # Should not crash

    @pytest.mark.asyncio
    async def test_empty_gt_url_never_matches(self):
        metric = SkyscannerUrlMatch(gt_url=[])
        await metric.reset()
        await metric.update(url=f"{FLIGHTS_BASE}/jfk/lax/260420/?rtn=0")
        result = await metric.compute()
        assert result.score == 0.0

    def test_malformed_flight_url(self):
        """URL with incomplete path should still parse without crashing."""
        r = parse_flight_url("https://www.skyscanner.net/transport/flights/")
        assert r["origin"] == ""
        assert r["destination"] == ""

    def test_malformed_carhire_url(self):
        """URL with incomplete path should still parse without crashing."""
        r = parse_carhire_url("https://www.skyscanner.net/carhire/results/")
        assert r["pickup_location"] == ""

    def test_malformed_hotel_url(self):
        """URL with no params should still parse without crashing."""
        r = parse_hotel_url("https://www.skyscanner.net/hotels/search")
        assert r["entity_id"] == ""


# =============================================================================
# 12. Real-World Multi-Filter Scenarios
# =============================================================================


class TestRealWorldScenarios:
    """Test real-world scenarios combining multiple filters."""

    def test_business_direct_roundtrip(self):
        """Business class, direct only, round-trip."""
        gt = (
            f"{FLIGHTS_BASE}/lhr/jfk/260420/260427/"
            "?adultsv2=1&cabinclass=business&rtn=1&stops=!oneStop,!twoPlusStops"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_family_oneway_economy(self):
        """2 adults + 2 children, one-way economy."""
        gt = f"{FLIGHTS_BASE}/lax/cdg/260420/?adultsv2=2&childrenv2=5|8&cabinclass=economy&rtn=0"
        match, _ = _match(gt, gt)
        assert match is True

    def test_hotel_full_params(self):
        """Hotel with all params populated."""
        gt = (
            f"{HOTELS_BASE}?entity_id=27544008&checkin=2026-04-20"
            "&checkout=2026-04-25&adults=2&rooms=1&sort=price"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_carhire_numeric_ids(self):
        """Car hire with browser-verified numeric IDs."""
        gt = f"{CARHIRE_BASE}/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30"
        match, _ = _match(gt, gt)
        assert match is True

    def test_carhire_different_numeric_ids(self):
        """Car hire with different pickup and dropoff numeric IDs."""
        gt = f"{CARHIRE_BASE}/95565050/95565051/2026-05-01T08:00/2026-05-05T18:00/35"
        match, _ = _match(gt, gt)
        assert match is True

    def test_carhire_different_locations(self):
        """Car hire with different pickup and dropoff (IATA legacy)."""
        gt = f"{CARHIRE_BASE}/LHR/LGW/2026-05-01T08:00/2026-05-05T18:00/35"
        match, _ = _match(gt, gt)
        assert match is True

    def test_domain_difference_still_matches(self):
        """Same search on different Skyscanner domains should match."""
        gt = "https://www.skyscanner.net/transport/flights/jfk/lax/260420/?rtn=0"
        agent = "https://www.skyscanner.co.in/transport/flights/jfk/lax/260420/?rtn=0"
        match, _ = _match(agent, gt)
        assert match is True

    def test_regional_hotel_domain(self):
        """Hotel search on regional domain."""
        gt = f"{HOTELS_BASE}?entity_id=27544008&sort=price"
        agent = "https://www.skyscanner.co.uk/hotels/search?entity_id=27544008&sort=price"
        match, _ = _match(agent, gt)
        assert match is True

    def test_3adults_premiumeconomy_direct(self):
        """3 adults, premium economy, direct only."""
        gt = (
            f"{FLIGHTS_BASE}/dxb/lhr/260501/"
            "?adultsv2=3&cabinclass=premiumeconomy&rtn=0&stops=!oneStop,!twoPlusStops"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_alliance_filter_flight(self):
        """Flight with alliance filter."""
        gt = f"{FLIGHTS_BASE}/jfk/lhr/260420/?alliances=oneworld&rtn=0"
        match, _ = _match(gt, gt)
        assert match is True

    def test_multi_alliance_flight(self):
        """Flight with multiple alliances including spaces."""
        gt = f"{FLIGHTS_BASE}/jfk/lhr/260420/?alliances=Star%20Alliance,SkyTeam&rtn=0"
        agent = f"{FLIGHTS_BASE}/jfk/lhr/260420/?alliances=SkyTeam,Star%20Alliance&rtn=0"
        match, _ = _match(agent, gt)
        assert match is True  # Set comparison, order independent

    def test_1stop_max_economy(self):
        """At most 1 stop, economy."""
        gt = f"{FLIGHTS_BASE}/ord/mia/260420/?adultsv2=1&cabinclass=economy&rtn=0&stops=!twoPlusStops"
        match, _ = _match(gt, gt)
        assert match is True


# =============================================================================
# 13. generate_task_config Tests
# =============================================================================


class TestGenerateTaskConfig:
    """Test task config generation utility."""

    def test_basic_config_generation(self):
        config = generate_task_config(
            task="Search for flights from JFK to LAX",
            location="New York, NY, USA",
            timezone="America/New_York",
            gt_url=["https://www.skyscanner.net/transport/flights/jfk/lax/260420/?rtn=0"],
        )
        assert config.task == "Search for flights from JFK to LAX"
        assert config.url == "https://www.skyscanner.net/"

    def test_config_with_ground_truth_url_string(self):
        config = generate_task_config(
            task="Search flights",
            location="New York, NY, USA",
            timezone="America/New_York",
            ground_truth_url="https://www.skyscanner.net/transport/flights/jfk/lax/260420/?rtn=0",
        )
        assert config.eval_config["gt_url"] == [
            "https://www.skyscanner.net/transport/flights/jfk/lax/260420/?rtn=0"
        ]

    def test_config_raises_without_urls(self):
        with pytest.raises(ValueError, match="Either 'gt_url' or 'ground_truth_url'"):
            generate_task_config(
                task="Search flights",
                location="New York, NY, USA",
                timezone="America/New_York",
            )

    def test_config_custom_start_url(self):
        config = generate_task_config(
            task="Search",
            location="London, UK",
            timezone="Europe/London",
            gt_url=["https://www.skyscanner.net/transport/flights/lhr/cdg/260420/?rtn=0"],
            url="https://www.skyscanner.co.uk/",
        )
        assert config.url == "https://www.skyscanner.co.uk/"

    def test_eval_config_target(self):
        config = generate_task_config(
            task="Test",
            location="Test",
            timezone="UTC",
            gt_url=["https://www.skyscanner.net/transport/flights/jfk/lax/260420/"],
        )
        assert "SkyscannerUrlMatch" in config.eval_config["_target_"]


# =============================================================================
# 14. ISO Date Format Tests (critical regex bug fix)
# =============================================================================
# Before the fix, parse_flight_url only matched 6-digit YYMMDD dates.
# dates.py always produces YYYY-MM-DD, so origin/dest/dates were empty
# and any flight URL would silently score 1.0 (false positive).


class TestISODateFormat:
    def test_iso_oneway_parses_origin_dest_date(self):
        url = FLIGHTS_BASE + "/jfk/lax/2026-04-20/?adultsv2=1&cabinclass=economy&rtn=0"
        r = parse_flight_url(url)
        assert r["origin"] == "jfk"
        assert r["destination"] == "lax"
        assert r["depart_date"] == "2026-04-20"
        assert r["return_date"] == ""

    def test_iso_roundtrip_parses_both_dates(self):
        url = FLIGHTS_BASE + "/jfk/lax/2026-04-20/2026-04-25/?adultsv2=1&rtn=1"
        r = parse_flight_url(url)
        assert r["depart_date"] == "2026-04-20"
        assert r["return_date"] == "2026-04-25"

    def test_iso_exact_match_passes(self):
        url = FLIGHTS_BASE + "/jfk/lax/2026-04-20/?adultsv2=1&cabinclass=economy&rtn=0"
        match, details = _match(url, url)
        assert match is True, "Expected match: " + str(details.get("mismatches"))

    def test_iso_origin_mismatch_detected(self):
        # Before fix: regex failed -> origin empty -> mismatch skipped -> false positive
        gt = FLIGHTS_BASE + "/jfk/lax/2026-04-20/?rtn=0"
        agent = FLIGHTS_BASE + "/syd/mel/2026-04-20/?rtn=0"
        match, details = _match(agent, gt)
        assert match is False
        assert any("rigin" in m for m in details["mismatches"])

    def test_iso_and_yymmdd_no_cross_match(self):
        # YYMMDD GT vs ISO agent: different string literals
        gt = FLIGHTS_BASE + "/jfk/lax/260420/?rtn=0"
        agent = FLIGHTS_BASE + "/jfk/lax/2026-04-20/?rtn=0"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 15. Hotel Children Encoding Tests (children=N&children_ages=X,Y)
# =============================================================================
# Bug fixed: parse_hotel_url previously did not parse children/children_ages.
# _match_hotel_urls previously did not check them — false positives for all
# hotel-children tasks (8 tasks in the benchmark).


class TestHotelChildrenEncoding:
    def test_hotel_parses_children_count_and_ages(self):
        url = HOTELS_BASE + "?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&children=2&children_ages=6,9&rooms=1"
        r = parse_hotel_url(url)
        assert r["children"] == "2"
        assert sorted(r["children_ages"]) == ["6", "9"]

    def test_hotel_parses_3_children_ages(self):
        url = HOTELS_BASE + "?entity_id=27544008&adults=2&children=3&children_ages=5,8,11"
        r = parse_hotel_url(url)
        assert r["children"] == "3"
        assert sorted(r["children_ages"]) == ["11", "5", "8"]

    def test_hotel_children_match_passes(self):
        url = HOTELS_BASE + "?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&children=2&children_ages=6,9&rooms=1"
        v = SkyscannerUrlMatch(gt_url=url)
        match, details = v._urls_match(url, url)
        assert match is True, str(details)

    def test_hotel_children_ages_mismatch_detected(self):
        # Before fix: children_ages not checked -> would return True (false positive)
        gt = HOTELS_BASE + "?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&children=2&children_ages=6,9&rooms=1"
        agent = HOTELS_BASE + "?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&rooms=1"
        v = SkyscannerUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert any("children_ages" in m for m in details["mismatches"])

    def test_hotel_children_age_order_independent(self):
        # Ages 5,8,11 vs 11,5,8 should still match (sorted comparison)
        gt = HOTELS_BASE + "?entity_id=27544008&adults=2&children=3&children_ages=5,8,11"
        agent = HOTELS_BASE + "?entity_id=27544008&adults=2&children=3&children_ages=11,5,8"
        v = SkyscannerUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is True, str(details)
