"""Hotels.com URL Match verifier for hotel search navigation.

This module provides functionality to verify AI agent navigation on Hotels.com
by comparing the agent's final URL against expected ground truth URLs.

Hotels.com is part of the Expedia Group and uses the SAME URL structure as
Expedia for hotel searches. This is a URL-BASED verifier — all search state
is encoded in the URL query parameters, not in the DOM.

The verifier handles all Hotels.com URL variations including:
- Search results path: /Hotel-Search?destination=...&startDate=...&endDate=...
- Destination: destination=New%20York (URL-encoded city name)
- Region ID: regionId=2621 (numeric internal area identifier)
- Check-in / Check-out: startDate=YYYY-MM-DD, endDate=YYYY-MM-DD
  Alternative params: d1, d2, checkIn, checkOut (all normalized)
- Adults: adults=2 (single room) or adults=2,1,1 (multi-room, comma-separated)
- Rooms: rooms=1 (number of rooms)
- Children: children=1_5,1_10 (RoomIndex_Age format, comma-separated)
  Alternative: childrenAges=5,10 (legacy format)
- Sort: sort=RECOMMENDED|PRICE_LOW_TO_HIGH|PRICE_HIGH_TO_LOW|DISTANCE|REVIEW
         |GUEST_RATING|STAR_RATING_HIGHEST_FIRST
- Star rating filter: f-star-rating=4,5 (comma-separated star levels)
- Price filter: f-price-min=50, f-price-max=200 (in dollars, NOT cents)
- Amenities filter: f-amenities=WIFI,POOL,FREE_BREAKFAST (comma-separated codes)
- Guest rating filter: f-guest-rating=8 (minimum rating threshold)
- Payment type: paymentType=FREE_CANCELLATION|PAY_LATER

Browser-Verified CLICKABLE Filters (Jun 2026 on hotels.com):
  Search bar (top):
    destination, startDate, endDate, adults, rooms, children
  Filter pills / sidebar:
    sort, f-star-rating, f-price, f-amenities, f-guest-rating, paymentType

Note: Hotels.com is an Expedia Group property. Its URL structure is nearly
identical to expedia.com/Hotel-Search. Prices are in DOLLARS (not cents).
"""

import re
from datetime import datetime
from itertools import product
from typing import Any, TypedDict
from urllib.parse import parse_qs, unquote, urlparse

from beartype import beartype
from loguru import logger
from pydantic import BaseModel

from navi_bench.base import BaseMetric, BaseTaskConfig, get_import_path
from navi_bench.dates import (
    initialize_placeholder_map,
    initialize_user_metadata,
    render_task_statement,
)


# =============================================================================
# TypedDicts
# =============================================================================


class InputDict(TypedDict, total=False):
    url: str


class FinalResult(BaseModel):
    score: float


class HotelsComVerifierResult(BaseModel):
    """Detailed verification result for Hotels.com URL matching."""

    score: float
    match: bool
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}


# =============================================================================
# CONSTANTS
# =============================================================================

# Valid Hotels.com domain patterns
VALID_BASE_DOMAINS = {
    "hotels.com",
    "www.hotels.com",
}

# Regional / localized domains (Hotels.com serves many country variants)
REGIONAL_DOMAINS = {
    "in.hotels.com",      # India
    "uk.hotels.com",      # United Kingdom
    "de.hotels.com",      # Germany
    "fr.hotels.com",      # France
    "es.hotels.com",      # Spain
    "it.hotels.com",      # Italy
    "jp.hotels.com",      # Japan
    "kr.hotels.com",      # South Korea
    "au.hotels.com",      # Australia
    "ca.hotels.com",      # Canada
    "mx.hotels.com",      # Mexico
    "br.hotels.com",      # Brazil
    "ar.hotels.com",      # Argentina
    "sg.hotels.com",      # Singapore
    "hk.hotels.com",      # Hong Kong
    "tw.hotels.com",      # Taiwan
    "nz.hotels.com",      # New Zealand
    "se.hotels.com",      # Sweden
    "no.hotels.com",      # Norway
    "dk.hotels.com",      # Denmark
    "fi.hotels.com",      # Finland
    "ie.hotels.com",      # Ireland
    "at.hotels.com",      # Austria
    "ch.hotels.com",      # Switzerland
    "nl.hotels.com",      # Netherlands
    "za.hotels.com",      # South Africa
    "my.hotels.com",      # Malaysia
    "ph.hotels.com",      # Philippines
    "th.hotels.com",      # Thailand
    "id.hotels.com",      # Indonesia
}

# Sort normalization mapping (browser-verified Jun 2026)
SORT_MAP = {
    # Canonical uppercase values (pass through)
    "RECOMMENDED": "RECOMMENDED",
    "PRICE_LOW_TO_HIGH": "PRICE_LOW_TO_HIGH",
    "PRICE_HIGH_TO_LOW": "PRICE_HIGH_TO_LOW",
    "DISTANCE": "DISTANCE",
    "DISTANCE_FROM_LANDMARK": "DISTANCE_FROM_LANDMARK",
    "REVIEW": "REVIEW",
    "GUEST_RATING": "GUEST_RATING",
    "STAR_RATING_HIGHEST_FIRST": "STAR_RATING_HIGHEST_FIRST",
    # Lowercase aliases
    "recommended": "RECOMMENDED",
    "price_low_to_high": "PRICE_LOW_TO_HIGH",
    "price": "PRICE_LOW_TO_HIGH",
    "price_high_to_low": "PRICE_HIGH_TO_LOW",
    "distance": "DISTANCE",
    "distance_from_landmark": "DISTANCE_FROM_LANDMARK",
    "review": "REVIEW",
    "review_score": "REVIEW",
    "guest_rating": "GUEST_RATING",
    "star_rating_highest_first": "STAR_RATING_HIGHEST_FIRST",
    "star_rating": "STAR_RATING_HIGHEST_FIRST",
    # Common aliases an agent might use
    "lowest_price": "PRICE_LOW_TO_HIGH",
    "cheapest": "PRICE_LOW_TO_HIGH",
    "highest_price": "PRICE_HIGH_TO_LOW",
    "most_expensive": "PRICE_HIGH_TO_LOW",
    "closest": "DISTANCE",
    "best_reviewed": "REVIEW",
    "top_rated": "GUEST_RATING",
    "stars": "STAR_RATING_HIGHEST_FIRST",
}

# Query parameters to IGNORE during comparison (tracking, session, UI state)
IGNORED_PARAMS = {
    "locale",
    "currency",
    "siteid",
    "rfrr",
    "tpid",
    "eapid",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "ref",
    "latLong",
    "theme",
    "userIntent",
    "selected",
    "searchId",
    "propertyId",
    "gclid",
    "msclkid",
    "semdtl",
    "semcid",
    "pwaDialogNested",
    "mapBounds",
    "neighborhood",
    "flexibility",
    "pos",
    "referrerUrl",
    # Auto-generated by Hotels.com during search execution
    "typeaheadCollationId",
    "regionId",
    "categorySearch",
    "useRewards",
    "d1",              # duplicate of startDate (auto-added)
    "d2",              # duplicate of endDate (auto-added)
    # Car search auto-generated params
    "dpln",            # destination ID (auto-set from location)
    "drid1",           # drop-off region ID (auto-set)
    "olat",            # pickup latitude (auto-set)
    "olon",            # pickup longitude (auto-set)
    "dlat",            # drop-off latitude (auto-set)
    "dlon",            # drop-off longitude (auto-set)
    "selPageIndex",    # pagination state
    "selCC",           # car class filter (separate comparison if needed)
}


# =============================================================================
# PARSING HELPERS
# =============================================================================


def _get_param(query: dict, *keys: str) -> str:
    """Get the first non-empty value from query dict for any of the keys.

    Handles both exact keys and case-insensitive fallback.
    """
    for key in keys:
        if key in query and query[key]:
            return query[key][0]
        key_lower = key.lower()
        if key_lower in query and query[key_lower]:
            return query[key_lower][0]
    return ""


