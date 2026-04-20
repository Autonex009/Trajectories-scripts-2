"""Pytest unit tests for Trainline URL Match verifier.

Tests the TrainlineUrlMatch class covering train search verification
with browser-verified URL patterns (Apr 2026).

Categories:
 1. Station URN Normalization
 2. Date Extraction
 3. Journey Type Normalization
 4. DOB → Age Classification
 5. URL Parsing (full URL extraction)
 6. URL Matching (origin, dest, dates, journey type, passengers)
 7. Domain Validation
 8. Async Lifecycle (reset → update → compute)
 9. Multi-GT URLs (OR semantics)
10. Edge Cases (empty URLs, non-Trainline domains)
11. generate_task_config Tests
"""

import pytest

from navi_bench.trainline.trainline_url_match import (
    TrainlineInfoGathering,
    TrainlineUrlMatch,
    TrainlineVerifierResult,
    parse_trainline_url,
    _normalize_station_urn,
    _extract_crs_prefix,
    _stations_match,
    _extract_date_only,
    _normalize_journey_type,
    _dob_to_age,
    _classify_passengers,
    _parse_passenger_summary,
    generate_task_config_deterministic,
)


# =============================================================================
# Helpers
# =============================================================================

SEARCH_BASE = "https://www.thetrainline.com/book/results"

# Common station URNs (browser-verified Apr 2026)
LONDON_STP = "urn:trainline:generic:loc:STP1555gb"
LONDON_KGX = "urn:trainline:generic:loc:KGX6121gb"
LONDON_EUS = "urn:trainline:generic:loc:EUS1444gb"
LONDON_PAD = "urn:trainline:generic:loc:PAD3087gb"
MANCHESTER = "urn:trainline:generic:loc:MAN2968gb"
EDINBURGH = "urn:trainline:generic:loc:EDB9328gb"
BIRMINGHAM = "urn:trainline:generic:loc:BHM1127gb"
LEEDS = "urn:trainline:generic:loc:LDS8487gb"
GLASGOW = "urn:trainline:generic:loc:GLC9012gb"
YORK = "urn:trainline:generic:loc:YRK8263gb"
PARIS = "urn:trainline:generic:loc:4916"

# Adult DOB (age ~35 on 2026-05-01)
ADULT_DOB = "1991-04-13"
# Second adult
ADULT_DOB_2 = "1988-07-20"
# Child DOB (age ~8 on 2026-05-01)
CHILD_DOB = "2018-06-15"
# Child DOB (age ~5 on 2026-05-01)
CHILD_DOB_2 = "2021-03-10"


def _build_url(
    origin: str = LONDON_EUS,
    destination: str = MANCHESTER,
    journey_type: str = "single",
    outward_date: str = "2026-05-01T13:15:00",
    inward_date: str = "",
    passengers: list[str] | None = None,
) -> str:
    """Build a Trainline search URL for testing."""
    params = [
        f"journeySearchType={journey_type}",
        f"origin={origin}",
        f"destination={destination}",
        f"outwardDate={outward_date}",
        "outwardDateType=departAfter",
    ]
    if inward_date:
        params.append(f"inwardDate={inward_date}")
        params.append("inwardDateType=departAfter")
    if passengers is None:
        passengers = [ADULT_DOB]
    for pax in passengers:
        params.append(f"passengers[]={pax}")
    return f"{SEARCH_BASE}?" + "&".join(params)


def _match(agent_url: str, gt_url: str) -> tuple[bool, dict]:
    """Shortcut to match two URLs."""
    v = TrainlineUrlMatch(gt_url=gt_url)
    return v._urls_match(agent_url, gt_url)


# =============================================================================
# 1. Station URN Normalization
# =============================================================================


