#!/usr/bin/env python
"""
Trip.com Hotel Search Verification Demo

Human-in-the-loop verification system for Trip.com hotel searches.
This demo tracks navigation via URL matching only (no JavaScript scraping).

Features:
- Real-time URL tracking during navigation
- Stealth browser configuration (anti-detection)
- Filter comparison with detailed diff output
- Multiple search scenarios (star rating, amenities, price, sort, etc.)

Author: NaviBench Team
"""

import asyncio
import sys
from dataclasses import dataclass, field
from typing import List

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.trip.trip_url_match import (
    TripUrlMatch,
    generate_task_config,
    CATEGORY_NAMES,
    AMENITY_IDS,
    SORT_IDS,
    PROPERTY_TYPE_TAGS,
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
    """Defines a Trip.com search verification scenario."""
    task_id: str
    name: str
    description: str
    task_prompt: str
    gt_url: str  # Ground truth URL (concrete, no placeholders)
    location: str
    timezone: str
    start_url: str = "https://us.trip.com"
    tags: list = field(default_factory=list)

    def __post_init__(self):
        """Validate scenario configuration."""
        assert self.task_id, "task_id is required"
        assert self.gt_url, "gt_url is required"


# =============================================================================
# TASK SCENARIOS
# =============================================================================

SCENARIOS: list[TaskScenario] = [
    # 1. NYC 5-Star + Pool + Sort by Lowest Price
    TaskScenario(
        task_id="trip/hotels/nyc/5star_pool_sort",
        name="NYC 5-Star Hotels with Pool (Sorted by Price)",
        description="5-star hotels in New York with a pool, sorted by lowest price",
        task_prompt=(
            "Search for 5-star hotels in New York for April 1-5, 2026 "
            "for 2 adults and 1 room. Filter for hotels with a swimming pool "
            "and sort results by lowest price."
        ),
        gt_url=(
            "https://us.trip.com/hotels/list?cityId=633"
            "&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&crn=1"
            "&listFilters=16~5*16*5,3~605*3*605,17~3*17*3"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["5-star", "pool", "sort", "nyc"],
    ),

    # 2. NYC Budget-Friendly: Price + Free Cancellation + Breakfast
    TaskScenario(
        task_id="trip/hotels/nyc/budget_breakfast",
        name="NYC Budget Hotels with Breakfast & Free Cancellation",
        description="Hotels under $150 with breakfast included and free cancellation",
        task_prompt=(
            "Search for hotels in New York for April 1-5, 2026 "
            "for 2 adults and 1 room. Filter for hotels priced under $150/night, "
            "with breakfast included, and free cancellation."
        ),
        gt_url=(
            "https://us.trip.com/hotels/list?cityId=633"
            "&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&crn=1"
            "&listFilters=15~Range*15*0~150,5~1*5*1,23~10*23*10"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["budget", "breakfast", "free-cancel", "nyc"],
    ),

    # 3. NYC 4+5 Star with Gym + Guest Rating 8+
    TaskScenario(
        task_id="trip/hotels/nyc/4_5star_gym_rating",
        name="NYC 4-5 Star Hotels with Gym, 8+ Rating",
        description="4- and 5-star hotels with a gym and at least 8+ guest rating",
        task_prompt=(
            "Search for 4- and 5-star hotels in New York for April 1-5, 2026 "
            "for 2 adults and 1 room. Filter for hotels with a gym "
            "and a guest rating of 8 or above."
        ),
        gt_url=(
            "https://us.trip.com/hotels/list?cityId=633"
            "&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&crn=1"
            "&listFilters=16~4*16*4,16~5*16*5,3~42*3*42,6~9*6*9"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["4-star", "5-star", "gym", "guest-rating", "nyc"],
    ),

    # 4. NYC Family: 2 adults + 1 child, 4+5 Star + Breakfast
    TaskScenario(
        task_id="trip/hotels/nyc/family_4star_breakfast",
        name="NYC Family: 4-5 Star with Breakfast (Child Age 5)",
        description="Family search with 1 child, 4-5 star hotels with breakfast",
        task_prompt=(
            "Search for 4- and 5-star hotels in New York for April 1-5, 2026 "
            "for 2 adults, 1 child (age 5), and 1 room. "
            "Filter for hotels with breakfast included."
        ),
        gt_url=(
            "https://us.trip.com/hotels/list?cityId=633"
            "&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&children=1&ages=5&crn=1"
            "&listFilters=16~4*16*4,16~5*16*5,5~1*5*1"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["family", "child", "4-star", "5-star", "breakfast", "nyc"],
    ),

    # 5. NYC Hotel-Type + WiFi + Price $300-600
    TaskScenario(
        task_id="trip/hotels/nyc/hotel_wifi_price",
        name="NYC Hotels with WiFi ($300-$600)",
        description="Hotel-type properties with WiFi in the $300-600 price range",
        task_prompt=(
            "Search for hotel-type properties in New York for April 1-5, 2026 "
            "for 2 adults and 1 room. Filter for hotels with free WiFi, "
            "priced between $300 and $600 per night."
        ),
        gt_url=(
            "https://us.trip.com/hotels/list?cityId=633"
            "&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&crn=1"
            "&listFilters=75~TAG_495*75*495,3~2*3*2,15~Range*15*300~600"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["hotel-type", "wifi", "price-range", "nyc"],
    ),

    # 6. NYC All-Filters: 5-Star + Pool + Breakfast + Free Cancel + Rating + Sort
    TaskScenario(
        task_id="trip/hotels/nyc/all_filters",
        name="NYC Ultimate: 5-Star + Pool + Breakfast + Cancel + Rating",
        description="Maximum filter complexity: star + amenity + breakfast + cancel + rating + sort",
        task_prompt=(
            "Search for 5-star hotels in New York for April 1-5, 2026 "
            "for 2 adults and 1 room. Apply ALL of these filters: "
            "swimming pool, breakfast included, free cancellation, "
            "guest rating 8+, and sort by lowest price."
        ),
        gt_url=(
            "https://us.trip.com/hotels/list?cityId=633"
            "&cityName=New%20York"
            "&checkin=2026-04-01&checkout=2026-04-05"
            "&adult=2&crn=1"
            "&listFilters=16~5*16*5,3~605*3*605,5~1*5*1,23~10*23*10,6~9*6*9,17~3*17*3"
        ),
        location="New York, NY, United States",
        timezone="America/New_York",
        tags=["5-star", "pool", "breakfast", "cancel", "rating", "sort", "complex"],
    ),
]


# =============================================================================
# FILTER LABEL HELPERS
# =============================================================================

def _humanize_filter(cat_id: str, value: str) -> str:
    """Convert a raw filter category + value into a human-readable label."""
    cat_name = CATEGORY_NAMES.get(cat_id, f"category_{cat_id}")

    if cat_id == "16":  # Star rating
        return f"{value}-star"
    elif cat_id == "3":  # Amenities
        amenity = AMENITY_IDS.get(value, f"amenity_{value}")
        return amenity.replace("_", " ").title()
    elif cat_id == "5":  # Breakfast
        return "Breakfast Included" if value == "1" else f"breakfast={value}"
    elif cat_id == "6":  # Guest rating
        rating_map = {"7": "6+", "8": "7+", "9": "8+", "10": "9+"}
        return f"Rating {rating_map.get(value, value)}+"
    elif cat_id == "15":  # Price range
        return f"${value.replace('~', ' – $')}/night"
    elif cat_id == "17":  # Sort
        sort_name = SORT_IDS.get(value, f"sort_{value}")
        return sort_name.replace("_", " ").title()
    elif cat_id == "23":  # Free cancellation
        return "Free Cancellation"
    elif cat_id == "75":  # Property type
        prop_name = PROPERTY_TYPE_TAGS.get(value, f"type_{value}")
        return prop_name.title()
    elif cat_id == "9":  # Location/area
        return f"Area ID {value[:20]}"
    else:
        return f"{cat_name}={value}"


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
        print(f"TRIP.COM HOTEL SEARCH VERIFICATION: {scenario.name}")
        print("=" * 80)
        print(f"Task ID:     {scenario.task_id}")
        print(f"Location:    {scenario.location}")
        print(f"Timezone:    {scenario.timezone}")
        print("-" * 80)
        print(f"TASK: {scenario.task_prompt}")
        print("-" * 80)
        gt_display = scenario.gt_url[:80] + "..." if len(scenario.gt_url) > 80 else scenario.gt_url
        print(f"Ground Truth URL:")
        print(f"  {gt_display}")
        print("=" * 80)

    @staticmethod
    def print_instructions() -> None:
        """Print user instructions."""
        print("\n" + "-" * 40)
        print("INSTRUCTIONS:")
        print("-" * 40)
        print("1. Use Trip.com to complete the hotel search")
        print("2. Set the correct city, dates, and guests")
        print("3. Apply all the required sidebar filters")
        print("4. The system tracks your URL automatically")
        print("5. Press ENTER when ready to verify")
        print("-" * 40 + "\n")

    @staticmethod
    def print_result(
        result,
        evaluator: TripUrlMatch,
        scenario: TaskScenario,
        final_url: str,
    ) -> None:
        """Print verification result with detailed URL comparison."""
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)

        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "❌ FAIL"

        print(f"Status:  {status}")
        print(f"Score:   {score_pct:.0f}%")
        print("-" * 80)

        if result.score >= 1.0:
            print("Your URL matches the expected hotel search criteria!")
        else:
            # Parse both URLs for comparison
            gt_parsed = evaluator._parse_trip_url(scenario.gt_url)
            agent_parsed = evaluator._parse_trip_url(final_url)

            print("URL COMPARISON:")
            print("-" * 80)

            # ── City ──
            print(f"\n📍 CITY:")
            gt_city = f"{gt_parsed['city_name']} (ID: {gt_parsed['city_id']})"
            agent_city = f"{agent_parsed['city_name']} (ID: {agent_parsed['city_id']})"
            print(f"   Expected: {gt_city}")
            print(f"   Got:      {agent_city}")
            city_ok = gt_parsed["city_id"] == agent_parsed["city_id"]
            print(f"   Status:   {'✓ Match' if city_ok else '✗ Mismatch'}")

            # ── Dates ──
            print(f"\n📅 DATES:")
            print(f"   Expected: {gt_parsed['checkin']} → {gt_parsed['checkout']}")
            print(f"   Got:      {agent_parsed['checkin']} → {agent_parsed['checkout']}")
            date_ok = (
                gt_parsed["checkin"] == agent_parsed["checkin"]
                and gt_parsed["checkout"] == agent_parsed["checkout"]
            )
            print(f"   Status:   {'✓ Match' if date_ok else '✗ Mismatch'}")

            # ── Guests ──
            print(f"\n👥 GUESTS:")
            gt_guests = f"{gt_parsed['adult']} adults"
            if gt_parsed["children"]:
                gt_guests += f", {gt_parsed['children']} children (ages: {','.join(gt_parsed['ages'])})"
            gt_guests += f", {gt_parsed['crn']} room(s)"
            agent_guests = f"{agent_parsed['adult']} adults"
            if agent_parsed["children"]:
                agent_guests += f", {agent_parsed['children']} children (ages: {','.join(agent_parsed['ages'])})"
            agent_guests += f", {agent_parsed['crn']} room(s)"
            print(f"   Expected: {gt_guests}")
            print(f"   Got:      {agent_guests}")
            guest_ok = (
                gt_parsed["adult"] == agent_parsed["adult"]
                and gt_parsed["children"] == agent_parsed["children"]
                and gt_parsed["crn"] == agent_parsed["crn"]
            )
            print(f"   Status:   {'✓ Match' if guest_ok else '✗ Mismatch'}")

            # ── Filters ──
            gt_filters = gt_parsed["filters"]
            agent_filters = agent_parsed["filters"]

            # Build flat filter sets for comparison
            gt_flat = {}
            for cat_id, values in gt_filters.items():
                cat_label = CATEGORY_NAMES.get(cat_id, f"cat_{cat_id}")
                for v in values:
                    gt_flat[f"{cat_label}:{v}"] = (cat_id, v)

            agent_flat = {}
            for cat_id, values in agent_filters.items():
                cat_label = CATEGORY_NAMES.get(cat_id, f"cat_{cat_id}")
                for v in values:
                    agent_flat[f"{cat_label}:{v}"] = (cat_id, v)

            matched = set(gt_flat.keys()) & set(agent_flat.keys())
            missing = set(gt_flat.keys()) - set(agent_flat.keys())
            extra = set(agent_flat.keys()) - set(gt_flat.keys())

            # Also detect category-level mismatches (same category, different value)
            gt_cats = {cat_id: vals for cat_id, vals in gt_filters.items()}
            agent_cats = {cat_id: vals for cat_id, vals in agent_filters.items()}
            wrong_value_cats = set()
            for cat_id in set(gt_cats.keys()) & set(agent_cats.keys()):
                if gt_cats[cat_id] != agent_cats[cat_id]:
                    wrong_value_cats.add(cat_id)

            print(f"\n🔧 FILTERS:")

            if matched:
                print(f"\n   ✓ Correct filters ({len(matched)}):")
                for key in sorted(matched):
                    cat_id, val = gt_flat[key]
                    print(f"     - {_humanize_filter(cat_id, val)}")

            if wrong_value_cats:
                print(f"\n   ✗ Wrong values ({len(wrong_value_cats)}):")
                for cat_id in sorted(wrong_value_cats):
                    cat_name = CATEGORY_NAMES.get(cat_id, f"cat_{cat_id}")
                    gt_vals = {_humanize_filter(cat_id, v) for v in gt_cats[cat_id]}
                    agent_vals = {_humanize_filter(cat_id, v) for v in agent_cats[cat_id]}
                    print(f"     - {cat_name}:")
                    print(f"       Expected: {', '.join(sorted(gt_vals))}")
                    print(f"       Got:      {', '.join(sorted(agent_vals))}")

            missing_cats = set(gt_cats.keys()) - set(agent_cats.keys())
            if missing_cats:
                print(f"\n   ✗ Missing filter categories ({len(missing_cats)}):")
                for cat_id in sorted(missing_cats):
                    cat_name = CATEGORY_NAMES.get(cat_id, f"cat_{cat_id}")
                    vals = [_humanize_filter(cat_id, v) for v in gt_cats[cat_id]]
                    print(f"     - {cat_name}: {', '.join(vals)}")

            extra_cats = set(agent_cats.keys()) - set(gt_cats.keys())
            if extra_cats:
                print(f"\n   ⚠ Extra filter categories ({len(extra_cats)}):")
                for cat_id in sorted(extra_cats):
                    cat_name = CATEGORY_NAMES.get(cat_id, f"cat_{cat_id}")
                    vals = [_humanize_filter(cat_id, v) for v in agent_cats[cat_id]]
                    print(f"     - {cat_name}: {', '.join(vals)}")

        print("\n" + "=" * 80)
        print("URLS:")
        print("-" * 80)
        print(f"Expected: {scenario.gt_url}")
        print(f"Got:      {final_url}")
        print("=" * 80 + "\n")

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
            print(f"  {status} {r['task_id']}")

        print("=" * 80 + "\n")


# =============================================================================
# RUNNER
# =============================================================================

async def run_scenario(scenario: TaskScenario) -> dict:
    """Run a single verification scenario."""

    # Create evaluator and config
    task_config = generate_task_config(
        task=scenario.task_prompt,
        gt_url=[scenario.gt_url],
        location=scenario.location,
        timezone=scenario.timezone,
        url=scenario.start_url,
    )

    evaluator = TripUrlMatch(gt_url=scenario.gt_url)
    reporter = ResultReporter()

    # Display task info
    reporter.print_header(scenario)
    reporter.print_instructions()

    input("Press ENTER to launch browser...")

    async with async_playwright() as p:
        # Launch browser
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)

        # Initialize evaluator
        await evaluator.reset()

        # Navigate to start URL
        logger.info(f"Opening {scenario.start_url}")
        await page.goto(scenario.start_url, timeout=60000, wait_until="domcontentloaded")

        # Track initial URL
        await evaluator.update(url=page.url)

        # Set up real-time URL tracking
        async def on_navigation():
            try:
                current_url = page.url
                await evaluator.update(url=current_url)
                if "trip.com" in current_url:
                    display_url = current_url[:100] + "..." if len(current_url) > 100 else current_url
                    print(f"📍 URL: {display_url}")
            except Exception as e:
                logger.debug(f"Navigation tracking error: {e}")

        page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))

        print("\n🌐 Browser ready — you are now the agent!")
        print("Navigate Trip.com and apply the required filters.\n")

        # Wait for user completion
        await asyncio.to_thread(
            input,
            "Press ENTER when you've completed the task... ",
        )

        # Get final URL
        final_url = page.url

        # Final evaluation
        await evaluator.update(url=final_url)
        result = await evaluator.compute_detailed()

        # Close browser
        await browser_mgr.close()

    # Display results
    reporter.print_result(result, evaluator, scenario, final_url)

    return {
        "task_id": scenario.task_id,
        "score": result.score,
        "final_url": final_url,
    }


# =============================================================================
# MENU
# =============================================================================

async def run_interactive_menu() -> None:
    """Run interactive scenario selection menu."""

    print("\n" + "=" * 80)
    print("TRIP.COM HOTEL SEARCH VERIFICATION SYSTEM")
    print("=" * 80)
    print("\nAvailable scenarios:\n")

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"  [{i}] {scenario.name}")
        print(f"      {scenario.description}")
        print()

    print(f"  [A] Run all scenarios")
    print(f"  [Q] Quit")
    print()

    choice = input(f"Select scenario (1-{len(SCENARIOS)}, A, or Q): ").strip().upper()

    results = []

    if choice == "Q":
        print("Goodbye!")
        return

    elif choice == "A":
        for scenario in SCENARIOS:
            result = await run_scenario(scenario)
            results.append(result)

            if scenario != SCENARIOS[-1]:
                cont = input("\nContinue to next scenario? (y/n): ").strip().lower()
                if cont != "y":
                    break

    elif choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        idx = int(choice) - 1
        result = await run_scenario(SCENARIOS[idx])
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
