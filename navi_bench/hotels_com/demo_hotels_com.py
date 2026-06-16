#!/usr/bin/env python
"""Hotels.com Demo Verifier — Hotel Search + Car Rental.

Demonstrates end-to-end URL verification for Hotels.com tasks.
Uses generate_task_config / generate_car_task_config to properly
resolve date placeholders before verification.
"""

import asyncio
import sys
from dataclasses import dataclass, field

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.hotels_com.hotels_com_url_match import (
    HotelsComCarUrlMatch,
    HotelsComUrlMatch,
    generate_car_task_config,
    generate_task_config,
)


# =============================================================================
# BROWSER CONFIGURATION
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
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


# =============================================================================
# TASK SCENARIO
# =============================================================================

@dataclass
class TaskScenario:
    """A single verification scenario."""
    task_id: str
    name: str
    task: str
    url: str
    location: str
    timezone: str
    gt_url: list[str]
    l2_category: str = "hotel_search"  # "hotel_search" or "car_rental"
    values: dict[str, str] = field(default_factory=dict)


def print_resolved_task(task_config, resolved_gt_url):
    """Print the resolved task config with placeholder values."""
    resolved_placeholders = getattr(
        task_config.user_metadata,
        "placeholders",
        {},
    )

    print("\n" + "=" * 60)
    print("RESOLVED TASK CONFIG")
    print("=" * 60)

    print("\nTask:")
    print(f"  {task_config.task}")

    print("\nPlaceholders:")
    if not resolved_placeholders:
        print("  None")
    else:
        for key, (desc, dates) in resolved_placeholders.items():
            print(f"  {key}: {dates}")

    print("\nResolved GT URLs:")
    for url in resolved_gt_url:
        print(f"  {url}")

    print("=" * 60 + "\n")


# =============================================================================
# DEMO SCENARIOS — HOTEL SEARCH
# =============================================================================

HOTEL_SCENARIOS: list[TaskScenario] = [
    TaskScenario(
        task_id="hotels_com/search/ny_cheap",
        name="New York Hotels — Lowest Price",
        task=(
            "Search for hotels in New York for 2 adults, checking in on "
            "{checkinDate} and checking out on {checkoutDate}. "
            "Sort by lowest price. 1 room."
        ),
        url="https://www.hotels.com/",
        location="United States",
        timezone="America/New_York",
        gt_url=[
            "https://www.hotels.com/Hotel-Search?destination=New%20York"
            "&startDate={checkinDate}&endDate={checkoutDate}"
            "&adults=2&rooms=1"
            "&sort=PRICE_LOW_TO_HIGH"
        ],
        values={
            "checkinDate": "{now() + timedelta(14)}",
            "checkoutDate": "{now() + timedelta(18)}",
        },
    ),
    TaskScenario(
        task_id="hotels_com/search/miami_5star_pool",
        name="Miami 5-Star with Pool",
        task=(
            "Find 5-star hotels in Miami with a pool on Hotels.com. "
            "2 adults, 1 room. Check-in {checkinDate}, check-out {checkoutDate}."
        ),
        url="https://www.hotels.com/",
        location="United States",
        timezone="America/New_York",
        gt_url=[
            "https://www.hotels.com/Hotel-Search?destination=Miami"
            "&startDate={checkinDate}&endDate={checkoutDate}"
            "&adults=2&rooms=1"
            "&star=5"
            "&amenities=POOL"
        ],
        values={
            "checkinDate": "{now() + timedelta(10)}",
            "checkoutDate": "{now() + timedelta(14)}",
        },
    ),
    TaskScenario(
        task_id="hotels_com/search/london_refundable_pets_wifi",
        name="London — Refundable, Pet-Friendly, WiFi",
        task=(
            "Search for hotels in London with fully refundable property options "
            "and should be pet friendly and have wifi included. "
            "2 adults, 1 room. {checkinDate} to {checkoutDate}. "
            "I want the flexibility to cancel if plans change."
        ),
        url="https://www.hotels.com/",
        location="United Kingdom",
        timezone="Europe/London",
        gt_url=[
            "https://www.hotels.com/Hotel-Search?"
            "destination=London%2C%20England%2C%20United%20Kingdom"
            "&startDate={checkinDate}&endDate={checkoutDate}"
            "&adults=2&rooms=1"
            "&paymentType=FREE_CANCELLATION"
            "&amenities=PETS&amenities=WIFI"
        ],
        values={
            "checkinDate": "{now() + timedelta(7)}",
            "checkoutDate": "{now() + timedelta(9)}",
        },
    ),
    TaskScenario(
        task_id="hotels_com/search/chicago_family",
        name="Chicago Family Trip (2 Adults, 2 Kids)",
        task=(
            "Search for a hotel in Chicago for 2 adults and 2 children "
            "(ages 5 and 10) on Hotels.com. "
            "Check-in {checkinDate}, check-out {checkoutDate}. 1 room."
        ),
        url="https://www.hotels.com/",
        location="United States",
        timezone="America/Chicago",
        gt_url=[
            "https://www.hotels.com/Hotel-Search?destination=Chicago"
            "&startDate={checkinDate}&endDate={checkoutDate}"
            "&adults=2&rooms=1&children=1_5,1_10"
        ],
        values={
            "checkinDate": "{now() + timedelta(21)}",
            "checkoutDate": "{now() + timedelta(25)}",
        },
    ),
]


