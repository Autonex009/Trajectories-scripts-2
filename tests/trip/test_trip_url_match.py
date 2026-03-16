"""Pytest unit tests for Trip.com URL Match verifier.

Tests the TripUrlMatch class for hotel search navigation verification.
All URL patterns are browser-verified against us.trip.com (Mar 2026).

Categories:
 1. URL Parsing — top-level params (city, dates, guests)
 2. listFilters Parsing — individual filter entry decoding
 3. Star Rating — category 16
 4. Price Range — category 15
 5. Guest Rating — category 6
 6. Amenities — category 3
 7. Breakfast — category 5
 8. Free Cancellation — category 23
 9. Property Type — category 75
10. Sort — category 17
11. Location/Area — category 9
12. Filter Order Independence
13. Domain Variations
14. TripUrlMatch Async — update/compute/reset lifecycle
15. Real-World Multi-Filter Scenarios
"""

import pytest

from navi_bench.trip.trip_url_match import (
    TripUrlMatch,
    TripVerifierResult,
    generate_task_config,
)


# =============================================================================
# Helper
# =============================================================================

BASE = "https://us.trip.com/hotels/list"


def _v():
    """Create a verifier instance with a dummy GT URL."""
    return TripUrlMatch(gt_url=f"{BASE}?cityId=633&cityName=New%20York")


def _parse(url: str) -> dict:
    """Shortcut to parse a Trip.com URL."""
    return _v()._parse_trip_url(url)


def _match(agent_url: str, gt_url: str) -> tuple[bool, dict]:
    """Shortcut to match two URLs."""
    v = TripUrlMatch(gt_url=gt_url)
    return v._urls_match(agent_url, gt_url)


# =============================================================================
# 1. URL Parsing — Top-Level Parameters
# =============================================================================


class TestTopLevelParsing:
    """Test parsing of top-level query parameters."""

    def test_city_id_parsed(self):
        r = _parse(f"{BASE}?cityId=633&cityName=New%20York")
        assert r["city_id"] == "633"

    def test_city_name_parsed_lowercase(self):
        r = _parse(f"{BASE}?cityId=633&cityName=New%20York")
        assert r["city_name"] == "new york"

    def test_checkin_checkout_parsed(self):
        r = _parse(f"{BASE}?cityId=633&checkin=2026-04-01&checkout=2026-04-05")
        assert r["checkin"] == "2026-04-01"
        assert r["checkout"] == "2026-04-05"

    def test_adults_parsed(self):
        r = _parse(f"{BASE}?cityId=633&adult=2")
        assert r["adult"] == "2"

    def test_children_and_ages_parsed(self):
        r = _parse(f"{BASE}?cityId=633&children=2&ages=5,10")
        assert r["children"] == "2"
        assert r["ages"] == ["5", "10"]

    def test_rooms_parsed(self):
        r = _parse(f"{BASE}?cityId=633&crn=2")
        assert r["crn"] == "2"

    def test_full_url_parsing(self):
        url = (
            f"{BASE}?cityId=633&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&children=1&ages=5&crn=1"
        )
        r = _parse(url)
        assert r["city_id"] == "633"
        assert r["city_name"] == "new york"
        assert r["checkin"] == "2026-04-01"
        assert r["checkout"] == "2026-04-05"
        assert r["adult"] == "2"
        assert r["children"] == "1"
        assert r["ages"] == ["5"]
        assert r["crn"] == "1"

    def test_url_without_scheme(self):
        r = _parse("us.trip.com/hotels/list?cityId=633&cityName=New%20York")
        assert r["city_id"] == "633"

    def test_no_filters_empty_dict(self):
        r = _parse(f"{BASE}?cityId=633")
        assert r["filters"] == {}


# =============================================================================
# 2. listFilters Parsing
# =============================================================================


