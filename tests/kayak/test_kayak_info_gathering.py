"""Pytest unit tests for Kayak Info Gathering verifier.

Tests the KayakInfoGathering class and helper functions for travel
search verification across Flights, Hotels, and Cars, including Kayak-specific 
anti-bot detection and UI filter fallbacks.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from navi_bench.kayak.kayak_info_gathering import (
    InfoDict,
    MultiCandidateQuery,
    KayakInfoGathering,
    generate_task_config_deterministic,
)

# =============================================================================
# Mock Classes
# =============================================================================

class MockFrame:
    """Mock Playwright Frame for testing JS evaluation."""
    def __init__(self, infos: list[InfoDict]):
        self.infos = infos

    async def evaluate(self, script: str) -> list[InfoDict]:
        return self.infos

class MockPage:
    """Mock Playwright Page for testing without browser."""
    def __init__(self, url: str, infos: list[InfoDict], content_text: str = ""):
        self._url = url
        self._content = content_text
        self.frames = [MockFrame(infos)]
        self.main_frame = self.frames[0]

    @property
    def url(self) -> str:
        return self._url

    async def content(self) -> str:
        return self._content

    async def wait_for_selector(self, selector: str, state: str = "attached", timeout: int = 10000):
        pass

    async def wait_for_timeout(self, timeout: int):
        pass


# =============================================================================
# KayakInfoGathering Basic Tests
# =============================================================================

class TestKayakInfoGatheringBasic:
    """Test basic KayakInfoGathering functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test verifier initialization."""
        queries = [[{"origins": ["lax"]}]]
        metric = KayakInfoGathering(queries=queries)

        assert metric.queries == queries
        assert len(metric._is_query_covered) == 1
        assert metric._is_query_covered[0] is False

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset clears all state."""
        queries = [[{"origins": ["lax"]}]]
        metric = KayakInfoGathering(queries=queries)

        metric._is_query_covered[0] = True
        metric._navigation_stack.append({"url": "test"})

        await metric.reset()

        assert metric._is_query_covered[0] is False
        assert len(metric._navigation_stack) == 0
        assert len(metric._all_infos) == 0

    @pytest.mark.asyncio
    async def test_compute_no_match(self):
        """Test compute returns 0 when no queries matched."""
        queries = [[{"origins": ["lax"]}]]
        metric = KayakInfoGathering(queries=queries)
        await metric.reset()

        result = await metric.compute()

        assert result.score == 0.0
        assert result.n_queries == 1
        assert result.n_covered == 0

    @pytest.mark.asyncio
    async def test_compute_all_matched(self):
        """Test compute returns 1.0 when all queries matched."""
        queries = [[{"origins": ["lax"]}]]
        metric = KayakInfoGathering(queries=queries)
        await metric.reset()

        metric._is_query_covered[0] = True
        result = await metric.compute()

        assert result.score == 1.0


# =============================================================================
# _check_multi_candidate_query Tests: FLIGHTS
# =============================================================================

class TestCheckMultiCandidateQueryFlights:
    """Test flight-specific constraints in _check_multi_candidate_query."""

    def test_origins_and_destinations(self):
        """Test exact origin and destination matching."""
        query = MultiCandidateQuery(origins=["del"], destinations=["bom"])
        info = InfoDict(origin="DEL", destination="BOM")
        result = KayakInfoGathering._check_multi_candidate_query(query, info)
        assert result is True

        info_fail = InfoDict(origin="BLR", destination="BOM")
        result_fail = KayakInfoGathering._check_multi_candidate_query(query, info_fail)
        assert result_fail is False

    def test_airlines_match_ticket(self):
        """Test airline matching directly on the flight card."""
        query = MultiCandidateQuery(airlines=["indigo", "spicejet"])
        info = InfoDict(airline="IndiGo")
        result = KayakInfoGathering._check_multi_candidate_query(query, info)
        assert result is True

    def test_airlines_match_global_filter(self):
        """Test airline matching via the global sidebar filter."""
        query = MultiCandidateQuery(airlines=["delta"])
        # The card says "Multiple Airlines" but Delta is checked in the sidebar
        info = InfoDict(airline="multiple airlines", filterAirlines=["Delta", "Air France"])
        result = KayakInfoGathering._check_multi_candidate_query(query, info)
        assert result is True

    def test_price_range_filters(self):
        """Test min and max price boundaries."""
        query = MultiCandidateQuery(min_price=10000.0, max_price=15000.0)
        info_pass = InfoDict(price=12500.0)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_pass) is True
        
        info_fail_low = InfoDict(price=9000.0)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_fail_low) is False
        
        info_fail_high = InfoDict(price=16000.0)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_fail_high) is False

    def test_stops_filters(self):
        """Test exact direct flights and max stops using both card and sidebar."""
        # 1. Require Direct (Card check)
        query_direct = MultiCandidateQuery(require_direct=True)
        info_direct = InfoDict(stops=0)
        assert KayakInfoGathering._check_multi_candidate_query(query_direct, info_direct) is True

        # 2. Max Stops = 1 (Filter check)
        query_1stop = MultiCandidateQuery(max_stops=1)
        info_filter_1stop = InfoDict(stops=None, filterStops=["Direct", "1 stop"])
        assert KayakInfoGathering._check_multi_candidate_query(query_1stop, info_filter_1stop) is True

    def test_cabin_classes(self):
        """Test cabin class extraction and validation."""
        query = MultiCandidateQuery(cabin_classes=["premium economy"])
        info = InfoDict(cabinClass="premium economy")
        assert KayakInfoGathering._check_multi_candidate_query(query, info) is True