class TestStationURNNormalization:
    """Test _normalize_station_urn for various formats."""

    def test_full_urn(self):
        assert _normalize_station_urn("urn:trainline:generic:loc:EUS1444gb") == "eus1444gb"

    def test_full_urn_uppercase(self):
        assert _normalize_station_urn("urn:trainline:generic:loc:MAN2968gb") == "man2968gb"

    def test_url_encoded_urn(self):
        result = _normalize_station_urn("urn%3Atrainline%3Ageneric%3Aloc%3AEUS1444gb")
        assert result == "eus1444gb"

    def test_bare_code(self):
        assert _normalize_station_urn("EUS1444gb") == "eus1444gb"

    def test_numeric_only_code(self):
        """Paris (Any) uses a numeric-only code."""
        assert _normalize_station_urn("urn:trainline:generic:loc:4916") == "4916"

    def test_case_insensitive(self):
        a = _normalize_station_urn("urn:trainline:generic:loc:STP1555GB")
        b = _normalize_station_urn("urn:trainline:generic:loc:stp1555gb")
        assert a == b

    def test_empty_string(self):
        assert _normalize_station_urn("") == ""

    def test_london_any(self):
        assert _normalize_station_urn("urn:trainline:generic:loc:182gb") == "182gb"

    def test_manchester_any(self):
        """Browser-verified: 115gb = Manchester (Any)."""
        assert _normalize_station_urn("urn:trainline:generic:loc:115gb") == "115gb"


# =============================================================================
# 1b. CRS Prefix Extraction & Station Matching
# =============================================================================


class TestCRSPrefixMatching:
    """Test _extract_crs_prefix and _stations_match.

    Browser-verified (Apr 2026): Kings Cross was observed as both
    KGX4832gb and KGX6121gb. The verifier matches on CRS prefix.
    """

    def test_extract_crs_eus(self):
        assert _extract_crs_prefix("eus1444gb") == "eus"

    def test_extract_crs_kgx(self):
        assert _extract_crs_prefix("kgx4832gb") == "kgx"
        assert _extract_crs_prefix("kgx6121gb") == "kgx"

    def test_extract_crs_man(self):
        assert _extract_crs_prefix("man2968gb") == "man"

    def test_extract_numeric_city_level(self):
        """City-level URNs (numeric-only) return as-is."""
        assert _extract_crs_prefix("182gb") == "182gb"
        assert _extract_crs_prefix("115gb") == "115gb"

    def test_extract_european_numeric(self):
        """European URNs (no country suffix) return as-is."""
        assert _extract_crs_prefix("4916") == "4916"

    def test_stations_match_same_exact(self):
        assert _stations_match("eus1444gb", "eus1444gb") is True

    def test_stations_match_different_suffix(self):
        """KGX4832gb vs KGX6121gb should match (same station, different suffix)."""
        assert _stations_match("kgx4832gb", "kgx6121gb") is True

    def test_stations_match_different_station(self):
        assert _stations_match("eus1444gb", "man2968gb") is False

    def test_stations_match_city_level_same(self):
        assert _stations_match("182gb", "182gb") is True

    def test_stations_match_city_level_different(self):
        """182gb (London Any) vs 115gb (Manchester Any) should NOT match."""
        assert _stations_match("182gb", "115gb") is False

    def test_stations_match_city_vs_specific(self):
        """182gb (London Any) vs eus1444gb (Euston) should NOT match."""
        assert _stations_match("182gb", "eus1444gb") is False

    def test_stations_match_empty(self):
        assert _stations_match("", "eus1444gb") is False
        assert _stations_match("eus1444gb", "") is False


# =============================================================================
# 2. Date Extraction
# =============================================================================


class TestDateExtraction:
    """Test _extract_date_only for Trainline datetime formats."""

    def test_iso_datetime(self):
        assert _extract_date_only("2026-05-01T13:15:00") == "2026-05-01"

    def test_iso_date_only(self):
        assert _extract_date_only("2026-05-01") == "2026-05-01"

    def test_url_encoded_datetime(self):
        assert _extract_date_only("2026-05-01T13%3A15%3A00") == "2026-05-01"

    def test_empty_string(self):
        assert _extract_date_only("") == ""

    def test_different_time(self):
        """Different times should produce the same date."""
        assert _extract_date_only("2026-05-01T08:00:00") == "2026-05-01"
        assert _extract_date_only("2026-05-01T23:59:00") == "2026-05-01"


# =============================================================================
# 3. Journey Type Normalization
# =============================================================================


