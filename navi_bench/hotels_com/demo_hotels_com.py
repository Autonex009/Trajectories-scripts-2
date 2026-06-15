#!/usr/bin/env python
import asyncio
import sys
from dataclasses import dataclass, field
from playwright.async_api import async_playwright
from loguru import logger

# Import the Hotels.com evaluators
from hotels_com_url_match import HotelsComUrlMatch, HotelsComCarUrlMatch

@dataclass
class BrowserConfig:
    headless: bool = False
    viewport_width: int = 1366
    viewport_height: int = 768
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    locale: str = "en-US"
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])

@dataclass
class TaskScenario:
    task_id: str
    name: str
    description: str
    url: str
    task_prompt: str
    gt_url: list  # Ground truth URL(s)
    location: str = "United States"
    timezone: str = "America/New_York"

# Demo Scenarios for Hotels.com US — Hotel Search
HOTEL_SCENARIOS: list[TaskScenario] = [
    TaskScenario(
        task_id="hotels_com/search/ny_cheap",
        name="New York Hotels — Lowest Price",
        description="Search for New York hotels and sort by lowest price.",
        url="https://www.hotels.com/",
        task_prompt=(
            "Search for hotels in New York on Hotels.com and sort by lowest price."
        ),
        gt_url=[
            "https://www.hotels.com/Hotel-Search?destination=New%20York&sort=PRICE_LOW_TO_HIGH"
        ],
    ),
    TaskScenario(
        task_id="hotels_com/search/miami_5star_pool",
        name="Miami 5-Star with Pool",
        description="Search for 5-star hotels in Miami with a pool.",
        url="https://www.hotels.com/",
        task_prompt=(
            "Find 5-star hotels in Miami with a pool on Hotels.com."
        ),
        gt_url=[
            "https://www.hotels.com/Hotel-Search?destination=Miami&f-star-rating=5&f-amenities=POOL"
        ],
    ),
    TaskScenario(
        task_id="hotels_com/search/chicago_family",
        name="Chicago Family Trip (2 Adults, 2 Kids)",
        description="Search for a room in Chicago for 2 adults and 2 kids (ages 5 and 10).",
        url="https://www.hotels.com/",
        task_prompt=(
            "Search for a hotel in Chicago for 2 adults and 2 children (ages 5 and 10) on Hotels.com."
        ),
        gt_url=[
            "https://www.hotels.com/Hotel-Search?destination=Chicago&adults=2&rooms=1&children=1_5,1_10"
        ],
    ),
]

# Demo Scenarios for Hotels.com US — Car Rental
CAR_SCENARIOS: list[TaskScenario] = [
    TaskScenario(
        task_id="hotels_com/car/jfk_basic",
        name="Car Rental — JFK Airport",
        description="Rent a car at JFK airport in New York with standard times.",
        url="https://www.hotels.com/carsearch",
        task_prompt=(
            "Rent a car at JFK airport in New York. "
            "Pick-up on July 10, 2026 and drop-off on July 14, 2026. "
            "Both pick-up and drop-off at 10:30 AM."
        ),
        gt_url=[
            "https://www.hotels.com/carsearch?locn=New%20York&pickupIATACode=JFK&d1=2026-7-10&d2=2026-7-14&time1=1030AM&time2=1030AM"
        ],
    ),
    TaskScenario(
        task_id="hotels_com/car/mia_diff_times",
        name="Car Rental — Miami Different Times",
        description="Rent a car at MIA with different pick-up and drop-off times.",
        url="https://www.hotels.com/carsearch",
        task_prompt=(
            "I need a car at Miami International Airport. "
            "Pick-up July 15, 2026 at 7:00 AM, "
            "drop-off July 19, 2026 at 5:00 PM."
        ),
        gt_url=[
            "https://www.hotels.com/carsearch?locn=Miami&pickupIATACode=MIA&d1=2026-7-15&d2=2026-7-19&time1=0700AM&time2=0500PM"
        ],
    ),
    TaskScenario(
        task_id="hotels_com/car/dfw_to_iah_oneway",
        name="Car Rental — DFW to IAH One-Way",
        description="One-way car rental from Dallas (DFW) to Houston (IAH).",
        url="https://www.hotels.com/carsearch",
        task_prompt=(
            "One-way car rental. Pick up at Dallas Fort Worth (DFW) "
            "on July 12, 2026 at 10:30 AM. Drop off at Houston George Bush "
            "Intercontinental (IAH) on July 14, 2026 at 10:30 AM."
        ),
        gt_url=[
            "https://www.hotels.com/carsearch?locn=Dallas&pickupIATACode=DFW&loc2=Houston&dropoffIATACode=IAH&d1=2026-7-12&d2=2026-7-14&time1=1030AM&time2=1030AM"
        ],
    ),
    TaskScenario(
        task_id="hotels_com/car/lga_unreliable",
        name="Car Rental — Airport Change (Unreliable Narrator)",
        description="Airport changes from JFK to EWR to LGA. Must pick FINAL.",
        url="https://www.hotels.com/carsearch",
        task_prompt=(
            "I want to rent a car at JFK -- no wait, I'm flying into "
            "Newark (EWR). Actually, we're landing at LaGuardia (LGA) "
            "because the JFK flight was cancelled. FINAL: Pick up at "
            "LaGuardia (LGA) on July 14, 2026 at 10:30 AM, "
            "return July 18, 2026 at 10:30 AM."
        ),
        gt_url=[
            "https://www.hotels.com/carsearch?locn=New%20York&pickupIATACode=LGA&d1=2026-7-14&d2=2026-7-18&time1=1030AM&time2=1030AM"
        ],
    ),
]

# Combine all scenarios
SCENARIOS: list[TaskScenario] = HOTEL_SCENARIOS + CAR_SCENARIOS

class ResultReporter:
    @staticmethod
    def print_result(result, evaluator, scenario) -> None:
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        
        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "❌ FAIL"
        
        print(f"Status:           {status}")
        print(f"Score:            {score_pct:.1f}%")
        print(f"Task:             {scenario.task_prompt}")
        print(f"Expected URL(s):  {scenario.gt_url}")
        print(f"Agent URL:        {evaluator._agent_url or '(none captured)'}")
        
        if hasattr(evaluator, '_match_details') and evaluator._match_details:
            mismatches = evaluator._match_details.get("mismatches", [])
            if mismatches:
                print(f"Mismatches:       {mismatches}")
        print("-" * 80)

async def run_scenario(scenario: TaskScenario) -> dict:
    # Determine evaluator type based on task_id
    if "car" in scenario.task_id or "car_rental" in scenario.task_id:
        evaluator = HotelsComCarUrlMatch(gt_url=scenario.gt_url)
    else:
        evaluator = HotelsComUrlMatch(gt_url=scenario.gt_url)
    reporter = ResultReporter()
    
    print(f"\n{'='*60}\nTASK: {scenario.task_prompt}\n{'='*60}")
    print(f"Expected URL(s):")
    for u in scenario.gt_url:
        print(f"  → {u}")
    input("Press ENTER to launch browser...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale="en-US", timezone_id=scenario.timezone)
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        await page.goto(scenario.url, timeout=60000, wait_until="domcontentloaded")
            
        await asyncio.to_thread(input, "\nNavigate and press ENTER when you've completed the task... ")
        
        try:
            active_page = context.pages[-1]
            final_url = active_page.url
            print(f"\n[SYSTEM] Verifying final URL: {final_url[:100]}...")
            
            await evaluator.update(url=final_url)
        except Exception as e:
            print(f"\n[ERROR] Failed to capture URL: {e}")
            
        result = await evaluator.compute()
        
        detailed = await evaluator.compute_detailed()
        
        await context.close()
        await browser.close()
    
    reporter.print_result(detailed, evaluator, scenario)
    return result

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
        print(f"      {s.description}\n")
    
    offset = len(HOTEL_SCENARIOS)
    print("--- Car Rental ---")
    for i, s in enumerate(CAR_SCENARIOS, offset + 1):
        print(f"  [{i}] {s.name}")
        print(f"      {s.description}\n")
    
    choice = input("Select scenario index: ")
    if choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        await run_scenario(SCENARIOS[int(choice) - 1])
    else:
        print("Invalid selection.")

if __name__ == "__main__":
    asyncio.run(main())
