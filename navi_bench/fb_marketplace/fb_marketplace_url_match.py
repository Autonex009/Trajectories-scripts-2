"""Facebook Marketplace URL Match verifier for marketplace search navigation.

This module provides functionality to verify AI agent navigation on Facebook
Marketplace by comparing the agent's final URL against expected ground truth URLs.

The verifier handles all Facebook Marketplace URL variations including:
- Search results path: /marketplace/[city_slug]/search/
- Category browsing: /marketplace/category/[category_slug]/
- Individual listings: /marketplace/item/[numeric_id]/
- Keyword search: query=<search_term>
- Price filters: minPrice, maxPrice
- Sort order: sortBy=best_match|price_ascend|price_descend|creation_time_descend|distance_ascend
- Item condition: itemCondition=new|used_like_new|used_good|used_fair
- Days since listed: daysSinceListed=1|7|30
- Delivery method: deliveryMethod=local_pick_up|shipping
- Exact match toggle: exact=true|false
- Vehicle filters: minYear, maxYear, minMileage, maxMileage, topLevelVehicleType, make, model
- Property filters: minBedrooms, maxBedrooms, minBathrooms, propertyType

Browser-Verified Patterns (Apr 2026 on facebook.com/marketplace):
  Search path: /marketplace/{city_slug}/search/?query={term}&{filters}
  Category path: /marketplace/category/{category_slug}/
  Listing path: /marketplace/item/{numeric_id}/
  City slug: sanfrancisco, newyork, losangeles, chicago, london, etc.
  Condition: itemCondition=new|used_like_new|used_good|used_fair
  Sort: sortBy=best_match|price_ascend|price_descend|creation_time_descend|distance_ascend
  Days: daysSinceListed=1 (24h), 7 (week), 30 (month)
  Delivery: deliveryMethod=local_pick_up|shipping
  Price: minPrice=INT, maxPrice=INT
  Exact: exact=true|false

Category Slugs (Browser-Verified Apr 2026):
  vehicles        → /marketplace/category/vehicles/
  electronics     → /marketplace/category/electronics/
  propertyrentals → /marketplace/category/propertyrentals/
  apparel         → /marketplace/category/apparel/
  furniture       → /marketplace/category/furniture/ (or /home/)
  entertainment   → /marketplace/category/entertainment/
  garden          → /marketplace/category/garden/
  hobbies         → /marketplace/category/hobbies/
  sporting        → /marketplace/category/sporting/
  toys            → /marketplace/category/toys/
  free            → /marketplace/category/free/
  pets            → /marketplace/category/pets/ (if region-available)

Note: Location is set via city_slug in URL path AND radius is session-based.
The verifier compares city_slug when GT specifies it.
"""

import re
from typing import Any
from typing_extensions import TypedDict
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


class MarketplaceVerifierResult(BaseModel):
    """Detailed verification result for Facebook Marketplace URL matching."""

    score: float
    match: bool
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}


# =============================================================================
# CONSTANTS
# =============================================================================

# Valid Facebook domain patterns
VALID_BASE_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "web.facebook.com",
}

# Query parameters to IGNORE during comparison (session/tracking)
IGNORED_PARAMS = {
    # Tracking & attribution
    "ref",
    "referral_code",
    "referral_story_type",
    "referral_surface",
    "tracking",
    "surface",
    "section_token",
    "__tn__",
    "__cft__",
    "contextRouterSourceType",
    # Facebook internal
    "fb_dtsg_ag",
    "jazoest",
    "lsd",
    # UTM
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    # Click IDs
    "gclid",
    "msclkid",
    "fbclid",
    # Session
    "locale",
    "surface_type",
    "fs",
    "_rdr",
}

# Sort order normalization
SORT_ORDER_MAP = {
    "best_match": "best_match",
    "bestmatch": "best_match",
    "default": "best_match",
    "price_ascend": "price_ascend",
    "priceascend": "price_ascend",
    "price_asc": "price_ascend",
    "price_low": "price_ascend",
    "price:_lowest_first": "price_ascend",
    "price_descend": "price_descend",
    "pricedescend": "price_descend",
    "price_desc": "price_descend",
    "price_high": "price_descend",
    "price:_highest_first": "price_descend",
    "creation_time_descend": "creation_time_descend",
    "creationtimedescend": "creation_time_descend",
    "newest": "creation_time_descend",
    "date_listed": "creation_time_descend",
    "date_listed:_newest_first": "creation_time_descend",
    "distance_ascend": "distance_ascend",
    "distanceascend": "distance_ascend",
    "nearest": "distance_ascend",
    "distance:_nearest_first": "distance_ascend",
}