# =============================================================================
# _check_multi_candidate_query Tests: HOTELS
# =============================================================================

class TestCheckMultiCandidateQueryHotels:
    """Test hotel-specific constraints in _check_multi_candidate_query."""

    def test_cities_match(self):
        """Test city location matching."""
        query = MultiCandidateQuery(cities=["prague", "paris"])
        info = InfoDict(city="Prague")
        assert KayakInfoGathering._check_multi_candidate_query(query, info) is True

    def test_min_stars_and_score(self):
        """Test hotel class (stars) and guest review score floors."""
        query = MultiCandidateQuery(min_stars=4, min_score=8.5)
        
        info_pass = InfoDict(stars=4, score=9.1)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_pass) is True
        
        info_fail_stars = InfoDict(stars=3, score=9.1)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_fail_stars) is False
        
        info_fail_score = InfoDict(stars=5, score=8.0)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_fail_score) is False

    def test_require_freebies(self):
        """Test freebies/amenities inclusion."""
        query = MultiCandidateQuery(require_freebies=["free breakfast", "free cancellation"])
        info_pass = InfoDict(freebies=["free parking", "free breakfast", "free cancellation"])
        assert KayakInfoGathering._check_multi_candidate_query(query, info_pass) is True
        
        info_fail = InfoDict(freebies=["free breakfast"]) # Missing cancellation
        assert KayakInfoGathering._check_multi_candidate_query(query, info_fail) is False


# =============================================================================
# _check_multi_candidate_query Tests: CARS
# =============================================================================

class TestCheckMultiCandidateQueryCars:
    """Test car-specific constraints in _check_multi_candidate_query."""

    def test_pickup_locations(self):
        """Test pickup location matching."""
        query = MultiCandidateQuery(pickup_locations=["denver"])
        info = InfoDict(pickUpLocation="Denver")
        assert KayakInfoGathering._check_multi_candidate_query(query, info) is True

    def test_min_passengers(self):
        """Test car passenger capacity floors."""
        query = MultiCandidateQuery(min_passengers=5)
        
        info_pass = InfoDict(passengers=7)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_pass) is True
        
        info_fail = InfoDict(passengers=4)
        assert KayakInfoGathering._check_multi_candidate_query(query, info_fail) is False


# =============================================================================
# Update and Compute Integration Tests
# =============================================================================

class TestUpdateAndComputeIntegration:
    """Test update and compute methods working together in Kayak."""

    @pytest.mark.asyncio
    async def test_domain_router_match(self):
        """Test matching from different subdomains using the router."""
        queries = [[{"cities": ["seattle"], "min_stars": 4}]]
        metric = KayakInfoGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.kayak.co.in/hotels/Seattle,WA",
            infos=[
                InfoDict(
                    title="Crowne Plaza Seattle",
                    stars=4,
                    price=20000.0,
                    pageType="hotel_results",
                    antiBotStatus="clear",
                    city="seattle"
                )
            ]
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert result.score == 1.0
        assert result.n_covered == 1

    @pytest.mark.asyncio
    async def test_anti_bot_blocked(self):
        """Test Cloudflare/PerimeterX block prevents scoring."""
        queries = [[{"origins": ["lax"]}]]
        metric = KayakInfoGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.kayak.co.in/flights/LAX-JFK",
            content_text="verify you are human", # Triggers Anti-Bot
            infos=[
                InfoDict(
                    origin="lax",
                    pageType="flight_results",
                    antiBotStatus="blocked_cloudflare",
                )
            ]
        )

        await metric.update(page=page)
        result = await metric.compute()

        # Should yield 0 score because anti-bot blocked the read during traversal
        assert result.score == 0.0


# =============================================================================
# Task Config Generation Tests
# =============================================================================

class TestTaskConfigGeneration:
    """Test task configuration generation and date injection."""

    @patch("navi_bench.dates.initialize_placeholder_map")
    def test_generate_task_config_deterministic_with_dates(self, mock_init_map):
        """Test task config injects dates into all three subdomain query fields."""
        # Mock the date resolver to return a successful tuple mapping
        mock_init_map.return_value = (
            {"dateRange": ("next Friday", ["2026-04-10"])}, 
            None
        )
        
        config = generate_task_config_deterministic(
            mode="any",
            task="Find flights on {dateRange}",
            queries=[[{"origins": ["lax"], "max_price": 500.0}]],
            location="Los Angeles, CA",
            timezone="America/Los_Angeles",
            values={"dateRange": "next Friday"}
        )

        assert "queries" in config.eval_config
        injected_query = config.eval_config["queries"][0][0]
        
        # Verify the dates were injected across all domains correctly
        assert injected_query["depart_dates"] == ["2026-04-10"]
        assert injected_query["check_in_dates"] == ["2026-04-10"]
        assert injected_query["pickup_dates"] == ["2026-04-10"]