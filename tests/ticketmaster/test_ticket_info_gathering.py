"""Pytest unit tests for Ticketmaster Info Gathering verifier.

Tests the TicketmasterInfoGathering class and helper functions for event
ticket search verification, including TM-specific anti-bot and UI filter fallbacks.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from navi_bench.ticketmaster.ticket_info_gathering import (
    InfoDict,
    MultiCandidateQuery,
    SingleCandidateQuery,
    TicketmasterInfoGathering,
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
# TicketmasterInfoGathering Basic Tests
# =============================================================================

class TestTicketmasterInfoGatheringBasic:
    """Test basic TicketmasterInfoGathering functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test verifier initialization."""
        queries = [[{"event_names": ["lakers"]}]]
        metric = TicketmasterInfoGathering(queries=queries)

        assert metric.queries == queries
        assert len(metric._is_query_covered) == 1
        assert metric._is_query_covered[0] is False

    @pytest.mark.asyncio
    async def test_repr(self):
        """Test string representation."""
        queries = [[{"event_names": ["lakers"]}]]
        metric = TicketmasterInfoGathering(queries=queries)

        repr_str = repr(metric)
        assert "TicketmasterInfoGathering" in repr_str
        assert "queries" in repr_str

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset clears all state."""
        queries = [[{"event_names": ["lakers"]}]]
        metric = TicketmasterInfoGathering(queries=queries)

        metric._is_query_covered[0] = True
        metric._navigation_stack.append({"url": "test"})

        await metric.reset()

        assert metric._is_query_covered[0] is False
        assert len(metric._navigation_stack) == 0
        assert len(metric._all_infos) == 0

    @pytest.mark.asyncio
    async def test_compute_no_match(self):
        """Test compute returns 0 when no queries matched."""
        queries = [[{"event_names": ["lakers"]}]]
        metric = TicketmasterInfoGathering(queries=queries)
        await metric.reset()

        result = await metric.compute()

        assert result.score == 0.0
        assert result.n_queries == 1
        assert result.n_covered == 0
        assert result.is_query_covered == [False]

    @pytest.mark.asyncio
    async def test_compute_all_matched(self):
        """Test compute returns 1.0 when all queries matched."""
        queries = [[{"event_names": ["lakers"]}]]
        metric = TicketmasterInfoGathering(queries=queries)
        await metric.reset()

        metric._is_query_covered[0] = True

        result = await metric.compute()

        assert result.score == 1.0
        assert result.n_queries == 1
        assert result.n_covered == 1
        assert result.is_query_covered == [True]


# =============================================================================
# _check_single_candidate_query Tests
# =============================================================================

class TestCheckSingleCandidateQuery:
    """Test _check_single_candidate_query method."""

    def test_event_name_match(self):
        """Test exact event name matching (case insensitive)."""
        query = SingleCandidateQuery(event_name="lakers")
        info = InfoDict(eventName="Lakers")
        result = TicketmasterInfoGathering._check_single_candidate_query(query, info)
        assert result is True

    def test_event_name_mismatch(self):
        query = SingleCandidateQuery(event_name="warriors")
        info = InfoDict(eventName="Lakers")
        result = TicketmasterInfoGathering._check_single_candidate_query(query, info)
        assert result is False

    def test_date_match(self):
        """Test exact date matching."""
        query = SingleCandidateQuery(date="2026-03-15")
        info = InfoDict(date="2026-03-15")
        result = TicketmasterInfoGathering._check_single_candidate_query(query, info)
        assert result is True


# =============================================================================
# _check_multi_candidate_query Tests (Ticketmaster Specific)
# =============================================================================

class TestCheckMultiCandidateQuery:
    """Test _check_multi_candidate_query method with TM specifics."""

    def test_event_names_match(self):
        """Test event names list matching (substring)."""
        query = MultiCandidateQuery(event_names=["lakers", "celtics"])
        info = InfoDict(eventName="Los Angeles Lakers vs Warriors")
        evidences = []
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, evidences)
        assert result is True

    def test_cities_match_standard(self):
        """Test standard cities matching."""
        query = MultiCandidateQuery(cities=["los angeles"])
        info = InfoDict(city="Los Angeles")
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_cities_match_filter_location_fallback(self):
        """Test cities matching via discovery UI filterLocation."""
        query = MultiCandidateQuery(cities=["chicago"])
        # Standard city is missing, but agent typed it in UI
        info = InfoDict(city=None, filterLocation="Chicago, IL")
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_exclude_resale_filter_success(self):
        """Test TM specific exclude_resale functionality."""
        query = MultiCandidateQuery(exclude_resale=True)
        # standard ticket, no resale flag
        info = InfoDict(isResale=False, filterTicketTypes=["standard"])
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_exclude_resale_filter_fail(self):
        """Test TM specific exclude_resale blocks resale tickets."""
        query = MultiCandidateQuery(exclude_resale=True)
        # Ticket is resale
        info = InfoDict(isResale=True)
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is False

    def test_require_resale_filter(self):
        """Test require_resale filter matches resale types."""
        query = MultiCandidateQuery(require_resale=True)
        # Global filter array says resale is checked
        info = InfoDict(isResale=False, filterTicketTypes=["resale"])
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_date_match_filter_date_range_fallback(self):
        """Test dates fallback using the discovery UI filterDateRange."""
        query = MultiCandidateQuery(dates=["2026-03-25"])
        # We are on the discovery page, no exact event date parsed, but UI filter is set
        info = InfoDict(date=None, filterDateRange="Mar 20 - Apr 15, 2026", availabilityStatus="available")
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_price_range_filters(self):
        """Test TM min/max price and quantity filters combined."""
        query = MultiCandidateQuery(
            min_price=100.0,
            max_price=300.0,
            ticket_quantities=[2, 4]
        )
        info = InfoDict(price=150.0, ticketCount=2)
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_row_and_section_filters(self):
        """Test specific row and section extraction."""
        query = MultiCandidateQuery(
            sections=["orchestra"],
            rows=["a", "b"]
        )
        info = InfoDict(section="Orchestra Center", row="B")
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, [])
        assert result is True

    def test_unavailable_require_available_true(self):
        """Test sold_out logic blocks correctly when require_available is True."""
        query = MultiCandidateQuery(require_available=True)
        info = InfoDict(availabilityStatus="sold_out")
        evidences = []
        result = TicketmasterInfoGathering._check_multi_candidate_query(query, info, evidences)
        
        assert result is False
        assert len(evidences) == 1
        assert evidences[0] == info


