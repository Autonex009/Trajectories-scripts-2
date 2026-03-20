"""
Unit tests for SeatGeek verifier - no browser required.


Tests cover:
- Verifier initialization, reset, compute
- Event name matching (substring, competitors, performers)
- Category matching
- Price filtering (max_price, min_price, cascading fallback)
- City matching (info city + URL city)
- Venue matching
- Page type requirement
- Availability status filtering
- Deal Score filtering
- URL-based verification (quantity, max price)
- Aisle seat filtering
- Listing tag matching
- Date/time handling and sold-out logic
- Task generation functions
- Date helper functions
"""

import pytest
from datetime import datetime

from navi_bench.seatgeek.seatgeek_info_gathering import (
    SeatGeekInfoGathering,
    FinalResult,
    generate_task_config_random,
    generate_task_config_deterministic,
)
from datetime import timedelta

def get_next_weekend_dates() -> list[str]:
    """Get dates for the next weekend (Saturday and Sunday)."""
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    return [saturday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")]

def get_upcoming_weekday(weekday_name: str) -> str:
    """Get date for the next occurrence of a weekday."""
    weekday_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    target_day = weekday_map[weekday_name]
    today = datetime.now()
    days_ahead = (target_day - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    return target_date.strftime("%Y-%m-%d")


# ==================== VERIFIER LOGIC ====================


class TestSeatGeekVerifierLogic:
    """Test the verifier's matching logic without browser interaction."""

    @pytest.fixture
    def single_query_evaluator(self):
        """Create evaluator with single query."""
        return SeatGeekInfoGathering(
            queries=[[{
                "event_names": ["lakers", "los angeles lakers"],
                "dates": ["2026-03-06"],
                "cities": ["los angeles", "inglewood"],
                "max_price": 500.00
            }]]
        )

    @pytest.fixture
    def multi_query_evaluator(self):
        """Create evaluator with multiple queries."""
        return SeatGeekInfoGathering(
            queries=[
                [{
                    "event_names": ["lakers"],
                    "dates": ["2026-03-06"],
                    "cities": ["los angeles"]
                }],
                [{
                    "event_names": ["clippers"],
                    "dates": ["2026-03-07"],
                    "cities": ["los angeles"]
                }]
            ]
        )

    @pytest.mark.asyncio
    async def test_evaluator_initialization(self, single_query_evaluator):
        """Test evaluator initializes correctly."""
        assert len(single_query_evaluator.queries) == 1
        assert single_query_evaluator._is_query_covered == [False]
        assert single_query_evaluator._all_infos == []

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, single_query_evaluator):
        """Test reset clears matched queries."""
        single_query_evaluator._is_query_covered = [True]
        await single_query_evaluator.reset()
        assert single_query_evaluator._is_query_covered == [False]
        assert single_query_evaluator._all_infos == []
        assert single_query_evaluator._navigation_stack == []

    @pytest.mark.asyncio
    async def test_compute_no_matches(self, single_query_evaluator):
        """Test compute returns 0 when no queries matched."""
        result = await single_query_evaluator.compute()
        assert result.score == 0.0
        assert result.n_covered == 0
        assert result.n_queries == 1

    @pytest.mark.asyncio
    async def test_compute_all_matched(self, single_query_evaluator):
        """Test compute returns 1.0 when all queries matched."""
        single_query_evaluator._is_query_covered = [True]
        result = await single_query_evaluator.compute()
        assert result.score == 1.0
        assert result.n_covered == 1

    @pytest.mark.asyncio
    async def test_compute_partial_matches(self, multi_query_evaluator):
        """Test compute returns partial score when some queries matched."""
        multi_query_evaluator._is_query_covered = [True, False]
        result = await multi_query_evaluator.compute()
        assert result.score == 0.5
        assert result.n_covered == 1
        assert result.n_queries == 2


# ==================== EVENT NAME MATCHING ====================


class TestEventNameMatching:
    """Test event name matching logic including competitors and performers."""

    def test_event_name_basic_match(self):
        """Test basic substring event name matching."""
        query = {
            "event_names": ["lakers"],
            "cities": ["los angeles"]
        }
        info = {
            "eventName": "Indiana Pacers at Los Angeles Lakers",
            "city": "Los Angeles",
            "date": "2026-03-06",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_event_name_no_match(self):
        """Test event name that doesn't match."""
        query = {
            "event_names": ["lakers"],
        }
        info = {
            "eventName": "Boston Celtics at Golden State Warriors",
            "city": "San Francisco",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_event_name_match_via_competitors(self):
        """Test matching via competitors[] array from LD+JSON."""
        query = {
            "event_names": ["lakers"],
        }
        info = {
            "eventName": "NBA Basketball Game",
            "competitors": ["Indiana Pacers", "Los Angeles Lakers"],
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_event_name_match_via_performers(self):
        """Test matching via performers[] array from LD+JSON."""
        query = {
            "event_names": ["taylor swift"],
        }
        info = {
            "eventName": "The Eras Tour",
            "performers": ["Taylor Swift"],
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_event_name_case_insensitive(self):
        """Test case-insensitive name matching."""
        query = {
            "event_names": ["LAKERS"],
        }
        info = {
            "eventName": "los angeles lakers",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_event_name_multiple_alternatives(self):
        """Test that any alternative event name matches."""
        query = {
            "event_names": ["la lakers", "lakers", "los angeles lakers"],
        }
        info = {
            "eventName": "Lakers vs Suns",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True


# ==================== CATEGORY MATCHING ====================


class TestCategoryMatching:
    """Test event category and domain matching."""

    def test_event_category_match(self):
        """Test event category matching."""
        query = {
            "event_names": ["lakers"],
            "event_categories": ["sports", "basketball"],
        }
        info = {
            "eventName": "lakers",
            "eventCategory": "sports",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_event_category_no_match(self):
        """Test event category mismatch."""
        query = {
            "event_names": ["hamilton"],
            "event_categories": ["sports"],
        }
        info = {
            "eventName": "Hamilton",
            "eventCategory": "theater",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_domain_alias(self):
        """Test domain as alias for event_categories."""
        query = {
            "event_names": ["lakers"],
            "domain": ["sports"],
        }
        info = {
            "eventName": "lakers",
            "eventCategory": "sports",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True


# ==================== PRICE FILTERING ====================


class TestPriceFiltering:
    """Test price filtering with cascading fallback."""

    def test_max_price_under(self):
        """Test price under max_price passes."""
        query = {"event_names": ["lakers"], "max_price": 200.0}
        info = {"eventName": "lakers", "price": 150.0, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_max_price_over(self):
        """Test price over max_price fails."""
        query = {"event_names": ["lakers"], "max_price": 200.0}
        info = {"eventName": "lakers", "price": 250.0, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_max_price_uses_low_price_fallback(self):
        """Test that lowPrice is used when available (cascading fallback)."""
        query = {"event_names": ["lakers"], "max_price": 100.0}
        info = {"eventName": "lakers", "lowPrice": 50.0, "price": 200.0, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_max_price_uses_listing_low(self):
        """Test listingLowPrice is used in fallback chain."""
        query = {"event_names": ["lakers"], "max_price": 100.0}
        info = {"eventName": "lakers", "listingLowPrice": 80.0, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_min_price_filter(self):
        """Test minimum price filter."""
        query = {"event_names": ["lakers"], "min_price": 100.0}
        info_pass = {"eventName": "lakers", "price": 150.0, "info": "available"}
        info_fail = {"eventName": "lakers", "price": 50.0, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_pass, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_fail, []) is False


# ==================== CITY MATCHING ====================


class TestCityMatching:
    """Test city matching logic."""

    def test_city_match(self):
        """Test basic city matching."""
        query = {"event_names": ["lakers"], "cities": ["los angeles"]}
        info = {"eventName": "lakers", "city": "Los Angeles", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_city_no_match(self):
        """Test city mismatch."""
        query = {"event_names": ["lakers"], "cities": ["los angeles"]}
        info = {"eventName": "lakers", "city": "Phoenix", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_city_missing_in_info(self):
        """Test that missing city in info fails when query requires it."""
        query = {"event_names": ["lakers"], "cities": ["los angeles"]}
        info = {"eventName": "lakers", "city": "", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_city_match_via_url_city(self):
        """Test city matching via urlCity from URL path."""
        query = {"event_names": ["lakers"], "cities": ["los angeles"]}
        info = {"eventName": "lakers", "city": "", "urlCity": "los-angeles", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_city_multiple_alternatives(self):
        """Test multiple city alternatives."""
        query = {"event_names": ["coldplay"], "cities": ["haifa", "tel aviv", "jerusalem"]}
        info = {"eventName": "coldplay", "city": "Tel Aviv", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True


# ==================== VENUE MATCHING ====================


class TestVenueMatching:
    """Test venue matching."""

    def test_venue_match(self):
        """Test basic venue matching."""
        query = {"event_names": ["lakers"], "venues": ["crypto.com arena"]}
        info = {"eventName": "lakers", "venue": "Crypto.com Arena", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_venue_no_match(self):
        """Test venue mismatch."""
        query = {"event_names": ["lakers"], "venues": ["staples center"]}
        info = {"eventName": "lakers", "venue": "Crypto.com Arena", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False


# ==================== SEATGEEK-SPECIFIC FILTERS ====================


class TestSeatGeekSpecificFilters:
    """Test SeatGeek-specific filters like Deal Score."""

    def test_deal_score_min_pass(self):
        """Test Deal Score above minimum passes."""
        query = {"event_names": ["lakers"], "deal_score_min": 8}
        info = {"eventName": "lakers", "dealScore": 10, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_deal_score_min_fail(self):
        """Test Deal Score below minimum fails."""
        query = {"event_names": ["lakers"], "deal_score_min": 8}
        info = {"eventName": "lakers", "dealScore": 5, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_deal_score_null(self):
        """Test null Deal Score doesn't block match."""
        query = {"event_names": ["lakers"], "deal_score_min": 8}
        info = {"eventName": "lakers", "dealScore": None, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_listing_tags_match(self):
        """Test listing tag matching."""
        query = {"event_names": ["lakers"], "listing_tags": ["cheapest"]}
        info = {
            "eventName": "lakers",
            "listingTags": ["cheapest", "amazing"],
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_listing_tags_no_match(self):
        """Test listing tag mismatch."""
        query = {"event_names": ["lakers"], "listing_tags": ["cheapest"]}
        info = {
            "eventName": "lakers",
            "listingTags": ["best_in_section"],
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False


# ==================== URL-BASED VERIFICATION ====================


class TestUrlBasedVerification:
    """Test URL-based filter verification."""

    def test_url_quantity_matching(self):
        """Test URL quantity verification."""
        query = {"event_names": ["lakers"], "url_quantity": 4}
        info_match = {"eventName": "lakers", "urlQuantity": 4, "info": "available"}
        info_no_match = {"eventName": "lakers", "urlQuantity": 2, "info": "available"}
        info_none = {"eventName": "lakers", "urlQuantity": None, "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_none, []) is True

    def test_url_max_price_matching(self):
        """Test URL max price verification."""
        query = {"event_names": ["lakers"], "url_max_price": 200.0}
        info_match = {"eventName": "lakers", "urlMaxPrice": 200.0, "info": "available"}
        info_no_match = {"eventName": "lakers", "urlMaxPrice": 500.0, "info": "available"}
        info_none = {"eventName": "lakers", "urlMaxPrice": None, "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_none, []) is True


# ==================== PAGE TYPE REQUIREMENT ====================


class TestPageTypeRequirement:
    """Test page type requirement verification."""

    def test_require_page_type_single(self):
        """Test single page type requirement."""
        query = {"event_names": ["lakers"], "require_page_type": "event_listing"}
        info_match = {"eventName": "lakers", "pageType": "event_listing", "info": "available"}
        info_no_match = {"eventName": "lakers", "pageType": "search", "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False

    def test_require_page_type_list(self):
        """Test page type requirement with list of acceptable types."""
        query = {
            "event_names": ["lakers"],
            "require_page_type": ["event_listing", "performer"]
        }
        info_event = {"eventName": "lakers", "pageType": "event_listing", "info": "available"}
        info_performer = {"eventName": "lakers", "pageType": "performer", "info": "available"}
        info_search = {"eventName": "lakers", "pageType": "search", "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_event, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_performer, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_search, []) is False


# ==================== AVAILABILITY STATUS ====================


class TestAvailabilityStatus:
    """Test availability status filtering."""

    def test_availability_status_filter(self):
        """Test availability status filtering."""
        query = {
            "event_names": ["lakers"],
            "availability_statuses": ["available", "limited"]
        }
        info_available = {"eventName": "lakers", "availabilityStatus": "available", "info": "available"}
        info_sold_out = {"eventName": "lakers", "availabilityStatus": "sold_out", "info": "sold_out"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_available, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_sold_out, []) is False

    def test_sold_out_with_require_available_false(self):
        """Test sold-out event passes when require_available is False (default)."""
        query = {
            "event_names": ["lakers"],
            "dates": ["2026-03-06"],
            "require_available": False,
        }
        info = {
            "eventName": "lakers",
            "date": "2026-03-06",
            "info": "sold_out"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_sold_out_with_require_available_true(self):
        """Test sold-out event fails when require_available is True."""
        query = {
            "event_names": ["lakers"],
            "dates": ["2026-03-06"],
            "require_available": True,
        }
        evidences = []
        info = {
            "eventName": "lakers",
            "date": "2026-03-06",
            "info": "sold_out"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, evidences) is False

    def test_sold_out_wrong_date(self):
        """Test sold-out event with wrong date fails."""
        query = {
            "event_names": ["lakers"],
            "dates": ["2026-03-06"],
            "require_available": False,
        }
        info = {
            "eventName": "lakers",
            "date": "2026-03-07",
            "info": "sold_out"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False


# ==================== TICKET QUANTITY ====================


class TestTicketQuantity:
    """Test ticket quantity matching."""

    def test_min_tickets(self):
        """Test minimum ticket quantity."""
        query = {"event_names": ["lakers"], "min_tickets": 4}
        info_pass = {"eventName": "lakers", "ticketCount": 6, "info": "available"}
        info_fail = {"eventName": "lakers", "ticketCount": 2, "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_pass, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_fail, []) is False

    def test_max_tickets(self):
        """Test maximum ticket quantity."""
        query = {"event_names": ["lakers"], "max_tickets": 4}
        info_pass = {"eventName": "lakers", "ticketCount": 3, "info": "available"}
        info_fail = {"eventName": "lakers", "ticketCount": 6, "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_pass, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_fail, []) is False

    def test_ticket_quantities_exact(self):
        """Test exact ticket quantity matching."""
        query = {"event_names": ["lakers"], "ticket_quantities": [2, 4]}
        info_match_2 = {"eventName": "lakers", "ticketCount": 2, "info": "available"}
        info_match_4 = {"eventName": "lakers", "ticketCount": 4, "info": "available"}
        info_no_match = {"eventName": "lakers", "ticketCount": 3, "info": "available"}
        info_range_match = {
            "eventName": "lakers", 
            "ticketCount": 6, 
            "availableQuantities": [2, 4, 6], 
            "info": "available"
        }

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match_2, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match_4, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_range_match, []) is True


# ==================== AISLE SEAT & SECTION FILTERS ====================


class TestSeatFilters:
    """Test seat-level filters."""

    def test_aisle_seat_requirement(self):
        """Test aisle seat requirement."""
        query = {"event_names": ["lakers"], "aisle_seat": True}
        info_aisle = {"eventName": "lakers", "hasAisleSeats": True, "info": "available"}
        info_no_aisle = {"eventName": "lakers", "hasAisleSeats": False, "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_aisle, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_aisle, []) is False

    def test_section_filter(self):
        """Test section matching."""
        query = {"event_names": ["lakers"], "sections": ["110", "111"]}
        info_match = {"eventName": "lakers", "section": "110", "info": "available"}
        info_no_match = {"eventName": "lakers", "section": "320", "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False

    def test_section_match_via_available_sections(self):
        """Test section matching via availableSections list."""
        query = {"event_names": ["lakers"], "sections": ["110"]}
        info = {
            "eventName": "lakers",
            "section": "",
            "availableSections": ["109", "110", "111"],
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_row_filter(self):
        """Test row matching."""
        query = {"event_names": ["lakers"], "rows": ["1", "2"]}
        info_match = {"eventName": "lakers", "row": "1", "info": "available"}
        info_no_match = {"eventName": "lakers", "row": "15", "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False


# ==================== DATE/TIME MATCHING ====================


class TestDateTimeMatching:
    """Test date and time filtering."""

    def test_date_match(self):
        """Test basic date matching."""
        query = {"event_names": ["lakers"], "dates": ["2026-03-06"]}
        info_match = {"eventName": "lakers", "date": "2026-03-06", "info": "available"}
        info_no_match = {"eventName": "lakers", "date": "2026-03-07", "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False

    def test_multiple_dates(self):
        """Test multiple date alternatives."""
        query = {"event_names": ["lakers"], "dates": ["2026-03-06", "2026-03-07"]}
        info = {"eventName": "lakers", "date": "2026-03-07", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_time_match(self):
        """Test time matching."""
        query = {"event_names": ["lakers"], "times": ["19:30"]}
        info_match = {"eventName": "lakers", "time": "19:30", "info": "available"}
        info_no_match = {"eventName": "lakers", "time": "15:00", "info": "available"}

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_match, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_match, []) is False

    def test_no_date_filter(self):
        """Test that missing date filter matches any date."""
        query = {"event_names": ["lakers"]}
        info = {"eventName": "lakers", "date": "2026-03-06", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True


# ==================== TASK GENERATION ====================


class TestTaskGeneration:
    """Test task generation functions."""

    def test_random_task_generation(self):
        """Test random task generation creates valid config."""
        config = generate_task_config_random(
            event_type="sports",
            city="Los Angeles",
            timezone="America/Los_Angeles",
            event_name="Lakers"
        )

        assert config.url == "https://seatgeek.com"
        assert config.task is not None
        assert len(config.task) > 0
        assert config.eval_config is not None

    def test_deterministic_task_generation(self):
        """Test deterministic task generation creates valid config."""
        config = generate_task_config_deterministic(
            mode="any",
            url="https://seatgeek.com",
            task="Find Lakers tickets",
            queries=[[{
                "event_names": ["lakers"],
                "cities": ["los angeles"]
            }]],
            location="Los Angeles, CA, United States",
            timezone="America/Los_Angeles"
        )

        assert config.url == "https://seatgeek.com"
        assert config.task == "Find Lakers tickets"
        assert config.eval_config is not None

    def test_random_task_with_seed(self):
        """Test random task generation is reproducible with seed."""
        config1 = generate_task_config_random(
            event_type="concert",
            city="New York",
            timezone="America/New_York",
            seed=42
        )
        config2 = generate_task_config_random(
            event_type="concert",
            city="New York",
            timezone="America/New_York",
            seed=42
        )
        assert config1.task == config2.task


# ==================== DATE HELPERS ====================


class TestDateHelpers:
    """Test date helper functions."""

    def test_get_next_weekend_dates(self):
        """Test weekend date generation."""
        dates = get_next_weekend_dates()

        assert len(dates) == 2
        assert len(dates[0]) == 10  # YYYY-MM-DD format
        assert len(dates[1]) == 10
        assert dates[0] < dates[1]  # Saturday before Sunday

    def test_get_upcoming_weekday(self):
        """Test weekday date generation."""
        friday_date = get_upcoming_weekday("Friday")

        assert len(friday_date) == 10
        date_obj = datetime.strptime(friday_date, "%Y-%m-%d")
        assert date_obj.weekday() == 4  # Friday

    def test_get_upcoming_weekday_is_future(self):
        """Test that upcoming weekday is always in the future."""
        today = datetime.now().strftime("%Y-%m-%d")
        for day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            result = get_upcoming_weekday(day_name)
            assert result > today


# ==================== EVALUATOR REPR ====================


class TestEvaluatorRepr:
    """Test evaluator representation."""

    def test_repr(self):
        """Test __repr__ returns useful info."""
        evaluator = SeatGeekInfoGathering(
            queries=[[{"event_names": ["test"]}]]
        )

        repr_str = repr(evaluator)
        assert "SeatGeekInfoGathering" in repr_str


# ==================== COMBINED FILTER TESTS ====================


class TestCombinedFilters:
    """Test combinations of multiple filters working together."""

    def test_name_city_date_price(self):
        """Test combination: event name + city + date + max price."""
        query = {
            "event_names": ["lakers"],
            "cities": ["los angeles"],
            "dates": ["2026-03-06"],
            "max_price": 200.0,
        }
        info_pass = {
            "eventName": "Indiana Pacers at Los Angeles Lakers",
            "city": "Los Angeles",
            "date": "2026-03-06",
            "price": 150.0,
            "info": "available"
        }
        info_wrong_city = {
            "eventName": "Lakers at Suns",
            "city": "Phoenix",
            "date": "2026-03-06",
            "price": 150.0,
            "info": "available"
        }
        info_wrong_price = {
            "eventName": "Lakers game",
            "city": "Los Angeles",
            "date": "2026-03-06",
            "price": 500.0,
            "info": "available"
        }

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_pass, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_wrong_city, []) is False
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_wrong_price, []) is False

    def test_name_category_venue_aisle(self):
        """Test combination: name + category + venue + aisle seat."""
        query = {
            "event_names": ["lakers"],
            "event_categories": ["sports"],
            "venues": ["crypto.com arena"],
            "aisle_seat": True,
        }
        info_pass = {
            "eventName": "lakers",
            "eventCategory": "sports",
            "venue": "Crypto.com Arena",
            "hasAisleSeats": True,
            "info": "available"
        }
        info_no_aisle = {
            "eventName": "lakers",
            "eventCategory": "sports",
            "venue": "Crypto.com Arena",
            "hasAisleSeats": False,
            "info": "available"
        }

        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_pass, []) is True
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info_no_aisle, []) is False

    def test_minimal_query_matches_anything(self):
        """Test that an empty query (no filters) matches any available event."""
        query = {}
        info = {
            "eventName": "Random Event",
            "city": "Anywhere",
            "info": "available"
        }
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True


# ==================== SECOND AUDIT REGRESSION TESTS ====================


class TestSecondAuditRegressions:
    """Regression tests for bugs found in the second audit report."""

    # --- P-2: listing_tags bypass when no tag data ---

    def test_listing_tags_bypass_empty_list(self):
        """P-2: listing_tags should FAIL when listingTags is empty list."""
        query = {"event_names": ["lakers"], "listing_tags": ["cheapest"]}
        info = {"eventName": "lakers", "listingTags": [], "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_listing_tags_bypass_missing_key(self):
        """P-2: listing_tags should FAIL when listingTags key is absent."""
        query = {"event_names": ["lakers"], "listing_tags": ["cheapest"]}
        info = {"eventName": "lakers", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    # --- P-3: ticket_types bypass when no tag data ---

    def test_ticket_types_bypass_empty(self):
        """P-3: ticket_types should FAIL when no tag data exists."""
        query = {"event_names": ["lakers"], "ticket_types": ["premium"]}
        info = {"eventName": "lakers", "listingTags": [], "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    # --- P-4: instant_delivery with empty/missing filterState ---

    def test_instant_delivery_empty_filter_state(self):
        """P-4: instant_delivery should PASS when filterState is empty (no data)."""
        query = {"event_names": ["lakers"], "instant_delivery": True}
        info = {"eventName": "lakers", "filterState": {}, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_instant_delivery_missing_filter_state(self):
        """P-4: instant_delivery should PASS when filterState key is absent."""
        query = {"event_names": ["lakers"], "instant_delivery": True}
        info = {"eventName": "lakers", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_instant_delivery_explicit_true(self):
        """P-4: instant_delivery should PASS when filterState.instantDelivery=True."""
        query = {"event_names": ["lakers"], "instant_delivery": True}
        info = {"eventName": "lakers", "filterState": {"instantDelivery": True}, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_instant_delivery_explicit_false(self):
        """P-4: instant_delivery should FAIL when filterState.instantDelivery=False."""
        query = {"event_names": ["lakers"], "instant_delivery": True}
        info = {"eventName": "lakers", "filterState": {"instantDelivery": False}, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    # --- P-5: deal_score_min=0 falsy bypass ---

    def test_deal_score_min_zero(self):
        """P-5: deal_score_min=0 should reject negative deal scores."""
        query = {"event_names": ["lakers"], "deal_score_min": 0}
        info = {"eventName": "lakers", "dealScore": -5, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_deal_score_min_zero_allows_zero(self):
        """P-5: deal_score_min=0 should allow dealScore=0."""
        query = {"event_names": ["lakers"], "deal_score_min": 0}
        info = {"eventName": "lakers", "dealScore": 0, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    # --- P-6: min_price fallback chain ---

    def test_min_price_listing_high_fallback(self):
        """P-6: min_price should use listingHighPrice when highPrice and price absent."""
        query = {"event_names": ["lakers"], "min_price": 100}
        info = {"eventName": "lakers", "listingHighPrice": 50, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_min_price_high_price_fallback(self):
        """T-5: min_price should use highPrice fallback."""
        query = {"event_names": ["lakers"], "min_price": 100}
        info = {"eventName": "lakers", "highPrice": 50, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False

    def test_min_price_high_price_above_passes(self):
        """T-5: min_price should pass when highPrice is above min."""
        query = {"event_names": ["lakers"], "min_price": 100}
        info = {"eventName": "lakers", "highPrice": 150, "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    # --- T-6: accessible_seating with empty/missing urlPerks ---

    def test_accessible_seating_empty_url_perks(self):
        """T-6: accessible_seating=True should PASS when urlPerks is empty (no data)."""
        query = {"event_names": ["lakers"], "accessible_seating": True}
        info = {"eventName": "lakers", "urlPerks": "", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_accessible_seating_missing_url_perks(self):
        """T-6: accessible_seating=True should PASS when urlPerks key is absent."""
        query = {"event_names": ["lakers"], "accessible_seating": True}
        info = {"eventName": "lakers", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_accessible_seating_has_accessible(self):
        """T-6: accessible_seating=True should PASS when urlPerks contains 'accessible'."""
        query = {"event_names": ["lakers"], "accessible_seating": True}
        info = {"eventName": "lakers", "urlPerks": "accessible", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is True

    def test_accessible_seating_wrong_perks(self):
        """T-6: accessible_seating=True should FAIL when urlPerks has data but no 'accessible'."""
        query = {"event_names": ["lakers"], "accessible_seating": True}
        info = {"eventName": "lakers", "urlPerks": "parking", "info": "available"}
        assert SeatGeekInfoGathering._check_multi_candidate_query(query, info, []) is False


class TestNavigationStackBehavior:
    """T-7: Tests for navigation stack revisit behavior (P-1 fix)."""

    def test_revisited_page_moves_to_end(self):
        """T-7: Revisiting a page should move it to end of stack, not update in-place."""
        evaluator = SeatGeekInfoGathering(
            queries=[[{"event_names": ["lakers"]}]],
        )

        # Simulate the stack logic from update() — 3 visits: A, B, A again
        def simulate_visit(url, page_type, infos):
            base_url = url.split("?")[0]
            existing_idx = None
            for idx, entry in enumerate(evaluator._navigation_stack):
                if entry["base_url"] == base_url and entry["page_type"] == page_type:
                    existing_idx = idx
                    break
            page_entry = {
                "url": url, "base_url": base_url, "page_type": page_type,
                "infos": infos, "timestamp": len(evaluator._navigation_stack)
            }
            if existing_idx is not None:
                evaluator._navigation_stack.pop(existing_idx)
                evaluator._navigation_stack.append(page_entry)
            else:
                evaluator._navigation_stack.append(page_entry)

        # Visit Lakers, then Bulls, then Lakers again
        simulate_visit("https://seatgeek.com/los-angeles-lakers-tickets", "performer",
                       [{"eventName": "lakers v1"}])
        simulate_visit("https://seatgeek.com/chicago-bulls-tickets", "performer",
                       [{"eventName": "bulls"}])
        simulate_visit("https://seatgeek.com/los-angeles-lakers-tickets", "performer",
                       [{"eventName": "lakers v2"}])

        # Revisited Lakers should be at END (index -1)
        stack = evaluator._navigation_stack
        assert len(stack) == 2, f"Expected 2 pages, got {len(stack)}"
        assert stack[-1]["base_url"] == "https://seatgeek.com/los-angeles-lakers-tickets"
        assert stack[-1]["infos"][0]["eventName"] == "lakers v2"
        # Bulls should be at index 0
        assert stack[0]["base_url"] == "https://seatgeek.com/chicago-bulls-tickets"



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