# Item condition normalization
CONDITION_MAP = {
    "new": "new",
    "used_like_new": "used_like_new",
    "used_good": "used_good",
    "used_fair": "used_fair",
    # Common aliases
    "like_new": "used_like_new",
    "likenew": "used_like_new",
    "like new": "used_like_new",
    "good": "used_good",
    "fair": "used_fair",
    "used": "used_good",  # generic "used" → "used_good" as default
}

# Delivery method normalization
DELIVERY_MAP = {
    "local_pick_up": "local_pick_up",
    "local_pickup": "local_pick_up",
    "pickup": "local_pick_up",
    "shipping": "shipping",
    "shipped": "shipping",
}

# Known category slugs → category IDs (browser-verified Apr 2026)
CATEGORY_SLUG_TO_ID = {
    "vehicles": "vehicles",
    "electronics": "electronics",
    "propertyrentals": "propertyrentals",
    "apparel": "apparel",
    "furniture": "furniture",
    "home": "home",
    "entertainment": "entertainment",
    "garden": "garden",
    "hobbies": "hobbies",
    "sporting": "sporting",
    "toys": "toys",
    "free": "free",
    "pets": "pets",
    "office": "office",
    "musicalinstruments": "musicalinstruments",
    "classifieds": "classifieds",
    "family": "family",
}

# Known city slugs (non-exhaustive, browser-verified Apr 2026)
KNOWN_CITY_SLUGS = {
    "sanfrancisco", "newyork", "losangeles", "chicago", "houston",
    "phoenix", "philadelphia", "sanantonio", "sandiego", "dallas",
    "austin", "seattle", "denver", "boston", "nashville",
    "portland", "miami", "atlanta", "detroit", "minneapolis",
    "london", "toronto", "vancouver", "sydney", "melbourne",
    "mumbai", "delhi", "bangalore", "hyderabad",
}

# Vehicle type normalization
VEHICLE_TYPE_MAP = {
    "car_truck": "car_truck",
    "car": "car_truck",
    "truck": "car_truck",
    "motorcycle": "motorcycle",
    "rv_camper": "rv_camper",
    "rv": "rv_camper",
    "camper": "rv_camper",
    "boat": "boat",
    "powersport": "powersport",
    "trailer": "trailer",
    "commercial": "commercial",
}