def _normalize_date(date_str: str) -> str:
    """Normalize a date string to YYYY-MM-DD format.

    Handles multiple Hotels.com date formats:
      - YYYY-MM-DD (standard — most common)
      - YYYY-M-D   (e.g., 2026-7-1 — from d1/d2 params)
      - M/D/YYYY   (e.g., 7/1/2026 — legacy format)
    """
    if not date_str:
        return ""

    date_str = date_str.strip()

    # M/D/YYYY format
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # YYYY-M-D or YYYY-MM-DD format
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", date_str)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    return date_str


def _normalize_sort(raw: str) -> str:
    """Normalize sort order to canonical uppercase value."""
    if not raw:
        return ""
    raw_clean = raw.strip()
    # Try direct lookup
    if raw_clean in SORT_MAP:
        return SORT_MAP[raw_clean]
    # Try lowercase
    raw_lower = raw_clean.lower().replace(" ", "_")
    return SORT_MAP.get(raw_lower, raw_clean.upper())


def _normalize_destination(raw: str) -> str:
    """Normalize a destination string for comparison.

    - URL-decode
    - Lowercase
    - Take only the city part (before first comma)
    - Strip whitespace
    """
    if not raw:
        return ""
    decoded = unquote(raw).strip().lower()
    # Take only the city part (e.g., "New York, New York, United States" → "new york")
    return decoded.split(",")[0].strip()


def _normalize_star_value(raw: str) -> str:
    """Normalize a single star rating value.

    Hotels.com uses x10 values in the browser:
        star=40 → '4' (4-star)
        star=50 → '5' (5-star)
        star=30 → '3' (3-star)
    Legacy GT URLs might use plain values:
        star=4  → '4'
        f-star-rating=4,5 → '4', '5'

    Strategy: if the value is a number ≥ 10, divide by 10.
    """
    if not raw:
        return ""
    raw = raw.strip()
    try:
        val = int(raw)
        if val >= 10:
            return str(val // 10)
        return str(val)
    except ValueError:
        return raw


def _parse_star_rating(raw: str) -> list[str]:
    """Parse star rating filter into sorted list of values.

    Input: "4,5" or "3,4,5" (comma-separated)
    Output: ["4", "5"] or ["3", "4", "5"]
    """
    if not raw:
        return []
    parts = [_normalize_star_value(p.strip()) for p in raw.split(",") if p.strip()]
    return sorted(parts)


def _parse_amenities(raw: str) -> list[str]:
    """Parse amenities filter into sorted list of values.

    Input: "WIFI,POOL,FREE_BREAKFAST" (comma-separated)
    Output: ["FREE_BREAKFAST", "POOL", "WIFI"]
    """
    if not raw:
        return []
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    return sorted(parts)

def _parse_multi_value_filter(values: list[str]) -> list[str]:
    """Parse repeated query-param filters into a normalized sorted list.

    Example:
        amenities=POOL&amenities=PETS
        -> ["PETS", "POOL"]
    """

    if not values:
        return []

    return sorted(
        value.strip().upper()
        for value in values
        if value and value.strip()
    )

def _parse_price_range(query: dict) -> tuple[int | None, int | None]:
    """
    Hotels.com price filters.

    Examples:

    nightly_price=256&nightly_price=462
        -> (256, 462)

    nightly_price=123&nightly_price=-2
        -> (123, None)

    nightly_price=-3&nightly_price=462
        -> (None, 462)
    """

    values = query.get("nightly_price", [])

    if len(values) >= 2:
        low = values[0]
        high = values[1]

        min_price = None
        max_price = None

        if low.isdigit():
            min_price = int(low)

        if high.isdigit():
            max_price = int(high)

        return min_price, max_price

    # legacy support
    price_min_raw = _get_param(query, "f-price-min", "price_min")
    price_max_raw = _get_param(query, "f-price-max", "price_max")

    price_min = (
        int(price_min_raw)
        if price_min_raw and price_min_raw.isdigit()
        else None
    )

    price_max = (
        int(price_max_raw)
        if price_max_raw and price_max_raw.isdigit()
        else None
    )

    return price_min, price_max

# =============================================================================
# URL PARSER
# =============================================================================


def parse_hotels_com_url(url: str) -> dict[str, Any]:
    """Parse a Hotels.com Hotel-Search URL into normalized components.

    Browser-verified Hotel URL anatomy (Jun 2026):
      /Hotel-Search?destination=New%20York%2C%20New%20York%2C%20United%20States
        &regionId=2621
        &startDate=2026-07-01&endDate=2026-07-05
        &adults=2
        &rooms=1
        &sort=RECOMMENDED
        [&children=1_5,1_10]  (RoomIndex_Age format)
        [&f-star-rating=4,5]
        [&paymentType=FREE_CANCELLATION]

    Returns dict with keys:
      destination, region_id, start_date, end_date,
      adults, rooms, children, children_ages, sort,
      star_rating, price_min, price_max, amenities,
      guest_rating, payment_type
    """
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=True)

    # --- Children parsing ---
    # Format A (browser-verified): children=1_5,1_10 (RoomIndex_Age)
    # Format B (legacy): childrenAges=5,10 (comma-separated)
    children_raw = _get_param(query, "children")
    children_ages_raw = _get_param(
        query, "childrenAges", "children_ages", "childrenAge"
    )

    children_count = ""
    children_ages: list[str] = []

    if children_raw and "_" in children_raw:
        # Browser-verified RoomIndex_Age format: children=1_5,1_10
        entries = [e.strip() for e in children_raw.split(",") if e.strip()]
        for entry in entries:
            parts = entry.split("_", 1)
            if len(parts) == 2:
                children_ages.append(parts[1])
            else:
                children_ages.append(entry)
        children_count = str(len(entries))
        children_ages = sorted(children_ages)
    elif children_ages_raw:
        # Legacy format: childrenAges=5,10
        children_ages = sorted(
            [a.strip() for a in children_ages_raw.split(",") if a.strip()]
        )
        children_count = _get_param(query, "children") or str(len(children_ages))
    elif children_raw:
        # Plain count without ages (e.g., children=2)
        children_count = children_raw

    # --- Adults (multi-room support) ---
    # adults=2 (single room) or adults=2,1,1 (multi-room: 2+1+1=4 total, 3 rooms)
    adults_raw = _get_param(query, "adults")
    if adults_raw and "," in adults_raw:
        adult_parts = [a.strip() for a in adults_raw.split(",") if a.strip()]
        adults_total = str(sum(int(a) for a in adult_parts if a.isdigit()))
        rooms_from_adults = str(len(adult_parts))
    else:
        adults_total = adults_raw
        rooms_from_adults = ""

    rooms_raw = _get_param(query, "rooms")
    rooms = (
        rooms_from_adults
        if rooms_from_adults and int(rooms_from_adults) > 1
        else rooms_raw
    )

    # --- Dates ---
    start_date = _normalize_date(
        _get_param(query, "startDate", "start_date", "checkIn", "checkin", "d1")
    )
    end_date = _normalize_date(
        _get_param(query, "endDate", "end_date", "checkOut", "checkout", "d2")
    )

    # --- Filters ---
    # Star rating: handles both formats:
    #   - Repeated params: star=40&star=50 (browser-generated, x10 values)
    #   - Comma-separated: f-star-rating=4,5 (legacy GT URLs)
    star_values = []

    if "star" in query:
        star_values = query["star"]
    else:
        star_raw = _get_param(query, "f-star-rating")
        if star_raw:
            star_values = star_raw.split(",")

    star_rating = sorted(
        _normalize_star_value(value.strip())
        for value in star_values
        if value.strip()
    )

    # Price range (in dollars)
    price_min, price_max = _parse_price_range(query)
    # price_min_raw = _get_param(query, "f-price-min", "price_min")
    # price_max_raw = _get_param(query, "f-price-max", "price_max")
    # price_min = int(price_min_raw) if price_min_raw and price_min_raw.isdigit() else None
    # price_max = int(price_max_raw) if price_max_raw and price_max_raw.isdigit() else None

    # Amenities: handles both formats:
    #   - Repeated params: amenities=PETS&amenities=WIFI (browser-generated)
    #   - Comma-separated: f-amenities=WIFI,POOL (legacy/GT URLs)
    amenities_multi = query.get("amenities", []) or query.get("f-amenities", [])
    if len(amenities_multi) > 1:
        # Repeated params: amenities=PETS&amenities=WIFI
        amenities = sorted(v.strip().upper() for v in amenities_multi if v.strip())
    else:
        # Single value (possibly comma-separated): f-amenities=WIFI,POOL or amenities=WIFI
        amenities_raw = _get_param(query, "f-amenities", "amenities")
        amenities = _parse_amenities(amenities_raw)

    # Guest rating: handles both formats:
    #   - Browser-generated: guestRating=40 (x10 value, 40 = "Very good 8+")
    #   - Legacy GT: f-guest-rating=8
    # We normalize to the raw value — both sides must use the same format.
    # The verifier compares normalized values, so GT should use the same
    # param name the browser uses.
    guest_rating = _get_param(query, "guestRating", "f-guest-rating", "guest_rating")

    # Payment type: paymentType=FREE_CANCELLATION
    payment_type = _get_param(
        query, "paymentType", "payment_type", "f-payment-type"
    ).upper() if _get_param(query, "paymentType", "payment_type", "f-payment-type") else ""

    # Room view filters
    room_views = _parse_multi_value_filter(
        query.get("room_views_group", [])
    )

    # Room amenities filters
    room_amenities = _parse_multi_value_filter(
        query.get("room_amenities_group", [])
    )

    # Accessibility filters
    accessibility = _parse_multi_value_filter(
        query.get("accessibility", [])
    )

    # Meal plan filters
    meal_plans = _parse_multi_value_filter(
        query.get("mealPlan", [])
    )

    return {
        "destination": _normalize_destination(
            _get_param(query, "destination")
        ),
        "region_id": _get_param(query, "regionId", "region_id"),
        "start_date": start_date,
        "end_date": end_date,
        "adults": adults_total,
        "rooms": rooms,
        "children": children_count,
        "children_ages": children_ages,
        "sort": _normalize_sort(_get_param(query, "sort")),
        "star_rating": star_rating,
        "price_min": price_min,
        "price_max": price_max,
        "amenities": amenities,
        "guest_rating": guest_rating,
        "payment_type": payment_type,
        "room_views": room_views,
        "room_amenities": room_amenities,
        "accessibility": accessibility,
        "meal_plans": meal_plans,
    }


