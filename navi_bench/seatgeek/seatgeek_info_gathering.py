"""SeatGeek info gathering verifier for event ticket searches.

This module provides functionality to verify AI agent ticket search results on SeatGeek
by gathering event information through JavaScript scraping and matching against expected queries.

Modeled after the StubHub verifier with a 3-layer extraction pipeline:
1. URL parsing (page type, event ID, filters)
2. LD+JSON extraction (event details, pricing, inventory)
3. DOM scraping (ticket listings via aria-label, filter state, listing tags)
"""

import functools
import itertools
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from beartype import beartype
from loguru import logger
from playwright.async_api import Page
from pydantic import BaseModel
from typing_extensions import TypedDict

from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path
from navi_bench.dates import initialize_placeholder_map, initialize_user_metadata, render_task_statement


class SingleCandidateQuery(TypedDict, total=False):
    """Single event query with specific criteria."""
    # Event Search Filters
    event_name: str | None
    event_category: str | None  # sports, concerts, theater, comedy
    date: str | None
    time: str | None
    venue: str | None
    city: str | None
    
    # Ticket Listing Filters
    min_tickets: int | None
    max_price: float | None
    min_price: float | None
    section: str | None
    row: str | None
    
    # Ticket Type Filters
    ticket_type: str | None  # standard, vip, premium, general_admission
    accessible_seating: bool | None
    aisle_seat: bool | None  # True if aisle seat required
    
    # SeatGeek-specific
    deal_score_min: int | None  # Minimum Deal Score (1-10)
    
    # Availability
    require_available: bool | None


class MultiCandidateQuery(TypedDict, total=False):
    """Multi-option event query allowing alternatives."""
    # Event Search Filters
    event_names: list[str] | None
    event_categories: list[str] | None  # sports, concerts, theater, comedy
    domain: list[str] | None  # Alias for event_categories
    dates: list[str] | None
    date_range: str | None  # today, this-weekend, this-week, this-month
    times: list[str] | None
    venues: list[str] | None
    cities: list[str] | None
    
    # Ticket Listing Filters
    min_tickets: int | None
    max_tickets: int | None
    ticket_quantities: list[int] | None
    max_price: float | None
    min_price: float | None
    sections: list[str] | None
    rows: list[str] | None
    
    # Ticket Type Filters
    ticket_types: list[str] | None  # standard, vip, premium, general_admission
    accessible_seating: bool | None
    aisle_seat: bool | None  # True if aisle seat required
    instant_delivery: bool | None  # True if instant delivery required
    
    # SeatGeek-specific
    deal_score_min: int | None  # Minimum Deal Score (1-10)
    listing_tags: list[str] | None  # cheapest, best_in_section, aisle, etc.
    
    # Availability
    require_available: bool | None
    
    # URL-based verification
    url_quantity: int | None  # Verify agent set correct ticket quantity
    url_max_price: float | None  # Verify agent set correct max price
    
    # Page type requirement
    require_page_type: str | list[str] | None  # event_listing, performer, category, search
    
    # Availability status filter
    availability_statuses: list[str] | None  # available, sold_out


class InputDict(TypedDict, total=False):
    """Input for update method."""
    page: Page