# =============================================================================
# DEMO SCENARIOS — CAR RENTAL
# =============================================================================

CAR_SCENARIOS: list[TaskScenario] = [
    TaskScenario(
        task_id="hotels_com/car/jfk_basic",
        name="Car Rental — JFK Airport",
        l2_category="car_rental",
        task=(
            "Rent a car at JFK airport in New York. "
            "Pick-up on {pickupDate} and drop-off on {dropoffDate}. "
            "Both pick-up and drop-off at 10:30 AM."
        ),
        url="https://www.hotels.com/carsearch",
        location="United States",
        timezone="America/New_York",
        gt_url=[
            "https://www.hotels.com/carsearch?"
            "locn=New%20York&pickupIATACode=JFK"
            "&d1={pickupDate}&d2={dropoffDate}"
            "&time1=1030AM&time2=1030AM"
        ],
        values={
            "pickupDate": "{now() + timedelta(14)}",
            "dropoffDate": "{now() + timedelta(18)}",
        },
    ),
    TaskScenario(
        task_id="hotels_com/car/mia_diff_times",
        name="Car Rental — Miami Different Times",
        l2_category="car_rental",
        task=(
            "I need a car at Miami International Airport. "
            "Pick-up {pickupDate} at 7:00 AM, "
            "drop-off {dropoffDate} at 5:00 PM."
        ),
        url="https://www.hotels.com/carsearch",
        location="United States",
        timezone="America/New_York",
        gt_url=[
            "https://www.hotels.com/carsearch?"
            "locn=Miami&pickupIATACode=MIA"
            "&d1={pickupDate}&d2={dropoffDate}"
            "&time1=0700AM&time2=0500PM"
        ],
        values={
            "pickupDate": "{now() + timedelta(10)}",
            "dropoffDate": "{now() + timedelta(15)}",
        },
    ),
    TaskScenario(
        task_id="hotels_com/car/dfw_to_iah_oneway",
        name="Car Rental — DFW to IAH One-Way",
        l2_category="car_rental",
        task=(
            "One-way car rental. Pick up at Dallas Fort Worth (DFW) "
            "on {pickupDate} at 10:30 AM. Drop off at Houston George Bush "
            "Intercontinental (IAH) on {dropoffDate} at 10:30 AM."
        ),
        url="https://www.hotels.com/carsearch",
        location="United States",
        timezone="America/Chicago",
        gt_url=[
            "https://www.hotels.com/carsearch?"
            "locn=Dallas&pickupIATACode=DFW"
            "&loc2=Houston&dropoffIATACode=IAH"
            "&d1={pickupDate}&d2={dropoffDate}"
            "&time1=1030AM&time2=1030AM"
        ],
        values={
            "pickupDate": "{now() + timedelta(7)}",
            "dropoffDate": "{now() + timedelta(10)}",
        },
    ),
    TaskScenario(
        task_id="hotels_com/car/lga_unreliable",
        name="Car Rental — Airport Change (Unreliable Narrator)",
        l2_category="car_rental",
        task=(
            "I want to rent a car at JFK -- no wait, I'm flying into "
            "Newark (EWR). Actually, we're landing at LaGuardia (LGA) "
            "because the JFK flight was cancelled. FINAL: Pick up at "
            "LaGuardia (LGA) on {pickupDate} at 10:30 AM, "
            "return {dropoffDate} at 10:30 AM."
        ),
        url="https://www.hotels.com/carsearch",
        location="United States",
        timezone="America/New_York",
        gt_url=[
            "https://www.hotels.com/carsearch?"
            "locn=New%20York&pickupIATACode=LGA"
            "&d1={pickupDate}&d2={dropoffDate}"
            "&time1=1030AM&time2=1030AM"
        ],
        values={
            "pickupDate": "{now() + timedelta(5)}",
            "dropoffDate": "{now() + timedelta(9)}",
        },
    ),
]