# =============================================================================
# VERIFIER CLASS
# =============================================================================


@beartype
class HotelsComUrlMatch(BaseMetric):
    """URL-based Hotels.com verifier for hotel search tasks.

    This is a URL-BASED verifier. Hotels.com encodes ALL search state in URL
    query parameters. No DOM parsing is needed — the URL alone contains the
    complete search specification.

    Browser-Verified (Jun 2026 on hotels.com):
    - Search path: /Hotel-Search
    - Core params: destination, startDate, endDate, adults, rooms
    - Sort: sort=RECOMMENDED|PRICE_LOW_TO_HIGH|PRICE_HIGH_TO_LOW|DISTANCE|REVIEW
    - Filters: f-star-rating, f-price-min, f-price-max, f-amenities, f-guest-rating
    - Payment: paymentType=FREE_CANCELLATION|PAY_LATER
    - Children: children=RoomIdx_Age (e.g., 1_5,1_10)
    - Domain: hotels.com, www.hotels.com, *.hotels.com (regional)

    Matching Rules:
    - If GT specifies a field and agent omits it → FAIL
    - If GT omits a field → agent value is ignored (pass)
    - Destination: case-insensitive, city-part only (before first comma)
    - Dates: normalized to YYYY-MM-DD, exact match
    - Sort: alias-normalized exact match
    - Star rating: sorted-set equality (order-independent)
    - Amenities: sorted-set equality
    - Price: exact integer match (in dollars)
    - Children ages: sorted-list equality
    """

    def __init__(self, gt_url: str | list[str]) -> None:
        """
        Args:
            gt_url: Ground truth URL(s). If a list is provided, matching ANY
                    URL in the list counts as a match (OR semantics).
        """
        super().__init__()
        if isinstance(gt_url, str):
            self.gt_urls = [gt_url]
        else:
            self.gt_urls = gt_url
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details: dict = {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(gt_urls={self.gt_urls})"

    async def reset(self) -> None:
        """Reset the match state for new evaluation."""
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details = {}

    async def update(self, **kwargs) -> None:
        """Update with new URL to check against ground truth."""
        inputs: InputDict = kwargs
        url = inputs.get("url", "")

        if not url:
            logger.debug("Empty URL provided")
            return

        # Validate domain
        parsed = urlparse(url.strip())
        domain = (parsed.hostname or "").lower()
        if domain and not self._is_valid_hotels_com_domain(domain):
            logger.debug(f"Ignoring non-Hotels.com URL: {url}")
            return

        # Must be a Hotel-Search URL
        path = (parsed.path or "").lower()
        if "hotel-search" not in path:
            logger.debug(f"Ignoring non-search URL: {url}")
            return

        # Don't overwrite after match
        if self._found_match:
            return

        self._agent_url = url

        for gt_url in self.gt_urls:
            match, details = self._urls_match(url, gt_url)
            if match:
                self._found_match = True
                self._matched_gt_url = gt_url
                self._match_details = details
                logger.info(f"Match found: {url[:100]}...")
                return

        logger.info(f"No match found: {url[:100]}...")

    async def compute(self) -> FinalResult:
        """Compute final score (1.0 = match, 0.0 = no match)."""
        score = 1.0 if self._found_match else 0.0
        result = FinalResult(score=score)
        logger.info(f"Final score: {score}")
        return result

    async def compute_detailed(self) -> HotelsComVerifierResult:
        """Compute detailed result with match info."""
        score = 1.0 if self._found_match else 0.0
        return HotelsComVerifierResult(
            score=score,
            match=self._found_match,
            agent_url=self._agent_url,
            gt_url=self._matched_gt_url,
            details=self._match_details,
        )

    # ========================================================================
    # DOMAIN VALIDATION
    # ========================================================================

    @staticmethod
    def _is_valid_hotels_com_domain(domain: str) -> bool:
        """Check if domain is a valid Hotels.com domain.

        Accepts:
        - Exact matches: hotels.com, www.hotels.com
        - Regional subdomains: in.hotels.com, uk.hotels.com, etc.
        - Any subdomain of hotels.com
        """
        domain = domain.lower().rstrip(".")

        # Direct match on known domains
        for base in VALID_BASE_DOMAINS:
            if domain == base:
                return True

        # Known regional domains
        for regional in REGIONAL_DOMAINS:
            if domain == regional:
                return True

        # Any subdomain of hotels.com
        if domain.endswith(".hotels.com"):
            return True

        return False

    # ========================================================================
    # URL MATCHING
    # ========================================================================

    def _urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        """Compare two Hotels.com URLs.

        Performs sequential field comparison. Returns (match, details).
        If any required field mismatches, returns False immediately with
        mismatch details.
        """
        details: dict[str, Any] = {"mismatches": []}

        try:
            agent = parse_hotels_com_url(agent_url)
            gt = parse_hotels_com_url(gt_url)

            # 1. Destination (case-insensitive, city-part only)
            if gt["destination"]:
                if not agent["destination"]:
                    details["mismatches"].append(
                        f"Destination missing (expected '{gt['destination']}')"
                    )
                    return False, details
                if agent["destination"] != gt["destination"]:
                    details["mismatches"].append(
                        f"Destination: '{agent['destination']}' "
                        f"vs '{gt['destination']}'"
                    )
                    return False, details

            # 2. Check-in date
            if gt["start_date"]:
                if not agent["start_date"]:
                    details["mismatches"].append(
                        f"Check-in date missing (expected '{gt['start_date']}')"
                    )
                    return False, details
                if agent["start_date"] != gt["start_date"]:
                    details["mismatches"].append(
                        f"Check-in: '{agent['start_date']}' "
                        f"vs '{gt['start_date']}'"
                    )
                    return False, details

            # 3. Check-out date
            if gt["end_date"]:
                if not agent["end_date"]:
                    details["mismatches"].append(
                        f"Check-out date missing (expected '{gt['end_date']}')"
                    )
                    return False, details
                if agent["end_date"] != gt["end_date"]:
                    details["mismatches"].append(
                        f"Check-out: '{agent['end_date']}' "
                        f"vs '{gt['end_date']}'"
                    )
                    return False, details

            # 4. Adults
            if gt["adults"]:
                if not agent["adults"]:
                    details["mismatches"].append(
                        f"Adults missing (expected '{gt['adults']}')"
                    )
                    return False, details
                if agent["adults"] != gt["adults"]:
                    details["mismatches"].append(
                        f"Adults: '{agent['adults']}' vs '{gt['adults']}'"
                    )
                    return False, details

            # 5. Rooms
            if gt["rooms"]:
                if not agent["rooms"]:
                    details["mismatches"].append(
                        f"Rooms missing (expected '{gt['rooms']}')"
                    )
                    return False, details
                if agent["rooms"] != gt["rooms"]:
                    details["mismatches"].append(
                        f"Rooms: '{agent['rooms']}' vs '{gt['rooms']}'"
                    )
                    return False, details

            # 6. Children count
            if gt["children"]:
                if not agent["children"]:
                    details["mismatches"].append(
                        f"Children missing (expected '{gt['children']}')"
                    )
                    return False, details
                if agent["children"] != gt["children"]:
                    details["mismatches"].append(
                        f"Children: '{agent['children']}' vs '{gt['children']}'"
                    )
                    return False, details

            # 7. Children ages (sorted list comparison)
            if gt["children_ages"]:
                if not agent["children_ages"]:
                    details["mismatches"].append(
                        f"Children ages missing (expected {gt['children_ages']})"
                    )
                    return False, details
                if agent["children_ages"] != gt["children_ages"]:
                    details["mismatches"].append(
                        f"Children ages: {agent['children_ages']} "
                        f"vs {gt['children_ages']}"
                    )
                    return False, details

            # 8. Sort order
            if gt["sort"]:
                if not agent["sort"]:
                    details["mismatches"].append(
                        f"Sort order missing (expected '{gt['sort']}')"
                    )
                    return False, details
                if agent["sort"] != gt["sort"]:
                    details["mismatches"].append(
                        f"Sort: '{agent['sort']}' vs '{gt['sort']}'"
                    )
                    return False, details

            # 9. Star rating (sorted set comparison)
            if gt["star_rating"]:
                if not agent["star_rating"]:
                    details["mismatches"].append(
                        f"Star rating missing (expected {gt['star_rating']})"
                    )
                    return False, details
                if agent["star_rating"] != gt["star_rating"]:
                    details["mismatches"].append(
                        f"Star rating: {agent['star_rating']} "
                        f"vs {gt['star_rating']}"
                    )
                    return False, details

            # 10. Price min
            if gt["price_min"] is not None:
                if agent["price_min"] is None:
                    details["mismatches"].append(
                        f"Price min missing (expected {gt['price_min']})"
                    )
                    return False, details
                if agent["price_min"] != gt["price_min"]:
                    details["mismatches"].append(
                        f"Price min: {agent['price_min']} vs {gt['price_min']}"
                    )
                    return False, details

            # 11. Price max
            if gt["price_max"] is not None:
                if agent["price_max"] is None:
                    details["mismatches"].append(
                        f"Price max missing (expected {gt['price_max']})"
                    )
                    return False, details
                if agent["price_max"] != gt["price_max"]:
                    details["mismatches"].append(
                        f"Price max: {agent['price_max']} vs {gt['price_max']}"
                    )
                    return False, details

            # 12. Amenities (sorted set comparison)
            if gt["amenities"]:
                if not agent["amenities"]:
                    details["mismatches"].append(
                        f"Amenities missing (expected {gt['amenities']})"
                    )
                    return False, details
                if agent["amenities"] != gt["amenities"]:
                    details["mismatches"].append(
                        f"Amenities: {agent['amenities']} "
                        f"vs {gt['amenities']}"
                    )
                    return False, details

            # 13. Guest rating
            if gt["guest_rating"]:
                if not agent["guest_rating"]:
                    details["mismatches"].append(
                        f"Guest rating missing (expected '{gt['guest_rating']}')"
                    )
                    return False, details
                if agent["guest_rating"] != gt["guest_rating"]:
                    details["mismatches"].append(
                        f"Guest rating: '{agent['guest_rating']}' "
                        f"vs '{gt['guest_rating']}'"
                    )
                    return False, details

            # 14. Payment type
            if gt["payment_type"]:
                if not agent["payment_type"]:
                    details["mismatches"].append(
                        f"Payment type missing (expected '{gt['payment_type']}')"
                    )
                    return False, details
                if agent["payment_type"] != gt["payment_type"]:
                    details["mismatches"].append(
                        f"Payment type: '{agent['payment_type']}' "
                        f"vs '{gt['payment_type']}'"
                    )
                    return False, details
            
            # 15. Room views
            if gt["room_views"]:
                if not agent["room_views"]:
                    details["mismatches"].append(
                        f"Room views missing (expected {gt['room_views']})"
                    )
                    return False, details

                if agent["room_views"] != gt["room_views"]:
                    details["mismatches"].append(
                        f"Room views: {agent['room_views']} "
                        f"vs {gt['room_views']}"
                    )
                    return False, details


            # 16. Room amenities
            if gt["room_amenities"]:
                if not agent["room_amenities"]:
                    details["mismatches"].append(
                        f"Room amenities missing (expected {gt['room_amenities']})"
                    )
                    return False, details

                if agent["room_amenities"] != gt["room_amenities"]:
                    details["mismatches"].append(
                        f"Room amenities: {agent['room_amenities']} "
                        f"vs {gt['room_amenities']}"
                    )
                    return False, details


            # 17. Accessibility
            if gt["accessibility"]:
                if not agent["accessibility"]:
                    details["mismatches"].append(
                        f"Accessibility missing (expected {gt['accessibility']})"
                    )
                    return False, details

                if agent["accessibility"] != gt["accessibility"]:
                    details["mismatches"].append(
                        f"Accessibility: {agent['accessibility']} "
                        f"vs {gt['accessibility']}"
                    )
                    return False, details


            # 18. Meal plans
            if gt["meal_plans"]:
                if not agent["meal_plans"]:
                    details["mismatches"].append(
                        f"Meal plans missing (expected {gt['meal_plans']})"
                    )
                    return False, details

                if agent["meal_plans"] != gt["meal_plans"]:
                    details["mismatches"].append(
                        f"Meal plans: {agent['meal_plans']} "
                        f"vs {gt['meal_plans']}"
                    )
                    return False, details

            return True, details

        except Exception as e:
            logger.error(f"Error comparing URLs: {e}")
            details["mismatches"].append(f"Parse error: {str(e)}")
            return False, details


# =============================================================================
# CAR SEARCH URL PARSER
# =============================================================================


def _normalize_time(raw: str) -> str:
    """Normalize a car pickup/dropoff time string.

    Hotels.com uses formats like ``1030AM``, ``0230PM``.
    Normalizes to uppercase with no spaces: e.g. ``1030AM``.
    """
    if not raw:
        return ""
    return raw.strip().upper().replace(" ", "")


def _normalize_car_location(raw: str) -> str:
    """Normalize a car rental location string for comparison.

    - URL-decode
    - Lowercase
    - Take only the city part (before first comma)
    - Strip parenthetical airport info
    - Strip whitespace
    """
    if not raw:
        return ""
    decoded = unquote(raw).strip().lower()
    # Take city part before first comma
    city = decoded.split(",")[0].strip()
    # Strip parenthetical airport info e.g. "new york (jfk-john f. kennedy intl.)"
    paren_idx = city.find("(")
    if paren_idx > 0:
        city = city[:paren_idx].strip()
    return city


def parse_hotels_com_car_url(url: str) -> dict[str, Any]:
    """Parse a Hotels.com car search URL into normalized components.

    Browser-verified Car Search URL anatomy (Jun 2026):
      /carsearch?locn=New%20York%2C%20NY%2C%20United%20States%20of%20America%20(JFK-John%20F.%20Kennedy%20Intl.)
        &pickupIATACode=JFK
        &olat=40.644166&olon=-73.782548
        &dpln=4933194
        &d1=2026-6-29&d2=2026-6-30
        &date1=6/29/2026&date2=6/30/2026
        &time1=1030AM&time2=1030AM
        &aarpcr=off
        [&loc2=...&dropoffIATACode=...]

    Returns dict with keys:
      pickup_location, dropoff_location, pickup_iata, dropoff_iata,
      pickup_date, dropoff_date, pickup_time, dropoff_time
    """
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=True)

    # --- Locations ---
    pickup_loc = _normalize_car_location(_get_param(query, "locn"))
    dropoff_loc = _normalize_car_location(_get_param(query, "loc2"))

    # --- IATA codes ---
    pickup_iata = _get_param(
        query, "pickupIATACode", "pickupiatacode"
    ).upper()
    dropoff_iata = _get_param(
        query, "dropoffIATACode", "dropoffiatacode"
    ).upper()

    # --- Dates (d1/d2 primary, date1/date2 alternative) ---
    pickup_date = _normalize_date(
        _get_param(query, "d1", "date1", "startDate", "start_date")
    )
    dropoff_date = _normalize_date(
        _get_param(query, "d2", "date2", "endDate", "end_date")
    )

    # --- Times ---
    pickup_time = _normalize_time(_get_param(query, "time1"))
    dropoff_time = _normalize_time(_get_param(query, "time2"))

    return {
        "pickup_location": pickup_loc,
        "dropoff_location": dropoff_loc,
        "pickup_iata": pickup_iata,
        "dropoff_iata": dropoff_iata,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "pickup_time": pickup_time,
        "dropoff_time": dropoff_time,
    }


