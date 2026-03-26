"""Skyscanner URL Match verifier for flight, hotel, and car hire search navigation.

This module provides functionality to verify AI agent navigation on Skyscanner
by comparing the agent's final URL against expected ground truth URLs.

The verifier handles all Skyscanner URL variations including:
- Flight search paths: /transport/flights/{origin}/{dest}/{YYMMDD}[/{YYMMDD}]
- Hotel search params: entity_id, checkin, checkout, adults, rooms, sort
- Car hire paths: /carhire/results/{pickup}/{dropoff}/{datetimeISO}/{datetimeISO}[/{age}]
- Flight query params: rtn, adultsv2, childrenv2, cabinclass, stops, airlines, alliances
- Domain variations: skyscanner.net, skyscanner.com, regional subdomains
- Filter order independence, case-insensitive comparison

Browser-Verified Patterns (Mar 2026 on skyscanner.net):
  Flight path: /transport/flights/jfk/lax/260420/260425/
  Flight params: adultsv2=2, cabinclass=business, rtn=1
  Stops: stops=!oneStop,!twoPlusStops (exclusion-prefix format)
  Alliances: alliances=Star Alliance (with space, URL-encoded %20)
  Airlines: airlines=-32593 (internal numeric IDs)
  Hotel params: entity_id=27544008, checkin=2026-04-20, checkout=2026-04-25
  Hotel sort: sort=price | -price | distance | -hotel_rating
  Car hire path: /carhire/results/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30
  Car hire locations: Internal numeric IDs, NOT IATA codes
"""

import re
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


class SkyscannerVerifierResult(BaseModel):
    """Detailed verification result for Skyscanner URL matching."""

    score: float
    match: bool
    page_type: str = ""
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}


# =============================================================================
# CONSTANTS
# =============================================================================

# Valid Skyscanner domain patterns — accept any subdomain of these
VALID_BASE_DOMAINS = {
    "skyscanner.net",
    "skyscanner.com",
}

# Regional domains (.co.in, .co.uk, .de, .fr, .jp, etc.)
REGIONAL_TLDS = {
    "skyscanner.co.in",
    "skyscanner.co.uk",
    "skyscanner.de",
    "skyscanner.fr",
    "skyscanner.es",
    "skyscanner.it",
    "skyscanner.jp",
    "skyscanner.com.au",
    "skyscanner.com.br",
    "skyscanner.ca",
    "skyscanner.se",
    "skyscanner.no",
    "skyscanner.dk",
    "skyscanner.fi",
    "skyscanner.pl",
    "skyscanner.pt",
    "skyscanner.ie",
    "skyscanner.at",
    "skyscanner.ch",
    "skyscanner.com.sg",
    "skyscanner.com.hk",
    "skyscanner.co.kr",
}

# Query parameters to IGNORE during flight comparison
# (session, tracking, UI-state only — not user-intentional search)
IGNORED_FLIGHT_PARAMS = {
    "locale",
    "market",
    "currency",
    "previousCultureSource",
    "ref",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "redirectedFrom",
    "associateid",
    "sdevent",
    "utm_content",
    "utm_term",
    "iym",           # inbound year-month (calendar view state)
    "oym",           # outbound year-month (calendar view state)
    "sortby",        # flight sort is DOM-only, unreliable in URL
}

# Query parameters to IGNORE during hotel comparison
IGNORED_HOTEL_PARAMS = {
    "locale",
    "market",
    "currency",
    "ref",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "redirectedFrom",
    "associateid",
    "is_dateless",
}

# Canonical cabin class values
CABIN_CLASSES = {"economy", "premiumeconomy", "business", "first"}

# Canonical alliance values (may have spaces, e.g. "Star Alliance")
# Browser-verified: alliances=Star Alliance (URL-encoded as Star%20Alliance)
ALLIANCES = {"oneworld", "skyteam", "star alliance"}


# =============================================================================
# PAGE TYPE DETECTION
# =============================================================================


def detect_page_type(url: str) -> str:
    """Detect the Skyscanner page type from a URL.

    Returns one of: 'flights', 'hotels', 'carhire', 'browse', 'multicity', 'other'.
    """
    parsed = urlparse(url.strip())
    path = parsed.path.lower()

    if "/transport/d/" in path:
        return "multicity"
    if "/transport/flights-from/" in path:
        return "browse"
    if "/transport/flights/" in path:
        return "flights"
    if "/hotels/" in path:
        return "hotels"
    if "/carhire/" in path:
        return "carhire"
    return "other"


