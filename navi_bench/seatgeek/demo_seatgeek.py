#!/usr/bin/env python
"""
SeatGeek Event Ticket Verification Demo

Human-in-the-loop verification system for SeatGeek ticket searches.
This demo uses JavaScript scraping to extract event data in real time:
- LD+JSON extraction (event name, date, venue, pricing, inventory)
- DOM scraping (ticket listings, sections, Deal Score, listing tags)
- URL parsing (page type, event ID, filters)

Features:
- Real-time page tracking via attach_to_context()
- Stealth browser configuration (anti-detection)
- Detailed match diff on failure (event name, date, city, price, etc.)
- Multiple search scenarios (sports, concerts, theater, filters)

Author: NaviBench Team
"""

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.seatgeek.seatgeek_info_gathering import (
    SeatGeekInfoGathering,
    MultiCandidateQuery,
    generate_task_config_deterministic,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BrowserConfig:
    """Browser launch configuration for stealth operation."""
    headless: bool = False
    viewport_width: int = 1366
    viewport_height: int = 768
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    locale: str = "en-US"

    # Anti-detection arguments
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


@dataclass
class TaskScenario:
    """Defines a SeatGeek search verification scenario."""
    task_id: str
    name: str
    description: str
    task_prompt: str
    queries: list[list[MultiCandidateQuery]]
    location: str
    timezone: str
    start_url: str = "https://seatgeek.com"
    tags: list = field(default_factory=list)

    def __post_init__(self):
        """Validate scenario configuration."""
        assert self.task_id, "task_id is required"
        assert self.queries, "queries is required"


# =============================================================================
# DATE HELPERS
# =============================================================================

def get_next_weekend_dates() -> list[str]:
    """Get dates for the next weekend (Saturday and Sunday)."""
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    
    saturday = today + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    
    return [
        saturday.strftime("%Y-%m-%d"),
        sunday.strftime("%Y-%m-%d")
    ]


def get_upcoming_weekday(weekday_name: str) -> str:
    """Get date for the next occurrence of a weekday."""
    weekday_map = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }
    
    target_day = weekday_map[weekday_name]
    today = datetime.now()
    days_ahead = (target_day - today.weekday()) % 7
    
    if days_ahead == 0:
        days_ahead = 7
    
    target_date = today + timedelta(days=days_ahead)
    return target_date.strftime("%Y-%m-%d")


def _next_date(days: int) -> str:
    """Get a date N days from now as YYYY-MM-DD."""
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def _weekend_dates() -> list[str]:
    """Get next Saturday + Sunday dates."""
    return get_next_weekend_dates()


def _next_weekday(name: str) -> str:
    """Get next occurrence of a weekday."""
    return get_upcoming_weekday(name)


# =============================================================================
# TASK SCENARIOS
# =============================================================================

