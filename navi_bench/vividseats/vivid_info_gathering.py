"""Vivid Seats info gathering verifier for event ticket searches."""

import functools
import itertools
import asyncio
import re
from pathlib import Path
from typing import Literal

from loguru import logger
from playwright.async_api import Page
from pydantic import BaseModel
from typing_extensions import TypedDict

from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path
from navi_bench.dates import initialize_user_metadata, initialize_placeholder_map, render_task_statement

class SingleCandidateQuery(TypedDict, total=False):
    event_name: str | None
    date: str | None

class MultiCandidateQuery(TypedDict, total=False):
    event_names: list[str] | None
    dates: list[str] | None
    cities: list[str] | None
    venues: list[str] | None
    
    quantity: int | None
    max_price: float | None
    min_price: float | None
    sections: list[str] | None
    rows: list[str] | None
    zones: list[str] | None
    
    require_super_seller: bool | None  # Vivid Seats specific feature
    require_available: bool | None

class InfoDict(TypedDict, total=False):
    url: str
    source: str
    eventName: str
    date: str
    time: str
    venue: str
    city: str
    section: str
    row: str
    zone: str
    price: float
    ticketCount: int
    isSuperSeller: bool
    availabilityStatus: str
    pageType: str
    antiBotStatus: str
    filterQuantity: int
    filterMinPrice: float
    filterMaxPrice: float
    filterDate: str
    filterZones: list[str]
    filterSuperSeller: bool

class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]