# =============================================================================
# PARSING HELPERS
# =============================================================================


def _normalize_stops(raw: str) -> set[str]:
    """Normalize the stops parameter into a canonical set.

    Skyscanner uses exclusion-prefix format:
        stops=!oneStop,!twoPlusStops  →  {'!oneStop', '!twoPlusStops'}
        stops=direct                   →  {'direct'}
    """
    parts = [s.strip() for s in raw.split(",") if s.strip()]
    return set(parts)


def _normalize_airlines(raw: str) -> set[str]:
    """Normalize airline IDs into a set.

    Airlines are internal numeric IDs, possibly negative:
        airlines=-32593,-32596  →  {'-32593', '-32596'}
    """
    parts = [a.strip() for a in raw.split(",") if a.strip()]
    return set(parts)


def _normalize_alliances(raw: str) -> set[str]:
    """Normalize alliances into a canonical set.

    Browser-verified: alliance values may contain spaces:
        alliances=Star Alliance  →  {'star alliance'}
        alliances=oneworld       →  {'oneworld'}

    Case-insensitive matching with whitespace normalization.
    """
    parts = [a.strip() for a in raw.split(",") if a.strip()]
    # Normalize: lowercase + collapse whitespace
    return {" ".join(a.lower().split()) for a in parts}


def _normalize_children(raw: str) -> list[str]:
    """Normalize children ages.

    childrenv2=5|8  →  ['5', '8']
    Also handles comma-separated fallback.
    """
    if "|" in raw:
        return sorted([c.strip() for c in raw.split("|") if c.strip()])
    return sorted([c.strip() for c in raw.split(",") if c.strip()])


# =============================================================================
# FLIGHT URL PARSER
# =============================================================================


def parse_flight_url(url: str) -> dict[str, Any]:
    """Parse a Skyscanner flight URL into normalized components.

    Flight URL anatomy:
      /transport/flights/{origin}/{dest}/{YYMMDD}[/{YYMMDD}][/]?params

    Returns dict with keys:
      origin, destination, depart_date, return_date,
      rtn, adults, children_ages, cabin_class,
      stops, airlines, alliances, prefer_directs
    """
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query, keep_blank_values=True)

    result: dict[str, Any] = {
        "origin": "",
        "destination": "",
        "depart_date": "",
        "return_date": "",
        "rtn": "",
        "adults": "",
        "children_ages": [],
        "cabin_class": "",
        "stops": set(),
        "airlines": set(),
        "alliances": set(),
        "prefer_directs": "",
    }

    # Extract path segments: /transport/flights/JFK/LAX/260420[/260425]
    flight_match = re.search(
        r"/transport/flights/([a-zA-Z]{2,5})/([a-zA-Z]{2,5})/(\d{6})(?:/(\d{6}))?",
        path,
        re.IGNORECASE,
    )
    if flight_match:
        result["origin"] = flight_match.group(1).lower()
        result["destination"] = flight_match.group(2).lower()
        result["depart_date"] = flight_match.group(3)
        if flight_match.group(4):
            result["return_date"] = flight_match.group(4)

    # Query parameters
    result["rtn"] = _get_param(query, "rtn")
    result["adults"] = _get_param(query, "adultsv2")
    result["cabin_class"] = _get_param(query, "cabinclass").lower()
    result["prefer_directs"] = _get_param(query, "preferdirects").lower()

    # Children ages
    children_raw = _get_param(query, "childrenv2")
    if children_raw:
        result["children_ages"] = _normalize_children(children_raw)

    # Stops (exclusion format)
    stops_raw = _get_param(query, "stops")
    if stops_raw:
        result["stops"] = _normalize_stops(stops_raw)

    # Airlines (numeric IDs)
    airlines_raw = _get_param(query, "airlines")
    if airlines_raw:
        result["airlines"] = _normalize_airlines(airlines_raw)

    # Alliances (UpperCamelCase)
    alliances_raw = _get_param(query, "alliances")
    if alliances_raw:
        result["alliances"] = _normalize_alliances(alliances_raw)

    return result


# =============================================================================
# HOTEL URL PARSER
# =============================================================================