def build_scenarios() -> list[TaskScenario]:
    """Build scenarios with live dates (resolved at runtime)."""

    weekend = _weekend_dates()
    next_sat = weekend[0]
    next_fri = _next_weekday("Friday")

    return [
        # 1. NBA: Simple event search
        TaskScenario(
            task_id="seatgeek/demo/nba/basic",
            name="NBA Game – Lakers in Los Angeles",
            description="Find Lakers tickets for the next Saturday",
            task_prompt=(
                f"Search for Los Angeles Lakers tickets in Los Angeles "
                f"for {next_sat}. Navigate to the event page and find "
                f"available tickets."
            ),
            queries=[[{
                "event_names": ["lakers", "los angeles lakers"],
                "dates": [next_sat],
                "cities": ["los angeles", "inglewood"],
            }]],
            location="Los Angeles, CA, United States",
            timezone="America/Los_Angeles",
            tags=["nba", "sports", "basic"],
        ),

        # 2. NFL: Event + Price filter
        TaskScenario(
            task_id="seatgeek/demo/nfl/price",
            name="NFL Game – Cowboys with Max Price $300",
            description="Find Cowboys tickets under $300",
            task_prompt=(
                f"Search for Dallas Cowboys tickets in Dallas for {next_sat}. "
                f"Find tickets priced under $300."
            ),
            queries=[[{
                "event_names": ["cowboys", "dallas cowboys"],
                "dates": [next_sat],
                "cities": ["dallas", "arlington"],
                "max_price": 300.0,
            }]],
            location="Dallas, TX, United States",
            timezone="America/Chicago",
            tags=["nfl", "sports", "price-filter"],
        ),

        # 3. Concert: Event search
        TaskScenario(
            task_id="seatgeek/demo/concert/basic",
            name="Concert – Find a Show in NYC",
            description="Search for concert tickets on a Friday night in NYC",
            task_prompt=(
                f"Search for concert tickets in New York for {next_fri}. "
                f"Navigate to any concert event page."
            ),
            queries=[[{
                "event_categories": ["concerts", "concert"],
                "dates": [next_fri],
                "cities": ["new york", "brooklyn"],
                "require_page_type": ["event_listing"],
            }]],
            location="New York, NY, United States",
            timezone="America/New_York",
            tags=["concerts", "nyc", "basic"],
        ),

        # 4. Theater: Broadway search
        TaskScenario(
            task_id="seatgeek/demo/theater/broadway",
            name="Theater – Broadway Show in NYC",
            description="Find Broadway theater tickets this weekend",
            task_prompt=(
                f"Search for Broadway theater tickets in New York "
                f"for {next_sat}. Navigate to a show event page."
            ),
            queries=[[{
                "event_categories": ["theater", "theatre"],
                "dates": [next_sat],
                "cities": ["new york"],
                "require_page_type": ["event_listing"],
            }]],
            location="New York, NY, United States",
            timezone="America/New_York",
            tags=["theater", "broadway", "nyc"],
        ),

        # 5. Sports: Multiple ticket filter
        TaskScenario(
            task_id="seatgeek/demo/sports/quantity",
            name="NBA – 4+ Tickets Under $200",
            description="Find a group of 4+ basketball tickets under $200 each",
            task_prompt=(
                f"Search for NBA tickets in Los Angeles for {next_sat}. "
                f"Find a listing with at least 4 tickets available, "
                f"each priced under $200."
            ),
            queries=[[{
                "event_names": ["lakers", "clippers"],
                "dates": [next_sat],
                "cities": ["los angeles", "inglewood"],
                "min_tickets": 4,
                "max_price": 200.0,
            }]],
            location="Los Angeles, CA, United States",
            timezone="America/Los_Angeles",
            tags=["nba", "quantity", "price-filter"],
        ),

        # 6. Complex: Multi-filter concert
        TaskScenario(
            task_id="seatgeek/demo/concert/complex",
            name="Concert – Specific Venue + Price + Aisle",
            description="Find concert tickets at a specific venue with aisle seats",
            task_prompt=(
                f"Search for concert tickets at Madison Square Garden in New York "
                f"for {next_fri}. Find tickets under $500 with aisle seats."
            ),
            queries=[[{
                "event_categories": ["concerts", "concert"],
                "dates": [next_fri],
                "cities": ["new york"],
                "venues": ["madison square garden"],
                "max_price": 500.0,
                "aisle_seat": True,
                "require_page_type": ["event_listing"],
            }]],
            location="New York, NY, United States",
            timezone="America/New_York",
            tags=["concerts", "venue", "aisle", "price-filter", "complex"],
        ),
    ]


# =============================================================================
# BROWSER MANAGER
# =============================================================================