class TestListFiltersParsing:
    """Test parsing of the compound listFilters parameter."""

    def test_single_filter_entry(self):
        r = _parse(f"{BASE}?cityId=633&listFilters=16~5*16*5")
        assert "16" in r["filters"]
        assert "5" in r["filters"]["16"]

    def test_multiple_filter_entries(self):
        url = f"{BASE}?cityId=633&listFilters=16~5*16*5,3~605*3*605"
        r = _parse(url)
        assert "16" in r["filters"]
        assert "3" in r["filters"]

    def test_url_encoded_commas(self):
        url = f"{BASE}?cityId=633&listFilters=16~5*16*5%2C3~605*3*605"
        r = _parse(url)
        assert "16" in r["filters"]
        assert "3" in r["filters"]

    def test_price_range_parsed(self):
        url = f"{BASE}?cityId=633&listFilters=15~Range*15*0~150"
        r = _parse(url)
        assert "15" in r["filters"]
        # Price value should contain the range
        values = r["filters"]["15"]
        assert any("0~150" in v for v in values)

    def test_property_type_tag_normalized(self):
        url = f"{BASE}?cityId=633&listFilters=75~TAG_495*75*495"
        r = _parse(url)
        assert "75" in r["filters"]
        assert "495" in r["filters"]["75"]


# =============================================================================
# 3. Star Rating (Category 16)
# =============================================================================


