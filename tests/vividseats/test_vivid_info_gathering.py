"""Pytest unit tests for Vivid Seats Info Gathering verifier.

Tests the VividSeatsInfoGathering class and helper functions for event
ticket search verification, including specific filters like Super Seller,
Zones, and substring venue matching in titles.
"""

import pytest
from unittest.mock import AsyncMock, patch

from navi_bench.vividseats.vividseats_info_gathering import (
    InfoDict,
    MultiCandidateQuery,
    SingleCandidateQuery,
    VividSeatsInfoGathering,
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
# VividSeatsInfoGathering Basic Tests
# =============================================================================

class TestVividSeatsInfoGatheringBasic:
    """Test basic VividSeatsInfoGathering functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test verifier initialization."""
        queries = [[{"event_names": ["gabriel iglesias"], "cities": ["dallas"]}]]
        metric = VividSeatsInfoGathering(queries=queries)

        assert metric.queries == queries
        assert len(metric._is_query_covered) == 1
        assert metric._is_query_covered[0] is False

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset clears all state."""
        queries = [[{"event_names": ["matt rife"]}]]
        metric = VividSeatsInfoGathering(queries=queries)
        metric._is_query_covered[0] = True
        
        await metric.reset()
        assert metric._is_query_covered[0] is False
        assert len(metric._all_infos) == 0

# =============================================================================
# _check_multi_candidate_query Tests (Vivid Seats Specific)
# =============================================================================

class TestCheckMultiCandidateQuery:
    """Test _check_multi_candidate_query method with Vivid Seats specifics."""

    def test_venue_substring_in_title_match(self):
        """Test the logic where venue is checked via event_names substring."""
        # Scenario: User asked for NRG Stadium, which we put in event_names
        query = MultiCandidateQuery(event_names=["houston rodeo", "nrg stadium"])
        info = InfoDict(eventTitle="Houston Rodeo - Forrest Frank - NRG Stadium")
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_city_parameter_match(self):
        """Test explicit city matching."""
        query = MultiCandidateQuery(cities=["los angeles"])
        info = InfoDict(city="Los Angeles")
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_require_super_seller_success(self):
        """Test that require_super_seller matches correctly."""
        query = MultiCandidateQuery(require_super_seller=True)
        info = InfoDict(isSuperSeller=True)
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_require_super_seller_fail(self):
        """Test that require_super_seller blocks standard sellers."""
        query = MultiCandidateQuery(require_super_seller=True)
        info = InfoDict(isSuperSeller=False)
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is False

    def test_zone_and_section_filters(self):
        """Test filtering by specific zones (e.g., Suites) and sections."""
        query = MultiCandidateQuery(zones=["suites"], sections=["suite 101"])
        info = InfoDict(zone="Suites", section="Suite 101")
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_price_range_and_quantity(self):
        """Test min/max price and ticket count requirements."""
        query = MultiCandidateQuery(min_price=150.0, max_price=200.0, quantity=4)
        info = InfoDict(price=175.0, ticketCount=4)
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_unavailable_require_available_true(self):
        """Test that sold_out status fails when available is required."""
        query = MultiCandidateQuery(require_available=True)
        info = InfoDict(availabilityStatus="sold_out")
        result = VividSeatsInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is False

# =============================================================================
# Integration Tests
# =============================================================================

class TestUpdateAndComputeIntegration:
    """Test the full flow from page update to score computation."""

    @pytest.mark.asyncio
    async def test_successful_ticket_find(self):
        """Test scoring 1.0 when a matching ticket is found in the DOM."""
        queries = [[{
            "event_names": ["les miserables", "morrison center"],
            "cities": ["boise"],
            "require_super_seller": True
        }]]
        metric = VividSeatsInfoGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.vividseats.com/les-miserables-tickets/production/123",
            infos=[
                InfoDict(
                    eventTitle="Les Misérables - Morrison Center",
                    city="Boise",
                    isSuperSeller=True,
                    availabilityStatus="available",
                    source="dom_ticket_listing"
                )
            ]
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert result.score == 1.0
        assert result.n_covered == 1

# =============================================================================
# Task Config Generation Tests
# =============================================================================

class TestTaskConfigGeneration:
    """Test Vivid Seats deterministic configuration helper."""

    def test_generate_task_config_deterministic(self):
        """Test config generation preserves custom parameters like zones."""
        config = generate_task_config_deterministic(
            mode="any",
            task="Find 4 suite tickets for the Houston Rodeo",
            queries=[
                [
                    {
                        "event_names": ["houston rodeo", "nrg stadium"],
                        "zones": ["suites"],
                        "quantity": 4
                    }
                ]
            ],
            location="Houston, TX",
            timezone="America/Chicago",
        )

        assert config.url == "https://www.vividseats.com/"
        assert config.eval_config["queries"][0][0]["zones"] == ["suites"]