class TestJourneyTypeNormalization:
    """Test _normalize_journey_type."""

    def test_single(self):
        assert _normalize_journey_type("single") == "single"

    def test_return(self):
        assert _normalize_journey_type("return") == "return"

    def test_open_return(self):
        assert _normalize_journey_type("openReturn") == "openReturn"

    def test_oneway_alias(self):
        assert _normalize_journey_type("oneway") == "single"

    def test_roundtrip_alias(self):
        assert _normalize_journey_type("roundtrip") == "return"

    def test_case_insensitive(self):
        assert _normalize_journey_type("SINGLE") == "single"
        assert _normalize_journey_type("Return") == "return"

    def test_empty(self):
        assert _normalize_journey_type("") == ""


# =============================================================================
# 4. DOB → Age Classification
# =============================================================================


class TestDOBClassification:
    """Test _dob_to_age and _classify_passengers."""

    def test_adult_age(self):
        assert _dob_to_age("1991-04-13", "2026-05-01") == 35

    def test_child_age(self):
        assert _dob_to_age("2018-06-15", "2026-05-01") == 7

    def test_exactly_16(self):
        """16 on travel date → adult."""
        assert _dob_to_age("2010-05-01", "2026-05-01") == 16

    def test_almost_16(self):
        """15 (birthday not yet reached) → child."""
        assert _dob_to_age("2010-05-02", "2026-05-01") == 15

    def test_infant(self):
        assert _dob_to_age("2025-06-15", "2026-05-01") == 0

    def test_classify_1_adult(self):
        result = _classify_passengers(["1991-04-13"], "2026-05-01")
        assert result == {"adults": 1, "children": 0, "total": 1}

    def test_classify_2_adults_1_child(self):
        result = _classify_passengers(
            ["1991-04-13", "1988-07-20", "2018-06-15"],
            "2026-05-01",
        )
        assert result == {"adults": 2, "children": 1, "total": 3}

    def test_classify_empty(self):
        result = _classify_passengers([], "2026-05-01")
        assert result == {"adults": 0, "children": 0, "total": 0}

    def test_classify_all_children(self):
        result = _classify_passengers(
            ["2018-06-15", "2021-03-10"],
            "2026-05-01",
        )
        assert result == {"adults": 0, "children": 2, "total": 2}


# =============================================================================
# 5. URL Parsing
# =============================================================================


class TestURLParsing:
    """Test parse_trainline_url for full URL extraction."""

    def test_basic_single(self):
        url = _build_url()
        r = parse_trainline_url(url)
        assert r["origin"] == "eus1444gb"
        assert r["destination"] == "man2968gb"
        assert r["outward_date"] == "2026-05-01"
        assert r["inward_date"] == ""
        assert r["journey_type"] == "single"
        assert r["adults"] == 1
        assert r["children"] == 0

    def test_return_trip(self):
        url = _build_url(
            journey_type="return",
            inward_date="2026-05-05T14:30:00",
            passengers=[ADULT_DOB, ADULT_DOB_2],
        )
        r = parse_trainline_url(url)
        assert r["journey_type"] == "return"
        assert r["outward_date"] == "2026-05-01"
        assert r["inward_date"] == "2026-05-05"
        assert r["adults"] == 2
        assert r["children"] == 0

    def test_with_children(self):
        url = _build_url(
            passengers=[ADULT_DOB, ADULT_DOB_2, CHILD_DOB, CHILD_DOB_2],
        )
        r = parse_trainline_url(url)
        assert r["adults"] == 2
        assert r["children"] == 2
        assert r["total_passengers"] == 4

    def test_paris_destination(self):
        url = _build_url(
            origin=LONDON_STP,
            destination=PARIS,
        )
        r = parse_trainline_url(url)
        assert r["origin"] == "stp1555gb"
        assert r["destination"] == "4916"

    def test_real_url_pattern(self):
        """Test with a realistic browser-captured URL."""
        url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&origin=urn%3Atrainline%3Ageneric%3Aloc%3ASTP1555gb"
            f"&destination=urn%3Atrainline%3Ageneric%3Aloc%3A4916"
            f"&outwardDate=2026-05-01T13%3A15%3A00"
            f"&outwardDateType=departAfter"
            f"&passengers%5B%5D=1991-04-13"
            f"&lang=en-us"
            f"&selectedTab=train"
        )
        r = parse_trainline_url(url)
        assert r["origin"] == "stp1555gb"
        assert r["destination"] == "4916"
        assert r["outward_date"] == "2026-05-01"
        assert r["journey_type"] == "single"

    def test_missing_passengers_defaults_to_1_adult(self):
        """Browser-verified: no passengers[] key → default 1 adult."""
        url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&origin=urn%3Atrainline%3Ageneric%3Aloc%3AEUS1444gb"
            f"&destination=urn%3Atrainline%3Ageneric%3Aloc%3AMAN2968gb"
            f"&outwardDate=2026-05-01T13%3A15%3A00"
            f"&outwardDateType=departAfter"
        )
        r = parse_trainline_url(url)
        assert r["adults"] == 1
        assert r["children"] == 0
        assert r["total_passengers"] == 1
        assert r["passenger_dobs"] == []