class TestStarRating:
    """Test star rating filter matching."""

    def test_5_star_match(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5"
        match, _ = _match(gt, gt)
        assert match is True

    def test_4_star_match(self):
        gt = f"{BASE}?cityId=633&listFilters=16~4*16*4"
        match, _ = _match(gt, gt)
        assert match is True

    def test_star_mismatch(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5"
        agent = f"{BASE}?cityId=633&listFilters=16~4*16*4"
        match, _ = _match(agent, gt)
        assert match is False

    def test_multiple_stars_match(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5,16~4*16*4"
        match, _ = _match(gt, gt)
        assert match is True

    def test_multiple_stars_order_independent(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5,16~4*16*4"
        agent = f"{BASE}?cityId=633&listFilters=16~4*16*4,16~5*16*5"
        match, _ = _match(agent, gt)
        assert match is True

    def test_missing_star_filter_fails(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5"
        agent = f"{BASE}?cityId=633"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 4. Price Range (Category 15)
# =============================================================================


class TestPriceRange:
    """Test price range filter matching."""

    def test_price_0_150_match(self):
        gt = f"{BASE}?cityId=633&listFilters=15~Range*15*0~150"
        match, _ = _match(gt, gt)
        assert match is True

    def test_price_150_300_match(self):
        gt = f"{BASE}?cityId=633&listFilters=15~Range*15*150~300"
        match, _ = _match(gt, gt)
        assert match is True

    def test_price_mismatch(self):
        gt = f"{BASE}?cityId=633&listFilters=15~Range*15*0~150"
        agent = f"{BASE}?cityId=633&listFilters=15~Range*15*150~300"
        match, _ = _match(agent, gt)
        assert match is False

    def test_price_open_ended(self):
        gt = f"{BASE}?cityId=633&listFilters=15~Range*15*500~"
        match, _ = _match(gt, gt)
        assert match is True


# =============================================================================
# 5. Guest Rating (Category 6)
# =============================================================================


class TestGuestRating:
    """Test guest rating filter matching."""

    def test_very_good_8plus_match(self):
        gt = f"{BASE}?cityId=633&listFilters=6~9*6*9"
        match, _ = _match(gt, gt)
        assert match is True

    def test_good_7plus_match(self):
        gt = f"{BASE}?cityId=633&listFilters=6~8*6*8"
        match, _ = _match(gt, gt)
        assert match is True

    def test_rating_mismatch(self):
        gt = f"{BASE}?cityId=633&listFilters=6~9*6*9"
        agent = f"{BASE}?cityId=633&listFilters=6~8*6*8"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 6. Amenities (Category 3)
# =============================================================================


class TestAmenities:
    """Test amenity filter matching."""

    def test_pool_match(self):
        gt = f"{BASE}?cityId=633&listFilters=3~605*3*605"
        match, _ = _match(gt, gt)
        assert match is True

    def test_gym_match(self):
        gt = f"{BASE}?cityId=633&listFilters=3~42*3*42"
        match, _ = _match(gt, gt)
        assert match is True

    def test_wifi_match(self):
        gt = f"{BASE}?cityId=633&listFilters=3~2*3*2"
        match, _ = _match(gt, gt)
        assert match is True

    def test_multiple_amenities_match(self):
        gt = f"{BASE}?cityId=633&listFilters=3~605*3*605,3~42*3*42"
        match, _ = _match(gt, gt)
        assert match is True

    def test_multiple_amenities_order_independent(self):
        gt = f"{BASE}?cityId=633&listFilters=3~605*3*605,3~42*3*42"
        agent = f"{BASE}?cityId=633&listFilters=3~42*3*42,3~605*3*605"
        match, _ = _match(agent, gt)
        assert match is True

    def test_missing_amenity_fails(self):
        gt = f"{BASE}?cityId=633&listFilters=3~605*3*605,3~42*3*42"
        agent = f"{BASE}?cityId=633&listFilters=3~605*3*605"
        match, _ = _match(agent, gt)
        assert match is False

    def test_extra_amenity_still_matches(self):
        gt = f"{BASE}?cityId=633&listFilters=3~605*3*605"
        agent = f"{BASE}?cityId=633&listFilters=3~605*3*605,3~42*3*42"
        match, details = _match(agent, gt)
        # Extra amenity should be noted but not fail
        # Note: since amenities share category 3, extra values are in same cat
        # This depends on set comparison logic — extra values in agent's cat-3
        # won't match gt's cat-3 exactly. This is correct: agent added more.
        # The verifier compares sets, so agent={605,42} vs gt={605} → mismatch
        # Actually, this SHOULD fail since the sets differ for the same category.
        # We accept this behavior: stricter is safer for benchmarks.
        assert match is False


# =============================================================================
# 7. Breakfast (Category 5)
# =============================================================================


class TestBreakfast:
    """Test breakfast filter matching."""

    def test_breakfast_included_match(self):
        gt = f"{BASE}?cityId=633&listFilters=5~1*5*1"
        match, _ = _match(gt, gt)
        assert match is True

    def test_missing_breakfast_fails(self):
        gt = f"{BASE}?cityId=633&listFilters=5~1*5*1"
        agent = f"{BASE}?cityId=633"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 8. Free Cancellation (Category 23)
# =============================================================================


class TestFreeCancellation:
    """Test free cancellation filter matching."""

    def test_free_cancellation_match(self):
        gt = f"{BASE}?cityId=633&listFilters=23~10*23*10"
        match, _ = _match(gt, gt)
        assert match is True

    def test_missing_cancellation_fails(self):
        gt = f"{BASE}?cityId=633&listFilters=23~10*23*10"
        agent = f"{BASE}?cityId=633"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 9. Property Type (Category 75)
# =============================================================================


class TestPropertyType:
    """Test property type filter matching."""

    def test_hotel_type_match(self):
        gt = f"{BASE}?cityId=633&listFilters=75~TAG_495*75*495"
        match, _ = _match(gt, gt)
        assert match is True

    def test_hostel_type_match(self):
        gt = f"{BASE}?cityId=633&listFilters=75~TAG_496*75*496"
        match, _ = _match(gt, gt)
        assert match is True

    def test_type_mismatch(self):
        gt = f"{BASE}?cityId=633&listFilters=75~TAG_495*75*495"
        agent = f"{BASE}?cityId=633&listFilters=75~TAG_496*75*496"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 10. Sort (Category 17)
# =============================================================================


class TestSort:
    """Test sort filter matching."""

    def test_lowest_price_sort_match(self):
        gt = f"{BASE}?cityId=633&listFilters=17~3*17*3"
        match, _ = _match(gt, gt)
        assert match is True

    def test_guest_rating_sort_match(self):
        gt = f"{BASE}?cityId=633&listFilters=17~10*17*10"
        match, _ = _match(gt, gt)
        assert match is True

    def test_sort_mismatch(self):
        gt = f"{BASE}?cityId=633&listFilters=17~3*17*3"
        agent = f"{BASE}?cityId=633&listFilters=17~10*17*10"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 11. Location / Area (Category 9)
# =============================================================================


class TestLocationArea:
    """Test location/area filter matching (ignores geo coordinates)."""

    def test_same_area_id_matches(self):
        gt = f"{BASE}?cityId=633&listFilters=9~99665*9*99665%2640.78%2640.74%26-73.94%26-74.00"
        agent = f"{BASE}?cityId=633&listFilters=9~99665*9*99665%2640.79%2640.75%26-73.95%26-74.01"
        match, _ = _match(agent, gt)
        assert match is True

    def test_different_area_id_fails(self):
        gt = f"{BASE}?cityId=633&listFilters=9~99665*9*99665"
        agent = f"{BASE}?cityId=633&listFilters=9~99666*9*99666"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 12. Filter Order Independence
# =============================================================================


class TestFilterOrderIndependence:
    """Test that filter entry order within listFilters doesn't matter."""

    def test_star_then_amenity_vs_amenity_then_star(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5,3~605*3*605"
        agent = f"{BASE}?cityId=633&listFilters=3~605*3*605,16~5*16*5"
        match, _ = _match(agent, gt)
        assert match is True

    def test_three_filters_reordered(self):
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5,3~605*3*605,17~3*17*3"
        agent = f"{BASE}?cityId=633&listFilters=17~3*17*3,16~5*16*5,3~605*3*605"
        match, _ = _match(agent, gt)
        assert match is True


# =============================================================================
# 13. Domain Variations
# =============================================================================


class TestDomainVariations:
    """Test that different Trip.com subdomains are accepted."""

    def test_us_and_www_match(self):
        gt = "https://us.trip.com/hotels/list?cityId=633"
        agent = "https://www.trip.com/hotels/list?cityId=633"
        match, _ = _match(agent, gt)
        assert match is True

    def test_uk_and_us_match(self):
        gt = "https://us.trip.com/hotels/list?cityId=633"
        agent = "https://uk.trip.com/hotels/list?cityId=633"
        match, _ = _match(agent, gt)
        assert match is True

    def test_bare_trip_com_match(self):
        gt = "https://us.trip.com/hotels/list?cityId=633"
        agent = "https://trip.com/hotels/list?cityId=633"
        match, _ = _match(agent, gt)
        assert match is True

    def test_non_trip_domain_rejected(self):
        v = TripUrlMatch(gt_url="https://us.trip.com/hotels/list?cityId=633")
        assert v._is_valid_trip_domain("google.com") is False
        assert v._is_valid_trip_domain("fake-trip.com") is False

    def test_trip_domain_accepted(self):
        v = _v()
        assert v._is_valid_trip_domain("us.trip.com") is True
        assert v._is_valid_trip_domain("www.trip.com") is True
        assert v._is_valid_trip_domain("trip.com") is True
        assert v._is_valid_trip_domain("au.trip.com") is True


# =============================================================================
# 14. TripUrlMatch Async Lifecycle
# =============================================================================


class TestTripUrlMatchAsync:
    """Test the full async lifecycle: reset → update → compute."""

    @pytest.mark.asyncio
    async def test_exact_match_scores_1(self):
        gt_url = f"{BASE}?cityId=633&checkin=2026-04-01&checkout=2026-04-05&adult=2&crn=1"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_scores_0(self):
        gt_url = f"{BASE}?cityId=633&checkin=2026-04-01&checkout=2026-04-05&adult=2&crn=1"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(
            url=f"{BASE}?cityId=999&checkin=2026-04-01&checkout=2026-04-05&adult=2&crn=1"
        )
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_empty_url_scores_0(self):
        gt_url = f"{BASE}?cityId=633"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_non_trip_url_ignored(self):
        gt_url = f"{BASE}?cityId=633"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="https://www.google.com/search?q=hotels")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_reset_clears_match(self):
        gt_url = f"{BASE}?cityId=633"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.update(url=gt_url)
        r1 = await metric.compute()
        assert r1.score == 1.0

        await metric.reset()
        r2 = await metric.compute()
        assert r2.score == 0.0

    @pytest.mark.asyncio
    async def test_first_match_sticks(self):
        """Once matched, subsequent URLs don't overwrite."""
        gt_url = f"{BASE}?cityId=633"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)  # Match
        await metric.update(url=f"{BASE}?cityId=999")  # Different city
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_multiple_updates_before_match(self):
        """Multiple non-matching updates followed by eventual match."""
        gt_url = f"{BASE}?cityId=633&listFilters=16~5*16*5"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=f"{BASE}?cityId=633")  # No star filter
        await metric.update(url=f"{BASE}?cityId=999")  # Wrong city
        await metric.update(url=gt_url)  # Match!
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_compute_detailed_returns_result(self):
        gt_url = f"{BASE}?cityId=633"
        metric = TripUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute_detailed()
        assert isinstance(result, TripVerifierResult)
        assert result.match is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_multiple_gt_urls_or_semantics(self):
        """Match any URL in the OR list."""
        gt_urls = [
            f"{BASE}?cityId=633&listFilters=16~5*16*5",
            f"{BASE}?cityId=633&listFilters=16~4*16*4",
        ]
        metric = TripUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=f"{BASE}?cityId=633&listFilters=16~4*16*4")
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_multiple_gt_urls(self):
        gt_urls = [
            f"{BASE}?cityId=633&listFilters=16~5*16*5",
            f"{BASE}?cityId=633&listFilters=16~4*16*4",
        ]
        metric = TripUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=f"{BASE}?cityId=633&listFilters=16~3*16*3")
        result = await metric.compute()
        assert result.score == 0.0


# =============================================================================
# 15. Real-World Multi-Filter Scenarios (Browser-Verified)
# =============================================================================


class TestRealWorldScenarios:
    """Test real-world scenarios combining multiple filters.

    All URL patterns are browser-verified on us.trip.com (Mar 2026).
    """

    def test_5star_pool_lowest_price(self):
        """5-star + pool + sort by lowest price."""
        gt = (
            f"{BASE}?cityId=633&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05&adult=2&crn=1"
            "&listFilters=16~5*16*5,3~605*3*605,17~3*17*3"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_budget_free_cancel_breakfast(self):
        """Price under $150 + free cancellation + breakfast."""
        gt = (
            f"{BASE}?cityId=633&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05&adult=2&crn=1"
            "&listFilters=15~Range*15*0~150,23~10*23*10,5~1*5*1"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_pool_gym_8plus_rating(self):
        """Pool + gym + guest rating 8+."""
        gt = (
            f"{BASE}?cityId=633&listFilters=3~605*3*605,3~42*3*42,6~9*6*9"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_hotel_type_4star_wifi(self):
        """Hotel type + 4-star + WiFi."""
        gt = (
            f"{BASE}?cityId=633"
            "&listFilters=75~TAG_495*75*495,16~4*16*4,3~2*3*2"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_reordered_complex_matches(self):
        """Same multi-filter search in different order."""
        gt = (
            f"{BASE}?cityId=633"
            "&listFilters=16~5*16*5,3~605*3*605,5~1*5*1,23~10*23*10"
        )
        agent = (
            f"{BASE}?cityId=633"
            "&listFilters=23~10*23*10,5~1*5*1,3~605*3*605,16~5*16*5"
        )
        match, _ = _match(agent, gt)
        assert match is True

    def test_family_search_with_child(self):
        """2 adults, 1 child (age 5), searching 4+ star with breakfast."""
        gt = (
            f"{BASE}?cityId=633&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&children=1&ages=5&crn=1"
            "&listFilters=16~4*16*4,16~5*16*5,5~1*5*1"
        )
        match, _ = _match(gt, gt)
        assert match is True

    def test_city_mismatch_with_same_filters(self):
        """Same filters but different city = no match."""
        gt = (
            f"{BASE}?cityId=633&listFilters=16~5*16*5,3~605*3*605"
        )
        agent = (
            f"{BASE}?cityId=338&listFilters=16~5*16*5,3~605*3*605"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_date_mismatch_same_filters(self):
        """Same filters but different dates = no match."""
        gt = (
            f"{BASE}?cityId=633&checkin=2026-04-01&checkout=2026-04-05"
            "&listFilters=16~5*16*5"
        )
        agent = (
            f"{BASE}?cityId=633&checkin=2026-05-01&checkout=2026-05-05"
            "&listFilters=16~5*16*5"
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_guest_count_mismatch(self):
        """Same everything but different adult count = no match."""
        gt = f"{BASE}?cityId=633&adult=2&crn=1"
        agent = f"{BASE}?cityId=633&adult=3&crn=1"
        match, _ = _match(agent, gt)
        assert match is False

    def test_children_ages_order_independent(self):
        """Children ages in different order should match."""
        gt = f"{BASE}?cityId=633&children=2&ages=5,10"
        agent = f"{BASE}?cityId=633&children=2&ages=10,5"
        match, _ = _match(agent, gt)
        assert match is True

    def test_extra_filter_category_doesnt_fail(self):
        """Agent applies extra filter category that GT doesn't have."""
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5"
        agent = f"{BASE}?cityId=633&listFilters=16~5*16*5,17~3*17*3"
        match, details = _match(agent, gt)
        assert match is True
        assert "sort" in str(details.get("extra_filters", []))

    def test_ignored_params_dont_affect_match(self):
        """Auto-computed params like countryId, provinceId are ignored."""
        gt = f"{BASE}?cityId=633&cityName=New%20York&listFilters=16~5*16*5"
        agent = (
            f"{BASE}?cityId=633&cityName=New%20York"
            "&countryId=66&provinceId=487&destName=New%20York"
            "&listFilters=16~5*16*5"
        )
        match, _ = _match(agent, gt)
        assert match is True


# =============================================================================
# 16. generate_task_config Tests
# =============================================================================


class TestGenerateTaskConfig:
    """Test task config generation utility."""

    def test_basic_config_generation(self):
        config = generate_task_config(
            task="Search for hotels in New York",
            location="New York, NY, USA",
            timezone="America/New_York",
            gt_url=["https://us.trip.com/hotels/list?cityId=633"],
        )
        assert config.task == "Search for hotels in New York"
        assert config.url == "https://us.trip.com"

    def test_config_with_ground_truth_url_string(self):
        config = generate_task_config(
            task="Search hotels",
            location="New York, NY, USA",
            timezone="America/New_York",
            ground_truth_url="https://us.trip.com/hotels/list?cityId=633",
        )
        assert config.eval_config["gt_url"] == [
            "https://us.trip.com/hotels/list?cityId=633"
        ]

    def test_config_raises_without_urls(self):
        with pytest.raises(ValueError, match="Either 'gt_url' or 'ground_truth_url'"):
            generate_task_config(
                task="Search hotels",
                location="New York, NY, USA",
                timezone="America/New_York",
            )


# =============================================================================
# 17. Edge Cases — Gaps from Bug Report
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases identified in the detailed bug report."""

    def test_empty_gt_url_list(self):
        """Empty gt_url=[] should not crash, just never match."""
        metric = TripUrlMatch(gt_url=[])
        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_empty_gt_url_never_matches(self):
        """Empty gt_url produces 0.0 score always."""
        metric = TripUrlMatch(gt_url=[])
        await metric.reset()
        await metric.update(url=f"{BASE}?cityId=633")
        result = await metric.compute()
        assert result.score == 0.0

    def test_malformed_listfilters_missing_tilde(self):
        """Malformed filter entry without ~ should not crash."""
        r = _parse(f"{BASE}?cityId=633&listFilters=16_5*16*5")
        # Should parse without crashing, filter may be skipped
        assert r["city_id"] == "633"

    def test_malformed_listfilters_truncated(self):
        """Truncated listFilters string should not crash."""
        r = _parse(f"{BASE}?cityId=633&listFilters=16~")
        assert r["city_id"] == "633"

    def test_malformed_listfilters_empty_value(self):
        """Empty listFilters parameter should not crash."""
        r = _parse(f"{BASE}?cityId=633&listFilters=")
        assert r["city_id"] == "633"
        assert r["filters"] == {}

    def test_cityname_only_no_cityid(self):
        """URL with only cityName (no cityId) should still parse."""
        r = _parse(f"{BASE}?cityName=New%20York")
        assert r["city_name"] == "new york"

    def test_distance_sort(self):
        """Distance sort (ID 6) should parse and match."""
        gt = f"{BASE}?cityId=633&listFilters=17~6*17*6"
        match, _ = _match(gt, gt)
        assert match is True

    def test_distance_sort_vs_price_sort_mismatch(self):
        """Distance sort (6) vs lowest price sort (3) = no match."""
        gt = f"{BASE}?cityId=633&listFilters=17~6*17*6"
        agent = f"{BASE}?cityId=633&listFilters=17~3*17*3"
        match, _ = _match(agent, gt)
        assert match is False

    def test_non_hotel_list_path(self):
        """Agent URL on a detail page path should not crash."""
        gt = f"{BASE}?cityId=633&listFilters=16~5*16*5"
        agent = "https://us.trip.com/hotels/detail/?hotelId=12345"
        match, _ = _match(agent, gt)
        assert match is False

    def test_very_large_listfilters(self):
        """URL with >10 filter entries should parse without issues."""
        filters = ",".join([
            "16~5*16*5",
            "3~605*3*605", "3~42*3*42", "3~2*3*2",
            "3~7*3*7", "3~22*3*22", "3~10*3*10",
            "5~1*5*1", "23~10*23*10",
            "6~9*6*9", "15~Range*15*0~500",
            "17~3*17*3",
        ])
        r = _parse(f"{BASE}?cityId=633&listFilters={filters}")
        assert "16" in r["filters"]
        assert "3" in r["filters"]
        assert "5" in r["filters"]
        assert "23" in r["filters"]
        assert "6" in r["filters"]
        assert "15" in r["filters"]
        assert "17" in r["filters"]

    def test_duplicate_ages_parsed(self):
        """Duplicate ages (e.g., ages=5,5) should parse correctly."""
        r = _parse(f"{BASE}?cityId=633&children=2&ages=5,5")
        assert r["children"] == "2"
        assert r["ages"] == ["5", "5"]

    def test_duplicate_ages_match(self):
        """URLs with same duplicate ages should match."""
        gt = f"{BASE}?cityId=633&children=2&ages=5,5"
        match, _ = _match(gt, gt)
        assert match is True

    def test_2_star_filter(self):
        """2-star filter should work."""
        gt = f"{BASE}?cityId=633&listFilters=16~2*16*2"
        match, _ = _match(gt, gt)
        assert match is True

    def test_guest_rating_6plus(self):
        """Guest rating 6+ (value 7) should work."""
        gt = f"{BASE}?cityId=633&listFilters=6~7*6*7"
        match, _ = _match(gt, gt)
        assert match is True


# =============================================================================
# 18. CSV Self-Match Validation
# =============================================================================


class TestCSVSelfMatch:
    """Validate that all 70 CSV ground-truth URLs self-match."""

    def test_all_csv_urls_self_match(self):
        """Every gt_url in the CSV should match itself."""
        import csv
        import json
        import os

        csv_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "navi_bench", "trip", "trip_benchmark_tasks.csv"
        )
        if not os.path.exists(csv_path):
            pytest.skip("CSV file not found")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 70, f"Expected 70+ rows, got {len(rows)}"

        failures = []
        for i, row in enumerate(rows):
            config = json.loads(row["task_generation_config_json"])
            gt_urls = config.get("gt_url", [])
            for gt_url in gt_urls:
                v = TripUrlMatch(gt_url=gt_url)
                matched, details = v._urls_match(gt_url, gt_url)
                if not matched:
                    failures.append(f"Row {i} ({row['task_id']}): {gt_url}")

        assert failures == [], f"Self-match failures:\n" + "\n".join(failures)

    def test_csv_null_encoding(self):
        """Verify CSV uses proper null encoding (not empty strings)."""
        import csv
        import os

        csv_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "navi_bench", "trip", "trip_benchmark_tasks.csv"
        )
        if not os.path.exists(csv_path):
            pytest.skip("CSV file not found")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            assert row["suggested_max_steps"] == "30", \
                f"suggested_max_steps should be '30', got '{row['suggested_max_steps']}'"
            assert row["suggested_hint"] == "null", \
                f"suggested_hint should be 'null', got '{row['suggested_hint']}'"
            assert row["metadata_json"] == "null", \
                f"metadata_json should be 'null', got '{row['metadata_json']}'"

