"""Pytest unit tests for TripAdvisor hotel info gathering."""

import csv
import json
from unittest.mock import patch
from pathlib import Path

import pytest

from navi_bench.base import DatasetItem
from navi_bench.tripadvisor.tripadvisor_info_gathering import (
    InfoDict,
    TripAdvisorHotelGathering,
    generate_task_config_deterministic,
)


class MockLocator:
    def __init__(self, text: str):
        self._text = text

    async def inner_text(self) -> str:
        return self._text


class MockPage:
    def __init__(self, url: str, info: InfoDict, *, title: str = "", body_text: str = "", html: str = ""):
        self._url = url
        self._info = info
        self._title = title
        self._body_text = body_text
        self._html = html or body_text

    @property
    def url(self) -> str:
        return self._url

    async def title(self) -> str:
        return self._title

    def locator(self, selector: str) -> MockLocator:
        assert selector == "body"
        return MockLocator(self._body_text)

    async def content(self) -> str:
        return self._html

    async def wait_for_load_state(self, state: str, timeout: int = 10000):
        return None

    async def wait_for_selector(self, selector: str, timeout: int = 15000):
        return None

    async def evaluate(self, script: str) -> InfoDict:
        return dict(self._info)


class TestTripAdvisorHotelGathering:
    @pytest.mark.asyncio
    async def test_update_records_clear_hotel_page(self):
        queries = [[{"brand": ["Comfort Inn"]}]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.tripadvisor.com/Hotels-g255060-Sydney_New_South_Wales-Hotels.html",
            info=InfoDict(
                pageType="hotel_results",
                antiBotStatus="clear",
                hotelName="Comfort Inn Sydney",
                activeFilters=[],
            ),
            title="Hotels in Sydney - Tripadvisor",
            body_text="Normal results page",
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert len(metric._navigation_stack) == 1
        assert metric._navigation_stack[0]["anti_bot"] == "clear"
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_anti_bot_blocked_page_prevents_scoring(self):
        queries = [[{"brand": ["Comfort Inn"]}]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.tripadvisor.com/Hotels-g255060-Sydney_New_South_Wales-Hotels.html",
            info=InfoDict(
                pageType="hotel_results",
                antiBotStatus="blocked_access_restricted",
                hotelName="Comfort Inn Sydney",
                activeFilters=[],
            ),
            title="Access is temporarily restricted",
            body_text="We detected unusual activity from your device or network.",
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert len(metric._navigation_stack) == 1
        assert metric._navigation_stack[0]["anti_bot"] == "blocked_access_restricted"
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_anti_bot_blocked_page_can_score_when_requested_fields_match(self):
        queries = [[{"brand": ["OYO"], "guests": 2, "rooms": 1, "check_in": "2026-04-25", "check_out": "2026-04-26", "min_stars": 5}]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.tripadvisor.com/Hotels-g293860-zfb11779-zfc5-a_ufe.true-India-Hotels.html",
            info=InfoDict(
                pageType="hotel_results",
                antiBotStatus="blocked_access_restricted",
                hotelName="THE BEST OYO Hotels in India 2026",
                guests=2,
                rooms=1,
                checkIn="2026-04-25",
                checkOut="2026-04-26",
                activeFilters=["5 Star"],
                hotelClasses=["5 Star"],
                popularFilters=["5 Star"],
            ),
            title="Access is temporarily restricted",
            body_text="THE BEST OYO Hotels in India 2026 5 Star",
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert len(metric._navigation_stack) == 1
        assert metric._navigation_stack[0]["anti_bot"] == "blocked_access_restricted"
        assert metric._navigation_stack[0]["info"]["requestedMisses"] == []
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_compute_tracks_best_result_info_instead_of_last_scrape(self):
        queries = [[{"amenities": ["Breakfast included"]}]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        metric._all_infos = [
            InfoDict(
                pageType="hotel_results",
                antiBotStatus="clear",
                amenities=["Breakfast included"],
                activeFilters=["Breakfast included"],
                requestedMatches=["Breakfast included"],
                requestedMisses=[],
            ),
            InfoDict(
                pageType="hotel_results",
                antiBotStatus="clear",
                amenities=0,
                activeFilters=[],
                requestedMatches=[],
                requestedMisses=["Breakfast included"],
            ),
        ]

        result = await metric.compute()

        assert result.score == 1.0
        assert metric._best_result_info is not None
        assert metric._best_result_info.get("requestedMisses") == []

    def test_collect_filter_candidates_ignores_zero_groups(self):
        info = InfoDict(
            activeFilters=["Pets Allowed", "Family-friendly"],
            amenities=0,
            styles=["Family-friendly"],
            popularFilters=0,
            selectedFiltersByGroup={
                "amenities": 0,
                "styles": ["Family-friendly"],
                "popularFilters": 0,
            },
        )

        candidates = TripAdvisorHotelGathering._collect_filter_candidates(
            info,
            ["amenities", "styles", "popularFilters", "activeFilters"],
        )

        assert "pets allowed" in candidates
        assert "family-friendly" in candidates

    def test_collect_filter_candidates_normalizes_labels(self):
        info = InfoDict(
            activeFilters=["Budget (123)"],
            styles=["Family-friendly"],
            selectedFiltersByGroup={"styles": ["Mid-range"]},
        )

        candidates = TripAdvisorHotelGathering._collect_filter_candidates(
            info,
            ["styles", "activeFilters"],
        )

        assert "budget" in candidates
        assert "family friendly" in candidates
        assert "mid range" in candidates

    def test_diagnose_requested_fields_matches_normalized_style_labels(self):
        metric = TripAdvisorHotelGathering(queries=[[{"styles": ["Budget"]}]])
        info = InfoDict(
            pageType="hotel_results",
            antiBotStatus="clear",
            activeFilters=["Budget (123)"],
            styles=["Mid-range"],
            selectedFiltersByGroup={"styles": ["Family-friendly"]},
        )

        matches, misses, extras = metric._diagnose_requested_fields(info)

        assert matches == ["Budget"]
        assert misses == []
        assert extras == []

    def test_diagnose_requested_fields_matches_style_from_selected_filter_bar(self):
        metric = TripAdvisorHotelGathering(queries=[[{"styles": ["Budget"]}]])
        info = InfoDict(
            pageType="hotel_results",
            antiBotStatus="clear",
            activeFilters=[],
            styles=0,
            selectedFilterBarValues=["Budget"],
            selectedFiltersByGroup={},
        )

        matches, misses, extras = metric._diagnose_requested_fields(info)

        assert matches == ["Budget"]
        assert misses == []
        assert extras == []

    def test_diagnose_requested_fields_matches_plus_style_labels(self):
        metric = TripAdvisorHotelGathering(queries=[[{"required_filters": ["4+ Bubbles"]}]])
        info = InfoDict(
            pageType="hotel_results",
            antiBotStatus="clear",
            activeFilters=["4+ Bubbles (88)"],
            selectedFiltersByGroup={},
        )

        matches, misses, extras = metric._diagnose_requested_fields(info)

        assert matches == ["4+ Bubbles"]
        assert misses == []
        assert extras == []

    def test_diagnose_requested_fields_detects_extra_filters(self):
        metric = TripAdvisorHotelGathering(queries=[[{"required_filters": ["Open now"]}]])
        info = InfoDict(
            pageType="hotel_results",
            antiBotStatus="clear",
            activeFilters=["Open now", "Free Wifi"],
            selectedFiltersByGroup={},
        )

        matches, misses, extras = metric._diagnose_requested_fields(info)

        assert matches == ["Open now"]
        assert misses == []
        assert extras == ["Free Wifi"]

    @pytest.mark.asyncio
    async def test_extra_filters_prevent_query_coverage(self):
        queries = [[{"required_filters": ["Open now"]}]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.tripadvisor.com/Hotels-g12345-Somewhere-Hotels.html",
            info=InfoDict(
                pageType="hotel_results",
                antiBotStatus="clear",
                activeFilters=["Open now", "Free Wifi"],
                selectedFiltersByGroup={},
            ),
            title="Hotels in Somewhere - Tripadvisor",
            body_text="Normal results page",
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert metric._navigation_stack[0]["info"]["requestedExtras"] == ["Free Wifi"]
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_cruise_page_query_can_score(self):
        queries = [[{
            "cities": ["Caribbean"],
            "departure_month": "May 2026",
            "cruiseLines": ["Royal Caribbean International"],
            "departingFrom": ["Cartagena"],
            "cabinTypes": ["Suite"],
            "ports": ["Aruba"],
            "deals": ["All Deals"],
            "sort_orders": ["Price"],
        }]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.tripadvisor.com/Cruises-g147237-Caribbean-Cruises",
            info=InfoDict(
                pageType="cruise_results",
                antiBotStatus="clear",
                geographicId="g147237",
                citySlug="Caribbean",
                departureMonth="May 2026",
                cruiseLines=["Royal Caribbean International"],
                departingFrom=["Cartagena"],
                cabinTypes=["Suite"],
                ports=["Aruba"],
                deals=["All Deals"],
                activeFilters=[
                    "Royal Caribbean International",
                    "Cartagena",
                    "Suite",
                    "Aruba",
                    "All Deals",
                ],
                selectedFilterBarValues=["Royal Caribbean International", "All Deals"],
                selectedFiltersByGroup={
                    "cruiseLines": ["Royal Caribbean International"],
                    "departingFrom": ["Cartagena"],
                    "cabinTypes": ["Suite"],
                    "ports": ["Aruba"],
                    "deals": ["All Deals"],
                },
                sortOrder="Price",
            ),
            title="Caribbean Cruises - Tripadvisor",
            body_text="Royal Caribbean International cruises from Cartagena to Aruba",
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert result.score == 1.0
        assert metric._navigation_stack[0]["info"]["requestedMisses"] == []

    @pytest.mark.asyncio
    async def test_cruise_page_query_can_score_with_price_range(self):
        queries = [[{
            "cities": ["Bahamas"],
            "departingFrom": ["Bayonne (Cape Liberty)"],
            "cruiseLengths": ["6-9 days"],
            "deals": ["Last Minute Deals"],
            "ports": ["Nassau"],
            "sort_orders": ["Best Value"],
            "min_price": 747,
            "max_price": 6270,
        }]]
        metric = TripAdvisorHotelGathering(queries=queries)
        await metric.reset()

        page = MockPage(
            url="https://www.tripadvisor.com/Cruises-g147414-Bahamas-Cruises",
            info=InfoDict(
                pageType="cruise_results",
                antiBotStatus="clear",
                geographicId="g147414",
                citySlug="Bahamas",
                departingFrom=["Bayonne (Cape Liberty)"],
                cruiseLengths=["6-9 days"],
                deals=["Last Minute Deals"],
                ports=["Nassau"],
                activeFilters=[
                    "Bayonne (Cape Liberty)",
                    "6-9 days",
                    "Last Minute Deals",
                    "Nassau",
                    "$747 $6,270",
                ],
                selectedFilterBarValues=["Last Minute Deals"],
                selectedFiltersByGroup={
                    "departingFrom": ["Bayonne (Cape Liberty)"],
                    "cruiseLengths": ["6-9 days"],
                    "deals": ["Last Minute Deals"],
                    "ports": ["Nassau"],
                },
                sortOrder="Best Value",
                priceRange={"min": 747, "max": 6270},
            ),
            title="Bahamas Cruises - Tripadvisor",
            body_text="Bahamas cruises to Nassau from Bayonne Cape Liberty",
        )

        await metric.update(page=page)
        result = await metric.compute()

        assert result.score == 1.0
        assert metric._navigation_stack[0]["info"]["requestedMisses"] == []
        assert metric._navigation_stack[0]["info"]["requestedExtras"] == []


class TestTaskConfigGeneration:
    @patch("navi_bench.tripadvisor.tripadvisor_info_gathering.initialize_placeholder_map")
    def test_generate_task_config_deterministic_injects_dates(self, mock_init_map):
        mock_init_map.return_value = (
            {
                "checkIn": ("April 15, 2026", ["2026-04-15"]),
                "checkOut": ("April 23, 2026", ["2026-04-23"]),
            },
            None,
        )

        config = generate_task_config_deterministic(
            mode="any",
            task="Find hotels for {checkIn} to {checkOut}",
            queries=[[{"check_in": "{checkIn}", "check_out": "{checkOut}"}]],
            location="Sydney, NSW, Australia",
            timezone="Australia/Sydney",
            values={"checkIn": "April 15, 2026", "checkOut": "April 23, 2026"},
        )

        assert config.eval_config["queries"][0][0]["check_in"] == "2026-04-15"
        assert config.eval_config["queries"][0][0]["check_out"] == "2026-04-23"

    @patch("navi_bench.tripadvisor.tripadvisor_info_gathering.initialize_placeholder_map")
    def test_generate_task_config_deterministic_injects_departure_month(self, mock_init_map):
        mock_init_map.return_value = (
            {
                "checkIn": ("May 2026", ["2026-05-01"]),
            },
            None,
        )

        config = generate_task_config_deterministic(
            mode="any",
            task="Find cruises departing in {checkIn}",
            queries=[[{"departure_month": "{checkIn}"}]],
            location="Caribbean",
            timezone="America/Puerto_Rico",
            values={"checkIn": "May 2026"},
        )

        assert config.eval_config["queries"][0][0]["departure_month"] == "May 2026"


class TestTripAdvisorTasksCatalog:
    def test_tasks_csv_rows_parse_and_generate_configs(self):
        tasks_path = Path(__file__).resolve().parents[2] / "navi_bench" / "tripadvisor" / "tasks.csv"

        with tasks_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert len(rows) >= 10

        task_ids = {row["task_id"] for row in rows}
        assert "tripadvisor/hotels/dubai_jumeirah_luxury/001" in task_ids
        assert "tripadvisor/hotels/mumbai_bestofthebest_luxury/001" in task_ids
        assert "tripadvisor/cruises/caribbean_royal_caribbean_cartagena_suite_aruba_price/001" in task_ids
        assert "tripadvisor/cruises/bahamas_bayonne_nassau_last_minute_best_value/001" in task_ids
        assert "tripadvisor/cruises/mexico_carnival_california_all_weekend_los_angeles_ship/001" in task_ids
        assert "tripadvisor/cruises/europe_celebrity_amsterdam_suite_last_minute_june/001" in task_ids
        assert "tripadvisor/cruises/hawaii_norwegian_balcony_all_deals_departure_date/001" in task_ids

        for row in rows:
            raw_config = json.loads(row["task_generation_config_json"])
            assert raw_config["_target_"] == "navi_bench.tripadvisor.tripadvisor_info_gathering.generate_task_config_deterministic"
            for query_group in raw_config["queries"]:
                for query in query_group:
                    assert query.get("cities") or query.get("geographic_ids")

            dataset_item = DatasetItem.model_validate(row)
            task_config = dataset_item.generate_task_config()

            assert task_config.url == "https://www.tripadvisor.com"
            assert task_config.eval_config["queries"]