# =============================================================================
# 6. URL Matching
# =============================================================================


class TestURLMatching:
    """Test URL comparison logic."""

    def test_exact_match(self):
        url = _build_url()
        match, _ = _match(url, url)
        assert match is True

    def test_origin_mismatch(self):
        gt = _build_url(origin=LONDON_EUS)
        agent = _build_url(origin=LONDON_PAD)
        match, details = _match(agent, gt)
        assert match is False
        assert any("Origin" in m for m in details["mismatches"])

    def test_destination_mismatch(self):
        gt = _build_url(destination=MANCHESTER)
        agent = _build_url(destination=EDINBURGH)
        match, _ = _match(agent, gt)
        assert match is False

    def test_outward_date_mismatch(self):
        gt = _build_url(outward_date="2026-05-01T13:15:00")
        agent = _build_url(outward_date="2026-05-02T13:15:00")
        match, _ = _match(agent, gt)
        assert match is False

    def test_same_date_different_time(self):
        """Time differences should NOT cause a mismatch."""
        gt = _build_url(outward_date="2026-05-01T08:00:00")
        agent = _build_url(outward_date="2026-05-01T22:30:00")
        match, _ = _match(agent, gt)
        assert match is True

    def test_different_numeric_suffix_same_station(self):
        """Browser-verified: KGX4832gb == KGX6121gb (same CRS prefix)."""
        gt = _build_url(origin="urn:trainline:generic:loc:KGX4832gb")
        agent = _build_url(origin="urn:trainline:generic:loc:KGX6121gb")
        match, _ = _match(agent, gt)
        assert match is True

    def test_agent_no_passengers_gt_1_adult(self):
        """Agent URL with no passengers[] should match GT with 1 adult."""
        gt = _build_url()  # 1 adult via ADULT_DOB
        agent_url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&origin={LONDON_EUS}"
            f"&destination={MANCHESTER}"
            f"&outwardDate=2026-05-01T13:15:00"
            f"&outwardDateType=departAfter"
        )
        match, _ = _match(agent_url, gt)
        assert match is True

    def test_inward_date_mismatch(self):
        gt = _build_url(
            journey_type="return",
            inward_date="2026-05-05T14:30:00",
        )
        agent = _build_url(
            journey_type="return",
            inward_date="2026-05-06T14:30:00",
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_journey_type_mismatch(self):
        gt = _build_url(journey_type="single")
        agent = _build_url(
            journey_type="return",
            inward_date="2026-05-05T14:30:00",
        )
        match, _ = _match(agent, gt)
        assert match is False

    def test_adult_count_mismatch(self):
        gt = _build_url(passengers=[ADULT_DOB])
        agent = _build_url(passengers=[ADULT_DOB, ADULT_DOB_2])
        match, details = _match(agent, gt)
        assert match is False
        assert any("Adults" in m for m in details["mismatches"])

    def test_child_count_mismatch(self):
        gt = _build_url(passengers=[ADULT_DOB, CHILD_DOB])
        agent = _build_url(passengers=[ADULT_DOB, CHILD_DOB, CHILD_DOB_2])
        match, details = _match(agent, gt)
        assert match is False
        assert any("Children" in m for m in details["mismatches"])

    def test_case_insensitive_urns(self):
        gt = _build_url(origin="urn:trainline:generic:loc:EUS1444gb")
        agent = _build_url(origin="urn:trainline:generic:loc:eus1444gb")
        match, _ = _match(agent, gt)
        assert match is True

    def test_url_encoded_vs_raw(self):
        """URL-encoded URNs should match raw URNs."""
        gt = _build_url(origin="urn:trainline:generic:loc:STP1555gb")
        agent_url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&origin=urn%3Atrainline%3Ageneric%3Aloc%3ASTP1555gb"
            f"&destination={MANCHESTER}"
            f"&outwardDate=2026-05-01T13%3A15%3A00"
            f"&outwardDateType=departAfter"
            f"&passengers%5B%5D={ADULT_DOB}"
        )
        match, _ = _match(agent_url, gt)
        assert match is True

    def test_extra_ignored_params_dont_affect_match(self):
        """Ignored params (lang, selectedTab) should not affect matching."""
        gt = _build_url()
        agent_url = _build_url() + "&lang=en-us&selectedTab=train&splitSave=true"
        match, _ = _match(agent_url, gt)
        assert match is True

    def test_gt_no_journey_type_agent_has(self):
        """If GT doesn't specify journey type, agent can have any."""
        gt_url = (
            f"{SEARCH_BASE}?"
            f"origin={LONDON_EUS}"
            f"&destination={MANCHESTER}"
            f"&outwardDate=2026-05-01T13:15:00"
            f"&passengers[]={ADULT_DOB}"
        )
        agent = _build_url(journey_type="single")
        match, _ = _match(agent, gt_url)
        assert match is True


