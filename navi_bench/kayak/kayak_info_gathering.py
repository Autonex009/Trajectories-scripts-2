"""Kayak info gathering verifier for flight searches."""

import functools
import asyncio
import re
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel
from typing_extensions import TypedDict

# Assuming you have a similar base structure as your previous project
from navi_bench.base import BaseMetric, BaseTaskConfig, get_import_path
from navi_bench.dates import initialize_user_metadata

class MultiCandidateQuery(TypedDict, total=False):
    origins: list[str] | None
    destinations: list[str] | None
    depart_dates: list[str] | None
    return_dates: list[str] | None
    airlines: list[str] | None
    
    max_price: float | None
    min_price: float | None
    max_stops: int | None
    cabin_classes: list[str] | None
    
    require_direct: bool | None

class InfoDict(TypedDict, total=False):
    url: str
    source: str
    origin: str
    destination: str
    departDate: str
    returnDate: str
    departTime: str
    arrivalTime: str
    airline: str
    price: float
    stops: int
    duration: str
    cabinClass: str
    pageType: str
    antiBotStatus: str
    
    filterMaxPrice: float
    filterMaxStops: int
    filterAirlines: list[str]

class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int
    queries: list[list[MultiCandidateQuery]]
    is_query_covered: list[bool]

class KayakInfoGathering(BaseMetric):
    def __init__(self, queries: list[list[MultiCandidateQuery]]) -> None:
        super().__init__()
        self.queries = queries
        self._all_infos: list[list[InfoDict]] = []
        self._is_query_covered: list[bool] = [False] * len(queries)
        self._navigation_stack: list[dict] = [] 
        self._tracked_pages: set = set()

    @functools.cached_property
    def js_script(self) -> str:
        with open(Path(__file__).parent / "kayak_info_gathering.js", "r") as f:
            return f.read()

    async def reset(self) -> None:
        self._all_infos = []
        self._is_query_covered = [False] * len(self.queries)
        self._navigation_stack = []
        self._tracked_pages = set()
    
    def attach_to_context(self, context) -> None:
        async def track_page(page) -> None:
            page_id = id(page)
            if page_id in self._tracked_pages: return
            self._tracked_pages.add(page_id)
            
            async def on_frame_navigated(frame):
                if frame != page.main_frame: return
                
                # --- NEW: Using frame.url to instantly block OTAs ---
                if "kayak.co.in" not in frame.url:
                    return
                # ----------------------------------------------------
                
                try:
                    logger.info(f"[NAV] Kayak: {frame.url[:80]}...")
                    await self.update(page=page)
                except Exception:
                    pass
            
            page.on("framenavigated", lambda f: asyncio.create_task(on_frame_navigated(f)))
        
        for page in context.pages:
            asyncio.create_task(track_page(page))
        context.on("page", lambda p: asyncio.create_task(track_page(p)))

    async def update(self, **kwargs) -> None:
        page = kwargs["page"]
        content = await page.content()
        
        if "px-captcha" in content or "challenge-running" in content or "verify you are human" in content.lower():
            logger.error("Agent blocked by Kayak Anti-Bot.")

        all_frame_infos: list[InfoDict] = []
        for frame in page.frames:
            try:
                frame_infos = await asyncio.wait_for(frame.evaluate(self.js_script), timeout=3.0)
                if frame_infos and isinstance(frame_infos, list):
                    all_frame_infos.extend(frame_infos)
            except Exception: pass
        
        # Deduplication
        unique_infos = []
        seen = set()
        for info in all_frame_infos:
            key = f"{info.get('airline')}-{info.get('departTime')}-{info.get('price')}-{info.get('source')}"
            if key not in seen:
                seen.add(key)
                unique_infos.append(info)
        
        infos = unique_infos

        if infos:
            print(f"\n[SCRAPED DATA FROM: {page.url[:60]}...]", flush=True)
            
            # --- NEW: Print the extracted sidebar filters ---
            first_info = infos[0]
            if first_info.get('filterMaxPrice') or first_info.get('filterAirlines') or first_info.get('filterStops'):
                print("-" * 50)
                print(">> ACTIVE GLOBALS FILTERS DETECTED:")
                if max_p := first_info.get('filterMaxPrice'):
                    print(f"   Max Price Slider: ₹{max_p}")
                if airlines := first_info.get('filterAirlines'):
                    print(f"   Airlines Checked: {', '.join(airlines)}")
                if stops := first_info.get('filterStops'):
                    print(f"   Stops Checked:    {', '.join(stops)}")
                print("-" * 50)
            # ------------------------------------------------

            for i, item in enumerate(infos[:10], 1):
                airline = item.get("airline", "Unknown").title()
                price = item.get("price", "N/A")
                stops = "Direct" if item.get("stops") == 0 else f"{item.get('stops')} Stops"
                depart = item.get("departTime", "XX:XX")
                arrive = item.get("arrivalTime", "XX:XX")
                
                print(f"  {i}. {depart}-{arrive} | {airline} | {stops} | ₹{price}", flush=True)

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
        for page_visit in reversed(self._navigation_stack):
            if page_visit["anti_bot"] != "clear":
                continue
                
            if page_visit["page_type"] == "flight_results":
                for i, alternative_conditions in enumerate(self.queries):
                    if self._is_query_covered[i]: continue
                    for info in page_visit["infos"]:
                        if self._check_alternative_conditions(i, alternative_conditions, info):
                            self._is_query_covered[i] = True
                            break
        
        n_queries = len(self.queries)
        n_covered = sum(self._is_query_covered)
        return FinalResult(score=n_covered / max(n_queries, 1), n_queries=n_queries, n_covered=n_covered, queries=self.queries, is_query_covered=self._is_query_covered)

    def _check_alternative_conditions(self, i: int, alternative_conditions: list[MultiCandidateQuery], info: InfoDict) -> bool:
        for alternative_condition in alternative_conditions:
            if self._check_multi_candidate_query(alternative_condition, info):
                return True
        return False

    @classmethod
    def _check_multi_candidate_query(cls, query: MultiCandidateQuery, info: InfoDict) -> bool:
        # 1. Origins
        if q_origins := query.get("origins"):
            info_origin = (info.get("origin") or "").lower()
            if not any(o.lower() == info_origin for o in q_origins): return False

        # 2. Destinations
        if q_destinations := query.get("destinations"):
            info_dest = (info.get("destination") or "").lower()
            if not any(d.lower() == info_dest for d in q_destinations): return False

        # 3. Depart Dates
        if q_depart_dates := query.get("depart_dates"):
            if info.get("departDate") not in q_depart_dates: return False

        # 4. Airlines (Check both the individual flight card AND the active global filters)
        if q_airlines := query.get("airlines"):
            ticket_airline = (info.get("airline") or "").lower()
            info_airlines = info.get("filterAirlines") or []
            
            # Did they find a specific flight card with this airline?
            ticket_matched = any(a.lower() in ticket_airline for a in q_airlines)
            # Or did they successfully apply the global airline filter in the sidebar?
            filter_matched = any(a.lower() in ia.lower() for a in q_airlines for ia in info_airlines)
            
            if not (ticket_matched or filter_matched): 
                return False

        # 5. Max Price (Checks both the flight card price AND the global slider)
        if "max_price" in query and query["max_price"] is not None:
            max_price = query["max_price"]
            eval_max_price = info.get("price") or info.get("filterMaxPrice")
            if eval_max_price is None or eval_max_price > max_price: return False

        # 6. Direct Flights Only
        if query.get("require_direct") is True:
            # We strictly check the scraped flight card here
            if info.get("stops") != 0: return False
            
        # 7. Max Stops
        if "max_stops" in query and query["max_stops"] is not None:
            eval_stops = info.get("stops")
            if eval_stops is None or eval_stops > query["max_stops"]: return False

        return True