"""Pytest unit tests for Rome2Rio Info Gathering verifier.

Tests the Rome2RioInfoGathering class and helper functions for travel
search verification across Routes, Schedules, Hotels, and Experiences.
"""

import pytest
from unittest.mock import AsyncMock, patch

# Adjust import paths based on your project structure
from navi_bench.rome2rio.rome2rio_info_gathering import (
    Info,
    Query,
    Rome2RioInfoGathering,
    FinalResult
)


# =============================================================================
# Mock Classes
# =============================================================================

class MockPage:
    """Mock Playwright Page for testing JS evaluation and update loops."""
    def __init__(self, url: str, infos: list[dict]):
        self._url = url
        self.infos = infos

    @property
    def url(self) -> str:
        return self._url

    async def evaluate(self, script: str) -> list[dict]:
        # Simulates returning the parsed list of dictionaries from the JS script
        return self.infos


# =============================================================================
# Rome2RioInfoGathering Basic Tests
# =============================================================================

class TestRome2RioInfoGatheringBasic:
    """Test basic Rome2RioInfoGathering state and functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test verifier initialization and state setup."""
        queries = [[{"modes": ["train"], "max_price": 5000.0}]]
        evaluator = Rome2RioInfoGathering(queries=queries)

        assert evaluator.queries == queries
        assert len(evaluator._covered) == 1
        assert evaluator._covered[0] is False
        assert len(evaluator._infos) == 0
        assert len(evaluator.seen_signatures) == 0

    @pytest.mark.asyncio
    async def test_compute_no_match(self):
        """Test compute returns 0 when no matching info is found."""
        queries = [[{"modes": ["fly"], "max_price": 5000.0}]]
        evaluator = Rome2RioInfoGathering(queries=queries)
        
        # Inject non-matching info
        evaluator._infos = [{"mode": "Train", "min_price": 6000.0, "duration": 120}]
        result = await evaluator.compute()

        assert result.score == 0.0
        assert result.n_queries == 1
        assert result.n_covered == 0

    @pytest.mark.asyncio
    async def test_compute_all_matched(self):
        """Test compute returns 1.0 when queries are satisfied."""
        queries = [[{"modes": ["train"], "max_price": 5000.0}]]
        evaluator = Rome2RioInfoGathering(queries=queries)
        
        # Inject matching info
        evaluator._infos = [{"mode": "Fly and Train", "min_price": 4500.0, "duration": 300}]
        result = await evaluator.compute()

        assert result.score == 1.0
        assert result.n_queries == 1
        assert result.n_covered == 1


# =============================================================================
# _match Logic Tests (Routes, Schedules, Hotels, Experiences)
# =============================================================================

class TestMatchLogic:
    """Test the filtering logic against query constraints."""

    def setup_method(self):
        self.evaluator = Rome2RioInfoGathering(queries=[])

    def test_modes_match(self):
        """Test substring mode matching (case-insensitive)."""
        query = Query(modes=["train", "emirates"])
        
        # Matches 'train'
        info_pass_1 = Info(mode="Bus and Train", min_price=1000)
        assert self.evaluator._match(query, info_pass_1) is True

        # Matches 'emirates'
        info_pass_2 = Info(mode="IndiGo Airlines, Emirates", min_price=50000)
        assert self.evaluator._match(query, info_pass_2) is True

        # Matches neither
        info_fail = Info(mode="Fly to London", min_price=30000)
        assert self.evaluator._match(query, info_fail) is False

    def test_price_boundaries(self):
        """Test maximum price caps using min_price extracted from JS."""
        query = Query(max_price=35000.0)
        
        # Passes (under budget)
        info_pass = Info(mode="Fly", min_price=32000.0)
        assert self.evaluator._match(query, info_pass) is True

        # Fails (over budget)
        info_fail_high = Info(mode="Fly", min_price=38000.0)
        assert self.evaluator._match(query, info_fail_high) is False

        # Fails (no price scraped)
        info_fail_none = Info(mode="Fly", min_price=None)
        assert self.evaluator._match(query, info_fail_none) is False

    def test_duration_boundaries(self):
        """Test max duration caps."""
        query = Query(max_duration=1200) # 20 hours
        
        # Passes
        info_pass = Info(mode="Train", duration=900)
        assert self.evaluator._match(query, info_pass) is True

        # Fails (too long)
        info_fail = Info(mode="Train", duration=1500)
        assert self.evaluator._match(query, info_fail) is False

        # Fails (no duration scraped)
        info_fail_none = Info(mode="Train", duration=None)
        assert self.evaluator._match(query, info_fail_none) is False

    def test_combined_constraints(self):
        """Test queries requiring multiple fields to match simultaneously."""
        query = Query(modes=["lufthansa"], max_price=50000.0, max_duration=1000)
        
        info_pass = Info(mode="Lufthansa", min_price=45000.0, duration=950)
        assert self.evaluator._match(query, info_pass) is True
        
        # Fails on duration
        info_fail_time = Info(mode="Lufthansa", min_price=45000.0, duration=1050)
        assert self.evaluator._match(query, info_fail_time) is False


# =============================================================================
# Update and Deduplication Integration Tests
# =============================================================================

class TestUpdateIntegration:
    """Test update cycle, JS evaluation handling, and signature deduplication."""

    @pytest.mark.asyncio
    @patch("navi_bench.rome2rio.rome2rio_info_gathering.Path.read_text")
    async def test_update_deduplication(self, mock_read_text):
        """Ensure identical routes or hotels are not appended twice across updates."""
        mock_read_text.return_value = "() => { return []; }" # Mock JS content
        
        queries = [[{"modes": ["fly"]}]]
        evaluator = Rome2RioInfoGathering(queries=queries)

        # 1. Simulate first page load (Routes)
        page1_results = [
            {"mode": "Fly to London", "min_price": 30000, "duration": 750, "pageType": "results"},
            {"mode": "Train via Paris", "min_price": 15000, "duration": 900, "pageType": "results"}
        ]
        page = MockPage(url="https://rome2rio.com/map", infos=page1_results)
        
        await evaluator.update(page=page)
        assert len(evaluator._infos) == 2
        assert len(evaluator.seen_signatures) == 2

        # 2. Simulate polling same page (Should not add duplicates)
        await evaluator.update(page=page)
        assert len(evaluator._infos) == 2 

        # 3. Simulate navigating to Hotels (different pageType handling)
        page2_results = [
            {"mode": "Hotel", "name": "Rho Hotel", "min_price": 12000, "pageType": "hotels"}
        ]
        page.infos = page2_results
        
        await evaluator.update(page=page)
        assert len(evaluator._infos) == 3
        assert "hotels_Rho Hotel_12000" in evaluator.seen_signatures

    @pytest.mark.asyncio
    @patch("navi_bench.rome2rio.rome2rio_info_gathering.Path.read_text")
    async def test_error_handling_during_evaluation(self, mock_read_text):
        """Test robust failure if the page JS evaluation crashes."""
        mock_read_text.return_value = "throw new Error('JS crashed');"
        evaluator = Rome2RioInfoGathering(queries=[])
        
        # Setup a page mock that raises an exception when evaluate is called
        class FailingPage:
            async def evaluate(self, script):
                raise Exception("Playwright Evaluation Failed")
        
        # Execution shouldn't crash the python script, just print the exception
        await evaluator.update(page=FailingPage())
        assert len(evaluator._infos) == 0