# =============================================================================
# 7. Domain Validation
# =============================================================================


class TestDomainValidation:
    """Test _is_valid_trainline_domain."""

    def _check(self, domain: str) -> bool:
        return TrainlineUrlMatch._is_valid_trainline_domain(domain)

    def test_thetrainline_com(self):
        assert self._check("thetrainline.com") is True

    def test_www_thetrainline_com(self):
        assert self._check("www.thetrainline.com") is True

    def test_trainline_eu(self):
        assert self._check("trainline.eu") is True

    def test_trainline_fr(self):
        assert self._check("trainline.fr") is True

    def test_www_trainline_com(self):
        assert self._check("www.trainline.com") is True

    def test_non_trainline(self):
        assert self._check("google.com") is False
        assert self._check("fake-trainline.com") is False

    def test_expedia_domain(self):
        assert self._check("expedia.com") is False

    def test_skyscanner_domain(self):
        assert self._check("skyscanner.net") is False


# =============================================================================
# 8. Async Lifecycle (update/compute/reset)
# =============================================================================


class TestAsyncLifecycle:
    """Test the full async lifecycle: reset → update → compute."""

    @pytest.mark.asyncio
    async def test_exact_match_scores_1(self):
        gt_url = _build_url()
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_scores_0(self):
        gt_url = _build_url(origin=LONDON_EUS)
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=_build_url(origin=LONDON_PAD))
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_empty_url_scores_0(self):
        gt_url = _build_url()
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_non_trainline_url_ignored(self):
        gt_url = _build_url()
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url="https://www.google.com/search?q=trains")
        result = await metric.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_reset_clears_match(self):
        gt_url = _build_url()
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.update(url=gt_url)
        r1 = await metric.compute()
        assert r1.score == 1.0

        await metric.reset()
        r2 = await metric.compute()
        assert r2.score == 0.0

    @pytest.mark.asyncio
    async def test_first_match_sticks(self):
        """Once matched, subsequent URLs don't overwrite."""
        gt_url = _build_url()
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)  # Match
        await metric.update(url=_build_url(origin=LONDON_PAD))  # Different
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_compute_detailed(self):
        gt_url = _build_url()
        metric = TrainlineUrlMatch(gt_url=gt_url)
        await metric.reset()
        await metric.update(url=gt_url)
        result = await metric.compute_detailed()
        assert isinstance(result, TrainlineVerifierResult)
        assert result.match is True
        assert result.score == 1.0


# =============================================================================
# 9. Multi-GT URLs (OR Semantics)
# =============================================================================