def parse_hotel_url(url: str) -> dict[str, Any]:
    """Parse a Skyscanner hotel search URL into normalized components.

    Hotel URL anatomy:
      /hotels/search?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25
        &adults=2&rooms=1&sort=price

    Returns dict with keys:
      entity_id, checkin, checkout, adults, rooms, sort
    """
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=True)

    return {
        "entity_id": _get_param(query, "entity_id"),
        "checkin": _get_param(query, "checkin"),
        "checkout": _get_param(query, "checkout"),
        "adults": _get_param(query, "adults"),
        "rooms": _get_param(query, "rooms"),
        "sort": _get_param(query, "sort").lower(),
    }


# =============================================================================
# CAR HIRE URL PARSER
# =============================================================================


def parse_carhire_url(url: str) -> dict[str, Any]:
    """Parse a Skyscanner car hire URL into normalized components.

    Car hire URL anatomy (browser-verified):
      /carhire/results/{pickup_id}/{dropoff_id}/{YYYY-MM-DDTHH:MM}/{YYYY-MM-DDTHH:MM}[/{age}]

    IMPORTANT: Pickup/Dropoff identifiers are internal numeric IDs, NOT IATA codes.
      e.g., Barcelona = 95565085, LHR = 95565050, LGW = 95565051
    The verifier accepts BOTH numeric IDs and IATA codes for backward compatability.

    Returns dict with keys:
      pickup_location, dropoff_location, pickup_datetime, dropoff_datetime, driver_age
    """
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")

    result: dict[str, Any] = {
        "pickup_location": "",
        "dropoff_location": "",
        "pickup_datetime": "",
        "dropoff_datetime": "",
        "driver_age": "",
    }

    # Extract path segments after /carhire/results/
    # Locations can be:
    #   - Internal numeric IDs (e.g., 95565085)
    #   - IATA codes (e.g., BCN, LHR) — for legacy/manual URLs
    #   - City slugs (e.g., barcelona)
    carhire_match = re.search(
        r"/carhire/results/([^/]+)/([^/]+)/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?:/(\d+))?",
        path,
        re.IGNORECASE,
    )
    if carhire_match:
        result["pickup_location"] = carhire_match.group(1).lower()
        result["dropoff_location"] = carhire_match.group(2).lower()
        result["pickup_datetime"] = carhire_match.group(3)
        result["dropoff_datetime"] = carhire_match.group(4)
        if carhire_match.group(5):
            result["driver_age"] = carhire_match.group(5)

    return result


# =============================================================================
# GENERIC HELPERS
# =============================================================================


def _get_param(query: dict, *keys: str) -> str:
    """Get the first non-empty value from query dict for any of the keys.

    Handles both exact keys and case-insensitive fallback.
    """
    for key in keys:
        if key in query and query[key]:
            return unquote(query[key][0])
        key_lower = key.lower()
        if key_lower in query and query[key_lower]:
            return unquote(query[key_lower][0])
    return ""


# =============================================================================
# VERIFIER CLASS
# =============================================================================