# =============================================================================
# _is_exhausted Tests
# =============================================================================

class TestIsExhausted:
    """Test _is_exhausted method."""

    def test_single_combination_exhausted(self):
        """Test single combination fully exhausted."""
        query = MultiCandidateQuery(
            event_names=["monster jam"],
            dates=["2026-03-15"],
        )
        evidences = [
            InfoDict(
                eventName="Monster Jam",
                date="2026-03-15",
                availabilityStatus="sold_out",
            )
        ]

        result = TicketmasterInfoGathering._is_exhausted(query, evidences)
        assert result is True


# =============================================================================
# Update and Compute Integration Tests
# =============================================================================

class TestUpdateAndComputeIntegration:
    """Test update and compute methods working together in TM."""

    @pytest.mark.asyncio
    async def test_event_listing_match_with_frames(self):
        """Test matching from event listing page using Frame evaluation."""
        queries = [[{"event_names": ["bruno mars"], "max_price": 400.0}]]
        metric = TicketmasterInfoGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.ticketmaster.com/event/123456",
            infos=[
                InfoDict(
                    eventName="Bruno Mars - The Romantic Tour",
                    price=250.0,
                    pageType="event_listing",
                    availabilityStatus="available",
                    source="dom_ticket_listing"
                )
            ]
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert result.score == 1.0
        assert result.n_covered == 1

    @pytest.mark.asyncio
    async def test_anti_bot_blocked(self):
        """Test perimeterX block prevents scoring."""
        queries = [[{"event_names": ["lakers"]}]]
        metric = TicketmasterInfoGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.ticketmaster.com/event/123456",
            content_text="Pardon the Interruption", # Triggers Anti-Bot
            infos=[
                InfoDict(
                    eventName="unknown",
                    pageType="unknown",
                    antiBotStatus="blocked_perimeterx",
                    source="fallback_metadata"
                )
            ]
        )

        await metric.update(page=page)
        result = await metric.compute()

        # Should yield 0 score because anti-bot blocked the read during traversal
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_fallback_to_discovery_page(self):
        """Test fallback to category/search page when no event_listing found."""
        queries = [[{"cities": ["chicago"], "dates": ["2026-04-18"]}]]
        metric = TicketmasterInfoGathering(queries=queries)
        await metric.reset()

        # Visit a discovery page
        category_page = MockPage(
            url="https://www.ticketmaster.com/discover/sports",
            infos=[
                InfoDict(
                    pageType="search_results",
                    filterLocation="Chicago",
                    filterDateRange="Apr 15 - Apr 30, 2026",
                    availabilityStatus="available"
                )
            ],
        )

        await metric.update(page=category_page)
        result = await metric.compute()

        assert result.score == 1.0


# =============================================================================
# Task Config Generation Tests
# =============================================================================

class TestTaskConfigGeneration:
    """Test task configuration generation functions."""

    def test_generate_task_config_deterministic(self):
        """Test deterministic task config generation."""
        config = generate_task_config_deterministic(
            mode="any",
            task="Find Lakers tickets in Los Angeles",
            queries=[
                [
                    {
                        "event_names": ["lakers"],
                        "cities": ["los angeles"],
                        "exclude_resale": True
                    }
                ]
            ],
            location="Los Angeles, CA",
            timezone="America/Los_Angeles",
        )

        assert config.task == "Find Lakers tickets in Los Angeles"
        assert config.url == "https://www.ticketmaster.com"
        assert "queries" in config.eval_config
        assert config.eval_config["queries"] == [
            [
                {
                    "event_names": ["lakers"],
                    "cities": ["los angeles"],
                    "exclude_resale": True
                }
            ]
        ]