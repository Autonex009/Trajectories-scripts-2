"""TripAdvisor Things to Do info gathering verifier."""

import asyncio
import copy
import functools
import random
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

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


class InfoDict(TypedDict, total=False):
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


class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]


@beartype
class TripAdvisorThingsToDoGathering(BaseInfoGathering):
    """Gather DOM state from TripAdvisor Things to Do result pages."""

    def __init__(self, queries: list[list[MultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries
        self._all_infos: list[InfoDict] = []
        self._is_query_covered: list[bool] = [False] * len(queries)
        self._best_result_info: InfoDict | None = None

    @functools.cached_property
    def js_script(self) -> str:
        return Path(__file__).with_name("tripadvisor_thingstodo_info_gathering.js").read_text(encoding="utf-8")

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

        info: InfoDict | None = None
        best_score = -1
        last_error: Exception | None = None

        for _ in range(4):
            try:
                await asyncio.sleep(0.75)
                candidate_info: InfoDict = await page.evaluate(self.js_script)
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
    def _collect_filter_candidates(cls, info: InfoDict) -> list[str]:
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
    def _collect_explicit_selected_filters(cls, info: InfoDict) -> list[str]:
        selected: list[str] = []
        for value in (info.get("tierSelections", {}) or {}).values():
            if value:
                selected.append(cls._normalize_text(value))
        for values in (info.get("selectedFiltersByGroup", {}) or {}).values():
            for value in values or []:
                selected.append(cls._normalize_text(value))
        return list(dict.fromkeys(selected))

    @classmethod
    def _expected_filter_labels(cls, query: MultiCandidateQuery) -> set[str]:
        expected: set[str] = set()
        for key in ("navbar", "category", "type", "type_filters", "required_filters"):
            for value in (query.get(key) or []):
                expected.add(cls._normalize_text(value))
        return expected

    @classmethod
    def _find_unexpected_filters(cls, query: MultiCandidateQuery, info: InfoDict) -> list[str]:
        expected = cls._expected_filter_labels(query)
        actual = cls._collect_explicit_selected_filters(info)
        unexpected: list[str] = []
        for value in actual:
            if value not in expected:
                unexpected.append(value)
        return unexpected

    @staticmethod
    def _parse_price_slider_value(info: InfoDict, label_fragment: str) -> int | None:
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
    def _extract_sort_order(cls, info: InfoDict) -> str:
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
    def _check_multi_candidate_query(cls, query: MultiCandidateQuery, info: InfoDict) -> bool:
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
    def _info_richness(info: InfoDict) -> int:
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
    def _extract_city_slug(cls, info: InfoDict) -> str:
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

    async def compute(self) -> FinalResult:
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

    @staticmethod
    def _is_scoreable_info(info: InfoDict) -> bool:
        anti_bot = info.get("antiBotStatus", "clear")
        if anti_bot == "clear":
            return True
        return not (info.get("requestedMisses") or []) and bool(info.get("requestedMatches") or [])

    def _select_best_result_info(self, candidate_infos: list[InfoDict]) -> InfoDict | None:
        best_info: InfoDict | None = None
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

    def _diagnose_requested_fields(self, info: InfoDict) -> tuple[list[str], list[str]]:
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
    def _diagnose_single_query(cls, query: MultiCandidateQuery, info: InfoDict) -> tuple[list[str], list[str]]:
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


def generate_task_config_deterministic(
    mode: Literal["any", "all"],
    task: str,
    queries: list[list[MultiCandidateQuery]],
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