class InfoDict(TypedDict, total=False):
    """Scraped event information from JavaScript — comprehensive.
    
    Populated by the JS scraper (seatgeek_info_gathering.js) which extracts
    data from 3 layers: URL, LD+JSON, and DOM.
    """
    # Basic Info
    url: str
    eventName: str
    eventCategory: str  # sports, concerts, theater, comedy
    eventType: str  # SportsEvent, MusicEvent, TheaterEvent, etc.
    
    # Date/Time
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    startDate: str  # ISO format from LD+JSON
    endDate: str
    doorTime: str
    
    # Location
    venue: str
    city: str
    state: str
    country: str
    postalCode: str
    streetAddress: str
    latitude: float
    longitude: float
    
    # Teams/Performers
    competitors: list[str]
    performers: list[str]
    
    # Pricing (from LD+JSON)
    lowPrice: float
    highPrice: float
    inventoryLevel: int
    currency: str
    
    # Pricing (from DOM listings)
    price: float
    priceWithFees: float
    listingLowPrice: float
    listingHighPrice: float
    listingLowPriceWithFees: float
    listingHighPriceWithFees: float
    
    # Ticket Details (from DOM listings)
    section: str
    row: str
    ticketCount: int
    availableQuantities: list[int]
    dealScore: int  # SeatGeek Deal Score (1-10)
    availableSections: list[str]
    totalListings: int
    listingCountText: int
    
    # Listing Tags (from DOM)
    listingTags: list[str]  # cheapest, best_in_section, aisle, etc.
    availableTags: list[str]
    hasAisleSeats: bool
    isAisle: bool
    
    # Filter State (from DOM)
    filterState: dict
    
    # URL Filter State
    urlQuantity: int
    urlMaxPrice: float
    urlMinPrice: float
    urlCity: str
    urlSearch: str
    urlPerks: str
    urlSection: str
    
    # Page Metadata
    pageType: str  # event_listing, performer, category, search, homepage
    eventId: str
    category: str  # nba, nfl, mlb, etc.
    title: str
    h1: str
    metaDescription: str
    ogTitle: str
    ogUrl: str
    
    # Availability Status
    availabilityStatus: str  # available, sold_out, cancelled, rescheduled
    info: str  # available, sold_out (compat with StubHub)
    eventStatus: str  # From LD+JSON
    offerAvailability: str  # From LD+JSON
    
    # Source tracking
    source: str  # ld+json, dom, dom_listing, seatgeek
    offerUrl: str


class FinalResult(BaseModel):
    """Final verification result."""
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]


# ==================== MAIN VERIFIER CLASS ====================


@beartype
class SeatGeekInfoGathering(BaseMetric):
    """Gather event ticket information from SeatGeek to evaluate query coverage.
    
    This verifier uses a 3-layer approach:
    1. URL parsing — event ID, category, page type, filter params
    2. LD+JSON extraction — event name, date, venue, teams, prices, inventory
    3. DOM scraping — ticket listings (section, row, price, Deal Score from aria-label),
       listing tags (cheapest, aisle, etc.), filter state
    
    The verifier tracks navigation across multiple pages and walks the stack
    backwards to find the most recent relevant page for matching.
    """

    def __init__(self, queries: list[list[MultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries
        self._all_infos: list[list[InfoDict]] = []
        self._is_query_covered: list[bool] = [False] * len(queries)
        self._unavailable_evidences: list[list[list[InfoDict]]] = [
            [[] for _ in alternative_conditions] for alternative_conditions in queries
        ]
        self._navigation_stack: list[dict] = []
        self._tracked_pages: set = set()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(queries={self.queries})"

    @functools.cached_property
    def js_script(self) -> str:
        """Load the JavaScript scraper."""
        with open(Path(__file__).parent / "seatgeek_info_gathering.js", "r") as f:
            return f.read()

    async def reset(self) -> None:
        """Reset all tracking state."""
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._unavailable_evidences = [
            [[] for _ in alternative_conditions] for alternative_conditions in self.queries
        ]
        self._navigation_stack: list[dict] = []
        self._tracked_pages: set = set()

    def attach_to_context(self, context) -> None:
        """
        Attach automatic navigation tracking to a browser context.
        
        All page navigations and new tabs will be automatically tracked.
        
        Usage:
            verifier = SeatGeekInfoGathering(queries=queries)
            await verifier.reset()
            verifier.attach_to_context(context)
            
            # ... agent navigates ...
            
            result = await verifier.compute()
        
        Args:
            context: Playwright BrowserContext to attach tracking to
        """
        import asyncio
        
        async def track_page(page) -> None:
            """Attach navigation tracking to a single page."""
            page_id = id(page)
            if page_id in self._tracked_pages:
                return
            self._tracked_pages.add(page_id)
            
            async def on_frame_navigated(frame):
                """Handle navigation events on this page."""
                if frame != page.main_frame:
                    return
                
                try:
                    logger.info(f"[SeatGeek NAV] {page.url[:80]}...")
                    await self.update(page=page)
                except Exception as e:
                    logger.warning(f"SeatGeek update failed: {e}")
            
            page.on("framenavigated", lambda f: asyncio.create_task(on_frame_navigated(f)))
            logger.info(f"SeatGeek tracking attached to page: {page.url[:60]}...")
        
        # Track existing pages
        for page in context.pages:
            asyncio.create_task(track_page(page))
        
        # Track new pages (tabs/popups)
        context.on("page", lambda p: asyncio.create_task(track_page(p)))

    async def update(self, **kwargs) -> None:
        """Update with new page information.
        
        Waits for relevant DOM elements to load based on page type,
        then injects the JS scraper to extract structured data.
        """
        inputs: InputDict = kwargs
        page = inputs["page"]
        url = page.url
        
        # ========== SKIP NON-SEATGEEK PAGES ==========
        if "seatgeek.com" not in url:
            logger.debug(f"Skipping non-SeatGeek URL: {url[:60]}")
            return
        
        # ========== WAIT FOR ELEMENTS ==========
        
        # On event pages: wait for ticket listings
        if re.search(r'/.+-tickets/.+/.+/\d+', url):
            try:
                await page.wait_for_selector(
                    'button[aria-label*="Section"], button[aria-label*="section"], '
                    '[data-testid="all-listings"]',
                    timeout=15000
                )
                logger.info("Found ticket listings on event page")
            except Exception:
                logger.info("No ticket listings found yet, proceeding anyway")
        
        # On performer pages: wait for event list
        elif url.rstrip('/').endswith('-tickets') and url.count('/') <= 4:
            try:
                await page.wait_for_selector(
                    'a[href*="-tickets/"], [class*="EventItem"], [data-testid*="event"]',
                    timeout=15000
                )
                logger.info("Found event list on performer page")
            except Exception:
                logger.info("No event list found, proceeding anyway")
        
        # On search pages: wait for results
        elif '/search' in url:
            try:
                await page.wait_for_selector(
                    'a[href*="-tickets"], [data-testid*="search"]',
                    timeout=15000
                )
                logger.info("Found search results")
            except Exception:
                logger.info("No search results found, proceeding anyway")
        
        # ========== RUN JAVASCRIPT SCRAPER ==========
        infos: list[InfoDict] = await page.evaluate(self.js_script)
        logger.info(f"SeatGeekInfoGathering.update gathered {len(infos)} intermediate infos: {infos}")

        self._all_infos.append(infos)
        
        # ========== DETERMINE PAGE TYPE ==========
        if infos:
            page_type = infos[0].get("pageType", "unknown")
        else:
            page_type = "unknown"
        
        # ========== SMART STACK MANAGEMENT ==========
        base_url = url.split("?")[0]
        
        # Check if this page already exists in stack
        existing_idx = None
        for idx, entry in enumerate(self._navigation_stack):
            if entry["base_url"] == base_url and entry["page_type"] == page_type:
                existing_idx = idx
                break
        
        page_entry = {
            "url": url,
            "base_url": base_url,
            "page_type": page_type,
            "infos": infos,
            "timestamp": len(self._navigation_stack)
        }
        
        if existing_idx is not None:
            # P-1 FIX: Remove old entry and append at end to maintain correct
            # visit order. In-place update would keep the old index position,
            # causing reversed() traversal to treat a revisited page as stale.
            self._navigation_stack.pop(existing_idx)
            self._navigation_stack.append(page_entry)
            logger.info(f"Page type: {page_type} (moved to end, stack depth: {len(self._navigation_stack)})")
        else:
            self._navigation_stack.append(page_entry)
            logger.info(f"Page type: {page_type} (new page, stack depth: {len(self._navigation_stack)})")
        
        # Log info for debugging
        for info in infos[:5]:
            logger.info(f"    📋 Found: {info.get('eventName', 'unknown')}")

    async def compute(self) -> FinalResult:
        """
        Compute final coverage score by walking backwards through navigation stack.
        
        STACK TRAVERSAL LOGIC:
        1. Walk stack in REVERSE (LIFO) — most recent page first
        2. Look for 'event_listing' pages (highest priority)
        3. Fall back to 'performer'/'category' pages for broader matching
        4. Handle sold-out events (credit agent if they found the right event)
        """
        
        logger.info(f"Computing with {len(self._navigation_stack)} pages in navigation stack")
        
        # ========== WALK BACKWARDS THROUGH STACK ==========
        event_listing_found = False
        category_page_infos: list[InfoDict] = []
        
        for page_visit in reversed(self._navigation_stack):
            page_type = page_visit["page_type"]
            page_url = page_visit["url"]
            page_infos = page_visit["infos"]
            
            if page_type == "event_listing" and not event_listing_found:
                event_listing_found = True
                logger.info(f"Found event_listing in stack: {page_url[:80]}...")
                
                for i, alternative_conditions in enumerate(self.queries):
                    if self._is_query_covered[i]:
                        continue
                    
                    for info in page_infos:
                        if self._check_alternative_conditions(i, alternative_conditions, info):
                            logger.info(
                                f"SeatGeekInfoGathering.compute: Query {i} MATCHED on event page: "
                                f"{info.get('eventName')}"
                            )
                            self._is_query_covered[i] = True
                            break
                        else:
                            event_name = info.get("eventName", "?")
                            city = info.get("city", "?")
                            logger.info(f"Event '{event_name}' (city={city}) did NOT match query {i}")
                
                break
            
            elif page_type in ["performer", "category", "search"]:
                category_page_infos.extend(page_infos)
        
        # ========== FALLBACK: Check performer/category pages ==========
        if category_page_infos:
            unmatched_count = sum(1 for covered in self._is_query_covered if not covered)
            if unmatched_count > 0:
                logger.info(f"Falling back to {len(category_page_infos)} infos from other pages for {unmatched_count} unmatched queries")
                
                for i, alternative_conditions in enumerate(self.queries):
                    if self._is_query_covered[i]:
                        continue
                    
                    for info in category_page_infos:
                        if self._check_alternative_conditions(i, alternative_conditions, info):
                            logger.info(
                                f"SeatGeekInfoGathering.compute: Query {i} MATCHED on fallback page: "
                                f"{info.get('eventName')}"
                            )
                            self._is_query_covered[i] = True
                            break
        
        # ========== Check exhausted queries (sold-out handling) ==========
        for i, alternative_conditions in enumerate(self.queries):
            if self._is_query_covered[i]:
                continue
            for j, alternative_condition in enumerate(alternative_conditions):
                if not self._is_exhausted(alternative_condition, self._unavailable_evidences[i][j]):
                    break
            else:
                logger.info(f"SeatGeekInfoGathering.compute found query {i} exhausted")
                self._is_query_covered[i] = True

        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)
        final_result = FinalResult(
            score=n_covered / max(n_queries, 1),
            n_queries=n_queries,
            n_covered=n_covered,
            queries=self.queries,
            is_query_covered=self._is_query_covered,
        )
        logger.info(f"SeatGeekInfoGathering.compute final result: {final_result}")
        return final_result

    def _check_alternative_conditions(
        self, i: int, alternative_conditions: list[MultiCandidateQuery], info: InfoDict
    ) -> bool:
        """Check if any alternative condition is covered by the info."""
        for j, alternative_condition in enumerate(alternative_conditions):
            evidences = self._unavailable_evidences[i][j]
            if self._check_multi_candidate_query(alternative_condition, info, evidences):
                return True
        return False

    @classmethod
    def _check_multi_candidate_query(
        cls, query: MultiCandidateQuery, info: InfoDict, evidences: list[InfoDict]
    ) -> bool:
        """Check if multi-candidate query matches the info — comprehensive filter matching."""
        
        # ========== EVENT SEARCH FILTERS ==========
        
        # Check event names using SUBSTRING matching
        # SeatGeek advantage: also checks competitors[] and performers[] from LD+JSON
        if query_names := query.get("event_names"):
            query_names = [name.lower() for name in query_names]
            event_name = info.get("eventName", "").lower()
            competitors = [c.lower() for c in info.get("competitors", [])]
            performers = [p.lower() for p in info.get("performers", [])]
            all_names = [event_name] + competitors + performers
            
            if not any(qname in name for qname in query_names for name in all_names):
                return False

        # Check event categories
        if query_categories := query.get("event_categories"):
            query_categories = [c.lower() for c in query_categories]
            event_category = info.get("eventCategory", "").lower()
            event_type = info.get("eventType", "").lower()
            category = info.get("category", "").lower()
            all_categories = [event_category, event_type, category]
            
            if not any(c in cat for c in query_categories for cat in all_categories if cat):
                return False

        # Check domain (alias for event_categories)
        if query_domain := query.get("domain"):
            query_domain = [d.lower() for d in query_domain]
            event_category = info.get("eventCategory", "").lower()
            category = info.get("category", "").lower()
            all_categories = [event_category, category]
            
            if not any(d in cat for d in query_domain for cat in all_categories if cat):
                return False

        # Check venues using SUBSTRING matching
        # BUG 2 FIX: If query requires venues, info MUST have a venue to match
        if venues := query.get("venues"):
            venues = [v.lower() for v in venues]
            venue = info.get("venue", "").lower()
            if not venue:
                return False
            if not any(v in venue for v in venues):
                return False

        # Check cities using SUBSTRING matching
        # IMPORTANT: If query requires cities, info MUST have a city to match
        if cities := query.get("cities"):
            cities = [c.lower() for c in cities]
            city = (info.get("city") or "").lower()
            url_city = (info.get("urlCity") or "").lower().replace("-", " ")
            all_cities = [city, url_city]
            
            # Must have at least one non-empty city source
            if not any(ci for ci in all_cities):
                return False
            if not any(c in ci for c in cities for ci in all_cities if ci):
                return False

        # ========== TICKET LISTING FILTERS ==========
        
        # Check minimum tickets
        # BUG 3 FIX: Use `is not None` instead of falsy check (ticketCount=0 is valid)
        if (min_tickets := query.get("min_tickets")) is not None:
            ticket_count = info.get("ticketCount")
            if ticket_count is not None and ticket_count < min_tickets:
                return False

        # Check maximum tickets
        if (max_tickets := query.get("max_tickets")) is not None:
            ticket_count = info.get("ticketCount")
            if ticket_count is not None and ticket_count > max_tickets:
                return False

        # Check exact ticket quantities
        if ticket_quantities := query.get("ticket_quantities"):
            ticket_count = info.get("ticketCount")
            if ticket_count is not None and ticket_count not in ticket_quantities:
                return False

        # Check maximum price — using cascading fallback:
        # LD+JSON lowPrice → DOM listing low → individual listing price
        # BUG 4 FIX: Use `is not None` to handle max_price=0.0 edge case
        if (max_price := query.get("max_price")) is not None:
            low_price = info.get("lowPrice")
            listing_low = info.get("listingLowPrice")
            price = info.get("price")
            
            # Pick first non-None price in fallback chain
            cheapest = low_price if low_price is not None else (listing_low if listing_low is not None else price)
            if cheapest is not None and cheapest > max_price:
                return False

        # Check minimum price
        # KARAN BUG FIX: Use highPrice fallback chain for min_price
        # We want to know if ANY ticket is above min_price, so check the HIGHEST priced ticket
        if (min_price := query.get("min_price")) is not None:
            high_price = info.get("highPrice")
            listing_high = info.get("listingHighPrice")
            price = info.get("price")
            priciest = high_price if high_price is not None else (listing_high if listing_high is not None else price)
            if priciest is not None and priciest < min_price:
                return False

        # Check sections using EXACT matching
        # BUG 11 FIX: Use exact equality to prevent section "1" matching "11"
        if sections := query.get("sections"):
            sections = [s.lower() for s in sections]
            section = info.get("section", "").lower()
            available_sections = [s.lower() for s in info.get("availableSections", [])]
            all_sections = [section] + available_sections
            
            if not any(s == sec for s in sections for sec in all_sections if sec):
                return False

        # Check rows using EXACT matching (row "1" must not match "15")
        if rows := query.get("rows"):
            rows = [r.lower() for r in rows]
            row = info.get("row", "").lower()
            if row and row not in rows:
                return False

        # Check aisle seat requirement
        if query.get("aisle_seat") is True:
            has_aisle = info.get("hasAisleSeats", False) or info.get("isAisle", False)
            if not has_aisle:
                return False

        # ========== TICKET TYPE FILTERS ==========

        # Check ticket types
        if ticket_types := query.get("ticket_types"):
            ticket_types = [t.lower() for t in ticket_types]
            # SeatGeek doesn't have explicit ticket type field,
            # but we can check listing tags and event category
            listing_tags = [t.lower() for t in info.get("listingTags", [])]
            available_tags = [t.lower() for t in info.get("availableTags", [])]
            all_tags = listing_tags + available_tags
            # P-3 FIX: Remove `if all_tags` guard — when ticket_types is required
            # but no tag data exists, the match should FAIL, not silently pass.
            if not any(t in tag for t in ticket_types for tag in all_tags):
                return False

        # Check accessible seating requirement
        if query.get("accessible_seating") is True:
            # SeatGeek accessible seating is a seat perk, check URL perks
            url_perks = (info.get("urlPerks") or "").lower()
            if url_perks and "accessible" not in url_perks:
                return False

        # Check instant delivery requirement
        # P-4 FIX: Only reject if filterState explicitly has instantDelivery=False.
        # When filterState is empty/missing (JS couldn't extract it), don't block.
        if query.get("instant_delivery") is True:
            filter_state = info.get("filterState")
            if isinstance(filter_state, dict) and "instantDelivery" in filter_state:
                if not filter_state["instantDelivery"]:
                    return False

        # ========== SEATGEEK-SPECIFIC FILTERS ==========
        
        # Check Deal Score minimum
        # P-5 FIX: Use `is not None` to handle deal_score_min=0 edge case
        if (deal_score_min := query.get("deal_score_min")) is not None:
            deal_score = info.get("dealScore")
            if deal_score is not None and deal_score < deal_score_min:
                return False

        # Check listing tags
        # P-2 FIX: Remove `if all_tags` guard — when listing_tags is required
        # but no tag data exists, the match should FAIL, not silently pass.
        if required_tags := query.get("listing_tags"):
            required_tags = [t.lower() for t in required_tags]
            listing_tags = [t.lower() for t in info.get("listingTags", [])]
            available_tags = [t.lower() for t in info.get("availableTags", [])]
            all_tags = listing_tags + available_tags
            if not any(t in tag for t in required_tags for tag in all_tags):
                return False

        # ========== URL-BASED VERIFICATION ==========
        
        # Check URL quantity
        # BUG 4 FIX: Use `is not None` to handle url_quantity=0 edge case
        if (url_quantity := query.get("url_quantity")) is not None:
            info_url_quantity = info.get("urlQuantity")
            if info_url_quantity is not None and info_url_quantity != url_quantity:
                return False
        
        # Check URL max price
        if (url_max_price := query.get("url_max_price")) is not None:
            info_url_max = info.get("urlMaxPrice")
            if info_url_max is not None and info_url_max != url_max_price:
                return False

        # ========== PAGE TYPE REQUIREMENT ==========
        
        if require_page_type := query.get("require_page_type"):
            page_type = info.get("pageType", "")
            if page_type:
                acceptable_types = require_page_type if isinstance(require_page_type, list) else [require_page_type]
                if page_type not in acceptable_types:
                    return False

        # ========== AVAILABILITY STATUS ==========
        # BUG 1 FIX: Use exact equality instead of substring to prevent
        # "available" matching "unavailable"
        if availability_statuses := query.get("availability_statuses"):
            availability_statuses = [s.lower() for s in availability_statuses]
            info_availability = info.get("availabilityStatus", info.get("info", "")).lower()
            if info_availability and info_availability not in availability_statuses:
                return False

        # ========== DATE/TIME FILTERS ==========
        
        query_dates = query.get("dates")
        query_times = query.get("times")
        
        require_available = query.get("require_available", False)
        
        available_info = info.get("info", "").lower()
        is_sold_out = "sold_out" in available_info or "unavailable" in available_info
        
        if is_sold_out:
            if require_available:
                # User explicitly requires available tickets — reject sold-out
                # Append as evidence if it matches the dates (or if no dates required)
                if not query_dates or info.get("date") in query_dates:
                    evidences.append(info)
                return False
            else:
                # require_available is False (default) — ACCEPT sold-out events!
                # Agent found the correct event, so they get full credit
                if query_dates:
                    if info.get("date") not in query_dates:
                        return False
                if query_times:
                    if info.get("time") not in query_times:
                        return False
                return True
        else:
            if query_dates:
                if info.get("date") not in query_dates:
                    return False
            if query_times:
                if info.get("time") not in query_times:
                    return False
            return True

    @classmethod
    def _check_single_candidate_query(cls, query: SingleCandidateQuery, info: InfoDict) -> bool:
        """Check if single-candidate query matches the info."""
        if (query_name := query.get("event_name")) is not None:
            event_name = info.get("eventName", "").lower()
            if query_name.lower() not in event_name:
                return False

        if (query_venue := query.get("venue")) is not None:
            if query_venue.lower() not in info.get("venue", "").lower():
                return False

        if (query_city := query.get("city")) is not None:
            if query_city.lower() not in (info.get("city") or "").lower():
                return False

        if (query_date := query.get("date")) is not None:
            if info.get("date") != query_date:
                return False

        if (query_time := query.get("time")) is not None:
            if info.get("time") != query_time:
                return False

        if (query_section := query.get("section")) is not None:
            if query_section.lower() not in info.get("section", "").lower():
                return False

        return True

    @classmethod
    def _is_exhausted(cls, query: MultiCandidateQuery, evidences: list[InfoDict]) -> bool:
        """Check if we've exhausted searching for the query."""
        query_names = query.get("event_names") or [None]
        query_venues = query.get("venues") or [None]
        query_cities = query.get("cities") or [None]
        query_dates = query.get("dates") or [None]
        query_times = query.get("times") or [None]

        for query_name, query_venue, query_city, query_date, query_time in itertools.product(
            query_names, query_venues, query_cities, query_dates, query_times
        ):
            found_match = False
            for info in evidences:
                if cls._check_single_candidate_query(
                    SingleCandidateQuery(
                        event_name=query_name,
                        venue=query_venue,
                        city=query_city,
                        date=query_date,
                        time=query_time,
                    ),
                    info,
                ):
                    found_match = True
                    break

            if not found_match:
                return False

        return True


# ==================== TASK CONFIG GENERATORS ====================


def generate_task_config_random(
    event_type: Literal["sports", "concert", "theater"],
    city: str,
    timezone: str,
    event_name: str | None = None,
    seed: int | None = None,
    url: str = "https://seatgeek.com",
) -> BaseTaskConfig:
    """Generate random task configuration for SeatGeek events.
    
    Args:
        event_type: Type of event (sports, concert, theater)
        city: City name for the event
        timezone: IANA timezone string (e.g., 'America/Los_Angeles')
        event_name: Optional specific event name
        seed: Random seed for reproducibility
        url: SeatGeek URL
    """
    if seed is not None:
        random.seed(seed)

    location = f"{city}"

    if not event_name:
        event_name = f"{event_type} event"

    # Random date (next 30 days)
    days_ahead = random.randint(1, 30)
    event_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    max_price = random.choice([200.0, 300.0, 500.0, 1000.0])
    min_tickets = random.randint(1, 4)

    task = (
        f"Search for {event_name} tickets in {city} "
        f"for {event_date} with at least {min_tickets} tickets "
        f"under ${max_price:.0f}"
    )

    user_metadata = UserMetadata(
        location=location,
        timezone=timezone,
        timestamp=int(datetime.now().timestamp()),
    )

    eval_config = {
        "_target_": get_import_path(SeatGeekInfoGathering),
        "queries": [[{
            "event_names": [event_name.lower()],
            "dates": [event_date],
            "cities": [city.lower()],
            "min_tickets": min_tickets,
            "max_price": max_price,
        }]]
    }

    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)


def generate_task_config_deterministic(
    mode: Literal["any", "all"],
    task: str,
    queries: list[list[MultiCandidateQuery]],
    location: str,
    timezone: str,
    timestamp: int | None = None,
    url: str = "https://seatgeek.com",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate deterministic task configuration.
    
    Args:
        mode: Task mode ("any" or "all"). Currently accepted for API
              compatibility but not used for query expansion. All queries
              are passed through unchanged.
        task: Task description string.  May contain ``{placeholder}``
              tokens that will be resolved using *values*.
        queries: List of query alternatives.  Query ``dates`` fields set
                 to a ``"{placeholder}"`` string will be replaced with
                 the resolved ISO dates from *values*.
        location: User location string.
        timezone: IANA timezone string.
        timestamp: Optional unix timestamp.  ``None`` means "now".
        url: Starting URL.
        values: Optional mapping of placeholder keys to relative-date
                expressions (e.g. ``{"dateRange": "the next Saturday"}``).
                Resolved at runtime via :func:`dates.resolve_placeholder_values`.
    """
    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(user_metadata, values)

    # Render {placeholder} tokens in task text
    rendered_task = render_task_statement(task, resolved_placeholders)

    # Inject resolved dates into query "dates" fields that are placeholder strings
    for placeholder_key, (_, dates) in resolved_placeholders.items():
        template_string = "{" + placeholder_key + "}"
        if not dates:
            raise ValueError(f"No future dates resolved for placeholder '{placeholder_key}'")
        for query_group in queries:
            for candidate_obj in query_group:
                if "dates" in candidate_obj and candidate_obj["dates"] == template_string:
                    candidate_obj["dates"] = dates

    eval_config = {
        "_target_": get_import_path(SeatGeekInfoGathering),
        "queries": queries
    }

    return BaseTaskConfig(url=url, task=rendered_task, user_metadata=user_metadata, eval_config=eval_config)


if __name__ == "__main__":
    import json
    from navi_bench.base import DatasetItem, instantiate

    dataset_row = {
        "task_id": "navi_bench/seatgeek/test/0",
        "task_generation_config_json": json.dumps({
            "_target_": "navi_bench.seatgeek.seatgeek_info_gathering.generate_task_config_deterministic",
            "mode": "any",
            "url": "https://seatgeek.com",
            "task": "Search for Lakers tickets in Los Angeles for February 26, 2026",
            "queries": [[{
                "event_names": ["lakers", "los angeles lakers"],
                "dates": ["2026-02-26"],
                "cities": ["los angeles", "phoenix"]
            }]],
            "location": "Los Angeles, CA, United States",
            "timezone": "America/Los_Angeles",
        }),
        "env": "real",
        "domain": "seatgeek",
        "l1_category": "e_commerce",
        "l2_category": "sports",
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
