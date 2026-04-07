#!/usr/bin/env python
"""
Booking.com Search Verification

Supports dynamic placeholders and new TaskScenario format.
"""

import asyncio
import sys
import re
from dataclasses import dataclass, field
from typing import List
from datetime import datetime, timedelta

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.booking.booking_url_match import (
    BookingUrlMatch,
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

    # Anti-detection arguments
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


# =============================================================================
# CONFIG
# =============================================================================
@dataclass
class TaskScenario:
    task_id: str
    name: str
    task: str
    url: str
    location: str
    timezone: str
    gt_url: list[str]
    values: dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    def __post_init__(self):
        assert self.task_id
        assert self.gt_url

def print_resolved_task(task_config, resolved_gt_url):
    resolved_placeholders = getattr(task_config.user_metadata, "placeholders", {})

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


SCENARIOS: list[TaskScenario] = [
    #---------------------STAYS TASKSCENARIOS----------------------
    TaskScenario(
        task_id="booking/hotels/paris/5star_price",
        name="Paris 5-Star Hotels with Filters",
        task=(
            "Search for 5-star hotels in Paris from {checkinDate} to {checkoutDate}, "
            "for 2 adults with free cancellation and breakfast included."
        ),
        url="https://www.booking.com",
        location="Paris, France",
        timezone="Europe/Paris",
        gt_url=[
            "https://www.booking.com/searchresults.en-gb.html?"
            "ss=Paris"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=2"
            "&no_rooms=1"
            "&group_children=0"
            "&nflt=mealplan%3D1%3Bclass%3D5%3Bfc%3D2"
        ],
        values={
            "checkinDate": "{now() + timedelta(7)}",
            "checkoutDate": "{now() + timedelta(10)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/barcelona/price_low_to_high",
        name="Barcelona Hotels Sorted by Price (Low to High)",
        task=(
            "Search for hotels in Barcelona from {checkinDate} to {checkoutDate}, "
            "for 2 adults sorted by price (lowest first) with free WiFi."
        ),
        url="https://www.booking.com",
        location="Barcelona, Spain",
        timezone="Europe/Madrid",
        gt_url=[
            "https://www.booking.com/searchresults.en-gb.html?"
            "ss=Barcelona"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=2&no_rooms=1&group_children=0"
            "&nflt=hotelfacility%3D107"
            "&order=price"
        ],
        values={
            "checkinDate": "{now() + timedelta(5)}",
            "checkoutDate": "{now() + timedelta(8)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/newyork/4star_budget",
        name="New York 4-Star Hotels with Budget Filter",
        task=(
            "Search for 4-star hotels in New York from {checkinDate} to {checkoutDate}, "
            "for 2 adults within a budget of $10000 per night."
        ),
        url="https://www.booking.com",
        location="New York, USA",
        timezone="America/New_York",
        gt_url=[
            "https://www.booking.com/searchresults.html?"
            "ss=New+York"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=2&no_rooms=1&group_children=0"
            "&nflt=class%3D4%3Bprice%3DINR-min-10000-1"
        ],
        values={
            "checkinDate": "{now() + timedelta(5)}",
            "checkoutDate": "{now() + timedelta(8)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/amsterdam/review_high",
        name="Amsterdam Hotels Sorted by Review Score",
        task=(
            "Search for hotels in Amsterdam from {checkinDate} to {checkoutDate}, "
            "for 2 adults sorted by highest review score with breakfast included."
        ),
        url="https://www.booking.com",
        location="Amsterdam, Netherlands",
        timezone="Europe/Amsterdam",
        gt_url=[
            "https://www.booking.com/searchresults.en-gb.html?"
            "ss=Amsterdam"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=2&no_rooms=1&group_children=0"
            "&nflt=mealplan%3D1"
            "&order=review_score"
        ],
        values={
            "checkinDate": "{now() + timedelta(6)}",
            "checkoutDate": "{now() + timedelta(9)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/dubai/luxury_pool",
        name="Dubai Luxury Hotels with Pool",
        task=(
            "Search for 5-star hotels in Dubai from {checkinDate} to {checkoutDate}, "
            "for 2 adults with a swimming pool and free WiFi."
        ),
        url="https://www.booking.com",
        location="Dubai, UAE",
        timezone="Asia/Dubai",
        gt_url=[
            "https://www.booking.com/searchresults.en-gb.html?"
            "ss=Dubai"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=2&no_rooms=1&group_children=0"
            "&nflt=class%3D5%3Bhotelfacility%3D433%3Bhotelfacility%3D107"
        ],
        values={
            "checkinDate": "{now() + timedelta(10)}",
            "checkoutDate": "{now() + timedelta(14)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/tokyo/wifi_airport_shuttle",
        name="Tokyo Hotels with Free WiFi and Airport Shuttle",
        task=(
            "Search for hotels in Tokyo from {checkinDate} to {checkoutDate}, "
            "for 1 adult with free WiFi, airport shuttle, and review score above 8."
        ),
        url="https://www.booking.com",
        location="Tokyo, Japan",
        timezone="Asia/Tokyo",
        gt_url=[
            "https://www.booking.com/searchresults.en-gb.html?"
            "ss=Tokyo"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=1&no_rooms=1&group_children=0"
            "&nflt=review_score%3D80%3Bhotelfacility%3D107%3Bhotelfacility%3D14"
        ],
        values={
            "checkinDate": "{now() + timedelta(6)}",
            "checkoutDate": "{now() + timedelta(9)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/singapore/central_location",
        name="Singapore Hotels in City Center",
        task=(
            "Search for hotels in Singapore from {checkinDate} to {checkoutDate}, "
            "for 2 adults located in the city center with free cancellation."
        ),
        url="https://www.booking.com",
        location="Singapore",
        timezone="Asia/Singapore",
        gt_url=[
            "https://www.booking.com/searchresults.en-gb.html?"
            "ss=Singapore"
            "&checkin={checkinDate}&checkout={checkoutDate}"
            "&group_adults=2&no_rooms=1&group_children=0"
            "&nflt=distance%3D1000%3Bfc%3D2"
        ],
        values={
            "checkinDate": "{now() + timedelta(8)}",
            "checkoutDate": "{now() + timedelta(11)}",
        },
    ),
    TaskScenario(
        task_id="booking/hotels/rome/review_breakfast_budget",
        name="Rome Hotels with Breakfast & High Rating",
        task=(
            "Search for a stay in Rome for 2 adults from {checkinDate} to {checkoutDate} "
            "with a review score of 8 or higher and breakfast included under 40000. "
            "Shortlist the most suitable hotel options that meet the criteria and are most "
            "likely to satisfy typical traveler expectations."
        ),
        url="https://www.booking.com",
        location="Italy",
        timezone="Europe/Rome",
        gt_url=[
            "https://www.booking.com/searchresults.html?"
            "ss=Rome&checkin={checkinDate}&checkout={checkoutDate}&"
            "group_adults=2&no_rooms=1&"
            "nflt=review_score%3D80%3Bprice%3DINR-min-40000-1%3Bmealplan%3D1"
        ],
        values={
            "checkinDate": "{now() + timedelta(36)}",
            "checkoutDate": "{now() + timedelta(40)}",
        },
    ),
    #---------------------FLIGHTS TASKSCENARIOS----------------------
    TaskScenario(
        task_id="booking/flights/delhi_to_paris/roundtrip",
        name="Delhi to Paris Round Trip Flights",
        task=(
            "Search for round-trip flights from Delhi to Paris "
            "departing on {departureDate} and returning on {returnDate} "
            "for 1 adult in economy class."
        ),
        url="https://www.booking.com/flights",
        location="Delhi, India",
        timezone="Asia/Kolkata",
        gt_url=[
            "https://www.booking.com/flights/results/?"
            "from=DEL.AIRPORT"
            "&to=PAR.CITY"
            "&type=ROUNDTRIP"
            "&depart={departureDate}"
            "&return={returnDate}"
            "&adults=1"
            "&cabinClass=ECONOMY"
        ],
        values={
            "departureDate": "{now() + timedelta(7)}",
            "returnDate": "{now() + timedelta(14)}",
        },
    ),
    TaskScenario(
        task_id="booking/flights/mumbai_to_paris/oneway_cheap_nonstop",
        name="Mumbai to Paris - One Way Cheapest Non-stop",
        task=(
            "Search for a one-way flight from Mumbai to Paris on {departureDate}, "
            "for 1 adult in economy class, sorted by cheapest and only non-stop flights."
        ),
        url="https://www.booking.com/flights",
        location="Mumbai, India",
        timezone="Asia/Kolkata",
        gt_url=[
            "https://www.booking.com/flights/results/?"
            "from=BOM.AIRPORT&to=PAR.CITY"
            "&type=ONEWAY"
            "&depart={departureDate}"
            "&adults=1"
            "&cabinClass=ECONOMY"
            "&sort=CHEAPEST"
            "&stops=0"
        ],
        values={
            "departureDate": "{now() + timedelta(30)}",
        },
    ),
    TaskScenario(
        task_id="booking/flights/mumbai_to_paris/fastest_nonstop",
        name="Mumbai to Paris - Fastest Non-stop",
        task=(
            "Search for a one-way flight from Mumbai to Paris on {departureDate}, "
            "for 1 adult in economy class, sorted by fastest and only non-stop flights."
        ),
        url="https://www.booking.com/flights",
        location="Mumbai, India",
        timezone="Asia/Kolkata",
        gt_url=[
            "https://www.booking.com/flights/results/?"
            "from=BOM.CITY&to=PAR.CITY"
            "&type=ONEWAY"
            "&depart={departureDate}"
            "&adults=1"
            "&cabinClass=ECONOMY"
            "&sort=FASTEST"
            "&stops=0"
        ],
        values={
            "departureDate": "{now() + timedelta(25)}",
        },
    ),
    TaskScenario(
        task_id="booking/flights/mumbai_to_paris/business_onestop",
        name="Mumbai to Paris - Business Class 1 Stop",
        task=(
            "Search for a one-way flight from Mumbai to Paris on {departureDate}, "
            "for 1 adult in business class with 1 stop."
        ),
        url="https://www.booking.com/flights",
        location="Mumbai, India",
        timezone="Asia/Kolkata",
        gt_url=[
            "https://www.booking.com/flights/results/?"
            "from=BOM.CITY&to=PAR.CITY"
            "&type=ONEWAY"
            "&depart={departureDate}"
            "&adults=1"
            "&cabinClass=BUSINESS"
            "&stops=1"
        ],
        values={
            "departureDate": "{now() + timedelta(22)}",
        },
    ),
    TaskScenario(
        task_id="booking/flights/mumbai_to_paris/business_onestop",
        name="Mumbai to Paris - Business Class 1 Stop",
        task=(
            "Search for a one-way flight from Mumbai to Paris on {departureDate}, "
            "for 1 adult in business class with 1 stop."
        ),
        url="https://www.booking.com/flights",
        location="Mumbai, India",
        timezone="Asia/Kolkata",
        gt_url=[
            "https://www.booking.com/flights/results/?"
            "from=BOM.CITY&to=PAR.CITY"
            "&type=ONEWAY"
            "&depart={departureDate}"
            "&adults=1"
            "&cabinClass=BUSINESS"
            "&stops=1"
        ],
        values={
            "departureDate": "Saturdays in next month",
        },
    ),
    #---------------------CARS TASKSCENARIOS----------------------
    TaskScenario(
        task_id="booking/cars/paris/economy",
        name="Paris Car Rental - Economy",
        task=(
            "Search for an economy car in Paris from {puDate} to {doDate}, "
            "for a driver aged 30. Include automatic transmission and AC if available."
        ),
        url="https://cars.booking.com",
        location="Paris, France",
        timezone="Europe/Paris",
        gt_url=[
            "https://cars.booking.com/search-results?"
            "locationName=Paris&dropLocationName=Paris&driversAge=30&"
            "puDay={puDateDay}&puMonth={puDateMonth}&puYear={puDateYear}&puHour=10&puMinute=0&"
            "doDay={doDateDay}&doMonth={doDateMonth}&doYear={doDateYear}&doHour=10&doMinute=0&"
            "filterCriteria_transmission=AUTOMATIC&filterCriteria_hasAirConditioning=true"
        ],
        values={
            "puDate": "{now() + timedelta(7)}",   
            "doDate": "{now() + timedelta(10)}",  
        },
    ),
    TaskScenario(
        task_id="booking/cars/london/compact",
        name="London Car Rental - Compact",
        task=(
            "Search for a compact car in London from {puDate} to {doDate}, "
            "Include manual transmission and air conditioning"
        ),
        url="https://cars.booking.com",
        location="London, UK",
        timezone="Europe/London",
        gt_url=[
            "https://cars.booking.com/search-results?"
            "locationName=London&dropLocationName=London&"
            "puDay={puDateDay}&puMonth={puDateMonth}&puYear={puDateYear}&puHour=10&puMinute=0&"
            "doDay={doDateDay}&doMonth={doDateMonth}&doYear={doDateYear}&doHour=10&doMinute=0&"
            "filterCriteria_transmission=MANUAL&"
            "filterCriteria_hasAirConditioning=true&"
            "filterCriteria_carCategory=small&"
        ],
        values={
            "puDate": "{now() + timedelta(3)}",
            "doDate": "{now() + timedelta(8)}",
        },
    ),
    TaskScenario(
    task_id="booking/cars/dubai/suv_auto",
        name="Dubai Car Rental - SUV Automatic",
        task=(
            "Search for an SUV in Dubai from {puDate} to {doDate}, "
            "Include automatic transmission and air conditioning"
        ),
        url="https://cars.booking.com",
        location="Dubai, UAE",
        timezone="Asia/Dubai",
        gt_url=[
            "https://cars.booking.com/search-results?"
            "locationName=Dubai&dropLocationName=Dubai&"
            "puDay={puDateDay}&puMonth={puDateMonth}&puYear={puDateYear}&puHour=10&puMinute=0&"
            "doDay={doDateDay}&doMonth={doDateMonth}&doYear={doDateYear}&doHour=10&doMinute=0&"
            "filterCriteria_transmission=AUTOMATIC&"
            "filterCriteria_hasAirConditioning=true&"
            "filterCriteria_carCategory=suvs"
        ],
        values={
            "puDate": "{now() + timedelta(5)}",
            "doDate": "{now() + timedelta(10)}",
        },
    ),
    TaskScenario(
        task_id="booking/cars/newyork/intermediate_manual",
        name="New York Car Rental - Intermediate Manual",
        task=(
            "Search for an intermediate car in New York from {puDate} to {doDate}, "
            "Include automatic transmission and air conditioning"
        ),
        url="https://cars.booking.com",
        location="New York, USA",
        timezone="America/New_York",
        gt_url=[
            "https://cars.booking.com/search-results?"
            "locationName=New York&dropLocationName=New York&"
            "puDay={puDateDay}&puMonth={puDateMonth}&puYear={puDateYear}&puHour=11&puMinute=0&"
            "doDay={doDateDay}&doMonth={doDateMonth}&doYear={doDateYear}&doHour=11&doMinute=0&"
            "filterCriteria_transmission=AUTOMATIC&"
            "filterCriteria_hasAirConditioning=true&"
            "filterCriteria_carCategory=medium&"
        ],
        values={
            "puDate": "{now() + timedelta(6)}",
            "doDate": "{now() + timedelta(11)}",
        },
    ),
    TaskScenario(
        task_id="booking/cars/paris_firstweek_pickup/10",
        name="Paris Electric Car Rental - First Week",
        task=(
            "Search for a fully electric rental car in Paris with pickup during the first week "
            "of the next month and drop-off in the same week at the same location. "
            "5-day rental"
        ),
        url="https://cars.booking.com",
        location="France",
        timezone="Europe/Paris",
        gt_url=[
            "https://cars.booking.com/search-results?"
            "locationName=Paris&dropLocationName=Paris&driversAge=30&"
            "puDay={puDateDay}&puMonth={puDateMonth}&puYear={puDateYear}&"
            "doDay={doDateDay}&doMonth={doDateMonth}&doYear={doDateYear}&"
            "filterCriteria_fuelType=Electric"
        ],
        values={
            "puDate": "the first week of the next month",
            "doDate": "the first week of the next month",
        },
    ),
    TaskScenario(
        task_id="booking/cars/paris_city_short_trip/6",
        name="Paris Car Rental - Top Rated Short Trip",
        task=(
            "Search for a car rental in Paris with pickup on {puDate} and drop-off on {doDate} "
            "at the same city location sorted by highest review score. "
            "Compare top-rated options and highlight those that combine high review scores "
            "with convenient rental conditions."
        ),
        url="https://cars.booking.com",
        location="France",
        timezone="Europe/Paris",
        gt_url=[
            "https://cars.booking.com/search-results?"
            "locationName=Paris&dropLocationName=Paris&driversAge=30&"
            "puDay={puDateDay}&puMonth={puDateMonth}&puYear={puDateYear}&"
            "doDay={doDateDay}&doMonth={doDateMonth}&doYear={doDateYear}&"
            "filterCriteria_sortBy=RATING&filterCriteria_sortAscending=true"
        ],
        values={
            "puDate": "{now() + timedelta(15)}",
            "doDate": "{now() + timedelta(18)}",
        },
    )
]


# =============================================================================
# BROWSER
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
# REPORTER
# =============================================================================

class ResultReporter:
    @staticmethod
    def print_header(scenario: TaskScenario):
        print("\n" + "=" * 60)
        print(f"SCENARIO: {scenario.name}")
        print("=" * 60)

        print(f"Task ID   : {scenario.task_id}")
        print(f"Location  : {scenario.location}")
        print(f"Timezone  : {scenario.timezone}")

        print("\nInstructions:")
        print(f"  {scenario.task}")

        print("=" * 60 + "\n")

    @staticmethod
    def print_result(result, evaluator, final_url: str):
        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)

        status = "✅ PASS" if result.score >= 1.0 else "❌ FAIL"

        print(f"Status : {status}")
        print(f"Score  : {result.score}")

        print("\nFinal URL:")
        print(f"  {final_url}")

        print("\nExpected (GT URL):")
        print(f"  {evaluator._matched_gt_url}")

        if not result.match:
            print("\nMismatches:")
            for m in result.details.get("mismatches", []):
                print(f"  - {m}")

        print("=" * 60 + "\n")


# =============================================================================
# RUNNER
# =============================================================================

async def run_scenario(scenario: TaskScenario) -> dict:
        """Run a single verification scenario."""

        # Generate config
        task_config = generate_task_config(
            task=scenario.task,
            gt_url=scenario.gt_url,
            location=scenario.location,
            timezone=scenario.timezone,
            url=scenario.url,
            values=scenario.values,
        )

        resolved_gt_url = task_config.eval_config["gt_url"]


        print_resolved_task(task_config, resolved_gt_url)

        evaluator = BookingUrlMatch(gt_url=resolved_gt_url)
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

            # Navigation tracking
            async def on_navigation():
                try:
                    current_url = page.url
                    await evaluator.update(url=current_url)

                    if "booking.com" in current_url:
                        display_url = current_url[:100] + "..." if len(current_url) > 100 else current_url
                        print(f"📍 URL: {display_url}")

                except Exception as e:
                    logger.debug(f"Navigation tracking error: {e}")

            page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))

            print("\n🌐 Browser ready — you are now the agent!")
            print("Apply the required filters on Booking.com.\n")

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
    logger.add(sys.stderr, level="INFO")

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i}] {scenario.name}")
    choice = input("\nSelect scenario index: ")
    if choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        await run_scenario(SCENARIOS[int(choice) - 1])


if __name__ == "__main__":
    asyncio.run(main())