class TestMultiGTURLs:
    """Test OR semantics with multiple ground truth URLs."""

    @pytest.mark.asyncio
    async def test_matches_first_gt(self):
        gt_urls = [
            _build_url(origin=LONDON_EUS),
            _build_url(origin=LONDON_KGX),
        ]
        metric = TrainlineUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=_build_url(origin=LONDON_EUS))
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_matches_second_gt(self):
        gt_urls = [
            _build_url(origin=LONDON_EUS),
            _build_url(origin=LONDON_KGX),
        ]
        metric = TrainlineUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=_build_url(origin=LONDON_KGX))
        result = await metric.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_matches_none(self):
        gt_urls = [
            _build_url(origin=LONDON_EUS),
            _build_url(origin=LONDON_KGX),
        ]
        metric = TrainlineUrlMatch(gt_url=gt_urls)
        await metric.reset()
        await metric.update(url=_build_url(origin=LONDON_PAD))
        result = await metric.compute()
        assert result.score == 0.0


# =============================================================================
# 10. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases."""

    def test_origin_missing_in_agent(self):
        gt = _build_url()
        agent_url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&destination={MANCHESTER}"
            f"&outwardDate=2026-05-01T13:15:00"
        )
        match, details = _match(agent_url, gt)
        assert match is False
        assert any("Origin missing" in m for m in details["mismatches"])

    def test_destination_missing_in_agent(self):
        gt = _build_url()
        agent_url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&origin={LONDON_EUS}"
            f"&outwardDate=2026-05-01T13:15:00"
        )
        match, details = _match(agent_url, gt)
        assert match is False
        assert any("Destination missing" in m for m in details["mismatches"])

    def test_outward_date_missing_in_agent(self):
        gt = _build_url()
        agent_url = (
            f"{SEARCH_BASE}?journeySearchType=single"
            f"&origin={LONDON_EUS}"
            f"&destination={MANCHESTER}"
        )
        match, details = _match(agent_url, gt)
        assert match is False
        assert any("Outward date missing" in m for m in details["mismatches"])

    def test_return_trip_missing_inward_date(self):
        gt = _build_url(
            journey_type="return",
            inward_date="2026-05-05T14:30:00",
        )
        agent = _build_url(journey_type="return")
        match, details = _match(agent, gt)
        assert match is False
        assert any("Inward date missing" in m for m in details["mismatches"])

    def test_completely_empty_url(self):
        gt = _build_url()
        v = TrainlineUrlMatch(gt_url=gt)
        match, details = v._urls_match("", gt)
        # Should not crash, just not match
        assert match is False

    def test_non_search_trainline_url(self):
        """A Trainline URL that's not a search results page."""
        gt = _build_url()
        agent = "https://www.thetrainline.com/train-times/london-to-manchester"
        match, _ = _match(agent, gt)
        assert match is False


# =============================================================================
# 12. Passenger Summary Parsing
# =============================================================================


class TestPassengerSummaryParsing:
    """Tests for _parse_passenger_summary()."""

    def test_1_adult(self):
        assert _parse_passenger_summary("1 adult") == (1, 0)

    def test_2_adults(self):
        assert _parse_passenger_summary("2 adults") == (2, 0)

    def test_1_adult_1_child(self):
        assert _parse_passenger_summary("1 adult, 1 child") == (1, 1)

    def test_2_adults_2_children(self):
        assert _parse_passenger_summary("2 adults, 2 children") == (2, 2)

    def test_3_adults(self):
        assert _parse_passenger_summary("3 adults") == (3, 0)

    def test_case_insensitive(self):
        assert _parse_passenger_summary("2 Adults, 1 Child") == (2, 1)

    def test_empty_defaults_to_1_adult(self):
        assert _parse_passenger_summary("") == (1, 0)

    def test_children_only(self):
        """Edge case: children only still parses correctly."""
        assert _parse_passenger_summary("2 children") == (0, 2)


# =============================================================================
# 13. TrainlineInfoGathering Query Matching
# =============================================================================