# =============================================================================
# CAR VERIFIER CLASS
# =============================================================================


class HotelsComCarVerifierResult(BaseModel):
    """Detailed verification result for Hotels.com car URL matching."""

    score: float
    match: bool
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}


@beartype
class HotelsComCarUrlMatch(BaseMetric):
    """URL-based Hotels.com verifier for car rental search tasks.

    This is a URL-BASED verifier for the /carsearch path. Hotels.com car
    rental searches encode search state in URL query parameters.

    Browser-Verified (Jun 2026 on www.hotels.com):
    - Search path: /carsearch
    - Location: locn (pick-up), loc2 (drop-off if different)
    - IATA codes: pickupIATACode, dropoffIATACode
    - Dates: d1 (YYYY-M-D), d2 (YYYY-M-D); alt: date1 (M/D/YYYY), date2
    - Times: time1 (e.g. 1030AM), time2
    - Internal: olat, olon, dpln (IGNORED — not user-specified)

    Matching Rules:
    - If GT specifies a field and agent omits it → FAIL
    - If GT omits a field → agent value is ignored (pass)
    - Location: case-insensitive, city-part only
    - IATA code: case-insensitive exact match
    - Dates: normalized to YYYY-MM-DD, exact match
    - Times: exact string match after normalization
    """

    def __init__(self, gt_url: str | list[str]) -> None:
        """
        Args:
            gt_url: Ground truth URL(s). If a list is provided, matching ANY
                    URL in the list counts as a match (OR semantics).
        """
        super().__init__()
        if isinstance(gt_url, str):
            self.gt_urls = [gt_url]
        else:
            self.gt_urls = gt_url
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details: dict = {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(gt_urls={self.gt_urls})"

    async def reset(self) -> None:
        """Reset the match state for new evaluation."""
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details = {}

    async def update(self, **kwargs) -> None:
        """Update with new URL to check against ground truth."""
        inputs: InputDict = kwargs
        url = inputs.get("url", "")

        if not url:
            logger.debug("Empty URL provided")
            return

        # Validate domain
        parsed = urlparse(url.strip())
        domain = (parsed.hostname or "").lower()
        if domain and not HotelsComUrlMatch._is_valid_hotels_com_domain(
            domain
        ):
            logger.debug(f"Ignoring non-Hotels.com URL: {url}")
            return

        # Must be a carsearch URL
        path = (parsed.path or "").lower()
        if "carsearch" not in path:
            logger.debug(f"Ignoring non-car-search URL: {url}")
            return

        # Don't overwrite after match
        if self._found_match:
            return

        self._agent_url = url

        for gt_url in self.gt_urls:
            match, details = self._urls_match(url, gt_url)
            if match:
                self._found_match = True
                self._matched_gt_url = gt_url
                self._match_details = details
                logger.info(f"Car match found: {url[:100]}...")
                return

        logger.info(f"No car match found: {url[:100]}...")

    async def compute(self) -> FinalResult:
        """Compute final score (1.0 = match, 0.0 = no match)."""
        score = 1.0 if self._found_match else 0.0
        result = FinalResult(score=score)
        logger.info(f"Car final score: {score}")
        return result

    async def compute_detailed(self) -> HotelsComCarVerifierResult:
        """Compute detailed result with match info."""
        score = 1.0 if self._found_match else 0.0
        return HotelsComCarVerifierResult(
            score=score,
            match=self._found_match,
            agent_url=self._agent_url,
            gt_url=self._matched_gt_url,
            details=self._match_details,
        )

    # ========================================================================
    # URL MATCHING
    # ========================================================================

    def _urls_match(
        self, agent_url: str, gt_url: str
    ) -> tuple[bool, dict]:
        """Compare two Hotels.com car search URLs.

        Performs sequential field comparison. Returns (match, details).
        """
        details: dict[str, Any] = {"mismatches": []}

        try:
            agent = parse_hotels_com_car_url(agent_url)
            gt = parse_hotels_com_car_url(gt_url)

            # 1. Pick-up location (city-part, case-insensitive)
            if gt["pickup_location"]:
                if not agent["pickup_location"]:
                    details["mismatches"].append(
                        f"Pick-up location missing "
                        f"(expected '{gt['pickup_location']}')"
                    )
                    return False, details
                if agent["pickup_location"] != gt["pickup_location"]:
                    details["mismatches"].append(
                        f"Pick-up location: '{agent['pickup_location']}' "
                        f"vs '{gt['pickup_location']}'"
                    )
                    return False, details

            # 2. Pick-up IATA code
            if gt["pickup_iata"]:
                if not agent["pickup_iata"]:
                    details["mismatches"].append(
                        f"Pick-up IATA missing "
                        f"(expected '{gt['pickup_iata']}')"
                    )
                    return False, details
                if agent["pickup_iata"] != gt["pickup_iata"]:
                    details["mismatches"].append(
                        f"Pick-up IATA: '{agent['pickup_iata']}' "
                        f"vs '{gt['pickup_iata']}'"
                    )
                    return False, details

            # 3. Pick-up date
            if gt["pickup_date"]:
                if not agent["pickup_date"]:
                    details["mismatches"].append(
                        f"Pick-up date missing "
                        f"(expected '{gt['pickup_date']}')"
                    )
                    return False, details
                if agent["pickup_date"] != gt["pickup_date"]:
                    details["mismatches"].append(
                        f"Pick-up date: '{agent['pickup_date']}' "
                        f"vs '{gt['pickup_date']}'"
                    )
                    return False, details

            # 4. Drop-off date
            if gt["dropoff_date"]:
                if not agent["dropoff_date"]:
                    details["mismatches"].append(
                        f"Drop-off date missing "
                        f"(expected '{gt['dropoff_date']}')"
                    )
                    return False, details
                if agent["dropoff_date"] != gt["dropoff_date"]:
                    details["mismatches"].append(
                        f"Drop-off date: '{agent['dropoff_date']}' "
                        f"vs '{gt['dropoff_date']}'"
                    )
                    return False, details

            # 5. Pick-up time
            if gt["pickup_time"]:
                if not agent["pickup_time"]:
                    details["mismatches"].append(
                        f"Pick-up time missing "
                        f"(expected '{gt['pickup_time']}')"
                    )
                    return False, details
                if agent["pickup_time"] != gt["pickup_time"]:
                    details["mismatches"].append(
                        f"Pick-up time: '{agent['pickup_time']}' "
                        f"vs '{gt['pickup_time']}'"
                    )
                    return False, details

            # 6. Drop-off time
            if gt["dropoff_time"]:
                if not agent["dropoff_time"]:
                    details["mismatches"].append(
                        f"Drop-off time missing "
                        f"(expected '{gt['dropoff_time']}')"
                    )
                    return False, details
                if agent["dropoff_time"] != gt["dropoff_time"]:
                    details["mismatches"].append(
                        f"Drop-off time: '{agent['dropoff_time']}' "
                        f"vs '{gt['dropoff_time']}'"
                    )
                    return False, details

            # 7. Drop-off location (only if GT specifies different loc)
            if gt["dropoff_location"]:
                if not agent["dropoff_location"]:
                    details["mismatches"].append(
                        f"Drop-off location missing "
                        f"(expected '{gt['dropoff_location']}')"
                    )
                    return False, details
                if agent["dropoff_location"] != gt["dropoff_location"]:
                    details["mismatches"].append(
                        f"Drop-off location: "
                        f"'{agent['dropoff_location']}' "
                        f"vs '{gt['dropoff_location']}'"
                    )
                    return False, details

            # 8. Drop-off IATA code
            if gt["dropoff_iata"]:
                if not agent["dropoff_iata"]:
                    details["mismatches"].append(
                        f"Drop-off IATA missing "
                        f"(expected '{gt['dropoff_iata']}')"
                    )
                    return False, details
                if agent["dropoff_iata"] != gt["dropoff_iata"]:
                    details["mismatches"].append(
                        f"Drop-off IATA: '{agent['dropoff_iata']}' "
                        f"vs '{gt['dropoff_iata']}'"
                    )
                    return False, details

            return True, details

        except Exception as e:
            logger.error(f"Error comparing car URLs: {e}")
            details["mismatches"].append(f"Parse error: {str(e)}")
            return False, details


# =============================================================================
# CAR TASK CONFIG GENERATION
# =============================================================================


def generate_car_task_config(
    task: str,
    location: str,
    timezone: str,
    gt_url: list[str] | None = None,
    ground_truth_url: str | None = None,
    timestamp: int | None = None,
    url: str = "https://www.hotels.com/carsearch",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate task configuration for Hotels.com car rental URL matching.

    Accepts either ``gt_url`` (list of strings) or ``ground_truth_url``
    (single string) for backward compat. Supports multi-date placeholder
    expansion for dynamic date tasks.

    Args:
        task: Task description. May contain ``{placeholder}`` tokens.
        location: User location string.
        timezone: IANA timezone string.
        gt_url: Ground-truth URL(s).
        ground_truth_url: Single GT URL (alternative to gt_url).
        timestamp: Unix timestamp. ``None`` means "now".
        url: Starting URL.
        values: Placeholder-key → relative-date expression mapping.
    """
    # Resolve gt_url from either parameter
    if gt_url is None and ground_truth_url is not None:
        gt_url = [ground_truth_url]
    elif isinstance(gt_url, str):
        gt_url = [gt_url]
    elif gt_url is None:
        raise ValueError(
            "Either 'gt_url' or 'ground_truth_url' must be provided."
        )

    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(
        user_metadata, values
    )

    # Render {placeholder} tokens in task text
    rendered_task = render_task_statement(task, resolved_placeholders)

    # ----------------------------
    # Generate all GT URL combinations
    # ----------------------------
    all_gt_urls: list[str] = []

    for template in gt_url:
        placeholders_in_template = {
            k: dates
            for k, (_, dates) in resolved_placeholders.items()
            if any(
                token in template
                for token in [
                    f"{{{k}}}",
                    f"{{{k}Day}}",
                    f"{{{k}Month}}",
                    f"{{{k}Year}}",
                ]
            )
        }

        if not placeholders_in_template:
            all_gt_urls.append(template)
            continue

        keys = list(placeholders_in_template.keys())
        date_lists = list(placeholders_in_template.values())

        for combination in product(*date_lists):
            rendered_u = template

            for k, v in zip(keys, combination):
                rendered_u = rendered_u.replace(f"{{{k}}}", v)

                try:
                    dt = datetime.strptime(v, "%Y-%m-%d")
                    replacements = {
                        f"{{{k}Day}}": str(dt.day),
                        f"{{{k}Month}}": str(dt.month),
                        f"{{{k}Year}}": str(dt.year),
                    }
                    for token, value in replacements.items():
                        if token in rendered_u:
                            rendered_u = rendered_u.replace(token, value)
                except Exception:
                    pass

            all_gt_urls.append(rendered_u)

    all_gt_urls = list(set(all_gt_urls))

    eval_target = get_import_path(HotelsComCarUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": all_gt_urls}

    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )


# =============================================================================
# TASK CONFIG GENERATION (HOTEL SEARCH)
# =============================================================================


def generate_task_config(
    task: str,
    location: str,
    timezone: str,
    gt_url: list[str] | None = None,
    ground_truth_url: str | None = None,
    timestamp: int | None = None,
    url: str = "https://www.hotels.com/",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate task configuration for Hotels.com URL matching.

    Accepts either ``gt_url`` (list of strings) or ``ground_truth_url``
    (single string) for backward compat. Supports multi-date placeholder
    expansion for dynamic date tasks.

    Args:
        task: Task description. May contain ``{placeholder}`` tokens.
        location: User location string.
        timezone: IANA timezone string.
        gt_url: Ground-truth URL(s).
        ground_truth_url: Single GT URL (alternative to gt_url).
        timestamp: Unix timestamp. ``None`` means "now".
        url: Starting URL.
        values: Placeholder-key → relative-date expression mapping.
    """
    # Resolve gt_url from either parameter
    if gt_url is None and ground_truth_url is not None:
        gt_url = [ground_truth_url]
    elif isinstance(gt_url, str):
        gt_url = [gt_url]
    elif gt_url is None:
        raise ValueError(
            "Either 'gt_url' or 'ground_truth_url' must be provided."
        )

    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(
        user_metadata, values
    )

    # Render {placeholder} tokens in task text
    rendered_task = render_task_statement(task, resolved_placeholders)

    # ----------------------------
    # Generate all GT URL combinations
    # ----------------------------
    all_gt_urls: list[str] = []

    for template in gt_url:
        placeholders_in_template = {
            k: dates
            for k, (_, dates) in resolved_placeholders.items()
            if any(
                token in template
                for token in [
                    f"{{{k}}}",
                    f"{{{k}Day}}",
                    f"{{{k}Month}}",
                    f"{{{k}Year}}",
                ]
            )
        }

        if not placeholders_in_template:
            all_gt_urls.append(template)
            continue

        keys = list(placeholders_in_template.keys())
        date_lists = list(placeholders_in_template.values())

        for combination in product(*date_lists):
            rendered_u = template

            for k, v in zip(keys, combination):
                rendered_u = rendered_u.replace(f"{{{k}}}", v)

                try:
                    dt = datetime.strptime(v, "%Y-%m-%d")
                    replacements = {
                        f"{{{k}Day}}": str(dt.day),
                        f"{{{k}Month}}": str(dt.month),
                        f"{{{k}Year}}": str(dt.year),
                    }
                    for token, value in replacements.items():
                        if token in rendered_u:
                            rendered_u = rendered_u.replace(token, value)
                except Exception:
                    pass

            all_gt_urls.append(rendered_u)

    all_gt_urls = list(set(all_gt_urls))

    eval_target = get_import_path(HotelsComUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": all_gt_urls}

    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )


# =============================================================================
# CAR RENTAL — RESULT MODEL
# =============================================================================


class HotelsComCarVerifierResult(BaseModel):
    """Detailed verification result for Hotels.com car rental URL matching."""

    score: float
    match: bool
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}


# =============================================================================
# CAR RENTAL — NORMALIZATION HELPERS
# =============================================================================


def _normalize_time(raw: str) -> str:
    """Normalize a time string to HHMM[AM|PM] format.

    Examples:
        '1030AM'   → '1030AM'
        '1030am'   → '1030AM'
        ' 0230 PM' → '0230PM'
        ''         → ''
    """
    if not raw:
        return ""
    return raw.strip().replace(" ", "").upper()


def _normalize_car_location(raw: str) -> str:
    """Normalize a car rental location for comparison.

    - URL-decode
    - Lowercase
    - Take city part only (before first comma or parenthesis)
    - Strip whitespace

    Examples:
        'New York, NY, United States'         → 'new york'
        'New York (JFK-John F. Kennedy Intl.)' → 'new york'
        'Los Angeles'                         → 'los angeles'
    """
    if not raw:
        return ""
    decoded = unquote(raw).strip().lower()
    # Remove airport code part in parentheses
    decoded = re.sub(r"\s*\(.*?\)\s*", "", decoded).strip()
    # Take city part only (before first comma)
    return decoded.split(",")[0].strip()


# =============================================================================
# CAR RENTAL — URL PARSER
# =============================================================================


def parse_hotels_com_car_url(url: str) -> dict[str, Any]:
    """Parse a Hotels.com /carsearch URL into normalized components.

    Browser-verified Car URL anatomy (Jun 2026):
      /carsearch?locn=Los%20Angeles%2C%20CA%2C%20United%20States%20of%20America%20(LAX-Los%20Angeles%20Intl.)
        &pickupCode=LAX                   (IATA code — browser uses pickupCode)
        &date1=7/1/2026&date2=7/5/2026    (M/D/YYYY format)
        &time1=1030AM&time2=1030AM
        &loc2=Houston                     (drop-off location, if different)
        &dropoffCode=IAH                  (drop-off airport IATA code)
        &dpln=5783884                     (auto-generated destination ID)
        &olat=33.94415&olon=-118.4032     (auto-generated coords)
        &selCC=["economy","compact"]      (car class filter, JSON array)
        &sort=PRICE                       (sort order)
    
    Also supports legacy param names:
        &pickupIATACode=JFK  &dropoffIATACode=IAH
        &d1=2026-7-10        &d2=2026-7-14
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # --- Pickup Location ---
    pickup_location = _normalize_car_location(
        _get_param(query, "locn", "loc1")
    )

    # --- Pickup IATA Code ---
    # Browser uses pickupCode, legacy uses pickupIATACode
    pickup_iata_raw = _get_param(query, "pickupCode", "pickupIATACode")
    pickup_iata = pickup_iata_raw.strip().upper() if pickup_iata_raw else ""

    # --- Dates ---
    pickup_date = _normalize_date(
        _get_param(query, "d1", "date1", "startDate")
    )
    dropoff_date = _normalize_date(
        _get_param(query, "d2", "date2", "endDate")
    )

    # --- Times ---
    pickup_time = _normalize_time(_get_param(query, "time1"))
    dropoff_time = _normalize_time(_get_param(query, "time2"))

    # --- Drop-off Location (one-way rentals) ---
    dropoff_location = _normalize_car_location(
        _get_param(query, "loc2")
    )

    # --- Drop-off IATA Code ---
    # Browser uses dropoffCode, legacy uses dropoffIATACode
    dropoff_iata_raw = _get_param(query, "dropoffCode", "dropoffIATACode")
    dropoff_iata = dropoff_iata_raw.strip().upper() if dropoff_iata_raw else ""

    return {
        "pickup_location": pickup_location,
        "pickup_iata": pickup_iata,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "pickup_time": pickup_time,
        "dropoff_time": dropoff_time,
        "dropoff_location": dropoff_location,
        "dropoff_iata": dropoff_iata,
    }


# =============================================================================
# CAR RENTAL — VERIFIER CLASS
# =============================================================================


class HotelsComCarUrlMatch(BaseMetric):
    """URL-based Hotels.com verifier for car rental tasks.

    Compares the agent's final /carsearch URL against expected ground truth
    URLs. All car search state is encoded in the URL query parameters.

    Parameters compared:
      - Pick-up location (locn) — city-part, case-insensitive
      - Pick-up IATA code (pickupIATACode)
      - Pick-up / Drop-off dates (d1, d2)
      - Pick-up / Drop-off times (time1, time2) — optional in GT
      - Drop-off location (loc2) — for one-way rentals
      - Drop-off IATA code (dropoffIATACode)
    """

    @beartype
    def __init__(self, *, gt_url: str | list[str]):
        super().__init__()
        if isinstance(gt_url, str):
            gt_url = [gt_url]
        self._gt_urls = gt_url
        self._agent_url: str = ""
        self._match_details: dict = {}
        self._matched_gt_url: str = ""

    async def reset(self) -> None:
        self._agent_url = ""
        self._match_details = {}
        self._matched_gt_url = ""

    async def update(self, *, url: str = "", **kwargs: Any) -> None:
        if not url:
            return
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # Only accept Hotels.com domains
        if not (host in VALID_BASE_DOMAINS or host in REGIONAL_DOMAINS):
            return
        # Only accept /carsearch paths
        if "/carsearch" not in parsed.path.lower():
            return
        self._agent_url = url

    async def compute(self) -> FinalResult:
        if not self._agent_url:
            return FinalResult(score=0.0)

        for gt_url in self._gt_urls:
            match, details = self._urls_match(self._agent_url, gt_url)
            if match:
                self._match_details = details
                self._matched_gt_url = gt_url
                return FinalResult(score=1.0)

        self._match_details = details  # noqa: F821 — last details from loop
        return FinalResult(score=0.0)

    async def compute_detailed(self) -> HotelsComCarVerifierResult:
        result = await self.compute()
        return HotelsComCarVerifierResult(
            score=result.score,
            match=result.score >= 1.0,
            agent_url=self._agent_url,
            gt_url=self._matched_gt_url or (self._gt_urls[0] if self._gt_urls else ""),
            details=self._match_details,
        )

    def _urls_match(
        self, agent_url: str, gt_url: str
    ) -> tuple[bool, dict]:
        """Compare agent car-search URL against a single ground-truth URL."""
        agent = parse_hotels_com_car_url(agent_url)
        gt = parse_hotels_com_car_url(gt_url)

        details: dict[str, Any] = {
            "agent_parsed": agent,
            "gt_parsed": gt,
            "mismatches": [],
        }

        # 1. Pick-up location
        if gt["pickup_location"]:
            if not agent["pickup_location"]:
                details["mismatches"].append(
                    f"Pick-up location missing (expected '{gt['pickup_location']}')"
                )
                return False, details
            if agent["pickup_location"] != gt["pickup_location"]:
                details["mismatches"].append(
                    f"Pick-up location: '{agent['pickup_location']}' "
                    f"vs '{gt['pickup_location']}'"
                )
                return False, details

        # 2. Pick-up IATA code
        if gt["pickup_iata"]:
            if not agent["pickup_iata"]:
                details["mismatches"].append(
                    f"Pick-up IATA missing (expected '{gt['pickup_iata']}')"
                )
                return False, details
            if agent["pickup_iata"] != gt["pickup_iata"]:
                details["mismatches"].append(
                    f"Pick-up IATA: '{agent['pickup_iata']}' "
                    f"vs '{gt['pickup_iata']}'"
                )
                return False, details

        # 3. Pick-up date
        if gt["pickup_date"]:
            if not agent["pickup_date"]:
                details["mismatches"].append(
                    f"Pick-up date missing (expected '{gt['pickup_date']}')"
                )
                return False, details
            if agent["pickup_date"] != gt["pickup_date"]:
                details["mismatches"].append(
                    f"Pick-up date: '{agent['pickup_date']}' "
                    f"vs '{gt['pickup_date']}'"
                )
                return False, details

        # 4. Drop-off date
        if gt["dropoff_date"]:
            if not agent["dropoff_date"]:
                details["mismatches"].append(
                    f"Drop-off date missing (expected '{gt['dropoff_date']}')"
                )
                return False, details
            if agent["dropoff_date"] != gt["dropoff_date"]:
                details["mismatches"].append(
                    f"Drop-off date: '{agent['dropoff_date']}' "
                    f"vs '{gt['dropoff_date']}'"
                )
                return False, details

        # 5. Pick-up time (optional — only check if GT specifies it)
        if gt["pickup_time"]:
            if not agent["pickup_time"]:
                details["mismatches"].append(
                    f"Pick-up time missing (expected '{gt['pickup_time']}')"
                )
                return False, details
            if agent["pickup_time"] != gt["pickup_time"]:
                details["mismatches"].append(
                    f"Pick-up time: '{agent['pickup_time']}' "
                    f"vs '{gt['pickup_time']}'"
                )
                return False, details

        # 6. Drop-off time (optional — only check if GT specifies it)
        if gt["dropoff_time"]:
            if not agent["dropoff_time"]:
                details["mismatches"].append(
                    f"Drop-off time missing (expected '{gt['dropoff_time']}')"
                )
                return False, details
            if agent["dropoff_time"] != gt["dropoff_time"]:
                details["mismatches"].append(
                    f"Drop-off time: '{agent['dropoff_time']}' "
                    f"vs '{gt['dropoff_time']}'"
                )
                return False, details

        # 7. Drop-off location (one-way)
        if gt["dropoff_location"]:
            if not agent["dropoff_location"]:
                details["mismatches"].append(
                    f"Drop-off location missing (expected '{gt['dropoff_location']}')"
                )
                return False, details
            if agent["dropoff_location"] != gt["dropoff_location"]:
                details["mismatches"].append(
                    f"Drop-off location: '{agent['dropoff_location']}' "
                    f"vs '{gt['dropoff_location']}'"
                )
                return False, details

        # 8. Drop-off IATA code
        if gt["dropoff_iata"]:
            if not agent["dropoff_iata"]:
                details["mismatches"].append(
                    f"Drop-off IATA missing (expected '{gt['dropoff_iata']}')"
                )
                return False, details
            if agent["dropoff_iata"] != gt["dropoff_iata"]:
                details["mismatches"].append(
                    f"Drop-off IATA: '{agent['dropoff_iata']}' "
                    f"vs '{gt['dropoff_iata']}'"
                )
                return False, details

        return True, details

    def __repr__(self) -> str:
        urls_repr = ", ".join(f"'{u}'" for u in self._gt_urls)
        return f"HotelsComCarUrlMatch(gt_url=[{urls_repr}])"


# =============================================================================
# CAR RENTAL — TASK CONFIG GENERATOR
# =============================================================================


@beartype
def generate_car_task_config(
    *,
    task: str,
    location: str,
    timezone: str,
    gt_url: list[str] | None = None,
    url: str = "https://www.hotels.com/carsearch",
    values: dict[str, str] | None = None,
    timestamp: datetime | None = None,
) -> BaseTaskConfig:
    """Generate a task configuration for Hotels.com car rental verification.

    Args:
        task: Task description with optional {placeholder} tokens.
        location: Geographic location for date context.
        timezone: IANA timezone for date resolution.
        gt_url: Ground truth URL(s) for the car search.
        url: Starting URL (default: /carsearch).
        values: Placeholder values for date substitution.
        timestamp: Optional fixed timestamp for reproducibility.

    Returns:
        BaseTaskConfig with eval_config targeting HotelsComCarUrlMatch.
    """
    if not gt_url:
        raise ValueError("gt_url is required for car rental task config")

    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(
        user_metadata, values
    )

    rendered_task = render_task_statement(task, resolved_placeholders)

    # Generate all GT URL combinations
    all_gt_urls: list[str] = []

    for template in gt_url:
        placeholders_in_template = {
            k: dates
            for k, (_, dates) in resolved_placeholders.items()
            if any(
                token in template
                for token in [
                    f"{{{k}}}",
                    f"{{{k}Day}}",
                    f"{{{k}Month}}",
                    f"{{{k}Year}}",
                ]
            )
        }

        if not placeholders_in_template:
            all_gt_urls.append(template)
            continue

        keys = list(placeholders_in_template.keys())
        date_lists = list(placeholders_in_template.values())

        for combination in product(*date_lists):
            rendered_u = template

            for k, v in zip(keys, combination):
                rendered_u = rendered_u.replace(f"{{{k}}}", v)

                try:
                    dt = datetime.strptime(v, "%Y-%m-%d")
                    replacements = {
                        f"{{{k}Day}}": str(dt.day),
                        f"{{{k}Month}}": str(dt.month),
                        f"{{{k}Year}}": str(dt.year),
                    }
                    for token, value in replacements.items():
                        if token in rendered_u:
                            rendered_u = rendered_u.replace(token, value)
                except Exception:
                    pass

            all_gt_urls.append(rendered_u)

    all_gt_urls = list(set(all_gt_urls))

    eval_target = get_import_path(HotelsComCarUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": all_gt_urls}

    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )



# =============================================================================
# STANDALONE DEMO

# =============================================================================


if __name__ == "__main__":
    import json

    from navi_bench.base import DatasetItem, instantiate

    dataset_row = {
        "task_id": "navi_bench/hotels_com/hotel_search/0",
        "task_generation_config_json": json.dumps(
            {
                "_target_": "navi_bench.hotels_com.hotels_com_url_match.generate_task_config",
                "url": "https://www.hotels.com/",
                "task": (
                    "Search for hotels in New York for 2 adults, checking in on "
                    "July 1st 2026 and checking out on July 5th 2026. "
                    "Sort by lowest price and filter for 4-star and 5-star hotels."
                ),
                "location": "San Francisco, CA, United States",
                "timezone": "America/Los_Angeles",
                "gt_url": [
                    "https://www.hotels.com/Hotel-Search?destination=New%20York"
                    "&startDate=2026-07-01&endDate=2026-07-05"
                    "&adults=2&rooms=1"
                    "&sort=PRICE_LOW_TO_HIGH"
                    "&f-star-rating=4,5"
                ],
            }
        ),
        "env": "real",
        "domain": "hotels_com",
        "l1_category": "travel",
        "l2_category": "hotel_search",
        "suggested_split": "train",
        "suggested_difficulty": "hard",
    }

    dataset_item = DatasetItem.model_validate(dataset_row)
    task_config = dataset_item.generate_task_config()
    evaluator = instantiate(task_config.eval_config)

    print("Loaded dataset item")
    print("-------------------")
    print(dataset_item)
    print()

    print("Generated task config")
    print("---------------------")
    print(task_config)
    print()

    print("Instantiated evaluator")
    print("----------------------")
    print(evaluator)