# Property type normalization
PROPERTY_TYPE_MAP = {
    "house": "house",
    "apartment": "apartment",
    "condo": "condo",
    "townhouse": "townhouse",
    "studio": "studio",
    "room": "room",
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


def _get_int_param(query: dict, *keys: str) -> int | None:
    """Get a parameter as integer, or None if missing/unparseable."""
    raw = _get_param(query, *keys)
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _normalize_query_text(text: str) -> str:
    """Normalize a search query string for comparison.

    - URL-decode
    - Lowercase
    - Collapse whitespace
    - Strip leading/trailing whitespace
    """
    if not text:
        return ""
    text = unquote(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_sort_order(raw: str) -> str:
    """Normalize sort order to canonical value."""
    if not raw:
        return ""
    return SORT_ORDER_MAP.get(raw.lower().strip(), raw.lower().strip())


def _normalize_condition(raw: str) -> str:
    """Normalize item condition to canonical value."""
    if not raw:
        return ""
    return CONDITION_MAP.get(raw.lower().strip(), raw.lower().strip())


def _normalize_delivery(raw: str) -> str:
    """Normalize delivery method to canonical value."""
    if not raw:
        return ""
    return DELIVERY_MAP.get(raw.lower().strip(), raw.lower().strip())


def _normalize_vehicle_type(raw: str) -> str:
    """Normalize vehicle type to canonical value."""
    if not raw:
        return ""
    return VEHICLE_TYPE_MAP.get(raw.lower().strip(), raw.lower().strip())


def _normalize_property_type(raw: str) -> str:
    """Normalize property type to canonical value."""
    if not raw:
        return ""
    return PROPERTY_TYPE_MAP.get(raw.lower().strip(), raw.lower().strip())


def _extract_city_slug(path: str) -> str:
    """Extract the city slug from a Marketplace URL path.

    Marketplace paths follow these patterns:
      /marketplace/{city_slug}/search/?...     → city_slug
      /marketplace/{city_slug}/                → city_slug
      /marketplace/category/{category_slug}/   → "" (no city)
      /marketplace/item/{id}/                  → "" (no city)
      /marketplace/search/?...                 → "" (no explicit city)
      /marketplace/                            → "" (homepage)

    Returns empty string if no city slug is found.
    """
    if not path:
        return ""

    path = path.strip("/")
    parts = path.split("/")

    # Path must start with "marketplace"
    if not parts or parts[0] != "marketplace":
        return ""

    # /marketplace/ only
    if len(parts) == 1:
        return ""

    # /marketplace/category/... → no city
    # /marketplace/item/... → no city
    # /marketplace/search/... → no explicit city
    if parts[1] in ("category", "item", "search", "create"):
        return ""

    # /marketplace/{city_slug}/... → city_slug
    # Validate: city slug should be all lowercase alphanumeric (no numbers-only IDs)
    candidate = parts[1].lower()
    if re.match(r"^[a-z]+$", candidate):
        return candidate

    # Numeric location ID (e.g., /marketplace/112345678/search/)
    # These are Facebook-internal location IDs, not city slugs
    if re.match(r"^\d+$", candidate):
        return candidate

    return candidate


def _extract_category_slug(path: str) -> str:
    """Extract the category slug from a Marketplace URL path.

    /marketplace/category/{category_slug}/  → category_slug
    /marketplace/.../search/?category_id=X  → "" (handled by query params)

    Returns empty string if no category slug in path.
    """
    if not path:
        return ""

    path = path.strip("/")
    parts = path.split("/")

    # Must be /marketplace/category/{slug}
    if len(parts) >= 3 and parts[0] == "marketplace" and parts[1] == "category":
        return parts[2].lower()

    return ""


# =============================================================================
# URL PARSER
# =============================================================================


def parse_marketplace_url(url: str) -> dict[str, Any]:
    """Parse a Facebook Marketplace URL into normalized components.

    Facebook Marketplace URL anatomy (browser-verified Apr 2026):
      /marketplace/{city_slug}/search?
        query=iphone+15
        &minPrice=100
        &maxPrice=500
        &sortBy=creation_time_descend
        &daysSinceListed=7
        &itemCondition=new
        &deliveryMethod=local_pick_up
        &exact=true

    Returns dict with keys:
      city_slug, category_slug, query, min_price, max_price,
      sort_by, days_since_listed, item_condition, delivery_method,
      exact, category_id,
      # Vehicle-specific
      min_year, max_year, min_mileage, max_mileage,
      vehicle_type, make, model,
      # Property-specific
      min_bedrooms, max_bedrooms, min_bathrooms, property_type
    """
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=True)

    result: dict[str, Any] = {
        # Path-derived
        "city_slug": "",
        "category_slug": "",
        # General search
        "query": "",
        "min_price": None,
        "max_price": None,
        "sort_by": "",
        "days_since_listed": None,
        "item_condition": "",
        "delivery_method": "",
        "exact": None,
        "category_id": "",
        # Vehicle-specific
        "min_year": None,
        "max_year": None,
        "min_mileage": None,
        "max_mileage": None,
        "vehicle_type": "",
        "make": "",
        "model": "",
        # Property-specific
        "min_bedrooms": None,
        "max_bedrooms": None,
        "min_bathrooms": None,
        "property_type": "",
    }

    # Path-derived components
    result["city_slug"] = _extract_city_slug(parsed.path)
    result["category_slug"] = _extract_category_slug(parsed.path)

    # Search query
    raw_query = _get_param(query, "query")
    result["query"] = _normalize_query_text(raw_query)

    # Price range
    result["min_price"] = _get_int_param(query, "minPrice", "minprice")
    result["max_price"] = _get_int_param(query, "maxPrice", "maxprice")

    # Sort order
    raw_sort = _get_param(query, "sortBy", "sortby")
    result["sort_by"] = _normalize_sort_order(raw_sort)

    # Days since listed
    result["days_since_listed"] = _get_int_param(
        query, "daysSinceListed", "daysssincelisted"
    )

    # Item condition
    raw_condition = _get_param(query, "itemCondition", "itemcondition")
    result["item_condition"] = _normalize_condition(raw_condition)

    # Delivery method
    raw_delivery = _get_param(query, "deliveryMethod", "deliverymethod")
    result["delivery_method"] = _normalize_delivery(raw_delivery)

    # Exact match
    raw_exact = _get_param(query, "exact")
    if raw_exact:
        result["exact"] = raw_exact.lower().strip() == "true"

    # Category ID (query param)
    result["category_id"] = _get_param(query, "category_id", "categoryID")

    # Vehicle-specific
    result["min_year"] = _get_int_param(query, "minYear", "minyear")
    result["max_year"] = _get_int_param(query, "maxYear", "maxyear")
    result["min_mileage"] = _get_int_param(query, "minMileage", "minmileage")
    result["max_mileage"] = _get_int_param(query, "maxMileage", "maxmileage")

    raw_vehicle_type = _get_param(
        query, "topLevelVehicleType", "toplevelVehicleType", "vehicletype"
    )
    result["vehicle_type"] = _normalize_vehicle_type(raw_vehicle_type)

    raw_make = _get_param(query, "make")
    result["make"] = raw_make.lower().strip() if raw_make else ""

    raw_model = _get_param(query, "model")
    result["model"] = raw_model.lower().strip() if raw_model else ""

    # Property-specific
    result["min_bedrooms"] = _get_int_param(query, "minBedrooms", "minbedrooms")
    result["max_bedrooms"] = _get_int_param(query, "maxBedrooms", "maxbedrooms")
    result["min_bathrooms"] = _get_int_param(query, "minBathrooms", "minbathrooms")

    raw_prop_type = _get_param(query, "propertyType", "propertytype")
    result["property_type"] = _normalize_property_type(raw_prop_type)

    return result


# =============================================================================
# VERIFIER CLASS
# =============================================================================


@beartype
class FbMarketplaceUrlMatch(BaseMetric):
    """Comprehensive Facebook Marketplace URL verifier for search/filter tasks.

    Browser-Verified (Apr 2026 on facebook.com/marketplace):
    - Search path: /marketplace/{city_slug}/search/?query=...&filters
    - Category path: /marketplace/category/{category_slug}/
    - All filters encoded as query parameters
    - City location encoded as path segment

    Matching Rules (hardened — no auto-pass loopholes):
    - If GT specifies a field and agent omits it → FAIL
    - Search query: case-insensitive, whitespace-normalized
    - Price/year/mileage: exact integer match
    - Condition/sort/delivery: normalized string match
    - City slug: case-insensitive match (if GT specifies)
    - Category: slug or ID match
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
        if domain and not self._is_valid_marketplace_domain(domain):
            logger.debug(f"Ignoring non-Facebook URL: {url}")
            return

        # Must be a marketplace URL
        if "/marketplace" not in (parsed.path or ""):
            logger.debug(f"Ignoring non-Marketplace URL: {url}")
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

    async def compute_detailed(self) -> MarketplaceVerifierResult:
        """Compute detailed result with match info."""
        score = 1.0 if self._found_match else 0.0
        return MarketplaceVerifierResult(
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
    def _is_valid_marketplace_domain(domain: str) -> bool:
        """Check if domain is a valid Facebook domain.

        Accepts:
        - Exact matches: facebook.com, www.facebook.com
        - Mobile: m.facebook.com
        - Web: web.facebook.com
        - Any subdomain of facebook.com
        """
        domain = domain.lower().rstrip(".")

        # Direct match on known domains
        for base in VALID_BASE_DOMAINS:
            if domain == base:
                return True

        # Any subdomain of facebook.com
        if domain.endswith(".facebook.com"):
            return True

        return False

    # ========================================================================
    # URL MATCHING
    # ========================================================================

    def _urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        """Compare two Facebook Marketplace URLs.

        Performs sequential field comparison. Returns (match, details).
        If any required field mismatches, returns False immediately with
        mismatch details.
        """
        details: dict[str, Any] = {"mismatches": [], "extra_params": []}

        try:
            agent = parse_marketplace_url(agent_url)
            gt = parse_marketplace_url(gt_url)

            # 1. City slug (if GT specifies one)
            if gt["city_slug"]:
                if not agent["city_slug"]:
                    details["mismatches"].append(
                        f"City slug missing (expected '{gt['city_slug']}')"
                    )
                    return False, details
                if agent["city_slug"].lower() != gt["city_slug"].lower():
                    details["mismatches"].append(
                        f"City slug: '{agent['city_slug']}' vs '{gt['city_slug']}'"
                    )
                    return False, details

            # 2. Category slug (path-based category)
            if gt["category_slug"]:
                if not agent["category_slug"]:
                    details["mismatches"].append(
                        f"Category slug missing (expected '{gt['category_slug']}')"
                    )
                    return False, details
                if agent["category_slug"] != gt["category_slug"]:
                    details["mismatches"].append(
                        f"Category slug: '{agent['category_slug']}' "
                        f"vs '{gt['category_slug']}'"
                    )
                    return False, details

            # 3. Category ID (query param)
            if gt["category_id"]:
                if not agent["category_id"]:
                    details["mismatches"].append(
                        f"Category ID missing (expected '{gt['category_id']}')"
                    )
                    return False, details
                if agent["category_id"].lower() != gt["category_id"].lower():
                    details["mismatches"].append(
                        f"Category ID: '{agent['category_id']}' "
                        f"vs '{gt['category_id']}'"
                    )
                    return False, details

            # 4. Search query (case-insensitive, whitespace-normalized)
            if gt["query"]:
                if not agent["query"]:
                    details["mismatches"].append(
                        f"Query missing (expected '{gt['query']}')"
                    )
                    return False, details
                if agent["query"] != gt["query"]:
                    details["mismatches"].append(
                        f"Query: '{agent['query']}' vs '{gt['query']}'"
                    )
                    return False, details

            # 5. Minimum price
            if gt["min_price"] is not None:
                if agent["min_price"] is None:
                    details["mismatches"].append(
                        f"Min price missing (expected {gt['min_price']})"
                    )
                    return False, details
                if agent["min_price"] != gt["min_price"]:
                    details["mismatches"].append(
                        f"Min price: {agent['min_price']} vs {gt['min_price']}"
                    )
                    return False, details

            # 6. Maximum price
            if gt["max_price"] is not None:
                if agent["max_price"] is None:
                    details["mismatches"].append(
                        f"Max price missing (expected {gt['max_price']})"
                    )
                    return False, details
                if agent["max_price"] != gt["max_price"]:
                    details["mismatches"].append(
                        f"Max price: {agent['max_price']} vs {gt['max_price']}"
                    )
                    return False, details

            # 7. Sort order
            if gt["sort_by"]:
                if not agent["sort_by"]:
                    details["mismatches"].append(
                        f"Sort order missing (expected '{gt['sort_by']}')"
                    )
                    return False, details
                if agent["sort_by"] != gt["sort_by"]:
                    details["mismatches"].append(
                        f"Sort order: '{agent['sort_by']}' vs '{gt['sort_by']}'"
                    )
                    return False, details

            # 8. Item condition
            if gt["item_condition"]:
                if not agent["item_condition"]:
                    details["mismatches"].append(
                        f"Condition missing (expected '{gt['item_condition']}')"
                    )
                    return False, details
                if agent["item_condition"] != gt["item_condition"]:
                    details["mismatches"].append(
                        f"Condition: '{agent['item_condition']}' "
                        f"vs '{gt['item_condition']}'"
                    )
                    return False, details

            # 9. Days since listed
            if gt["days_since_listed"] is not None:
                if agent["days_since_listed"] is None:
                    details["mismatches"].append(
                        f"Days since listed missing "
                        f"(expected {gt['days_since_listed']})"
                    )
                    return False, details
                if agent["days_since_listed"] != gt["days_since_listed"]:
                    details["mismatches"].append(
                        f"Days since listed: {agent['days_since_listed']} "
                        f"vs {gt['days_since_listed']}"
                    )
                    return False, details

            # 10. Delivery method
            if gt["delivery_method"]:
                if not agent["delivery_method"]:
                    details["mismatches"].append(
                        f"Delivery missing (expected '{gt['delivery_method']}')"
                    )
                    return False, details
                if agent["delivery_method"] != gt["delivery_method"]:
                    details["mismatches"].append(
                        f"Delivery: '{agent['delivery_method']}' "
                        f"vs '{gt['delivery_method']}'"
                    )
                    return False, details

            # 11. Exact match toggle
            if gt["exact"] is not None:
                if agent["exact"] is None:
                    details["mismatches"].append(
                        f"Exact flag missing (expected {gt['exact']})"
                    )
                    return False, details
                if agent["exact"] != gt["exact"]:
                    details["mismatches"].append(
                        f"Exact: {agent['exact']} vs {gt['exact']}"
                    )
                    return False, details

            # ============================================================
            # Vehicle-specific filters
            # ============================================================

            # 12. Min year
            if gt["min_year"] is not None:
                if agent["min_year"] is None:
                    details["mismatches"].append(
                        f"Min year missing (expected {gt['min_year']})"
                    )
                    return False, details
                if agent["min_year"] != gt["min_year"]:
                    details["mismatches"].append(
                        f"Min year: {agent['min_year']} vs {gt['min_year']}"
                    )
                    return False, details

            # 13. Max year
            if gt["max_year"] is not None:
                if agent["max_year"] is None:
                    details["mismatches"].append(
                        f"Max year missing (expected {gt['max_year']})"
                    )
                    return False, details
                if agent["max_year"] != gt["max_year"]:
                    details["mismatches"].append(
                        f"Max year: {agent['max_year']} vs {gt['max_year']}"
                    )
                    return False, details

            # 14. Min mileage
            if gt["min_mileage"] is not None:
                if agent["min_mileage"] is None:
                    details["mismatches"].append(
                        f"Min mileage missing (expected {gt['min_mileage']})"
                    )
                    return False, details
                if agent["min_mileage"] != gt["min_mileage"]:
                    details["mismatches"].append(
                        f"Min mileage: {agent['min_mileage']} "
                        f"vs {gt['min_mileage']}"
                    )
                    return False, details

            # 15. Max mileage
            if gt["max_mileage"] is not None:
                if agent["max_mileage"] is None:
                    details["mismatches"].append(
                        f"Max mileage missing (expected {gt['max_mileage']})"
                    )
                    return False, details
                if agent["max_mileage"] != gt["max_mileage"]:
                    details["mismatches"].append(
                        f"Max mileage: {agent['max_mileage']} "
                        f"vs {gt['max_mileage']}"
                    )
                    return False, details

            # 16. Vehicle type
            if gt["vehicle_type"]:
                if not agent["vehicle_type"]:
                    details["mismatches"].append(
                        f"Vehicle type missing "
                        f"(expected '{gt['vehicle_type']}')"
                    )
                    return False, details
                if agent["vehicle_type"] != gt["vehicle_type"]:
                    details["mismatches"].append(
                        f"Vehicle type: '{agent['vehicle_type']}' "
                        f"vs '{gt['vehicle_type']}'"
                    )
                    return False, details

            # 17. Make
            if gt["make"]:
                if not agent["make"]:
                    details["mismatches"].append(
                        f"Make missing (expected '{gt['make']}')"
                    )
                    return False, details
                if agent["make"] != gt["make"]:
                    details["mismatches"].append(
                        f"Make: '{agent['make']}' vs '{gt['make']}'"
                    )
                    return False, details

            # 18. Model
            if gt["model"]:
                if not agent["model"]:
                    details["mismatches"].append(
                        f"Model missing (expected '{gt['model']}')"
                    )
                    return False, details
                if agent["model"] != gt["model"]:
                    details["mismatches"].append(
                        f"Model: '{agent['model']}' vs '{gt['model']}'"
                    )
                    return False, details

            # ============================================================
            # Property-specific filters
            # ============================================================

            # 19. Min bedrooms
            if gt["min_bedrooms"] is not None:
                if agent["min_bedrooms"] is None:
                    details["mismatches"].append(
                        f"Min bedrooms missing (expected {gt['min_bedrooms']})"
                    )
                    return False, details
                if agent["min_bedrooms"] != gt["min_bedrooms"]:
                    details["mismatches"].append(
                        f"Min bedrooms: {agent['min_bedrooms']} "
                        f"vs {gt['min_bedrooms']}"
                    )
                    return False, details

            # 20. Max bedrooms
            if gt["max_bedrooms"] is not None:
                if agent["max_bedrooms"] is None:
                    details["mismatches"].append(
                        f"Max bedrooms missing (expected {gt['max_bedrooms']})"
                    )
                    return False, details
                if agent["max_bedrooms"] != gt["max_bedrooms"]:
                    details["mismatches"].append(
                        f"Max bedrooms: {agent['max_bedrooms']} "
                        f"vs {gt['max_bedrooms']}"
                    )
                    return False, details

            # 21. Min bathrooms
            if gt["min_bathrooms"] is not None:
                if agent["min_bathrooms"] is None:
                    details["mismatches"].append(
                        f"Min bathrooms missing "
                        f"(expected {gt['min_bathrooms']})"
                    )
                    return False, details
                if agent["min_bathrooms"] != gt["min_bathrooms"]:
                    details["mismatches"].append(
                        f"Min bathrooms: {agent['min_bathrooms']} "
                        f"vs {gt['min_bathrooms']}"
                    )
                    return False, details

            # 22. Property type
            if gt["property_type"]:
                if not agent["property_type"]:
                    details["mismatches"].append(
                        f"Property type missing "
                        f"(expected '{gt['property_type']}')"
                    )
                    return False, details
                if agent["property_type"] != gt["property_type"]:
                    details["mismatches"].append(
                        f"Property type: '{agent['property_type']}' "
                        f"vs '{gt['property_type']}'"
                    )
                    return False, details

            return True, details

        except Exception as e:
            logger.error(f"Error comparing URLs: {e}")
            details["mismatches"].append(f"Parse error: {str(e)}")
            return False, details


# =============================================================================
# TASK CONFIG GENERATION
# =============================================================================


def generate_task_config(
    task: str,
    location: str,
    timezone: str,
    gt_url: list[str] | None = None,
    ground_truth_url: str | None = None,
    timestamp: int | None = None,
    url: str = "https://www.facebook.com/marketplace/",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate task configuration for Facebook Marketplace URL matching.

    Accepts either ``gt_url`` (list of strings) or ``ground_truth_url``
    (single string) for backward compat.

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

    # Substitute resolved dates into gt_url strings
    rendered_gt_urls: list[str] = []
    for u in gt_url:
        rendered_u = u
        for placeholder_key, (_, dates) in resolved_placeholders.items():
            template = "{" + placeholder_key + "}"
            if template in rendered_u and dates:
                rendered_u = rendered_u.replace(template, dates[0])
        rendered_gt_urls.append(rendered_u)

    eval_target = get_import_path(FbMarketplaceUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": rendered_gt_urls}
    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )


def generate_task_config_deterministic(
    task: str,
    queries: list[list[str]],
    location: str,
    timezone: str,
    timestamp: int | None = None,
    url: str = "https://www.facebook.com/marketplace/",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate task configuration for deterministic Marketplace URL-matching.

    This is the new-format config generator that uses ``queries``
    (list of URL alternatives) consistent with Trainline/Kayak patterns.

    Args:
        task: Natural language task description with ``{placeholder}`` tokens.
        queries: Nested list of GT URLs: ``[["url1"], ["url2"]]``.
                 Each inner list is a set of alternative URLs for one query.
        location: User location (e.g. "United States").
        timezone: IANA timezone (e.g. "America/Los_Angeles").
        timestamp: Unix timestamp. ``None`` means "now".
        url: Starting URL for the agent.
        values: Placeholder-key → relative-date expression mapping.
    """
    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(
        user_metadata, values
    )

    # Render {placeholder} tokens in task text
    rendered_task = render_task_statement(task, resolved_placeholders)

    # Resolve dates in query URLs — flatten to single list for URL match
    all_rendered_urls: list[str] = []
    for url_alternatives in queries:
        for u in url_alternatives:
            rendered_u = u
            for placeholder_key, (_, dates) in resolved_placeholders.items():
                template = "{" + placeholder_key + "}"
                if template in rendered_u and dates:
                    rendered_u = rendered_u.replace(template, dates[0])
            all_rendered_urls.append(rendered_u)

    eval_target = get_import_path(FbMarketplaceUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": all_rendered_urls}
    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )
