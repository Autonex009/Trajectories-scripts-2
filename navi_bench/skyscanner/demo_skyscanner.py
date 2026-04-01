#!/usr/bin/env python
"""
Skyscanner URL Match Verification Demo
======================================

Human-in-the-loop verification system for Skyscanner travel searches.
Covers Flights, Hotels, and Car Hire with real-time URL tracking.

How it works:
  1. Pick a scenario (flight / hotel / car hire search)
  2. The browser opens Skyscanner automatically
  3. Navigate Skyscanner to find the requested travel option
  4. Press ENTER — the system checks your final URL against the ground truth
  5. A detailed pass/fail report is printed

Features:
  - Real-time URL tracking via page.on('framenavigated')
  - Stealth browser config (anti-bot evasion)
  - Supports all Skyscanner URL formats (flights, hotels, car hire)
  - Dynamic date resolution (evergreen — works on any run date)
  - Detailed match diff on failure (origin, dest, dates, cabin, filters)

Author: NaviBench Team
"""

import asyncio
import sys
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

# Dynamically add the project root to sys.path so the module can be run from any directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.skyscanner.skyscanner_url_match import (
    SkyscannerUrlMatch,
    SkyscannerInfoGathering,
    generate_task_config,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BrowserConfig:
    """Browser launch configuration with stealth settings."""
    headless: bool = False
    viewport_width: int = 1366
    viewport_height: int = 768
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    locale: str = "en-GB"
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


# =============================================================================
# DATE HELPERS  (evergreen — resolved at runtime)
# =============================================================================

def _d(offset: int) -> str:
    """Return YYYY-MM-DD for today + offset days."""
    return (date.today() + timedelta(days=offset)).strftime("%Y-%m-%d")


def _yymmdd(offset: int) -> str:
    """Return YYMMDD (Skyscanner flight path format) for today + offset days."""
    return (date.today() + timedelta(days=offset)).strftime("%y%m%d")


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

@dataclass
class DemoScenario:
    """One verification scenario."""
    task_id: str
    name: str
    category: str          # flights | hotels | carhire
    description: str
    task_prompt: str
    gt_url: str = ""       # ground truth URL (may contain formatted dates)
    queries: list = None   # for info gathering scenarios
    start_url: str = "https://www.skyscanner.net/"
    tags: list = field(default_factory=list)
    hint: str = ""


def build_scenarios() -> list[DemoScenario]:
    """Build all demo scenarios with live dates resolved at runtime."""

    # ---------- FLIGHTS ----------
    flights = [
        # F1 — Easy: one-way economy
        DemoScenario(
            task_id="skyscanner/demo/flights/oneway_economy",
            name="[FLIGHT] One-Way Economy — JFK → LAX",
            category="flights",
            description="Basic one-way economy search",
            task_prompt=(
                f"Search for a one-way economy flight from New York (JFK) to Los Angeles (LAX) "
                f"departing on {_d(7)}. 1 adult."
            ),
            gt_url=(
                f"https://www.skyscanner.net/transport/flights/jfk/lax/{_yymmdd(7)}"
                "/?adultsv2=1&cabinclass=economy&rtn=0"
            ),
            tags=["easy", "economy"],
        ),

        # F2 — Medium: round-trip + cabin
        DemoScenario(
            task_id="skyscanner/demo/flights/roundtrip_business",
            name="[FLIGHT] Round-Trip Business — LHR → CDG",
            category="flights",
            description="Round-trip business class, 2 adults",
            task_prompt=(
                f"Search for a round-trip business class flight from London Heathrow (LHR) "
                f"to Paris Charles de Gaulle (CDG). Depart {_d(10)}, return {_d(13)}. 2 adults."
            ),
            gt_url=(
                f"https://www.skyscanner.net/transport/flights/lhr/cdg/{_yymmdd(10)}/{_yymmdd(13)}"
                "/?adultsv2=2&cabinclass=business&rtn=1"
            ),
            tags=["medium", "business", "roundtrip"],
            hint="Both departure and return dates must match exactly.",
        ),

        # F3 — Medium: direct-only filter
        DemoScenario(
            task_id="skyscanner/demo/flights/direct_only",
            name="[FLIGHT] Direct Only — JFK → LAX",
            category="flights",
            description="Non-stop filter applied in URL",
            task_prompt=(
                f"Search for a direct (non-stop) one-way economy flight from JFK to LAX "
                f"on {_d(5)}. 1 adult. Filter to non-stop flights only."
            ),
            gt_url=(
                f"https://www.skyscanner.net/transport/flights/jfk/lax/{_yymmdd(5)}"
                "/?adultsv2=1&cabinclass=economy&rtn=0&stops=!oneStop,!twoPlusStops"
            ),
            tags=["medium", "stops-filter"],
            hint="The stops=!oneStop,!twoPlusStops parameter must appear in the URL.",
        ),

        # F4 — Hard: family + children ages
        DemoScenario(
            task_id="skyscanner/demo/flights/family",
            name="[FLIGHT] Family Flight — LAX → CDG + 2 Children",
            category="flights",
            description="2 adults + 2 children (ages 5 & 8), economy",
            task_prompt=(
                f"Search for a one-way economy flight from Los Angeles (LAX) to Paris (CDG) "
                f"on {_d(20)} for 2 adults and 2 children aged 5 and 8."
            ),
            gt_url=(
                f"https://www.skyscanner.net/transport/flights/lax/cdg/{_yymmdd(20)}"
                "/?adultsv2=2&childrenv2=5|8&cabinclass=economy&rtn=0"
            ),
            tags=["hard", "family", "children"],
            hint="Children ages must be pipe-separated in the URL: childrenv2=5|8",
        ),

        # F5 — Hard: alliance filter
        DemoScenario(
            task_id="skyscanner/demo/flights/star_alliance",
            name="[FLIGHT] Star Alliance — FRA → JFK",
            category="flights",
            description="One-way, economy, Star Alliance filter",
            task_prompt=(
                f"Search for a one-way economy flight from Frankfurt (FRA) to New York (JFK) "
                f"on {_d(20)} for 1 adult. Filter results to Star Alliance airlines only."
            ),
            gt_url=(
                f"https://www.skyscanner.net/transport/flights/fra/jfk/{_yymmdd(20)}"
                "/?adultsv2=1&cabinclass=economy&rtn=0&alliances=Star%20Alliance"
            ),
            tags=["hard", "alliance"],
            hint="Alliance filter: alliances=Star%20Alliance (space URL-encoded).",
        ),

        # F6 — Hard: all filters combined
        DemoScenario(
            task_id="skyscanner/demo/flights/ultimate",
            name="[FLIGHT] Ultra Hard — JFK → LHR, First Class, Direct, Oneworld",
            category="flights",
            description="Round-trip, first class, direct, Oneworld, 2 adults + 1 child (12)",
            task_prompt=(
                f"Search for a direct round-trip first class flight from New York (JFK) to London (LHR), "
                f"departing {_d(12)}, returning {_d(17)}. 2 adults, 1 child aged 12. "
                f"Filter to Oneworld alliance and non-stop flights only."
            ),
            gt_url=(
                f"https://www.skyscanner.net/transport/flights/jfk/lhr/{_yymmdd(12)}/{_yymmdd(17)}"
                "/?adultsv2=2&childrenv2=12&cabinclass=first&rtn=1"
                "&stops=!oneStop,!twoPlusStops&alliances=Oneworld"
            ),
            tags=["hard", "first", "direct", "alliance", "children"],
            hint="All of: direct + first class + child + Oneworld alliance must be applied.",
        ),
    ]

    # ---------- HOTELS ----------
    hotels = [
        # H1 — Easy: basic hotel search
        DemoScenario(
            task_id="skyscanner/demo/hotels/london_basic",
            name="[HOTEL] London — 2 Adults, 1 Room",
            category="hotels",
            description="Basic hotel search in London",
            task_prompt=(
                f"Search for hotels in London (entity_id 27544008), "
                f"checking in {_d(7)} and checking out {_d(12)}. 2 adults, 1 room."
            ),
            gt_url=(
                f"https://www.skyscanner.net/hotels/search"
                f"?entity_id=27544008&checkin={_d(7)}&checkout={_d(12)}&adults=2&rooms=1"
            ),
            tags=["easy"],
        ),

        # H2 — Medium: sort by price
        DemoScenario(
            task_id="skyscanner/demo/hotels/nyc_price_sort",
            name="[HOTEL] NYC — Sort by Lowest Price",
            category="hotels",
            description="Hotel search in New York, sorted by price",
            task_prompt=(
                f"Search for hotels in New York (entity_id 27537542), "
                f"checking in {_d(9)} and checking out {_d(13)}. "
                f"2 adults, 1 room. Sort results by lowest price."
            ),
            gt_url=(
                f"https://www.skyscanner.net/hotels/search"
                f"?entity_id=27537542&checkin={_d(9)}&checkout={_d(13)}&adults=2&rooms=1&sort=price"
            ),
            tags=["medium", "sort"],
            hint="The sort=price parameter must appear in the URL.",
        ),

        # H3 — Medium: sort by rating + 2 rooms
        DemoScenario(
            task_id="skyscanner/demo/hotels/paris_rating",
            name="[HOTEL] Paris — 3 Adults, 2 Rooms, Highest Rating",
            category="hotels",
            description="Hotel search in Paris, 3 adults in 2 rooms, by rating",
            task_prompt=(
                f"Search for hotels in Paris (entity_id 27539733), "
                f"checking in {_d(11)} and checking out {_d(14)}. "
                f"3 adults, 2 rooms. Sort by highest guest rating."
            ),
            gt_url=(
                f"https://www.skyscanner.net/hotels/search"
                f"?entity_id=27539733&checkin={_d(11)}&checkout={_d(14)}"
                "&adults=3&rooms=2&sort=-hotel_rating"
            ),
            tags=["medium", "sort", "multi-room"],
            hint="sort=-hotel_rating (note the minus sign for descending).",
        ),

        # H4 — Hard: children ages
        DemoScenario(
            task_id="skyscanner/demo/hotels/tokyo_family",
            name="[HOTEL] Tokyo — Family with 2 Children (ages 6 & 9)",
            category="hotels",
            description="Hotel search in Tokyo, 2 adults + 2 children",
            task_prompt=(
                f"Search for hotels in Tokyo (entity_id 27540552), "
                f"checking in {_d(40)} and checking out {_d(47)}. "
                f"2 adults, 2 children aged 6 and 9 in 1 room. Sort by highest rating."
            ),
            gt_url=(
                f"https://www.skyscanner.net/hotels/search"
                f"?entity_id=27540552&checkin={_d(40)}&checkout={_d(47)}"
                "&adults=2&children=2&children_ages=6,9&rooms=1&sort=-hotel_rating"
            ),
            tags=["hard", "children", "sort"],
            hint="Hotel children encoding: children=2&children_ages=6,9 (NOT childrenv2).",
        ),

        # H5 — Hard: large group + 3 children
        DemoScenario(
            task_id="skyscanner/demo/hotels/dubai_family_3kids",
            name="[HOTEL] Dubai — 2 Adults + 3 Children, Highest Price",
            category="hotels",
            description="Dubai hotel with 3 children in 2 rooms, luxury sort",
            task_prompt=(
                f"Search for hotels in Dubai (entity_id 27540488), "
                f"checking in {_d(13)} and checking out {_d(19)}. "
                f"2 adults and 3 children (ages 5, 8, 11) in 2 rooms. Sort by highest price."
            ),
            gt_url=(
                f"https://www.skyscanner.net/hotels/search"
                f"?entity_id=27540488&checkin={_d(13)}&checkout={_d(19)}"
                "&adults=2&children=3&children_ages=5,8,11&rooms=2&sort=-price"
            ),
            tags=["hard", "children", "multi-room"],
            hint="children=3&children_ages=5,8,11 AND 2 rooms with sort=-price.",
        ),
    ]

    # ---------- CAR HIRE ----------
    # Browser-verified location IDs:
    # BCN=95565085, JFK=95565058, LHR=95565050, LGW=95565051, CDG=95565060, DXB=95565088
    carhire = [
        # C1 — Easy: same pickup/dropoff
        DemoScenario(
            task_id="skyscanner/demo/carhire/bcn_basic",
            name="[CAR HIRE] Barcelona — 5 Day Rental",
            category="carhire",
            description="Simple same-location car hire in Barcelona",
            task_prompt=(
                f"Search for a car hire in Barcelona, "
                f"picking up on {_d(25)} at 10:00 and dropping off on {_d(30)} at 10:00. "
                f"Driver age 30."
            ),
            gt_url=(
                f"https://www.skyscanner.net/carhire/results/95565085/95565085"
                f"/{_d(25)}T10:00/{_d(30)}T10:00/30"
            ),
            tags=["easy"],
        ),

        # C2 — Medium: different airports (LHR → LGW)
        DemoScenario(
            task_id="skyscanner/demo/carhire/lhr_lgw",
            name="[CAR HIRE] LHR → LGW — Different Pickup/Dropoff",
            category="carhire",
            description="One-way car hire from Heathrow to Gatwick",
            task_prompt=(
                f"Search for a car hire picking up at London Heathrow on {_d(32)} at 08:00 "
                f"and dropping off at London Gatwick on {_d(36)} at 18:00. Driver age 35."
            ),
            gt_url=(
                f"https://www.skyscanner.net/carhire/results/95565050/95565051"
                f"/{_d(32)}T08:00/{_d(36)}T18:00/35"
            ),
            tags=["medium"],
            hint="LHR ID=95565050, LGW ID=95565051 — must be different in the URL.",
        ),

        # C3 — Medium: no driver age
        DemoScenario(
            task_id="skyscanner/demo/carhire/cdg_noage",
            name="[CAR HIRE] Paris CDG — No Driver Age",
            category="carhire",
            description="Car hire without driver age in URL",
            task_prompt=(
                f"Search for a car hire at Paris CDG airport, "
                f"picking up on {_d(26)} at 12:00 and dropping off on {_d(29)} at 12:00. "
                f"No driver age needed."
            ),
            gt_url=(
                f"https://www.skyscanner.net/carhire/results/95565060/95565060"
                f"/{_d(26)}T12:00/{_d(29)}T12:00"
            ),
            tags=["medium"],
            hint="URL should NOT include a driver age segment at the end.",
        ),

        # C4 — Hard: cross-border, different IDs
        DemoScenario(
            task_id="skyscanner/demo/carhire/bcn_cdg",
            name="[CAR HIRE] Barcelona → Paris CDG (Cross-Border)",
            category="carhire",
            description="One-way cross-border car hire",
            task_prompt=(
                f"Search for a one-way car hire picking up in Barcelona on {_d(63)} at 09:00 "
                f"and dropping off at Paris CDG on {_d(72)} at 17:00. Driver age 50."
            ),
            gt_url=(
                f"https://www.skyscanner.net/carhire/results/95565085/95565060"
                f"/{_d(63)}T09:00/{_d(72)}T17:00/50"
            ),
            tags=["hard"],
            hint="BCN ID=95565085, CDG ID=95565060 — must be different location IDs.",
        ),

        # C5 — Hard: precise non-standard times + corrected JFK ID
        DemoScenario(
            task_id="skyscanner/demo/carhire/jfk_night",
            name="[CAR HIRE] JFK — Late Night Pickup (23:30)",
            category="carhire",
            description="Precise non-standard pickup time, young driver",
            task_prompt=(
                f"Search for a car hire at JFK Airport picking up on {_d(197)} at 23:30 "
                f"and dropping off on {_d(202)} at 06:00. Driver age 33."
            ),
            gt_url=(
                f"https://www.skyscanner.net/carhire/results/95565058/95565058"
                f"/{_d(197)}T23:30/{_d(202)}T06:00/33"
            ),
            tags=["hard"],
            hint="JFK ID=95565058. Time must be 23:30 exactly (not rounded to 00:00 or 09:00).",
        ),

        # C6 -- Info Gathering Dom Extraction
        DemoScenario(
            task_id="skyscanner/demo/info/carhire",
            name="[INFO GATHERING] Find SUV in Miami under ₹25k",
            category="carhire",
            description="Agent must find an SUV listing in Miami directly on screen",
            task_prompt=(
                f"Search for a car hire picking up at MIA on {_d(10)}. Find an SUV under ₹25,000. Extract provider and price."
            ),
            gt_url="",
            queries=[[{"car_types": ["SUV"], "max_price": 25000.0, "pickup_dates": [_d(10)]}]],
            tags=["info_gathering"],
            hint="Navigate to Miami car hire, select SUV, verify price on screen then press ENTER.",
        ),
    ]

    return flights + hotels + carhire