class BrowserManager:
    """Manages browser lifecycle with stealth configuration."""

    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self.browser = None
        self.context = None
        self.page = None

    async def launch(self, playwright) -> tuple:
        """Launch browser with stealth configuration."""
        self.browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=self.config.launch_args,
        )

        self.context = await self.browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            user_agent=self.config.user_agent,
            locale=self.config.locale,
        )

        # Anti-detection scripts
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        self.page = await self.context.new_page()
        return self.browser, self.context, self.page

    async def close(self) -> None:
        """Close browser and cleanup."""
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
    def print_header(scenario: TaskScenario) -> None:
        """Print task header."""
        print("\n" + "=" * 80)
        print(f"SEATGEEK TICKET VERIFICATION: {scenario.name}")
        print("=" * 80)
        print(f"Task ID:     {scenario.task_id}")
        print(f"Location:    {scenario.location}")
        print(f"Timezone:    {scenario.timezone}")
        print("-" * 80)
        print(f"TASK: {scenario.task_prompt}")
        print("-" * 80)

        # Show expected query details
        for qi, query_group in enumerate(scenario.queries):
            print(f"\nQuery {qi + 1} (match ANY of {len(query_group)} alternative(s)):")
            for ai, alt in enumerate(query_group):
                print(f"  Alternative {ai + 1}:")
                if names := alt.get("event_names"):
                    print(f"    Event Names:  {', '.join(names)}")
                if cats := alt.get("event_categories"):
                    print(f"    Categories:   {', '.join(cats)}")
                if dates := alt.get("dates"):
                    print(f"    Dates:        {', '.join(dates)}")
                if cities := alt.get("cities"):
                    print(f"    Cities:       {', '.join(cities)}")
                if venues := alt.get("venues"):
                    print(f"    Venues:       {', '.join(venues)}")
                if (mp := alt.get("max_price")) is not None:
                    print(f"    Max Price:    ${mp:.0f}")
                if (mt := alt.get("min_tickets")) is not None:
                    print(f"    Min Tickets:  {mt}")
                if alt.get("aisle_seat"):
                    print(f"    Aisle Seat:   Required")
                if rpt := alt.get("require_page_type"):
                    print(f"    Page Type:    {rpt}")

        print("=" * 80)

    @staticmethod
    def print_instructions() -> None:
        """Print user instructions."""
        print("\n" + "-" * 40)
        print("INSTRUCTIONS:")
        print("-" * 40)
        print("1. Use SeatGeek to find the requested event")
        print("2. Navigate to the specific event page")
        print("3. Apply any required ticket filters")
        print("4. The system tracks all pages automatically")
        print("5. Press ENTER when ready to verify")
        print("-" * 40 + "\n")

    @staticmethod
    def print_result(result, verifier: SeatGeekInfoGathering) -> None:
        """Print verification result with detailed comparison."""
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)

        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "❌ FAIL"

        print(f"Status:  {status}")
        print(f"Score:   {score_pct:.0f}%")
        print(f"Queries: {result.n_covered}/{result.n_queries} covered")
        print("-" * 80)

        if result.score >= 1.0:
            print("All queries matched! The agent found the correct event(s).")
        else:
            # Show per-query breakdown
            for qi, (covered, query_group) in enumerate(
                zip(result.is_query_covered, result.queries)
            ):
                q_status = "✅" if covered else "❌"
                print(f"\n{q_status} Query {qi + 1}:")

                for alt in query_group:
                    if names := alt.get("event_names"):
                        print(f"   Event Names:  {', '.join(names)}")
                    if cats := alt.get("event_categories"):
                        print(f"   Categories:   {', '.join(cats)}")
                    if dates := alt.get("dates"):
                        print(f"   Dates:        {', '.join(dates)}")
                    if cities := alt.get("cities"):
                        print(f"   Cities:       {', '.join(cities)}")
                    if venues := alt.get("venues"):
                        print(f"   Venues:       {', '.join(venues)}")
                    if (mp := alt.get("max_price")) is not None:
                        print(f"   Max Price:    ${mp:.0f}")
                    if (mt := alt.get("min_tickets")) is not None:
                        print(f"   Min Tickets:  {mt}")
                    if alt.get("aisle_seat"):
                        print(f"   Aisle Seat:   Required")

        # Show navigation stack info
        nav_stack = verifier._navigation_stack
        if nav_stack:
            print(f"\n📍 NAVIGATION STACK ({len(nav_stack)} pages visited):")
            for entry in nav_stack:
                pt = entry["page_type"]
                url = entry["url"][:80] + "..." if len(entry["url"]) > 80 else entry["url"]
                n_infos = len(entry["infos"])
                print(f"   [{pt}] ({n_infos} items) {url}")

        # Show scraped event data from last event_listing page
        for entry in reversed(nav_stack):
            if entry["page_type"] == "event_listing" and entry["infos"]:
                info = entry["infos"][0]
                print(f"\n📋 SCRAPED EVENT DATA (from last event page):")
                if name := info.get("eventName"):
                    print(f"   Event Name:   {name}")
                if cat := info.get("eventCategory"):
                    print(f"   Category:     {cat}")
                if date := info.get("date"):
                    print(f"   Date:         {date}")
                if time := info.get("time"):
                    print(f"   Time:         {time}")
                if venue := info.get("venue"):
                    print(f"   Venue:        {venue}")
                if city := info.get("city"):
                    print(f"   City:         {city}")
                if (lp := info.get("lowPrice")) is not None:
                    print(f"   Low Price:    ${lp}")
                if (hp := info.get("highPrice")) is not None:
                    print(f"   High Price:   ${hp}")
                if (ds := info.get("dealScore")) is not None:
                    print(f"   Deal Score:   {ds}/10")
                if sect := info.get("section"):
                    print(f"   Section:      {sect}")
                if row := info.get("row"):
                    print(f"   Row:          {row}")
                if (tc := info.get("ticketCount")) is not None:
                    print(f"   Ticket Count: {tc}")
                if tags := info.get("listingTags"):
                    print(f"   Listing Tags: {', '.join(tags)}")
                if avail := info.get("availabilityStatus"):
                    print(f"   Availability: {avail}")
                break

        print("\n" + "=" * 80)

    @staticmethod
    def print_summary(results: list) -> None:
        """Print summary of all results."""
        if not results:
            return

        print("\n" + "=" * 80)
        print("SESSION SUMMARY")
        print("=" * 80)

        total = len(results)
        passed = sum(1 for r in results if r["score"] >= 1.0)

        print(f"Total Scenarios:  {total}")
        print(f"Passed:           {passed}")
        print(f"Success Rate:     {passed / total * 100:.1f}%")

        print("-" * 80)
        for r in results:
            status = "✅" if r["score"] >= 1.0 else "❌"
            print(f"  {status} {r['task_id']} — {r['covered']}/{r['total']} queries")

        print("=" * 80 + "\n")