@beartype
class SkyscannerUrlMatch(BaseMetric):
    """Comprehensive Skyscanner URL verifier for flights, hotels, and car hire.

    Browser-Verified (Mar 2026 on skyscanner.net):
    - Flight path: /transport/flights/{origin}/{dest}/{YYMMDD}[/{YYMMDD}]
    - Flight params: adultsv2, childrenv2, cabinclass, rtn, stops, airlines, alliances
    - Hotel params: entity_id, checkin, checkout, adults, rooms, sort
    - Car hire path: /carhire/results/{numeric_id}/{numeric_id}/{datetimeISO}/{datetimeISO}/{age}
    - Car hire locations use INTERNAL NUMERIC IDs (95565085), not IATA codes
    - Domain variations: .net, .com, regional (.co.in, .co.uk, .de, etc.)
    - Stops use exclusion-prefix: stops=!oneStop,!twoPlusStops
    - Airlines use internal numeric IDs
    - Alliances may have spaces: Star Alliance, oneworld, SkyTeam
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
        self._page_type = ""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(gt_urls={self.gt_urls})"

    async def reset(self) -> None:
        """Reset the match state for new evaluation."""
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details = {}
        self._page_type = ""

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
        if domain and not self._is_valid_skyscanner_domain(domain):
            logger.debug(f"Ignoring non-Skyscanner URL: {url}")
            return

        # Don't overwrite after match
        if self._found_match:
            return

        self._agent_url = url
        self._page_type = detect_page_type(url)

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

    async def compute_detailed(self) -> SkyscannerVerifierResult:
        """Compute detailed result with match info."""
        score = 1.0 if self._found_match else 0.0
        return SkyscannerVerifierResult(
            score=score,
            match=self._found_match,
            page_type=self._page_type,
            agent_url=self._agent_url,
            gt_url=self._matched_gt_url,
            details=self._match_details,
        )

    # ========================================================================
    # DOMAIN VALIDATION
    # ========================================================================

    @staticmethod
    def _is_valid_skyscanner_domain(domain: str) -> bool:
        """Check if domain is a valid Skyscanner domain.

        Accepts:
        - Exact matches: skyscanner.net, skyscanner.com
        - www prefix: www.skyscanner.net
        - Regional: skyscanner.co.in, skyscanner.co.uk, skyscanner.de
        - Any subdomain of the above
        """
        domain = domain.lower().rstrip(".")

        # Direct match on known domains
        for base in VALID_BASE_DOMAINS:
            if domain == base or domain.endswith("." + base):
                return True

        # Regional TLDs
        for regional in REGIONAL_TLDS:
            if domain == regional or domain.endswith("." + regional):
                return True

        # Generic pattern: anything.skyscanner.xxx
        if re.match(r"^([\w-]+\.)*skyscanner\.\w+(\.\w+)?$", domain):
            return True

        return False

    # ========================================================================
    # URL MATCHING DISPATCH
    # ========================================================================

    def _urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        """Compare two Skyscanner URLs based on detected page type."""
        details: dict[str, Any] = {"mismatches": [], "extra_params": []}

        try:
            gt_type = detect_page_type(gt_url)
            agent_type = detect_page_type(agent_url)

            # Page types must match
            if gt_type != agent_type:
                details["mismatches"].append(
                    f"Page type mismatch: agent='{agent_type}' vs gt='{gt_type}'"
                )
                return False, details

            if gt_type == "flights":
                return self._match_flight_urls(agent_url, gt_url, details)
            elif gt_type == "hotels":
                return self._match_hotel_urls(agent_url, gt_url, details)
            elif gt_type == "carhire":
                return self._match_carhire_urls(agent_url, gt_url, details)
            else:
                details["mismatches"].append(f"Unsupported page type: {gt_type}")
                return False, details

        except Exception as e:
            logger.error(f"Error comparing URLs: {e}")
            details["mismatches"].append(f"Parse error: {str(e)}")
            return False, details

    # ========================================================================
    # FLIGHT MATCHING
    # ========================================================================

    def _match_flight_urls(
        self, agent_url: str, gt_url: str, details: dict
    ) -> tuple[bool, dict]:
        """Compare two flight search URLs."""
        agent = parse_flight_url(agent_url)
        gt = parse_flight_url(gt_url)

        # 1. Origin
        if gt["origin"]:
            if not agent["origin"]:
                details["mismatches"].append(
                    f"Origin missing (expected '{gt['origin']}')"
                )
                return False, details
            if agent["origin"] != gt["origin"]:
                details["mismatches"].append(
                    f"Origin: '{agent['origin']}' vs '{gt['origin']}'"
                )
                return False, details

        # 2. Destination
        if gt["destination"]:
            if not agent["destination"]:
                details["mismatches"].append(
                    f"Destination missing (expected '{gt['destination']}')"
                )
                return False, details
            if agent["destination"] != gt["destination"]:
                details["mismatches"].append(
                    f"Destination: '{agent['destination']}' vs '{gt['destination']}'"
                )
                return False, details

        # 3. Departure date
        if gt["depart_date"]:
            if not agent["depart_date"]:
                details["mismatches"].append(
                    f"Depart date missing (expected '{gt['depart_date']}')"
                )
                return False, details
            if agent["depart_date"] != gt["depart_date"]:
                details["mismatches"].append(
                    f"Depart date: '{agent['depart_date']}' vs '{gt['depart_date']}'"
                )
                return False, details

        # 4. Return date
        if gt["return_date"]:
            if not agent["return_date"]:
                details["mismatches"].append(
                    f"Return date missing (expected '{gt['return_date']}')"
                )
                return False, details
            if agent["return_date"] != gt["return_date"]:
                details["mismatches"].append(
                    f"Return date: '{agent['return_date']}' vs '{gt['return_date']}'"
                )
                return False, details

        # 5. Trip type (rtn)
        if gt["rtn"]:
            if agent["rtn"] and agent["rtn"] != gt["rtn"]:
                details["mismatches"].append(
                    f"Trip type (rtn): '{agent['rtn']}' vs '{gt['rtn']}'"
                )
                return False, details

        # 6. Adults
        if gt["adults"]:
            if agent["adults"] and agent["adults"] != gt["adults"]:
                details["mismatches"].append(
                    f"Adults: '{agent['adults']}' vs '{gt['adults']}'"
                )
                return False, details

        # 7. Children ages (order-independent)
        if gt["children_ages"]:
            if not agent["children_ages"]:
                details["mismatches"].append(
                    f"Children ages missing (expected {gt['children_ages']})"
                )
                return False, details
            if sorted(agent["children_ages"]) != sorted(gt["children_ages"]):
                details["mismatches"].append(
                    f"Children ages: {agent['children_ages']} vs {gt['children_ages']}"
                )
                return False, details

        # 8. Cabin class
        if gt["cabin_class"]:
            if agent["cabin_class"] and agent["cabin_class"] != gt["cabin_class"]:
                details["mismatches"].append(
                    f"Cabin class: '{agent['cabin_class']}' vs '{gt['cabin_class']}'"
                )
                return False, details

        # 9. Stops (set comparison — exclusion-prefix format)
        if gt["stops"]:
            if not agent["stops"]:
                details["mismatches"].append(
                    f"Stops filter missing (expected {gt['stops']})"
                )
                return False, details
            if agent["stops"] != gt["stops"]:
                details["mismatches"].append(
                    f"Stops: {agent['stops']} vs {gt['stops']}"
                )
                return False, details

        # 10. Airlines (set comparison — numeric IDs)
        if gt["airlines"]:
            if not agent["airlines"]:
                details["mismatches"].append(
                    f"Airlines filter missing (expected {gt['airlines']})"
                )
                return False, details
            if agent["airlines"] != gt["airlines"]:
                details["mismatches"].append(
                    f"Airlines: {agent['airlines']} vs {gt['airlines']}"
                )
                return False, details

        # 11. Alliances (set comparison — case-insensitive)
        if gt["alliances"]:
            if not agent["alliances"]:
                details["mismatches"].append(
                    f"Alliances filter missing (expected {gt['alliances']})"
                )
                return False, details
            if agent["alliances"] != gt["alliances"]:
                details["mismatches"].append(
                    f"Alliances: {agent['alliances']} vs {gt['alliances']}"
                )
                return False, details

        # 12. Prefer directs (fallback param — some URLs use this)
        if gt["prefer_directs"]:
            if agent["prefer_directs"] and agent["prefer_directs"] != gt["prefer_directs"]:
                details["mismatches"].append(
                    f"Prefer directs: '{agent['prefer_directs']}' vs '{gt['prefer_directs']}'"
                )
                return False, details

        return True, details

    # ========================================================================
    # HOTEL MATCHING
    # ========================================================================

    def _match_hotel_urls(
        self, agent_url: str, gt_url: str, details: dict
    ) -> tuple[bool, dict]:
        """Compare two hotel search URLs."""
        agent = parse_hotel_url(agent_url)
        gt = parse_hotel_url(gt_url)

        # 1. Entity ID (location identifier)
        if gt["entity_id"]:
            if not agent["entity_id"]:
                details["mismatches"].append(
                    f"entity_id missing (expected '{gt['entity_id']}')"
                )
                return False, details
            if agent["entity_id"] != gt["entity_id"]:
                details["mismatches"].append(
                    f"entity_id: '{agent['entity_id']}' vs '{gt['entity_id']}'"
                )
                return False, details

        # 2. Check-in date
        if gt["checkin"]:
            if not agent["checkin"]:
                details["mismatches"].append(
                    f"checkin missing (expected '{gt['checkin']}')"
                )
                return False, details
            if agent["checkin"] != gt["checkin"]:
                details["mismatches"].append(
                    f"checkin: '{agent['checkin']}' vs '{gt['checkin']}'"
                )
                return False, details

        # 3. Check-out date
        if gt["checkout"]:
            if not agent["checkout"]:
                details["mismatches"].append(
                    f"checkout missing (expected '{gt['checkout']}')"
                )
                return False, details
            if agent["checkout"] != gt["checkout"]:
                details["mismatches"].append(
                    f"checkout: '{agent['checkout']}' vs '{gt['checkout']}'"
                )
                return False, details

        # 4. Adults
        if gt["adults"]:
            if agent["adults"] and agent["adults"] != gt["adults"]:
                details["mismatches"].append(
                    f"adults: '{agent['adults']}' vs '{gt['adults']}'"
                )
                return False, details

        # 5. Rooms
        if gt["rooms"]:
            if agent["rooms"] and agent["rooms"] != gt["rooms"]:
                details["mismatches"].append(
                    f"rooms: '{agent['rooms']}' vs '{gt['rooms']}'"
                )
                return False, details

        # 6. Sort
        if gt["sort"]:
            if not agent["sort"]:
                details["mismatches"].append(
                    f"sort missing (expected '{gt['sort']}')"
                )
                return False, details
            if agent["sort"] != gt["sort"]:
                details["mismatches"].append(
                    f"sort: '{agent['sort']}' vs '{gt['sort']}'"
                )
                return False, details

        return True, details

    # ========================================================================
    # CAR HIRE MATCHING
    # ========================================================================

    def _match_carhire_urls(
        self, agent_url: str, gt_url: str, details: dict
    ) -> tuple[bool, dict]:
        """Compare two car hire search URLs."""
        agent = parse_carhire_url(agent_url)
        gt = parse_carhire_url(gt_url)

        # 1. Pickup location
        if gt["pickup_location"]:
            if not agent["pickup_location"]:
                details["mismatches"].append(
                    f"Pickup location missing (expected '{gt['pickup_location']}')"
                )
                return False, details
            if agent["pickup_location"] != gt["pickup_location"]:
                details["mismatches"].append(
                    f"Pickup location: '{agent['pickup_location']}' vs '{gt['pickup_location']}'"
                )
                return False, details

        # 2. Dropoff location
        if gt["dropoff_location"]:
            if not agent["dropoff_location"]:
                details["mismatches"].append(
                    f"Dropoff location missing (expected '{gt['dropoff_location']}')"
                )
                return False, details
            if agent["dropoff_location"] != gt["dropoff_location"]:
                details["mismatches"].append(
                    f"Dropoff location: '{agent['dropoff_location']}' vs '{gt['dropoff_location']}'"
                )
                return False, details

        # 3. Pickup datetime
        if gt["pickup_datetime"]:
            if not agent["pickup_datetime"]:
                details["mismatches"].append(
                    f"Pickup datetime missing (expected '{gt['pickup_datetime']}')"
                )
                return False, details
            if agent["pickup_datetime"] != gt["pickup_datetime"]:
                details["mismatches"].append(
                    f"Pickup datetime: '{agent['pickup_datetime']}' vs '{gt['pickup_datetime']}'"
                )
                return False, details

        # 4. Dropoff datetime
        if gt["dropoff_datetime"]:
            if not agent["dropoff_datetime"]:
                details["mismatches"].append(
                    f"Dropoff datetime missing (expected '{gt['dropoff_datetime']}')"
                )
                return False, details
            if agent["dropoff_datetime"] != gt["dropoff_datetime"]:
                details["mismatches"].append(
                    f"Dropoff datetime: '{agent['dropoff_datetime']}' vs '{gt['dropoff_datetime']}'"
                )
                return False, details

        # 5. Driver age (optional — don't fail if GT doesn't require it)
        if gt["driver_age"]:
            if agent["driver_age"] and agent["driver_age"] != gt["driver_age"]:
                details["mismatches"].append(
                    f"Driver age: '{agent['driver_age']}' vs '{gt['driver_age']}'"
                )
                return False, details

        return True, details


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
    url: str = "https://www.skyscanner.net/",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate task configuration for Skyscanner URL matching.

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
        raise ValueError("Either 'gt_url' or 'ground_truth_url' must be provided.")

    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(user_metadata, values)

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

    eval_target = get_import_path(SkyscannerUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": rendered_gt_urls}
    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )
