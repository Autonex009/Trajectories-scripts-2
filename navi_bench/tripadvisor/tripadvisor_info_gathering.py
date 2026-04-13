"""TripAdvisor hotel info gathering verifier."""

import asyncio
import copy
import functools
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from beartype import beartype
from loguru import logger
from playwright.async_api import Page
from pydantic import BaseModel
from typing_extensions import TypedDict

from navi_bench.base import BaseMetric, BaseTaskConfig, get_import_path
from navi_bench.dates import initialize_placeholder_map, initialize_user_metadata, render_task_statement



class BaseInfoGathering(BaseMetric):
    """Local compatibility shim for site-specific info-gathering verifiers."""


class MultiCandidateQuery(TypedDict, total=False):
    brand: list[str] | None
    geographic_ids: list[str] | None
    cities: list[str] | None
    guests: int | None
    rooms: int | None
    check_in: str | None
    check_out: str | None
    check_in_dates: list[str] | None
    check_out_dates: list[str] | None
    min_stars: int | None
    amenities: list[str] | None
    styles: list[str] | None
    propertyTypes: list[str] | None
    cruiseLines: list[str] | None
    departingFrom: list[str] | None
    cruiseLengths: list[str] | None
    cruiseStyles: list[str] | None
    ships: list[str] | None
    cabinTypes: list[str] | None
    ports: list[str] | None
    departure_month: str | None
    min_price: float | int | None
    max_price: float | int | None
    required_filters: list[str] | None
    sort_orders: list[str] | None
    require_hotel_results_page: bool | None


class InfoDict(TypedDict, total=False):
    url: str
    pageType: str
    antiBotStatus: str
    geographicId: str | None
    citySlug: str | None
    hotelName: str | None
    brands: list[str] | int
    amenities: list[str] | int
    styles: list[str] | int
    deals: list[str] | int
    awards: list[str] | int
    propertyTypes: list[str] | int
    cruiseLines: list[str] | int
    departingFrom: list[str] | int
    cruiseLengths: list[str] | int
    cruiseStyles: list[str] | int
    ships: list[str] | int
    cabinTypes: list[str] | int
    ports: list[str] | int
    neighborhoods: list[str] | int
    travelerRatings: list[str] | int
    hotelClasses: list[str] | int
    popularFilters: list[str] | int
    departureMonth: str | None
    priceRange: dict[str, float | int | str | None]
    selectedFiltersByGroup: dict[str, list[str] | int]
    requestedMatches: list[str]
    requestedMisses: list[str]
    requestedExtras: list[str]
    price: float | None
    rating: float | None
    guests: int | None
    rooms: int | None
    checkIn: str | None
    checkOut: str | None
    reservationTime: str | None
    urlDate: str | None
    urlTime: str | None
    activeFilters: list[str]
    selectedFilterBarValues: list[str]
    sortOrder: str | None
    source: str


class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]


@beartype
class TripAdvisorHotelGathering(BaseInfoGathering):
    """Gather DOM and LD+JSON state from TripAdvisor hotel search pages."""

    def __init__(self, queries: list[list[MultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries
        self._all_infos: list[InfoDict] = []
        self._is_query_covered: list[bool] = [False] * len(queries)
        self._best_result_info: InfoDict | None = None
        self._navigation_stack: list[dict] = []
        self._tracked_pages: set[int] = set()
        self._page_last_url: dict[int, str] = {}
        self._page_last_update_ts: dict[int, float] = {}

    @functools.cached_property
    def js_script(self) -> str:
        with open(Path(__file__).with_name("tripadvisor_info_gathering.js"), "r", encoding="utf-8") as f:
            return f.read()

    async def reset(self) -> None:
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._best_result_info = None
        self._navigation_stack = []
        self._tracked_pages = set()
        self._page_last_url = {}
        self._page_last_update_ts = {}

    def attach_to_context(self, context) -> None:
        async def track_page(page) -> None:
            page_id = id(page)
            if page_id in self._tracked_pages:
                return
            self._tracked_pages.add(page_id)

            async def on_frame_navigated(frame):
                if frame != page.main_frame:
                    return
                current_url = frame.url
                last_url = self._page_last_url.get(page_id)
                if current_url == last_url:
                    return
                self._page_last_url[page_id] = current_url

                if "tripadvisor.com" not in current_url.lower():
                    return
                try:
                    await self.update(page=page)
                except Exception as exc:
                    logger.warning(f"TripAdvisor update failed: {exc}")

            page.on("framenavigated", lambda f: asyncio.create_task(on_frame_navigated(f)))

        for page in context.pages:
            asyncio.create_task(track_page(page))
        context.on("page", lambda p: asyncio.create_task(track_page(p)))

    async def update(self, **kwargs) -> None:
        page: Page = kwargs["page"]
        url = page.url.lower()
        if "tripadvisor.com" not in url:
            return

        if url in ("https://www.tripadvisor.com", "https://www.tripadvisor.com/"):
            logger.debug("Skipping TripAdvisor homepage")
            return

        skip_url_fragments = [
            "/rewards",
            "/account",
            "/login",
            "/signin",
            "/help",
            "/support",
            "/cookie",
            "/privacy",
            "/terms",
            "facebook.com",
            "twitter.com",
        ]
        if any(fragment in url for fragment in skip_url_fragments):
            logger.debug(f"Skipping irrelevant TripAdvisor page: {page.url}")
            return

        # Give the page a chance to finish loading after navigation.
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        # Check if we hit the block page.
        page_title = ""
        page_body_text = ""
        try:
            page_title = await page.title()
            try:
                page_body_text = await page.locator("body").inner_text()
            except Exception:
                # Body may not be available yet, fall back to raw HTML when necessary.
                page_body_text = await page.content()
        except Exception as exc:
            if "Execution context was destroyed" in str(exc):
                logger.debug("TripAdvisor update skipped because navigation invalidated page context")
                return
            raise

        normalized_page_text = f"{page_title}\n{page_body_text}".lower()
        block_signatures = [
            "access is temporarily restricted",
            "unusual activity",
            "are you a robot",
            "please verify your browser",
            "unusual traffic",
            "access denied",
            "captcha",
            "your request looks automated",
            "verification required",
        ]

        blocked = any(signature in normalized_page_text for signature in block_signatures)
        if blocked and ("/hotels-" in url or "/hotels-g" in url or "/hotels" in url):
            logger.warning(f"TripAdvisor access restriction detected on {url}")
        elif blocked:
            logger.debug(f"TripAdvisor block signature found on non-hotel page: {url}")

        try:
            await page.wait_for_selector(
                'button[data-automation="checkin"], div[data-automation="sort"] button, script[type="application/ld+json"]',
                timeout=15000,
            )
        except Exception:
            logger.debug("TripAdvisor key selectors not ready yet; continuing with best-effort scrape")

        await asyncio.sleep(1.0)

        info: InfoDict | None = None
        best_score = -1
        last_error: Exception | None = None
        if page.is_closed():
            logger.warning("TripAdvisor page is already closed; skipping hotel info extraction.")
            return

        for attempt in range(4):
            try:
                candidate_info: InfoDict = await page.evaluate(self.js_script)
                candidate_score = self._info_richness(candidate_info)
                if candidate_score > best_score:
                    info = candidate_info
                    best_score = candidate_score
                if candidate_score >= 8:
                    break
                await asyncio.sleep(0.6)
            except Exception as e:
                last_error = e
                if "Execution context was destroyed" in str(e):
                    logger.debug("Page context destroyed during evaluation; retrying.")
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    continue
                if "Target page, context or browser has been closed" in str(e):
                    logger.warning("TripAdvisor page or browser was closed before hotel info could be extracted.")
                    return
                logger.error(f"Failed to extract hotel info on attempt {attempt + 1}: {e}")
                await asyncio.sleep(0.5)

        if info is None:
            if last_error is not None:
                logger.error(f"Failed to extract hotel info: {last_error}")
            return

        info["url"] = page.url
        if blocked and info.get("antiBotStatus", "clear") == "clear":
            info["antiBotStatus"] = "blocked_access_restricted"
        matches, misses, extras = self._diagnose_requested_fields(info)
        info["requestedMatches"] = matches
        info["requestedMisses"] = misses
        info["requestedExtras"] = extras

        page_entry = {
            "url": page.url,
            "base_url": page.url.split("?")[0],
            "page_type": info.get("pageType", "unknown"),
            "anti_bot": info.get("antiBotStatus", "unknown"),
            "info": info,
        }
        existing_idx = next(
            (
                i
                for i, entry in enumerate(self._navigation_stack)
                if entry["base_url"] == page_entry["base_url"] and entry["page_type"] == page_entry["page_type"]
            ),
            None,
        )
        if existing_idx is not None:
            self._navigation_stack[existing_idx] = page_entry
        else:
            self._navigation_stack.append(page_entry)

        if info.get("antiBotStatus", "clear") != "clear":
            logger.warning(f"TripAdvisor page marked as anti-bot restricted: {page.url}")
            self._all_infos.append(info)
            return

        if info.get("pageType") == "other":
            logger.debug(f"Skipping non-hotel TripAdvisor page: {page.url}")
            self._all_infos.append(info)
            return

        logger.debug(f"TripAdvisorHotelGathering gathered info from {page.url[:100]}...")
        self._all_infos.append(info)

    @staticmethod
    def _info_richness(info: InfoDict) -> int:
        score = 0
        if info.get("pageType") in ("hotel_results", "restaurant_results", "cruise_results"):
            score += 2
        if info.get("checkIn"):
            score += 1
        if info.get("checkOut"):
            score += 1
        if info.get("departureMonth"):
            score += 1
        if info.get("guests") is not None:
            score += 1
        if info.get("rooms") is not None:
            score += 1
        score += len(info.get("activeFilters", []) or [])
        score += len(info.get("selectedFilterBarValues", []) or []) * 2
        for key in (
            "brands", "amenities", "styles", "deals", "awards", "propertyTypes", "neighborhoods", "travelerRatings",
            "hotelClasses", "popularFilters", "cruiseLines", "departingFrom", "cruiseLengths", "cruiseStyles", "ships",
            "cabinTypes", "ports",
        ):
            value = info.get(key)
            if isinstance(value, list) and value:
                score += len(value)
        return score

    async def compute(self) -> FinalResult:
        candidate_infos: list[InfoDict]
        if self._navigation_stack:
            candidate_infos = [
                entry["info"]
                for entry in reversed(self._navigation_stack)
                if self._is_scoreable_info(entry["info"])
            ]
        else:
            candidate_infos = [info for info in reversed(self._all_infos) if self._is_scoreable_info(info)]

        self._best_result_info = self._select_best_result_info(candidate_infos)

        for info in candidate_infos:
            for idx, alternatives in enumerate(self.queries):
                if self._is_query_covered[idx]:
                    continue
                if any(self._check_multi_candidate_query(query, info) for query in alternatives):
                    self._is_query_covered[idx] = True

        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)
        return FinalResult(
            score=n_covered / max(n_queries, 1),
            n_queries=n_queries,
            n_covered=n_covered,
            queries=self.queries,
            is_query_covered=self._is_query_covered,
        )

    def _select_best_result_info(self, candidate_infos: list[InfoDict]) -> InfoDict | None:
        best_info: InfoDict | None = None
        best_key: tuple[int, int, int, int] | None = None

        for info in candidate_infos:
            coverage_count = sum(
                1
                for alternatives in self.queries
                if any(self._check_multi_candidate_query(query, info) for query in alternatives)
            )
            _, misses, extras = self._diagnose_requested_fields(info)
            key = (coverage_count, -len(misses), -len(extras), self._info_richness(info))
            if best_key is None or key > best_key:
                best_key = key
                best_info = info

        return best_info

    @staticmethod
    def _is_scoreable_info(info: InfoDict) -> bool:
        anti_bot = info.get("antiBotStatus", "clear")
        if anti_bot == "clear":
            return True

        requested_misses = info.get("requestedMisses") or []
        requested_matches = info.get("requestedMatches") or []
        requested_extras = info.get("requestedExtras") or []
        if requested_misses or requested_extras or not requested_matches:
            return False
        # Brand matches come from the hotel title, which is visible even on
        # fully-blocked pages and is therefore unreliable. Require at least one
        # structural match (guests, rooms, dates, star rating, filters, etc.)
        # before treating a blocked page as scoreable.
        return any(not m.startswith("brand:") for m in requested_matches)

    @classmethod
    def _check_multi_candidate_query(cls, query: MultiCandidateQuery, info: InfoDict) -> bool:
        if query.get("require_hotel_results_page", True) and info.get("pageType") not in ("hotel_results", "restaurant_results", "cruise_results"):
            return False

        if brands := query.get("brand"):
            hotel_name = (info.get("hotelName") or "").lower()
            explicit_brands = cls._collect_filter_candidates(info, ["brands"])
            if not any(
                brand.lower() in hotel_name
                or any(brand.lower() in explicit for explicit in explicit_brands)
                for brand in brands
            ):
                return False

        if geographic_ids := query.get("geographic_ids"):
            info_geo = (info.get("geographicId") or "").lower()
            if info_geo not in [g.lower() for g in geographic_ids]:
                return False

        if cities := query.get("cities"):
            city_slug = (info.get("citySlug") or "").lower().replace("_", " ")
            if not any(city.lower() in city_slug for city in cities):
                return False

        if (guests := query.get("guests")) is not None:
            info_guests = info.get("guests")
            if info_guests is not None and info_guests != guests:
                return False

        if (rooms := query.get("rooms")) is not None:
            info_rooms = info.get("rooms")
            if info_rooms is not None and info_rooms != rooms:
                return False

        if check_in := query.get("check_in"):
            if not cls._dates_match(info.get("checkIn"), check_in):
                return False

        if check_out := query.get("check_out"):
            if not cls._dates_match(info.get("checkOut"), check_out):
                return False

        if check_in_dates := query.get("check_in_dates"):
            if not any(cls._dates_match(info.get("checkIn"), candidate) for candidate in check_in_dates):
                return False

        if check_out_dates := query.get("check_out_dates"):
            if not any(cls._dates_match(info.get("checkOut"), candidate) for candidate in check_out_dates):
                return False

        if departure_month := query.get("departure_month"):
            if not cls._months_match(info.get("departureMonth"), departure_month):
                return False

        if (min_stars := query.get("min_stars")) is not None:
            active_filters = cls._collect_filter_candidates(info, ["hotelClasses", "popularFilters", "activeFilters"])
            expected_star_label = f"{min_stars} star"
            if not any(expected_star_label in f or expected_star_label + "s" in f for f in active_filters):
                return False

        if amenities := query.get("amenities"):
            explicit_filters = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "amenities",
                    "brands",
                    "deals",
                    "awards",
                    "propertyTypes",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                ],
            )
            for amenity in amenities:
                lowered = cls._normalize_filter_text(amenity)
                if not any(lowered in candidate for candidate in explicit_filters):
                    return False

        if styles := query.get("styles"):
            explicit_filters = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "styles",
                    "brands",
                    "deals",
                    "awards",
                    "propertyTypes",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                ],
            )
            for style in styles:
                lowered = cls._normalize_filter_text(style)
                if not any(lowered in candidate for candidate in explicit_filters):
                    return False

        if property_types := query.get("propertyTypes"):
            explicit_filters = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "propertyTypes",
                    "brands",
                    "deals",
                    "awards",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                ],
            )
            for property_type in property_types:
                lowered = cls._normalize_filter_text(property_type)
                if not any(lowered in candidate for candidate in explicit_filters):
                    return False

        if cuisines := query.get("cuisines"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cuisines", "activeFilters"])
            for cuisine in cuisines:
                lowered = cls._normalize_filter_text(cuisine)
                if not any(lowered in c for c in available):
                    return False

        if establishment_types := query.get("establishmentTypes"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "establishmentTypes", "activeFilters"])
            for est_type in establishment_types:
                lowered = cls._normalize_filter_text(est_type)
                if not any(lowered in c for c in available):
                    return False

        if meal_types := query.get("mealTypes"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "mealTypes", "activeFilters"])
            for meal_type in meal_types:
                lowered = cls._normalize_filter_text(meal_type)
                if not any(lowered in c for c in available):
                    return False

        if query_diets := query.get("diets"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "diets", "activeFilters"])
            for diet in query_diets:
                lowered = cls._normalize_filter_text(diet)
                if not any(lowered in c for c in available):
                    return False

        if dining_options := query.get("diningOptions"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "diningOptions", "activeFilters"])
            for option in dining_options:
                lowered = cls._normalize_filter_text(option)
                if not any(lowered in c for c in available):
                    return False

        if neighborhoods := query.get("neighborhoods"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "neighborhoods", "activeFilters"])
            for neighborhood in neighborhoods:
                lowered = cls._normalize_filter_text(neighborhood)
                if not any(lowered in c for c in available):
                    return False

        if cruise_lines := query.get("cruiseLines"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cruiseLines", "activeFilters"])
            for cruise_line in cruise_lines:
                lowered = cls._normalize_filter_text(cruise_line)
                if not any(lowered in c for c in available):
                    return False

        if departing_from := query.get("departingFrom"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "departingFrom", "activeFilters"])
            for departure in departing_from:
                lowered = cls._normalize_filter_text(departure)
                if not any(lowered in c for c in available):
                    return False

        if cruise_lengths := query.get("cruiseLengths"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cruiseLengths", "activeFilters"])
            for cruise_length in cruise_lengths:
                lowered = cls._normalize_filter_text(cruise_length)
                if not any(lowered in c for c in available):
                    return False

        if cruise_styles := query.get("cruiseStyles"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cruiseStyles", "activeFilters"])
            for cruise_style in cruise_styles:
                lowered = cls._normalize_filter_text(cruise_style)
                if not any(lowered in c for c in available):
                    return False

        if ships := query.get("ships"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "ships", "activeFilters"])
            for ship in ships:
                lowered = cls._normalize_filter_text(ship)
                if not any(lowered in c for c in available):
                    return False

        if cabin_types := query.get("cabinTypes"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cabinTypes", "activeFilters"])
            for cabin_type in cabin_types:
                lowered = cls._normalize_filter_text(cabin_type)
                if not any(lowered in c for c in available):
                    return False

        if ports := query.get("ports"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "ports", "activeFilters"])
            for port in ports:
                lowered = cls._normalize_filter_text(port)
                if not any(lowered in c for c in available):
                    return False

        if date := query.get("date"):
            if not cls._dates_match(info.get("checkIn"), date) and not cls._dates_match(info.get("urlDate"), date):
                return False

        if time_val := query.get("time"):
            if not cls._times_match(info.get("reservationTime"), time_val) and not cls._times_match(info.get("urlTime"), time_val):
                return False

        if (min_price := query.get("min_price")) is not None:
            info_min_price = cls._extract_price_bound(info, "min")
            if info_min_price is None or round(float(info_min_price), 2) != round(float(min_price), 2):
                return False

        if (max_price := query.get("max_price")) is not None:
            info_max_price = cls._extract_price_bound(info, "max")
            if info_max_price is None or round(float(info_max_price), 2) != round(float(max_price), 2):
                return False

        if required_filters := query.get("required_filters"):
            active_filters = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "amenities",
                    "styles",
                    "brands",
                    "deals",
                    "awards",
                    "propertyTypes",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                    "cuisines",
                    "dishes",
                    "establishmentTypes",
                    "mealTypes",
                    "diets",
                    "diningOptions",
                ],
            )
            for required_filter in required_filters:
                required = cls._normalize_filter_text(required_filter)
                if not any(required in active for active in active_filters):
                    return False

        if sort_orders := query.get("sort_orders"):
            info_sort = (info.get("sortOrder") or "").lower()
            if not any(sort_order.lower() in info_sort for sort_order in sort_orders):
                return False

        extras = cls._detect_extra_filters(query, info)
        if extras:
            return False

        return True

    @staticmethod
    def _normalize_date_string(value: str | None) -> str | None:
        if not value:
            return None

        candidate = value.strip()
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%A, %B %d, %Y", "%B %d, %Y", "%a, %b %d", "%b %d, %Y"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                if fmt == "%a, %b %d":
                    return candidate
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return candidate.lower()

    @classmethod
    def _dates_match(cls, scraped_value: str | None, expected_value: str | None) -> bool:
        scraped = cls._normalize_date_string(scraped_value)
        expected = cls._normalize_date_string(expected_value)
        if not expected:
            return True
        if not scraped:
            return False
        return scraped == expected

    @staticmethod
    def _normalize_month_string(value: str | None) -> str | None:
        if not value:
            return None

        candidate = value.strip()
        for fmt in ("%B %Y", "%b %Y", "%Y-%m", "%Y/%m", "%A, %B %d, %Y", "%B %d, %Y"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.strftime("%Y-%m")
            except ValueError:
                continue
        return candidate.lower()

    @classmethod
    def _months_match(cls, scraped_value: str | None, expected_value: str | None) -> bool:
        scraped = cls._normalize_month_string(scraped_value)
        expected = cls._normalize_month_string(expected_value)
        if not expected:
            return True
        if not scraped:
            return False
        return scraped == expected

    @classmethod
    def _times_match(cls, scraped_value: str | None, expected_value: str | None) -> bool:
        if not expected_value:
            return True
        if not scraped_value:
            return False
        try:
            hour, minute = map(int, expected_value.split(":"))
        except (ValueError, AttributeError):
            return expected_value.lower() in scraped_value.lower()

        if scraped_value.isdigit() and len(scraped_value) in (3, 4):
            # URL format HHMM or HMM
            expected_hm_str = f"{hour:02d}{minute:02d}"
            expected_h_str = f"{hour}{minute:02d}"
            if scraped_value == expected_hm_str or scraped_value == expected_h_str:
                return True
        if hour == 0:
            h12, ampm = 12, "AM"
        elif hour < 12:
            h12, ampm = hour, "AM"
        elif hour == 12:
            h12, ampm = 12, "PM"
        else:
            h12, ampm = hour - 12, "PM"
        candidates = [
            f"{h12}:{minute:02d} {ampm}",
            f"{h12}:{minute:02d}{ampm}",
            f"{hour:02d}:{minute:02d}",
            f"{hour}:{minute:02d}",
        ]
        scraped_lower = scraped_value.lower()
        return any(c.lower() in scraped_lower for c in candidates)

    @staticmethod
    def _extract_price_bound(info: InfoDict, bound: Literal["min", "max"]) -> float | None:
        price_range = info.get("priceRange") or {}
        if not isinstance(price_range, dict):
            return None

        candidate_keys = [bound]
        if bound == "min":
            candidate_keys.append("minInput")
        if bound == "max":
            candidate_keys.append("maxInput")

        for key in candidate_keys:
            value = price_range.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = re.sub(r"[^0-9.]", "", value)
                if cleaned:
                    try:
                        return float(cleaned)
                    except ValueError:
                        continue
        return None

    @classmethod
    def _expected_price_filter_candidates(cls, query: MultiCandidateQuery) -> set[str]:
        candidates: set[str] = set()
        min_price = query.get("min_price")
        max_price = query.get("max_price")
        if min_price is None and max_price is None:
            return candidates

        def format_price(value: float | int) -> str:
            numeric = float(value)
            if numeric.is_integer():
                return f"{int(numeric):,}"
            return f"{numeric:,.2f}".rstrip("0").rstrip(".")

        pieces = []
        if min_price is not None:
            pieces.append(f"${format_price(min_price)}")
        if max_price is not None:
            pieces.append(f"${format_price(max_price)}")

        if pieces:
            joined = " ".join(pieces)
            candidates.add(cls._normalize_filter_text(joined))
            candidates.add(cls._normalize_filter_text(joined.replace(",", "")))
            candidates.add(cls._normalize_filter_text(" ".join(piece.replace(",", "") for piece in pieces)))

        return candidates

    @staticmethod
    def _normalize_filter_text(value: str) -> str:
        normalized = value.strip().lower()
        normalized = normalized.replace("’", "'")
        normalized = normalized.replace("‘", "'")
        normalized = normalized.replace("“", '"')
        normalized = normalized.replace("”", '"')
        normalized = re.sub(r"^\s*remove\s+", " ", normalized)
        normalized = re.sub(r"\s+filter\s*$", " ", normalized)
        normalized = re.sub(r"\s+selected\s*$", " ", normalized)
        normalized = normalized.replace("selected filter", " ")
        normalized = re.sub(r"\(\s*\d[\d,]*\s*\)\s*$", " ", normalized)
        normalized = re.sub(r"\s+\d[\d,]*\s*$", " ", normalized)
        normalized = normalized.replace(",", " ")
        normalized = normalized.replace("(", " ")
        normalized = normalized.replace(")", " ")
        normalized = normalized.replace("&", " and ")
        normalized = normalized.replace("+", " plus ")
        normalized = normalized.replace("/", " ")
        normalized = normalized.replace("-", " ")
        # Canonicalize "wi fi" → "wifi" so "Free Wi-Fi" matches "Free Wifi"
        normalized = normalized.replace("wi fi", "wifi")
        # Canonicalize bubble ratings: "4 of 5 bubbles and up" → "4 plus bubbles"
        normalized = re.sub(
            r"(\d+)\s+of\s+5\s+bubbles?", r"\1 plus bubbles", normalized
        )
        # Strip "and up" suffix which adds no matching value
        normalized = re.sub(r"\s*\band\s+up\b", "", normalized)
        normalized = " ".join(normalized.split())
        return normalized

    @staticmethod
    def _normalize_sort_text(value: str) -> str:
        normalized = TripAdvisorHotelGathering._normalize_filter_text(value)
        normalized = re.sub(r"\b(highest|top) rated\b", "highest rating", normalized)
        normalized = re.sub(r"\b(highest|top) rating\b", "highest rating", normalized)
        normalized = re.sub(r"\brate\b", "rating", normalized)
        normalized = re.sub(r"\b(least|low|lowest) rated\b", "lowest rating", normalized)
        normalized = re.sub(r"\b(least|low|lowest) rating\b", "lowest rating", normalized)
        return normalized

    @staticmethod
    def _collect_filter_candidates(info: InfoDict, keys: list[str]) -> list[str]:
        candidates: list[str] = []
        selected_by_group = info.get("selectedFiltersByGroup", {})

        for key in keys:
            for value in info.get(key, []) or []:
                candidates.append(TripAdvisorHotelGathering._normalize_filter_text(value))
            for value in selected_by_group.get(key, []) or []:
                candidates.append(TripAdvisorHotelGathering._normalize_filter_text(value))
        return list(dict.fromkeys(candidates))


    @classmethod
    def _diagnose_single_query(cls, query: MultiCandidateQuery, info: InfoDict) -> tuple[list[str], list[str]]:
        matches: list[str] = []
        misses: list[str] = []

        def record(label: str, ok: bool) -> None:
            (matches if ok else misses).append(label)

        if brands := query.get("brand"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "brands", "activeFilters"])
            hotel_name = cls._normalize_filter_text(info.get("hotelName") or "")
            for brand in brands:
                lowered = cls._normalize_filter_text(brand)
                record(f"brand:{brand}", lowered in hotel_name or any(lowered in item for item in available))

        if geographic_ids := query.get("geographic_ids"):
            info_geo = (info.get("geographicId") or "").lower()
            for geographic_id in geographic_ids:
                record(f"geographic_id:{geographic_id}", info_geo == geographic_id.lower())

        if cities := query.get("cities"):
            city_slug = (info.get("citySlug") or "").lower().replace("_", " ")
            for city in cities:
                lowered = cls._normalize_filter_text(city)
                record(f"city:{city}", lowered in city_slug)

        if (guests := query.get("guests")) is not None:
            record(f"guests:{guests}", info.get("guests") == guests)

        if (rooms := query.get("rooms")) is not None:
            record(f"rooms:{rooms}", info.get("rooms") == rooms)

        if check_in := query.get("check_in"):
            record(f"check_in:{check_in}", cls._dates_match(info.get("checkIn"), check_in))

        if check_out := query.get("check_out"):
            record(f"check_out:{check_out}", cls._dates_match(info.get("checkOut"), check_out))

        if departure_month := query.get("departure_month"):
            record(f"departure_month:{departure_month}", cls._months_match(info.get("departureMonth"), departure_month))

        if amenities := query.get("amenities"):
            available = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "amenities",
                    "deals",
                    "awards",
                    "propertyTypes",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                ],
            )
            for amenity in amenities:
                lowered = cls._normalize_filter_text(amenity)
                record(amenity, any(lowered in item for item in available))

        if styles := query.get("styles"):
            available = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "styles",
                    "deals",
                    "awards",
                    "propertyTypes",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                ],
            )
            for style in styles:
                lowered = cls._normalize_filter_text(style)
                record(style, any(lowered in item for item in available))

        if property_types := query.get("propertyTypes"):
            available = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "propertyTypes",
                    "deals",
                    "awards",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                ],
            )
            for property_type in property_types:
                lowered = cls._normalize_filter_text(property_type)
                record(property_type, any(lowered in item for item in available))

        if required_filters := query.get("required_filters"):
            available = cls._collect_filter_candidates(
                info,
                [
                    "selectedFilterBarValues",
                    "amenities",
                    "styles",
                    "brands",
                    "deals",
                    "awards",
                    "propertyTypes",
                    "neighborhoods",
                    "travelerRatings",
                    "hotelClasses",
                    "popularFilters",
                    "activeFilters",
                    "cuisines",
                    "dishes",
                    "establishmentTypes",
                    "mealTypes",
                    "diets",
                    "diningOptions",
                ],
            )
            for required in required_filters:
                lowered = cls._normalize_filter_text(required)
                record(required, any(lowered in item for item in available))

        if (min_stars := query.get("min_stars")) is not None:
            available = cls._collect_filter_candidates(info, ["hotelClasses", "popularFilters", "activeFilters"])
            label = f"{min_stars} star"
            record(label, any(label in item or f"{label}s" in item for item in available))

        if sort_orders := query.get("sort_orders"):
            info_sort = cls._normalize_sort_text(info.get("sortOrder") or "")
            for sort_order in sort_orders:
                normalized_sort = cls._normalize_sort_text(sort_order)
                record(
                    f"sort:{sort_order}",
                    bool(
                        info_sort == normalized_sort or
                        normalized_sort in info_sort or
                        info_sort in normalized_sort
                    ),
                )

        if cuisines := query.get("cuisines"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cuisines", "activeFilters"])
            for cuisine in cuisines:
                lowered = cls._normalize_filter_text(cuisine)
                record(f"cuisine:{cuisine}", any(lowered in item for item in available))

        if establishment_types := query.get("establishmentTypes"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "establishmentTypes", "activeFilters"])
            for est_type in establishment_types:
                lowered = cls._normalize_filter_text(est_type)
                record(f"establishment:{est_type}", any(lowered in item for item in available))

        if meal_types := query.get("mealTypes"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "mealTypes", "activeFilters"])
            for meal_type in meal_types:
                lowered = cls._normalize_filter_text(meal_type)
                record(f"meal:{meal_type}", any(lowered in item for item in available))

        if query_diets := query.get("diets"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "diets", "activeFilters"])
            for diet in query_diets:
                lowered = cls._normalize_filter_text(diet)
                record(f"diet:{diet}", any(lowered in item for item in available))

        if dining_options := query.get("diningOptions"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "diningOptions", "activeFilters"])
            for option in dining_options:
                lowered = cls._normalize_filter_text(option)
                record(f"diningOption:{option}", any(lowered in item for item in available))

        if neighborhoods := query.get("neighborhoods"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "neighborhoods", "activeFilters"])
            for neighborhood in neighborhoods:
                lowered = cls._normalize_filter_text(neighborhood)
                record(f"neighborhood:{neighborhood}", any(lowered in item for item in available))

        if cruise_lines := query.get("cruiseLines"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cruiseLines", "activeFilters"])
            for cruise_line in cruise_lines:
                lowered = cls._normalize_filter_text(cruise_line)
                record(f"cruiseLine:{cruise_line}", any(lowered in item for item in available))

        if departing_from := query.get("departingFrom"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "departingFrom", "activeFilters"])
            for departure in departing_from:
                lowered = cls._normalize_filter_text(departure)
                record(f"departingFrom:{departure}", any(lowered in item for item in available))

        if cruise_lengths := query.get("cruiseLengths"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cruiseLengths", "activeFilters"])
            for cruise_length in cruise_lengths:
                lowered = cls._normalize_filter_text(cruise_length)
                record(f"cruiseLength:{cruise_length}", any(lowered in item for item in available))

        if cruise_styles := query.get("cruiseStyles"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cruiseStyles", "activeFilters"])
            for cruise_style in cruise_styles:
                lowered = cls._normalize_filter_text(cruise_style)
                record(f"cruiseStyle:{cruise_style}", any(lowered in item for item in available))

        if ships := query.get("ships"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "ships", "activeFilters"])
            for ship in ships:
                lowered = cls._normalize_filter_text(ship)
                record(f"ship:{ship}", any(lowered in item for item in available))

        if cabin_types := query.get("cabinTypes"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "cabinTypes", "activeFilters"])
            for cabin_type in cabin_types:
                lowered = cls._normalize_filter_text(cabin_type)
                record(f"cabinType:{cabin_type}", any(lowered in item for item in available))

        if ports := query.get("ports"):
            available = cls._collect_filter_candidates(info, ["selectedFilterBarValues", "ports", "activeFilters"])
            for port in ports:
                lowered = cls._normalize_filter_text(port)
                record(f"port:{port}", any(lowered in item for item in available))

        if date := query.get("date"):
            record(f"date:{date}", cls._dates_match(info.get("checkIn"), date) or cls._dates_match(info.get("urlDate"), date))

        if time_val := query.get("time"):
            record(f"time:{time_val}", cls._times_match(info.get("reservationTime"), time_val) or cls._times_match(info.get("urlTime"), time_val))

        if (min_price := query.get("min_price")) is not None:
            record(f"min_price:{min_price}", cls._extract_price_bound(info, "min") == float(min_price))

        if (max_price := query.get("max_price")) is not None:
            record(f"max_price:{max_price}", cls._extract_price_bound(info, "max") == float(max_price))

        return matches, misses

    @classmethod
    def _expected_filter_candidates(cls, query: MultiCandidateQuery) -> set[str]:
        candidates: set[str] = set()
        filter_fields = [
            "required_filters",
            "amenities",
            "styles",
            "propertyTypes",
            "brand",
            "deals",
            "awards",
            "neighborhoods",
            "travelerRatings",
            "hotelClasses",
            "cruiseLines",
            "departingFrom",
            "cruiseLengths",
            "cruiseStyles",
            "ships",
            "cabinTypes",
            "ports",
            "cuisines",
            "dishes",
            "establishmentTypes",
            "mealTypes",
            "diets",
            "diningOptions",
        ]
        for field in filter_fields:
            for value in query.get(field) or []:
                candidates.add(cls._normalize_filter_text(value))

        if (min_stars := query.get("min_stars")) is not None:
            candidates.add(cls._normalize_filter_text(f"{min_stars} star"))
            candidates.add(cls._normalize_filter_text(f"{min_stars} stars"))

        if cities := query.get("cities"):
            for city in cities:
                candidates.add(cls._normalize_filter_text(city))

        if geographic_ids := query.get("geographic_ids"):
            for geographic_id in geographic_ids:
                candidates.add(cls._normalize_filter_text(geographic_id))

        if sort_orders := query.get("sort_orders"):
            for sort_order in sort_orders:
                candidates.add(cls._normalize_sort_text(sort_order))

        candidates.update(cls._expected_price_filter_candidates(query))

        return candidates

    RESTAURANT_DEFAULT_FILTERS = {"restaurants"}

    @classmethod
    def _detect_extra_filters(cls, query: MultiCandidateQuery, info: InfoDict) -> list[str]:
        expected = cls._expected_filter_candidates(query)

        # Only activeFilters and selectedFilterBarValues represent filters the
        # user explicitly applied. Individual category fields (styles, amenities,
        # brands, etc.) reflect sidebar items that may be visible but unselected,
        # so scanning them produces false extras.
        raw_values: list[str] = []
        for key in ("activeFilters", "selectedFilterBarValues"):
            for value in info.get(key, []) or []:
                raw_values.append(value)
            for value in (info.get("selectedFiltersByGroup", {}) or {}).get(key, []) or []:
                raw_values.append(value)

        if not raw_values:
            return []

        is_restaurant = info.get("pageType") == "restaurant_results"
        ignorable = cls.RESTAURANT_DEFAULT_FILTERS if is_restaurant else set()

        extras = []
        seen = set()
        for original in raw_values:
            normalized = cls._normalize_filter_text(original)
            if (query.get("min_price") is not None or query.get("max_price") is not None) and re.fullmatch(r"\$?\d[\d,]*(?:\.\d+)?(?:\s+\$?\d[\d,]*(?:\.\d+)?)+", normalized):
                continue
            if normalized and normalized not in expected and normalized not in ignorable and normalized not in seen:
                extras.append(original)
                seen.add(normalized)
        return extras

    def _diagnose_requested_fields(self, info: InfoDict) -> tuple[list[str], list[str], list[str]]:
        best_matches: list[str] = []
        best_misses: list[str] | None = None
        best_extras: list[str] = []

        for alternatives in self.queries:
            for query in alternatives:
                matches, misses = self._diagnose_single_query(query, info)
                extras = self._detect_extra_filters(query, info)
                if best_misses is None or len(misses) < len(best_misses) or (
                    len(misses) == len(best_misses) and len(extras) < len(best_extras)
                ):
                    best_matches = matches
                    best_misses = misses
                    best_extras = extras
                if not misses and not extras:
                    return matches, misses, extras

        return best_matches, best_misses or [], best_extras or []


def generate_task_config_deterministic(
    mode: Literal["any", "all"],
    task: str,
    queries: list[list[MultiCandidateQuery]],
    location: str,
    timezone: str,
    timestamp: int | None = None,
    url: str = "https://www.tripadvisor.com/",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    values = values or {}
    try:
        resolved_placeholders, _ = initialize_placeholder_map(user_metadata, values)
    except ValueError:
        resolved_placeholders = {}
        for placeholder_key, raw_value in values.items():
            try:
                single_placeholder_map, _ = initialize_placeholder_map(user_metadata, {placeholder_key: raw_value})
                resolved_placeholders.update(single_placeholder_map)
            except ValueError:
                resolved_placeholders[placeholder_key] = (raw_value, [])
    rendered_task = render_task_statement(task, resolved_placeholders)

    queries = copy.deepcopy(queries)
    for placeholder_key, (rendered_value, iso_dates) in resolved_placeholders.items():
        template_string = "{" + placeholder_key + "}"
        iso_value = iso_dates[0] if iso_dates else rendered_value
        for query_group in queries:
            for query in query_group:
                if query.get("check_in") == template_string:
                    query["check_in"] = iso_value
                if query.get("check_out") == template_string:
                    query["check_out"] = iso_value
                if query.get("date") == template_string:
                    query["date"] = iso_value
                if query.get("departure_month") == template_string:
                    query["departure_month"] = rendered_value

    eval_config = {
        "_target_": get_import_path(TripAdvisorHotelGathering),
        "queries": queries,
    }
    return BaseTaskConfig(url=url, task=rendered_task, user_metadata=user_metadata, eval_config=eval_config)


class ThingsToDoMultiCandidateQuery(TypedDict, total=False):
    cities: list[str] | None
    navbar: list[str] | None
    category: list[str] | None
    type: list[str] | None
    type_filters: list[str] | None
    required_filters: list[str] | None
    sort_orders: list[str] | None
    date_range_contains: list[str] | None
    min_price: int | None
    max_price: int | None
    require_results_page: bool | None


class ThingsToDoInfoDict(TypedDict, total=False):
    url: str
    pageType: str
    antiBotStatus: str
    geographicId: str | None
    citySlug: str | None
    cityName: str | None
    actionBarValues: list[str]
    activeFilters: list[str]
    selectedFiltersByGroup: dict[str, list[str]]
    sortOrder: str | None
    dateRange: dict[str, str | None]
    refreshState: dict[str, bool | str | None]
    tierSelections: dict[str, str | None]
    priceSlider: dict[str, str]
    resultsCount: int
    resultsSample: list[dict]
    requestedMatches: list[str]
    requestedMisses: list[str]


class ThingsToDoFinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[ThingsToDoMultiCandidateQuery]]
    is_query_covered: list[bool]


@beartype
class TripAdvisorThingsToDoGathering(BaseInfoGathering):
    """Gather DOM state from TripAdvisor Things to Do result pages."""

    def __init__(self, queries: list[list[ThingsToDoMultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries
        self._all_infos: list[ThingsToDoInfoDict] = []
        self._is_query_covered: list[bool] = [False] * len(queries)
        self._best_result_info: ThingsToDoInfoDict | None = None

    @functools.cached_property
    def js_script(self) -> str:
        return Path(__file__).with_name("tripadvisor_info_gathering.js").read_text(encoding="utf-8")

    async def reset(self) -> None:
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._best_result_info = None

    async def update(self, **kwargs) -> None:
        page: Page = kwargs["page"]
        url = page.url.lower()
        if "tripadvisor.com" not in url:
            return

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        info: ThingsToDoInfoDict | None = None
        best_score = -1
        last_error: Exception | None = None

        for _ in range(4):
            try:
                await asyncio.sleep(0.75)
                candidate_info: ThingsToDoInfoDict = await page.evaluate(self.js_script)
                candidate_score = self._info_richness(candidate_info)
                if candidate_score > best_score:
                    info = candidate_info
                    best_score = candidate_score
                if candidate_score >= 8:
                    break
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(random.uniform(0.4, 0.8))

        if info is None:
            if last_error is not None:
                logger.warning(f"Failed to extract Things to Do info: {last_error}")
            return

        info["url"] = page.url
        matches, misses = self._diagnose_requested_fields(info)
        info["requestedMatches"] = matches
        info["requestedMisses"] = misses
        self._all_infos.append(info)

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = value.strip().lower()
        normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
        normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
        normalized = normalized.replace("â€™", "'").replace("â€˜", "'")
        normalized = normalized.replace("â€œ", '"').replace("â€", '"')
        normalized = re.sub(r"^\s*remove\s+", " ", normalized)
        normalized = re.sub(r"\s+selected\s*$", " ", normalized)
        normalized = re.sub(r"\(\s*\d[\d,]*\s*\)\s*$", " ", normalized)
        normalized = normalized.replace("&", " and ")
        normalized = normalized.replace("/", " ")
        normalized = normalized.replace("-", " ")
        normalized = " ".join(normalized.split())
        if normalized in {"theatre", "theatres", "theaters"}:
            normalized = "theater"
        if "5 of 5 bubbles" in normalized:
            normalized = "5 bubbles"
        if "4 of 5 bubbles and up" in normalized:
            normalized = "4 of 5 bubbles"
        return normalized

    @classmethod
    def _collect_filter_candidates(cls, info: ThingsToDoInfoDict) -> list[str]:
        candidates: list[str] = []
        for value in info.get("actionBarValues", []) or []:
            candidates.append(cls._normalize_text(value))
        for value in info.get("activeFilters", []) or []:
            candidates.append(cls._normalize_text(value))
        for value in (info.get("tierSelections", {}) or {}).values():
            if value:
                candidates.append(cls._normalize_text(value))
        for values in (info.get("selectedFiltersByGroup", {}) or {}).values():
            for value in values or []:
                candidates.append(cls._normalize_text(value))
        return list(dict.fromkeys(candidates))

    @classmethod
    def _collect_explicit_selected_filters(cls, info: ThingsToDoInfoDict) -> list[str]:
        selected: list[str] = []
        for value in (info.get("tierSelections", {}) or {}).values():
            if value:
                selected.append(cls._normalize_text(value))
        for values in (info.get("selectedFiltersByGroup", {}) or {}).values():
            for value in values or []:
                selected.append(cls._normalize_text(value))
        return list(dict.fromkeys(selected))

    @classmethod
    def _expected_filter_labels(cls, query: ThingsToDoMultiCandidateQuery) -> set[str]:
        expected: set[str] = set()
        for key in ("navbar", "category", "type", "type_filters", "required_filters"):
            for value in (query.get(key) or []):
                expected.add(cls._normalize_text(value))
        return expected

    @classmethod
    def _find_unexpected_filters(cls, query: ThingsToDoMultiCandidateQuery, info: ThingsToDoInfoDict) -> list[str]:
        expected = cls._expected_filter_labels(query)
        actual = cls._collect_explicit_selected_filters(info)
        unexpected: list[str] = []
        for value in actual:
            if value not in expected:
                unexpected.append(value)
        return unexpected

    @staticmethod
    def _parse_price_slider_value(info: ThingsToDoInfoDict, label_fragment: str) -> int | None:
        for label, raw_value in (info.get("priceSlider") or {}).items():
            if label_fragment.lower() in label.lower():
                try:
                    return int(raw_value)
                except (TypeError, ValueError):
                    return None
        return None

    @classmethod
    def _normalize_sort_label(cls, value: str | None) -> str:
        text = cls._normalize_text(value or "")
        if not text:
            return ""
        text = re.sub(r"^(sorted by|sort by|sort)\s+", "", text).strip()
        text = text.replace("traveller", "traveler").replace("favourites", "favorites").strip()
        if text == "traveler ranking":
            return "traveler favorites"
        return text

    @classmethod
    def _decode_sort_token(cls, token: str | None) -> str:
        raw = (token or "").strip()
        if not raw:
            return ""
        decoded = raw.replace("__5F__", " ").replace("__5f__", " ").replace("_", " ").strip()
        return cls._normalize_sort_label(decoded)

    @classmethod
    def _extract_sort_order(cls, info: ThingsToDoInfoDict) -> str:
        sort_order = cls._normalize_sort_label(info.get("sortOrder") or "")
        if sort_order:
            return sort_order

        url = info.get("url") or ""
        path = urlparse(url).path
        match = re.search(r"a_sort\.([A-Z0-9_]+)-", path, re.IGNORECASE)
        if not match:
            return ""

        return cls._decode_sort_token(match.group(1))

    @classmethod
    def _check_multi_candidate_query(cls, query: ThingsToDoMultiCandidateQuery, info: ThingsToDoInfoDict) -> bool:
        if query.get("require_results_page", True) and info.get("pageType") != "things_to_do_results":
            return False

        if cities := query.get("cities"):
            city_slug = cls._extract_city_slug(info)
            if not any(cls._normalize_text(city) in city_slug for city in cities):
                return False

        if navbar := query.get("navbar"):
            current_navbar = cls._normalize_text((info.get("tierSelections", {}) or {}).get("navbar") or "")
            if not any(cls._normalize_text(value) in current_navbar for value in navbar):
                return False

        if category := query.get("category"):
            current_category = cls._normalize_text((info.get("tierSelections", {}) or {}).get("category") or "")
            if not any(cls._normalize_text(value) in current_category for value in category):
                return False

        if type_values := query.get("type"):
            current_type = cls._normalize_text((info.get("tierSelections", {}) or {}).get("type") or "")
            if not any(cls._normalize_text(value) in current_type for value in type_values):
                return False

        candidates = cls._collect_filter_candidates(info)

        if type_filters := query.get("type_filters"):
            for value in type_filters:
                normalized = cls._normalize_text(value)
                if not any(normalized in candidate for candidate in candidates):
                    return False

        if required_filters := query.get("required_filters"):
            for value in required_filters:
                normalized = cls._normalize_text(value)
                if not any(normalized in candidate for candidate in candidates):
                    return False

        if sort_orders := query.get("sort_orders"):
            sort_value = cls._extract_sort_order(info)
            if not any(cls._normalize_text(value) in sort_value for value in sort_orders):
                return False

        if date_range_contains := query.get("date_range_contains"):
            date_text = cls._normalize_text(
                (info.get("dateRange", {}) or {}).get("ariaLabel")
                or (info.get("dateRange", {}) or {}).get("label")
                or ""
            )
            for value in date_range_contains:
                if cls._normalize_text(value) not in date_text:
                    return False

        if (min_price := query.get("min_price")) is not None:
            scraped_min = cls._parse_price_slider_value(info, "minimum")
            if scraped_min is not None and scraped_min < min_price:
                return False

        if (max_price := query.get("max_price")) is not None:
            scraped_max = cls._parse_price_slider_value(info, "maximum")
            if scraped_max is not None and scraped_max > max_price:
                return False

        if cls._find_unexpected_filters(query, info):
            return False

        return True

    @staticmethod
    def _info_richness(info: ThingsToDoInfoDict) -> int:
        score = 0
        if info.get("pageType") == "things_to_do_results":
            score += 2
        score += len(info.get("actionBarValues", []) or [])
        score += len(info.get("activeFilters", []) or [])
        score += min(len(info.get("resultsSample", []) or []), 5)
        if info.get("sortOrder"):
            score += 1
        if (info.get("dateRange") or {}).get("ariaLabel"):
            score += 1
        return score

    @classmethod
    def _extract_city_slug(cls, info: ThingsToDoInfoDict) -> str:
        city_name = info.get("cityName") or ""
        if city_name.strip():
            return cls._normalize_text(city_name)

        city_slug = (info.get("citySlug") or "").replace("_", " ")
        if city_slug.strip():
            return cls._normalize_text(city_slug)

        url = info.get("url") or ""
        path = urlparse(url).path
        match = re.search(r"/(?:Attractions|Activities)-g\d+-(?:.*-)?([A-Za-z][A-Za-z0-9_]+)\.html", path, re.IGNORECASE)
        if match:
            return cls._normalize_text(match.group(1).replace("_", " "))
        return ""

    async def compute(self) -> ThingsToDoFinalResult:
        candidate_infos = [info for info in reversed(self._all_infos) if self._is_scoreable_info(info)]
        self._best_result_info = self._select_best_result_info(candidate_infos)

        for info in candidate_infos:
            for idx, alternatives in enumerate(self.queries):
                if self._is_query_covered[idx]:
                    continue
                if any(self._check_multi_candidate_query(query, info) for query in alternatives):
                    self._is_query_covered[idx] = True

        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)
        return ThingsToDoFinalResult(
            score=n_covered / max(n_queries, 1),
            n_queries=n_queries,
            n_covered=n_covered,
            queries=self.queries,
            is_query_covered=self._is_query_covered,
        )

    @staticmethod
    def _is_scoreable_info(info: ThingsToDoInfoDict) -> bool:
        anti_bot = info.get("antiBotStatus", "clear")
        if anti_bot == "clear":
            return True
        return not (info.get("requestedMisses") or []) and bool(info.get("requestedMatches") or [])

    def _select_best_result_info(self, candidate_infos: list[ThingsToDoInfoDict]) -> ThingsToDoInfoDict | None:
        best_info: ThingsToDoInfoDict | None = None
        best_key: tuple[int, int] | None = None
        for info in candidate_infos:
            coverage_count = sum(
                1
                for alternatives in self.queries
                if any(self._check_multi_candidate_query(query, info) for query in alternatives)
            )
            key = (coverage_count, self._info_richness(info))
            if best_key is None or key > best_key:
                best_key = key
                best_info = info
        return best_info

    def _diagnose_requested_fields(self, info: ThingsToDoInfoDict) -> tuple[list[str], list[str]]:
        best_matches: list[str] = []
        best_misses: list[str] | None = None

        for alternatives in self.queries:
            for query in alternatives:
                matches, misses = self._diagnose_single_query(query, info)
                if best_misses is None or len(misses) < len(best_misses):
                    best_matches = matches
                    best_misses = misses
                if not misses:
                    return matches, misses

        return best_matches, best_misses or []

    @classmethod
    def _diagnose_single_query(cls, query: ThingsToDoMultiCandidateQuery, info: ThingsToDoInfoDict) -> tuple[list[str], list[str]]:
        matches: list[str] = []
        misses: list[str] = []

        def record(label: str, ok: bool) -> None:
            (matches if ok else misses).append(label)

        if cities := query.get("cities"):
            city_slug = cls._extract_city_slug(info)
            for city in cities:
                record(f"city:{city}", cls._normalize_text(city) in city_slug)

        if navbar := query.get("navbar"):
            current_navbar = cls._normalize_text((info.get("tierSelections", {}) or {}).get("navbar") or "")
            for value in navbar:
                record(f"navbar:{value}", cls._normalize_text(value) in current_navbar)

        if category := query.get("category"):
            current_category = cls._normalize_text((info.get("tierSelections", {}) or {}).get("category") or "")
            for value in category:
                record(f"category:{value}", cls._normalize_text(value) in current_category)

        if type_values := query.get("type"):
            current_type = cls._normalize_text((info.get("tierSelections", {}) or {}).get("type") or "")
            for value in type_values:
                record(f"type:{value}", cls._normalize_text(value) in current_type)

        candidates = cls._collect_filter_candidates(info)

        if type_filters := query.get("type_filters"):
            for value in type_filters:
                normalized = cls._normalize_text(value)
                record(f"type:{value}", any(normalized in candidate for candidate in candidates))

        if required_filters := query.get("required_filters"):
            for value in required_filters:
                normalized = cls._normalize_text(value)
                record(value, any(normalized in candidate for candidate in candidates))

        if sort_orders := query.get("sort_orders"):
            sort_value = cls._extract_sort_order(info)
            for value in sort_orders:
                record(f"sort:{value}", cls._normalize_text(value) in sort_value)

        if date_range_contains := query.get("date_range_contains"):
            date_text = cls._normalize_text(
                (info.get("dateRange", {}) or {}).get("ariaLabel")
                or (info.get("dateRange", {}) or {}).get("label")
                or ""
            )
            for value in date_range_contains:
                record(f"date:{value}", cls._normalize_text(value) in date_text)

        if (min_price := query.get("min_price")) is not None:
            scraped_min = cls._parse_price_slider_value(info, "minimum")
            record(f"min_price:{min_price}", scraped_min is not None and scraped_min >= min_price)

        if (max_price := query.get("max_price")) is not None:
            scraped_max = cls._parse_price_slider_value(info, "maximum")
            record(f"max_price:{max_price}", scraped_max is not None and scraped_max <= max_price)

        for value in cls._find_unexpected_filters(query, info):
            record(f"extra:{value}", False)

        return matches, misses


def generate_thingstodo_task_config_deterministic(
    mode: Literal["any", "all"],
    task: str,
    queries: list[list[ThingsToDoMultiCandidateQuery]],
    location: str,
    timezone: str,
    timestamp: int | None = None,
    url: str = "https://www.tripadvisor.com/Attractions",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    values = values or {}
    resolved_placeholders, _ = initialize_placeholder_map(user_metadata, values)
    rendered_task = render_task_statement(task, resolved_placeholders)

    queries = copy.deepcopy(queries)
    for placeholder_key, (rendered_value, _) in resolved_placeholders.items():
        template_string = "{" + placeholder_key + "}"
        for query_group in queries:
            for query in query_group:
                if "date_range_contains" in query:
                    query["date_range_contains"] = [
                        rendered_value if item == template_string else item
                        for item in (query.get("date_range_contains") or [])
                    ]

    eval_config = {
        "_target_": get_import_path(TripAdvisorThingsToDoGathering),
        "queries": queries,
    }
    return BaseTaskConfig(url=url, task=rendered_task, user_metadata=user_metadata, eval_config=eval_config)


TRIPADVISOR_HOTEL_PATH_RE = re.compile(
    r"^/Hotels-(?P<geo_id>g\d+)-.*\.html$",
    re.IGNORECASE,
)


class TripAdvisorUrlInputDict(TypedDict, total=False):
    url: str


class TripAdvisorUrlMatchResult(BaseModel):
    score: float


InputDict = TripAdvisorUrlInputDict


class TripAdvisorUrlDetails(BaseModel):
    is_hotel_url: bool
    geographic_id: str | None = None
    normalized_url: str = ""


def normalize_tripadvisor_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


_normalize_url = normalize_tripadvisor_url


def is_tripadvisor_hotel_url(url: str) -> bool:
    """Return True when the URL points to a TripAdvisor hotel-results page."""
    parsed = urlparse(normalize_tripadvisor_url(url))
    host = (parsed.hostname or "").lower()
    if "tripadvisor.com" not in host:
        return False
    return bool(TRIPADVISOR_HOTEL_PATH_RE.match(parsed.path))


def extract_geographic_id(url: str) -> str | None:
    """Extract the TripAdvisor geographic ID such as ``g187791`` from the URL."""
    parsed = urlparse(normalize_tripadvisor_url(url))
    match = TRIPADVISOR_HOTEL_PATH_RE.match(parsed.path)
    return match.group("geo_id").lower() if match else None


def get_tripadvisor_url_details(url: str) -> TripAdvisorUrlDetails:
    normalized_url = normalize_tripadvisor_url(url)
    return TripAdvisorUrlDetails(
        is_hotel_url=is_tripadvisor_hotel_url(normalized_url),
        geographic_id=extract_geographic_id(normalized_url),
        normalized_url=normalized_url,
    )


@beartype
class TripAdvisorUrlMatch(BaseMetric):
    """Simple URL verifier for TripAdvisor hotel pages.

    A match succeeds when:
    - the visited URL is a TripAdvisor hotel-results page, and
    - its geographic ID matches the ground-truth geographic ID.
    """

    def __init__(self, gt_url: str) -> None:
        super().__init__()
        self.gt_url = gt_url
        self._matched = False

        gt_details = get_tripadvisor_url_details(gt_url)
        self._gt_geo_id = gt_details.geographic_id

    async def reset(self) -> None:
        self._matched = False

    async def update(self, **kwargs) -> None:
        inputs: TripAdvisorUrlInputDict = kwargs
        url = inputs.get("url", "")
        details = get_tripadvisor_url_details(url)
        if not details.is_hotel_url:
            return

        if self._gt_geo_id and details.geographic_id == self._gt_geo_id:
            self._matched = True

    async def compute(self) -> TripAdvisorUrlMatchResult:
        return TripAdvisorUrlMatchResult(score=1.0 if self._matched else 0.0)