class VividSeatsInfoGathering(BaseMetric):
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

    @functools.cached_property
    def js_script(self) -> str:
        with open(Path(__file__).parent / "vivid_info_gathering.js", "r") as f:
            return f.read()

    async def reset(self) -> None:
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._unavailable_evidences = [[[] for _ in alternative_conditions] for alternative_conditions in self.queries]
        self._navigation_stack = []
        self._tracked_pages = set()
    
    def attach_to_context(self, context) -> None:
        async def track_page(page) -> None:
            page_id = id(page)
            if page_id in self._tracked_pages: return
            self._tracked_pages.add(page_id)
            
            async def on_frame_navigated(frame):
                if frame != page.main_frame: return
                try:
                    logger.info(f"[NAV] VS: {page.url[:80]}...")
                    await self.update(page=page)
                except Exception as e:
                    pass
            
            page.on("framenavigated", lambda f: asyncio.create_task(on_frame_navigated(f)))
        
        for page in context.pages:
            asyncio.create_task(track_page(page))
        context.on("page", lambda p: asyncio.create_task(track_page(p)))

    async def update(self, **kwargs) -> None:
        page = kwargs["page"]
        content = await page.content()
        
        if "px-captcha" in content or "challenge-running" in content:
            logger.error("Agent blocked by Vivid Seats Anti-Bot (PerimeterX/Cloudflare).")

        all_frame_infos: list[InfoDict] = []
        for frame in page.frames:
            try:
                # Add a 3-second timeout to prevent Playwright from hanging on frozen frames
                frame_infos = await asyncio.wait_for(frame.evaluate(self.js_script), timeout=3.0)
                if frame_infos and isinstance(frame_infos, list):
                    all_frame_infos.extend(frame_infos)
            except Exception: pass
        
        # Deduplication logic
        unique_infos = []
        seen = set()
        for info in all_frame_infos:
            key = f"{info.get('eventName')}-{info.get('date')}-{info.get('section')}-{info.get('row')}-{info.get('price')}-{info.get('source')}"
            if key not in seen:
                seen.add(key)
                unique_infos.append(info)
        
        infos = unique_infos

        # =====================================================================
        # REAL-TIME PRINTING
        # =====================================================================
        if infos:
            print(f"\n[SCRAPED DATA FROM: {page.url[:60]}...]", flush=True)
            
            # --- Print Active Filters ---
            first_info = infos[0]
            qty = first_info.get("filterQuantity")
            min_p = first_info.get("filterMinPrice")
            max_p = first_info.get("filterMaxPrice")
            ss_only = first_info.get("filterSuperSeller")
            filter_date = first_info.get("filterDate")
            filter_zones = first_info.get("filterZones", [])
            
            filters_applied = []
            if filter_date: filters_applied.append(f"Date: {filter_date}")
            if qty is not None: filters_applied.append(f"Qty: {qty}")
            if min_p is not None: filters_applied.append(f"Min Price: ${min_p}")
            if max_p is not None: filters_applied.append(f"Max Price: ${max_p}")
            if filter_zones: filters_applied.append(f"Zones: {', '.join(filter_zones).title()}")
            if ss_only: filters_applied.append("Super Seller Only")
            
            if filters_applied:
                print(f"  [ACTIVE FILTERS] ➔ {' | '.join(filters_applied)}", flush=True)
            else:
                print(f"  [ACTIVE FILTERS] ➔ None detected", flush=True)
            print("-" * 65)
            # ---------------------------------

            for i, item in enumerate(infos[:10], 1): # Print first 10 items
                name = item.get("eventName", "Unknown").title()
                price = item.get("price", "N/A")
                sec = item.get("section", "N/A")
                row = item.get("row", "N/A")
                seller = "🌟 Super Seller" if item.get("isSuperSeller") else "🎫 Standard"
                print(f"  {i}. {name} | Sec: {sec}, Row: {row} | ${price} | {seller}", flush=True)
            
            if len(infos) > 10:
                print(f"  ... and {len(infos) - 10} more items.", flush=True)
        # =====================================================================
        
        page_type = infos[0].get("pageType", "unknown") if infos else "unknown"
        anti_bot = infos[0].get("antiBotStatus", "unknown") if infos else "unknown"

        self._all_infos.append(infos)
        
        base_url = page.url.split("?")[0]
        page_entry = {"url": page.url, "base_url": base_url, "page_type": page_type, "anti_bot": anti_bot, "infos": infos}
        
        existing_idx = next((i for i, e in enumerate(self._navigation_stack) if e["base_url"] == base_url and e["page_type"] == page_type), None)
        if existing_idx is not None:
            self._navigation_stack[existing_idx] = page_entry
        else:
            self._navigation_stack.append(page_entry)

    async def compute(self) -> FinalResult:
        event_listing_found = False
        fallback_infos: list[InfoDict] = []
        
        for page_visit in reversed(self._navigation_stack):
            if page_visit["anti_bot"] in ["blocked_perimeterx", "blocked_cloudflare"]:
                continue
                
            if page_visit["page_type"] == "event_listing" and not event_listing_found:
                event_listing_found = True
                for i, alternative_conditions in enumerate(self.queries):
                    if self._is_query_covered[i]: continue
                    for info in page_visit["infos"]:
                        if self._check_alternative_conditions(i, alternative_conditions, info):
                            self._is_query_covered[i] = True
                            break
                break
            elif page_visit["page_type"] in ["event_category", "search_results"]:
                fallback_infos.extend(page_visit["infos"])
        
        if not event_listing_found and fallback_infos:
            for i, alternative_conditions in enumerate(self.queries):
                if self._is_query_covered[i]: continue
                for info in fallback_infos:
                    if self._check_alternative_conditions(i, alternative_conditions, info):
                        self._is_query_covered[i] = True
                        break

        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)
        return FinalResult(score=n_covered / max(n_queries, 1), n_queries=n_queries, n_covered=n_covered, queries=self.queries, is_query_covered=self._is_query_covered)

    def _check_alternative_conditions(self, i: int, alternative_conditions: list[MultiCandidateQuery], info: InfoDict) -> bool:
        for j, alternative_condition in enumerate(alternative_conditions):
            if self._check_multi_candidate_query(alternative_condition, info):
                return True
        return False

    @classmethod
    def _check_multi_candidate_query(cls, query: MultiCandidateQuery, info: InfoDict) -> bool:
        # Event Names
        if q_names := query.get("event_names"):
            if not any(q.lower() in info.get("eventName", "").lower() for q in q_names): return False

        # Cities
        if q_cities := query.get("cities"):
            city_data = (info.get("city") or "").lower()
            if not any(c.lower() in city_data for c in q_cities): return False

        # Venues
        if q_venues := query.get("venues"):
            venue_data = (info.get("venue") or "").lower()
            if not venue_data or not any(v.lower() in venue_data for v in q_venues): return False

        # Quantity
        if q_qty := query.get("quantity"):
            # Evaluates against scraped individual ticket count or the global page filter
            info_qty = info.get("ticketCount") or info.get("filterQuantity")
            if info_qty is None or info_qty < q_qty: return False

        # Min Price (Includes check for Falsy 0.0 values)
        if "min_price" in query and query["min_price"] is not None:
            min_price = query["min_price"]
            eval_min_price = info.get("price") or info.get("filterMinPrice")
            if eval_min_price is None or eval_min_price < min_price: return False

        # Max Price (Includes check for Falsy 0.0 values)
        if "max_price" in query and query["max_price"] is not None:
            max_price = query["max_price"]
            eval_max_price = info.get("price") or info.get("filterMaxPrice")
            if eval_max_price is None or eval_max_price > max_price: return False
                
        # Sections (Normalized prefix stripping)
        if q_sections := query.get("sections"):
            info_sec = (info.get("section") or "").lower()
            normalized_info_sec = re.sub(r'^(section|sec)\s*', '', info_sec.strip())
            normalized_queries = [re.sub(r'^(section|sec)\s*', '', s.strip().lower()) for s in q_sections]
            
            if not info_sec or not any(q in normalized_info_sec for q in normalized_queries):
                return False

        # Rows
        if q_rows := query.get("rows"):
            row_data = (info.get("row") or "").lower()
            if not row_data or not any(r.lower() in row_data for r in q_rows): return False

        # Super Seller (Vivid Seats specific)
        if query.get("require_super_seller") is True:
            if not info.get("isSuperSeller", False) and not info.get("filterSuperSeller", False): return False

        # Availability Status
        if require_available := query.get("require_available", False):
            if info.get("availabilityStatus", "available") == "sold_out": return False

        # Dates (Includes fallback for Discovery/Search pages)
        if q_dates := query.get("dates"):
            info_date = info.get("date")
            
            # Helper function to check if the query date is satisfied by the UI Date Range filter
            def is_date_satisfied():
                if info_date in q_dates:
                    return True
                
                # Fallback to UI Filter Date Range (e.g. "Mar 3 - Apr 30, 2026")
                filter_date = info.get("filterDate") or info.get("filterDateRange")
                if filter_date:
                    range_match = re.search(r'(\w+\s+\d+).*?(\w+\s+\d+,\s*\d{4})', filter_date)
                    if range_match:
                        from datetime import datetime
                        try:
                            year = datetime.now().year
                            range_start = datetime.strptime(range_match.group(1) + f" {year}", "%b %d %Y")
                            range_end = datetime.strptime(range_match.group(2).replace(',', ''), "%b %d %Y")
                            for q_date in q_dates:
                                try:
                                    qd = datetime.strptime(q_date, "%Y-%m-%d")
                                    if range_start <= qd <= range_end:
                                        return True
                                except ValueError:
                                    continue
                        except ValueError:
                            pass
                return False
            
            if not is_date_satisfied():
                return False
        
        # Zones [FIXED: Checks both per-ticket zone and global filter]
        if q_zones := query.get("zones"):
            ticket_zone = (info.get("zone") or "").lower()
            info_zones = info.get("filterZones") or []
            
            # Check if any queried zone matches the individual ticket's zone
            ticket_zone_matched = any(z.lower() in ticket_zone for z in q_zones)
            
            # Check if any queried zone matches the globally active zone filters
            filter_zone_matched = any(z.lower() in [iz.lower() for iz in info_zones] for z in q_zones)
            
            if not (ticket_zone_matched or filter_zone_matched): 
                return False

        return True

def generate_task_config_deterministic(
    mode: Literal["any", "all"], 
    task: str, 
    queries: list[list[MultiCandidateQuery]], 
    location: str, 
    timezone: str, 
    timestamp: int | None = None, 
    url: str = "https://www.vividseats.com/",
    values: dict[str, str] | None = None
) -> BaseTaskConfig:
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    
    if values:
        # 1. Resolve relative dates and apply time-travel/bumping logic
        placeholder_map, current_date = initialize_placeholder_map(user_metadata, values)
        
        # 2. Render the natural language prompt with the resolved text
        task = render_task_statement(task, placeholder_map)
        
        # 3. Inject the bumped ISO dates directly into the queries
        # FIX: The placeholder map stores a tuple of (natural_language_str, list_of_iso_dates)
        date_tuple = placeholder_map.get("dateRange")
        
        if date_tuple and isinstance(date_tuple, tuple) and len(date_tuple) == 2:
            _, resolved_iso_dates = date_tuple  # Unpack the tuple
            
            if resolved_iso_dates:
                for alternative_conditions in queries:
                    for query in alternative_conditions:
                        query["dates"] = resolved_iso_dates
                        
    eval_config = {"_target_": get_import_path(VividSeatsInfoGathering), "queries": queries}
    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)