# =============================================================================
# BROWSER MANAGER
# =============================================================================

class BrowserManager:
    """Manages browser lifecycle with stealth anti-bot configuration."""

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self.browser = None
        self.context = None
        self.page = None

    async def launch(self, playwright):
        self.browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=self.config.launch_args,
        )
        self.context = await self.browser.new_context(
            viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
            user_agent=self.config.user_agent,
            locale=self.config.locale,
        )
        # Standard anti-bot init script
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
        """)
        self.page = await self.context.new_page()
        return self.browser, self.context, self.page

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


# =============================================================================
# RESULT REPORTER
# =============================================================================

class ResultReporter:
    """Formats and displays verification results."""

    @staticmethod
    def print_header(s: DemoScenario) -> None:
        cat_emoji = {"flights": "✈️", "hotels": "🏨", "carhire": "🚗"}.get(s.category, "🔍")
        print("\n" + "=" * 80)
        print(f"SKYSCANNER VERIFICATION  {cat_emoji}  {s.name}")
        print("=" * 80)
        print(f"Task ID  : {s.task_id}")
        print(f"Tags     : {', '.join(s.tags)}")
        if s.hint:
            print(f"Hint     : {s.hint}")
        print("-" * 80)
        print(f"TASK:\n  {s.task_prompt}")
        print("-" * 80)
        print(f"GT URL:\n  {s.gt_url}")
        print("=" * 80)

    @staticmethod
    def print_instructions() -> None:
        print("\nINSTRUCTIONS:")
        print("  1. Use Skyscanner to complete the task above")
        print("  2. Navigate to the final results page")
        print("  3. Press ENTER here to verify your URL")
        print()

    @staticmethod
    def print_result(score: float, agent_url: str, gt_url: str, details: dict) -> None:
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        status = "✅  PASS" if score >= 1.0 else "❌  FAIL"
        print(f"Status   : {status}")
        print(f"Score    : {score:.0%}")
        print(f"Agent URL: {agent_url[:100]}{'...' if len(agent_url) > 100 else ''}")
        if score < 1.0 and details.get("mismatches"):
            print("\nMismatches:")
            for m in details["mismatches"]:
                print(f"  ✗ {m}")
        print("=" * 80)

    @staticmethod
    def print_summary(results: list[dict]) -> None:
        if not results:
            return
        total = len(results)
        passed = sum(1 for r in results if r["score"] >= 1.0)
        print("\n" + "=" * 80)
        print("SESSION SUMMARY")
        print("=" * 80)
        print(f"  Total : {total}  |  Passed : {passed}  |  Failed : {total - passed}")
        print(f"  Rate  : {passed / total * 100:.1f}%")
        print("-" * 80)
        for r in results:
            icon = "✅" if r["score"] >= 1.0 else "❌"
            print(f"  {icon}  {r['task_id']}")
        print("=" * 80 + "\n")


# =============================================================================
# RUNNER
# =============================================================================

async def run_scenario(scenario: DemoScenario) -> dict:
    """Run one interactive verification scenario."""
    reporter = ResultReporter()
    reporter.print_header(scenario)
    reporter.print_instructions()

    input("Press ENTER to launch browser...")

    visited_urls: list[str] = []

    async with async_playwright() as p:
        mgr = BrowserManager()
        browser, context, page = await mgr.launch(p)

        if scenario.queries is not None:
            # Mount Info Gathering DOM listeners instantly
            verifier = SkyscannerInfoGathering(queries=scenario.queries)
            verifier.attach_to_context(context)
        else:
            verifier = SkyscannerUrlMatch(gt_url=scenario.gt_url)
            await verifier.reset()
        def on_navigate(frame):
            if frame == page.main_frame:
                u = page.url
                if u and u not in visited_urls:
                    visited_urls.append(u)
                    logger.debug(f"Visited: {u}")

        page.on("framenavigated", on_navigate)

        await page.goto(scenario.start_url, timeout=60_000, wait_until="domcontentloaded")

        print("\n🌐 Browser ready — complete the task above, then press ENTER here.")
        await asyncio.to_thread(input, "Press ENTER when done... ")

        # Final URL is the current page URL
        final_url = page.url
        visited_urls.append(final_url)

        await mgr.close()

    if scenario.queries is not None:
        result = await verifier.compute()
        best_score = result.score
        best_details = {"queries": scenario.queries, "is_query_covered": result.is_query_covered}
    else:
        best_score = 0.0
        best_details: dict = {}
        for u in visited_urls:
            try:
                await verifier.reset()
                await verifier.update(url=u, page=page)
                result = await verifier.compute()
                if result.score > best_score:
                    best_score = result.score
                    best_details = verifier._match_details
            except Exception as e:
                logger.debug(f"Error evaluating URL {u}: {e}")

    reporter.print_result(best_score, final_url, scenario.gt_url, best_details)

    return {"task_id": scenario.task_id, "score": best_score}


# =============================================================================
# INTERACTIVE MENU
# =============================================================================

async def run_menu() -> None:
    scenarios = build_scenarios()
    reporter = ResultReporter()

    print("\n" + "=" * 80)
    print("SKYSCANNER VERIFIER DEMO")
    print("=" * 80)
    for i, s in enumerate(scenarios, 1):
        emoji = {"flights": "✈️", "hotels": "🏨", "carhire": "🚗"}.get(s.category, "?")
        print(f"  [{i:2d}] {emoji}  {s.name}")
        print(f"        {s.description}")

    print(f"\n  [A]  Run all {len(scenarios)} scenarios")
    print("  [Q]  Quit\n")

    choice = input(f"Select (1–{len(scenarios)}, A, Q): ").strip().upper()
    results: list[dict] = []

    if choice == "Q":
        print("Goodbye!")
        return

    elif choice == "A":
        for i, s in enumerate(scenarios):
            r = await run_scenario(s)
            results.append(r)
            if i < len(scenarios) - 1:
                if input("\nContinue? (y/n): ").strip().lower() != "y":
                    break

    elif choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        results.append(await run_scenario(scenarios[int(choice) - 1]))

    else:
        print("Invalid choice.")
        return

    reporter.print_summary(results)


# =============================================================================
# MAIN
# =============================================================================

async def main():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>",
        level="INFO",
    )
    try:
        await run_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