class TestInfoGatheringQueryMatch:
    """Tests for TrainlineInfoGathering._check_query()."""

    def _make_info(self, **overrides):
        """Build a mock InfoDict."""
        base = {
            "source": "dom_search_header",
            "pageType": "train_results",
            "antiBotStatus": "clear",
            "originStation": "London Euston",
            "destinationStation": "Manchester Piccadilly",
            "passengerSummary": "1 adult",
            "adults": 1,
            "children": 0,
            "journeyType": "single",
            "urlOrigin": "urn:trainline:generic:loc:EUS1444gb",
            "urlDestination": "urn:trainline:generic:loc:MAN2968gb",
        }
        base.update(overrides)
        return base

    def test_match_origin_station(self):
        query = {"origin_station": "London Euston"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True

    def test_mismatch_origin_station(self):
        query = {"origin_station": "London Paddington"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is False

    def test_match_destination_station(self):
        query = {"destination_station": "Manchester Piccadilly"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True

    def test_mismatch_destination_station(self):
        query = {"destination_station": "Edinburgh"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is False

    def test_match_passenger_summary(self):
        query = {"passenger_summary": "1 adult"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True

    def test_mismatch_passenger_summary(self):
        query = {"passenger_summary": "2 adults"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is False

    def test_match_adults_children(self):
        query = {"passenger_summary": "2 adults, 1 child"}
        info = self._make_info(
            passengerSummary="2 adults, 1 child", adults=2, children=1
        )
        assert TrainlineInfoGathering._check_query(query, info) is True

    def test_match_journey_type(self):
        query = {"journey_type": "single"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True

    def test_mismatch_journey_type(self):
        query = {"journey_type": "return"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is False

    def test_empty_query_matches_all(self):
        """A query with no constraints should match any info."""
        query = {}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True

    def test_url_crs_matching(self):
        """URL-level CRS prefix matching via 'urls' field."""
        query = {
            "urls": [
                "https://www.thetrainline.com/book/results"
                "?journeySearchType=single"
                "&origin=urn:trainline:generic:loc:EUS1444gb"
                "&destination=urn:trainline:generic:loc:MAN2968gb"
                "&outwardDate=2026-05-01T12:00:00"
            ]
        }
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True

    def test_url_crs_mismatch(self):
        """URL-level CRS prefix does NOT match."""
        query = {
            "urls": [
                "https://www.thetrainline.com/book/results"
                "?journeySearchType=single"
                "&origin=urn:trainline:generic:loc:PAD3087gb"
                "&destination=urn:trainline:generic:loc:MAN2968gb"
            ]
        }
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is False

    def test_substring_station_match(self):
        """Partial station name should match (e.g., 'Euston' in 'London Euston')."""
        query = {"origin_station": "Euston"}
        assert TrainlineInfoGathering._check_query(query, self._make_info()) is True


# =============================================================================
# 14. generate_task_config_deterministic
# =============================================================================


class TestDeterministicTaskConfig:
    """Tests for generate_task_config_deterministic()."""

    def test_basic_generation(self):
        config = generate_task_config_deterministic(
            task="Find trains from London Euston to Manchester",
            queries=[
                [
                    "https://www.thetrainline.com/book/results"
                    "?journeySearchType=single"
                    "&origin=urn:trainline:generic:loc:EUS1444gb"
                    "&destination=urn:trainline:generic:loc:MAN2968gb"
                    "&outwardDate=2026-05-01T12:00:00"
                ]
            ],
            location="United Kingdom",
            timezone="Europe/London",
            passenger_summary_scraped="1 adult",
            origin_station="London Euston",
            destination_station="Manchester Piccadilly",
        )
        assert config.task is not None
        assert "TrainlineInfoGathering" in config.eval_config["_target_"]
        assert len(config.eval_config["queries"]) == 1

    def test_multi_adult_passenger(self):
        config = generate_task_config_deterministic(
            task="Train for 3 adults",
            queries=[["https://www.thetrainline.com/book/results?origin=x"]],
            location="United Kingdom",
            timezone="Europe/London",
            passenger_summary_scraped="3 adults",
        )
        query = config.eval_config["queries"][0][0]
        assert query["adults"] == 3
        assert query["children"] == 0

    def test_family_passenger(self):
        config = generate_task_config_deterministic(
            task="Train for family",
            queries=[["https://www.thetrainline.com/book/results?origin=x"]],
            location="United Kingdom",
            timezone="Europe/London",
            passenger_summary_scraped="2 adults, 1 child",
        )
        query = config.eval_config["queries"][0][0]
        assert query["adults"] == 2
        assert query["children"] == 1