# =============================================================================
# RUNNER
# =============================================================================

async def run_scenario(scenario: TaskScenario) -> dict:
    """Run a single verification scenario."""

    # Create evaluator
    evaluator = SeatGeekInfoGathering(queries=scenario.queries)
    reporter = ResultReporter()

    # Display task info
    reporter.print_header(scenario)
    reporter.print_instructions()

    input("Press ENTER to launch browser...")

    async with async_playwright() as p:
        # Launch browser
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)

        # Initialize evaluator and attach auto-tracking
        await evaluator.reset()
        evaluator.attach_to_context(context)

        # Navigate to start URL
        logger.info(f"Opening {scenario.start_url}")
        await page.goto(
            scenario.start_url,
            timeout=60000,
            wait_until="domcontentloaded",
        )

        print("\n🌐 Browser ready — you are now the agent!")
        print("Navigate SeatGeek to find the requested event.\n")
        print("The system automatically tracks every page you visit.")
        print("All SeatGeek pages are scraped for event data in real time.\n")

        # Wait for user completion
        await asyncio.to_thread(
            input,
            "Press ENTER when you've completed the task... ",
        )

        # Final scrape of the current page
        try:
            await evaluator.update(page=page)
        except Exception as e:
            logger.warning(f"Final update failed: {e}")

        # Compute result
        result = await evaluator.compute()

        # Close browser
        await browser_mgr.close()

    # Display results
    reporter.print_result(result, evaluator)

    return {
        "task_id": scenario.task_id,
        "score": result.score,
        "covered": result.n_covered,
        "total": result.n_queries,
    }


# =============================================================================
# MENU
# =============================================================================

async def run_interactive_menu() -> None:
    """Run interactive scenario selection menu."""

    scenarios = build_scenarios()

    print("\n" + "=" * 80)
    print("SEATGEEK TICKET VERIFICATION SYSTEM")
    print("=" * 80)
    print("\nAvailable scenarios:\n")

    for i, scenario in enumerate(scenarios, 1):
        print(f"  [{i}] {scenario.name}")
        print(f"      {scenario.description}")
        print()

    print(f"  [A] Run all scenarios")
    print(f"  [Q] Quit")
    print()

    choice = input(f"Select scenario (1-{len(scenarios)}, A, or Q): ").strip().upper()

    results = []

    if choice == "Q":
        print("Goodbye!")
        return

    elif choice == "A":
        for scenario in scenarios:
            result = await run_scenario(scenario)
            results.append(result)

            if scenario != scenarios[-1]:
                cont = input("\nContinue to next scenario? (y/n): ").strip().lower()
                if cont != "y":
                    break

    elif choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        idx = int(choice) - 1
        result = await run_scenario(scenarios[idx])
        results.append(result)

    else:
        print("Invalid choice. Please try again.")
        return

    # Print summary
    ResultReporter.print_summary(results)


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main entry point."""

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    try:
        await run_interactive_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