# Combine all scenarios
SCENARIOS: list[TaskScenario] = HOTEL_SCENARIOS + CAR_SCENARIOS


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
    @staticmethod
    def print_header(scenario: TaskScenario):
        print("\n" + "=" * 60)
        print(f"SCENARIO: {scenario.name}")
        print("=" * 60)

        print(f"Task ID   : {scenario.task_id}")
        print(f"Category  : {scenario.l2_category}")
        print(f"Location  : {scenario.location}")
        print(f"Timezone  : {scenario.timezone}")

        print("\nInstructions:")
        print(f"  {scenario.task}")

        print("=" * 60 + "\n")

    @staticmethod
    def print_result(result, evaluator, final_url: str):
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)

        status = "✅ PASS" if result.score >= 1.0 else "❌ FAIL"

        print(f"Status:           {status}")
        print(f"Score:            {result.score * 100:.1f}%")

        print(f"\nAgent URL:")
        print(f"  {final_url}")

        print(f"\nExpected (GT URL):")
        print(f"  {evaluator._matched_gt_url or evaluator._gt_urls}")

        if not result.match:
            mismatches = result.details.get("mismatches", [])
            if mismatches:
                print(f"\nMismatches:")
                for m in mismatches:
                    print(f"  - {m}")

        print("-" * 80)


# =============================================================================
# SCENARIO RUNNER
# =============================================================================

async def run_scenario(scenario: TaskScenario) -> dict:
    """Run a single verification scenario with proper placeholder resolution."""

    # --- Resolve placeholders via generate_task_config / generate_car_task_config ---
    if scenario.l2_category == "car_rental":
        task_config = generate_car_task_config(
            task=scenario.task,
            gt_url=scenario.gt_url,
            location=scenario.location,
            timezone=scenario.timezone,
            url=scenario.url,
            values=scenario.values,
        )
    else:
        task_config = generate_task_config(
            task=scenario.task,
            gt_url=scenario.gt_url,
            location=scenario.location,
            timezone=scenario.timezone,
            url=scenario.url,
            values=scenario.values,
        )

    resolved_gt_url = task_config.eval_config["gt_url"]

    # Show the resolved config (dates resolved, not raw placeholders)
    print_resolved_task(task_config, resolved_gt_url)

    # --- Create evaluator with RESOLVED GT URLs ---
    if scenario.l2_category == "car_rental":
        evaluator = HotelsComCarUrlMatch(gt_url=resolved_gt_url)
    else:
        evaluator = HotelsComUrlMatch(gt_url=resolved_gt_url)

    reporter = ResultReporter()
    reporter.print_header(scenario)

    input("Press ENTER to launch browser...")

    async with async_playwright() as p:
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)

        await evaluator.reset()

        logger.info(f"Opening {scenario.url}")
        await page.goto(scenario.url, timeout=60000, wait_until="domcontentloaded")

        await evaluator.update(url=page.url)

        # Track navigation — update evaluator on every page change
        async def on_navigation():
            try:
                current_url = page.url
                await evaluator.update(url=current_url)

                if "hotels.com" in current_url:
                    display_url = (
                        current_url[:100] + "..."
                        if len(current_url) > 100
                        else current_url
                    )
                    print(f"📍 URL: {display_url}")

            except Exception as e:
                logger.debug(f"Navigation tracking error: {e}")

        page.on(
            "framenavigated",
            lambda frame: asyncio.create_task(on_navigation()),
        )

        print("\n🌐 Browser ready — you are now the agent!")
        print("Apply the required filters on Hotels.com.\n")

        await asyncio.to_thread(
            input,
            "Press ENTER when you've completed the task... ",
        )

        final_url = page.url

        await evaluator.update(url=final_url)
        result = await evaluator.compute_detailed()

        await browser_mgr.close()

    reporter.print_result(result, evaluator, final_url)

    return {
        "task_id": scenario.task_id,
        "score": result.score,
        "final_url": final_url,
    }


# =============================================================================
# MAIN
# =============================================================================

async def main():
    logger.remove()
    logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")

    print("\n" + "=" * 60)
    print("  Hotels.com US — Demo Verifier")
    print("  Verify URL-based navigation tasks")
    print("  Categories: Hotel Search + Car Rental")
    print("=" * 60 + "\n")

    print("--- Hotel Search ---")
    for i, s in enumerate(HOTEL_SCENARIOS, 1):
        print(f"  [{i}] {s.name}")
        print(f"      {s.task[:80]}...\n")

    offset = len(HOTEL_SCENARIOS)
    print("--- Car Rental ---")
    for i, s in enumerate(CAR_SCENARIOS, offset + 1):
        print(f"  [{i}] {s.name}")
        print(f"      {s.task[:80]}...\n")

    choice = input("Select scenario index: ")
    if choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        await run_scenario(SCENARIOS[int(choice) - 1])
    else:
        print("Invalid selection.")


if __name__ == "__main__":
    asyncio.run(main())
