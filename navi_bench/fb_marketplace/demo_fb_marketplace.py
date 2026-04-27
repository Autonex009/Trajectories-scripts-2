#!/usr/bin/env python
"""
Facebook Marketplace URL Match Verification Demo
=================================================

Human-in-the-loop verification system for Facebook Marketplace searches.
Covers General Goods, Vehicles, Property Rentals, Price Math, and Red Herrings.

How it works:
  1. Pick a scenario (general search / vehicle / property / price-math / red-herring)
  2. The browser opens Facebook Marketplace automatically
  3. Navigate Marketplace to find the requested items using filters
  4. Press ENTER — the system checks your final URL against the ground truth
  5. A detailed pass/fail report is printed

Features:
  - Real-time URL tracking via page.on('framenavigated')
  - Stealth browser config (anti-bot evasion)
  - Supports all Marketplace URL formats (search, category, listing)
  - Detailed match diff on failure (query, price, condition, sort, city, etc.)

Author: NaviBench Team
"""

import asyncio
import sys
import os
from dataclasses import dataclass, field

# Dynamically add the project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.fb_marketplace.fb_marketplace_url_match import (
    FbMarketplaceUrlMatch,
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
    locale: str = "en-US"
    launch_args: list = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

@dataclass
class DemoScenario:
    """One verification scenario."""
    task_id: str
    name: str
    category: str          # general | vehicles | property | price_math | red_herring | ultra_hard
    description: str
    task_prompt: str
    gt_url: list           # ground truth URL(s)
    start_url: str = "https://www.facebook.com/marketplace/"
    tags: list = field(default_factory=list)
    hint: str = ""


def build_scenarios() -> list[DemoScenario]:
    """Build all demo scenarios."""

    # ---------- GENERAL GOODS ----------
    general = [
        # G1 — Multi-filter: price + sort + condition
        DemoScenario(
            task_id="fb_marketplace/demo/general/desk",
            name="[GENERAL] Mid-Century Desk — SF, $75–$250, Good, Cheapest",
            category="general",
            description="Price range + sort + condition + city",
            task_prompt=(
                "I'm redecorating my San Francisco apartment and need a mid-century modern desk. "
                "Budget is between $75 and $250. Show me what's available, sorted by lowest price "
                "first. Only interested in items in good condition or better."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/sanfrancisco/search/"
                "?query=mid+century+modern+desk&minPrice=75&maxPrice=250"
                "&sortBy=price_ascend&itemCondition=used_good"
            ],
            tags=["general", "price_range", "sort", "condition"],
            hint="4 filters: query + price range + sort + condition. City slug in path.",
        ),

        # G2 — Sort + delivery + price + days
        DemoScenario(
            task_id="fb_marketplace/demo/general/sofa",
            name="[GENERAL] Sectional Sofa — NYC, <$800, Newest, Pickup",
            category="general",
            description="Sort by newest + delivery + max price + city",
            task_prompt=(
                "My roommate just moved out and took the couch — I need a replacement ASAP. "
                "Looking for a sectional sofa in New York, must be under $800. I want to see the "
                "newest listings first so I don't miss anything. Local pickup only."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/newyork/search/"
                "?query=sectional+sofa&maxPrice=800"
                "&sortBy=creation_time_descend&deliveryMethod=local_pick_up"
            ],
            tags=["general", "sort", "delivery", "price"],
            hint="sortBy=creation_time_descend + deliveryMethod=local_pick_up.",
        ),

        # G3 — Days + exact + price + city
        DemoScenario(
            task_id="fb_marketplace/demo/general/vinyl",
            name="[GENERAL] Vinyl Records — Chicago, <$50, Week, Exact",
            category="general",
            description="Days since listed + exact match + price + city",
            task_prompt=(
                "I collect vinyl records and I'm specifically looking for ones in the Chicago area. "
                "My budget maxes out at $50. I only want to see listings from the past week — "
                "anything older is probably already gone. Show me exact matches only."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/chicago/search/"
                "?query=vinyl+records&maxPrice=50&daysSinceListed=7&exact=true"
            ],
            tags=["general", "days", "exact", "price"],
            hint="daysSinceListed=7 + exact=true must both appear.",
        ),
    ]

    # ---------- VEHICLES ----------
    vehicles = [
        # V1 — Full vehicle filter stack
        DemoScenario(
            task_id="fb_marketplace/demo/vehicle/camry",
            name="[VEHICLE] Toyota Camry — Dallas, 2019+, <60K mi, $15K–$25K",
            category="vehicles",
            description="Full vehicle filter stack: make + model + year + mileage + price + type",
            task_prompt=(
                "I'm looking for a used Toyota Camry, 2019 or newer, with less than 60,000 miles. "
                "Budget is $15,000 to $25,000. Dallas area."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/dallas/search/"
                "?query=toyota+camry&minPrice=15000&maxPrice=25000"
                "&minYear=2019&maxMileage=60000"
                "&topLevelVehicleType=car_truck&make=toyota&model=camry"
            ],
            tags=["vehicle", "make", "model", "year", "mileage", "price"],
            hint="All vehicle filters: make, model, minYear, maxMileage, topLevelVehicleType.",
        ),

        # V2 — Motorcycle type
        DemoScenario(
            task_id="fb_marketplace/demo/vehicle/harley",
            name="[VEHICLE] Harley Davidson — Phoenix, $8K–$20K, 2010+, Cheapest",
            category="vehicles",
            description="Motorcycle type + make + year + sort",
            task_prompt=(
                "Looking for a motorcycle — specifically a Harley Davidson. Budget: $8,000 to "
                "$20,000. Phoenix area. Year 2010 or newer. Want to see prices lowest to highest."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/phoenix/search/"
                "?query=harley+davidson&minPrice=8000&maxPrice=20000"
                "&minYear=2010&topLevelVehicleType=motorcycle"
                "&make=harley+davidson&sortBy=price_ascend"
            ],
            tags=["vehicle", "motorcycle", "make", "year", "sort"],
            hint="topLevelVehicleType=motorcycle (not car_truck).",
        ),

        # V3 — Boat type + sort
        DemoScenario(
            task_id="fb_marketplace/demo/vehicle/boat",
            name="[VEHICLE] Fishing Boat — Chicago, $5K–$15K, Newest",
            category="vehicles",
            description="Vehicle type boat + sort by newest",
            task_prompt=(
                "Need a boat for lake fishing. Nothing fancy — a small fishing boat or bass boat. "
                "Chicago area. Budget $5,000 to $15,000. Want to see the newest listings."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/chicago/search/"
                "?query=fishing+boat&minPrice=5000&maxPrice=15000"
                "&topLevelVehicleType=boat&sortBy=creation_time_descend"
            ],
            tags=["vehicle", "boat", "sort"],
            hint="topLevelVehicleType=boat + sortBy=creation_time_descend.",
        ),
    ]

    # ---------- PROPERTY RENTALS ----------
    property_rentals = [
        # P1 — Full property stack
        DemoScenario(
            task_id="fb_marketplace/demo/property/apartment_sf",
            name="[PROPERTY] 2BR Apartment — SF, $2K–$3.5K, 1+ Bath",
            category="property",
            description="Bedrooms + bathrooms + property type + price range",
            task_prompt=(
                "My girlfriend and I are moving in together and looking for a 2-bedroom apartment "
                "in San Francisco. Budget is $2,000 to $3,500 per month. We need at least 1 bathroom."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/sanfrancisco/search/"
                "?minPrice=2000&maxPrice=3500&minBedrooms=2&maxBedrooms=2"
                "&minBathrooms=1&propertyType=apartment"
            ],
            tags=["property", "bedrooms", "bathrooms", "type", "price"],
            hint="minBedrooms=2&maxBedrooms=2 for exactly 2 bedrooms.",
        ),

        # P2 — House with sort
        DemoScenario(
            task_id="fb_marketplace/demo/property/house_phoenix",
            name="[PROPERTY] House — Phoenix, 3BR+, 2BA+, $1.8K–$3K, Nearest",
            category="property",
            description="House rental with bedrooms + bathrooms + sort by distance",
            task_prompt=(
                "Retiring and moving to Phoenix — looking for a house rental. 3+ bedrooms, "
                "2+ bathrooms. Budget between $1,800 and $3,000. Show me the nearest listings first."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/phoenix/search/"
                "?minPrice=1800&maxPrice=3000&minBedrooms=3&minBathrooms=2"
                "&propertyType=house&sortBy=distance_ascend"
            ],
            tags=["property", "house", "bedrooms", "bathrooms", "sort"],
            hint="propertyType=house + sortBy=distance_ascend.",
        ),
    ]

    # ---------- PRICE MATH ----------
    price_math = [
        # PM1 — Budget addition
        DemoScenario(
            task_id="fb_marketplace/demo/price_math/laptop",
            name="[PRICE MATH] Laptop — $650 + $350 = $1000 budget",
            category="price_math",
            description="Agent must compute $650 + $350 = $1000 max budget",
            task_prompt=(
                "I just sold my old MacBook for $650 and I want to use that money plus $350 from "
                "savings to buy a new laptop. So my total budget is $1,000. Looking in the "
                "San Francisco area for any laptop, new condition. Show me cheapest first."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/sanfrancisco/search/"
                "?query=laptop&maxPrice=1000&itemCondition=new&sortBy=price_ascend"
            ],
            tags=["price_math", "addition"],
            hint="Budget math: $650 + $350 = $1,000. Must extract correct maxPrice=1000.",
        ),

        # PM2 — Variable budget (min/max from sale range)
        DemoScenario(
            task_id="fb_marketplace/demo/price_math/couch",
            name="[PRICE MATH] Couch — Sale $200–$350 + $400 = $600–$750",
            category="price_math",
            description="Agent must compute variable min/max from sale range + savings",
            task_prompt=(
                "Selling my old couch for somewhere between $200 and $350. Whatever I get, plus an "
                "additional $400 I've saved, will go toward a new couch. So my minimum budget is $600 "
                "and maximum is $750. Atlanta area. Good condition. Local pickup."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/atlanta/search/"
                "?query=couch&minPrice=600&maxPrice=750"
                "&itemCondition=used_good&deliveryMethod=local_pick_up"
            ],
            tags=["price_math", "variable_budget"],
            hint="min=$200+$400=$600, max=$350+$400=$750. Both minPrice AND maxPrice required.",
        ),

        # PM3 — Exclusion math (gift card can't be used)
        DemoScenario(
            task_id="fb_marketplace/demo/price_math/ps5",
            name="[PRICE MATH] PS5 — $100+$75+$250=$425 (exclude $25 GC)",
            category="price_math",
            description="Agent must exclude the $25 gift card from the total",
            task_prompt=(
                "My birthday money situation: Grandma gave $100, uncle gave $75, parents gave $250, "
                "and my sister gave a $25 gift card which I can't use on Marketplace. So I have $425 "
                "in cash. Looking for a PlayStation 5 in New York. Used like-new is fine. "
                "Show me exact matches only, sorted by cheapest first. Local pickup."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/newyork/search/"
                "?query=playstation+5&maxPrice=425&itemCondition=used_like_new"
                "&exact=true&sortBy=price_ascend&deliveryMethod=local_pick_up"
            ],
            tags=["price_math", "exclusion"],
            hint="EXCLUDE the $25 gift card: $100+$75+$250=$425 only. maxPrice=425.",
        ),
    ]

    # ---------- RED HERRINGS ----------
    red_herrings = [
        # RH1 — Brand preference is NOT a filter
        DemoScenario(
            task_id="fb_marketplace/demo/red_herring/camera",
            name="[RED HERRING] Canon Lens — Ignore Dave's Sony opinions",
            category="red_herring",
            description="Task contains irrelevant brand debate (Sony vs Canon)",
            task_prompt=(
                "I'm a professional photographer who shoots with Canon. My friend Dave just switched "
                "to Sony and won't stop talking about how much better the autofocus is. He's so annoying. "
                "Anyway, I need a Canon 70-200mm f/2.8 lens. Los Angeles. $500 to $1,500. "
                "Like-new only. Sort by cheapest. Exact matches only. Dave can keep his Sony opinions."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/losangeles/search/"
                "?query=canon+70-200mm+f2.8&minPrice=500&maxPrice=1500"
                "&itemCondition=used_like_new&sortBy=price_ascend&exact=true"
            ],
            tags=["red_herring", "brand_debate"],
            hint="Dave's Sony opinions are IRRELEVANT. Only Canon lens filters matter.",
        ),

        # RH2 — Dimensions are NOT URL filters
        DemoScenario(
            task_id="fb_marketplace/demo/red_herring/power_rack",
            name="[RED HERRING] Power Rack — Ignore safety bar concerns",
            category="red_herring",
            description="Task mentions safety bars, lifting buddy, brand — none are filters",
            task_prompt=(
                "My home gym needs a power rack. I've been doing squats with dumbbells like an "
                "animal. My lifting buddy uses a Rogue R-3 and loves it but those are $600+ new. "
                "I'm looking for any power rack in Philadelphia, $200 to $500. Good condition. "
                "I need the safety bars to work — I lift alone and don't want to die under the bar. "
                "Sort by nearest to me since I'll need to pick this up with my truck."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/philadelphia/search/"
                "?query=power+rack&minPrice=200&maxPrice=500"
                "&itemCondition=used_good&sortBy=distance_ascend"
            ],
            tags=["red_herring", "safety_specs"],
            hint="Brand (Rogue), safety bars, lifting alone are NOT filters. sortBy=distance_ascend.",
        ),
    ]

    # ---------- ULTRA-HARD ----------
    ultra_hard = [
        DemoScenario(
            task_id="fb_marketplace/demo/ultra_hard/midi",
            name="[ULTRA-HARD] MIDI Keyboard — 7 Simultaneous Filters",
            category="ultra_hard",
            description="Maximum difficulty: 7+ combined filters + narrative red herrings",
            task_prompt=(
                "I need a very specific setup for my home studio. Looking for a 49-key MIDI keyboard "
                "controller in San Francisco. Budget is between $100 and $350. Must be in like-new "
                "condition because I'm recording an album and can't deal with sticky keys. "
                "Show me exact matches only, sorted by cheapest first. Only interested in listings "
                "from the past week. Local pickup — I ride the Muni and can carry it on the bus."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/sanfrancisco/search/"
                "?query=49+key+midi+keyboard+controller&minPrice=100&maxPrice=350"
                "&itemCondition=used_like_new&exact=true&sortBy=price_ascend"
                "&daysSinceListed=7&deliveryMethod=local_pick_up"
            ],
            tags=["ultra_hard", "all_filters"],
            hint="ALL 7 filters must be set: query, price range, condition, exact, sort, days, delivery.",
        ),

        # UH2 — Income math + property filters
        DemoScenario(
            task_id="fb_marketplace/demo/ultra_hard/house_rental",
            name="[ULTRA-HARD] House Rental — Income Math ($4500×2×0.30=$2700)",
            category="ultra_hard",
            description="Income math + 5 property filters + sort + days",
            task_prompt=(
                "I'm looking for a 3-bedroom house to rent in Seattle. My partner and I both work "
                "from home and we have a toddler, so we need the space. Budget: we each earn about "
                "$4,500/month after taxes, and housing experts say to spend no more than 30% of "
                "combined income on rent. So that's $9,000 combined, 30% is $2,700. We need at least "
                "2 bathrooms. Property type must be a house. Sort by nearest. Only last week's listings."
            ),
            gt_url=[
                "https://www.facebook.com/marketplace/seattle/search/"
                "?maxPrice=2700&minBedrooms=3&minBathrooms=2"
                "&propertyType=house&sortBy=distance_ascend&daysSinceListed=7"
            ],
            tags=["ultra_hard", "income_math", "property"],
            hint="Income: 2×$4500=9000, ×0.30=$2700. Must compute maxPrice=2700.",
        ),
    ]

    return general + vehicles + property_rentals + price_math + red_herrings + ultra_hard


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

    CATEGORY_EMOJIS = {
        "general": "🛒",
        "vehicles": "🚗",
        "property": "🏠",
        "price_math": "🧮",
        "red_herring": "🎭",
        "ultra_hard": "💀",
    }

    @staticmethod
    def print_header(s: DemoScenario) -> None:
        emoji = ResultReporter.CATEGORY_EMOJIS.get(s.category, "🔍")
        print("\n" + "=" * 80)
        print(f"FB MARKETPLACE VERIFICATION  {emoji}  {s.name}")
        print("=" * 80)
        print(f"Task ID  : {s.task_id}")
        print(f"Tags     : {', '.join(s.tags)}")
        if s.hint:
            print(f"Hint     : {s.hint}")
        print("-" * 80)
        print(f"TASK:\n  {s.task_prompt}")
        print("-" * 80)
        print(f"GT URL:\n  {s.gt_url[0]}")
        if len(s.gt_url) > 1:
            for u in s.gt_url[1:]:
                print(f"  (alt) {u}")
        print("=" * 80)

    @staticmethod
    def print_instructions() -> None:
        print("\nINSTRUCTIONS:")
        print("  1. Use Facebook Marketplace to complete the task above")
        print("  2. Apply all required filters (query, price, condition, sort, etc.)")
        print("  3. If a login modal appears, close it (click X)")
        print("  4. Press ENTER here to verify your URL")
        print()

    @staticmethod
    def print_result(score: float, agent_url: str, gt_url: list, details: dict) -> None:
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        status = "✅  PASS" if score >= 1.0 else "❌  FAIL"
        print(f"Status   : {status}")
        print(f"Score    : {score:.0%}")
        agent_display = agent_url[:100] + ("..." if len(agent_url) > 100 else "")
        print(f"Agent URL: {agent_display}")
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

        verifier = FbMarketplaceUrlMatch(gt_url=scenario.gt_url)
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

    best_score = 0.0
    best_details: dict = {}
    for u in visited_urls:
        try:
            await verifier.reset()
            await verifier.update(url=u)
            result = await verifier.compute()
            if result.score > best_score:
                best_score = result.score
                best_details = getattr(verifier, "_match_details", {})
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
    print("FACEBOOK MARKETPLACE VERIFIER DEMO")
    print("=" * 80)
    for i, s in enumerate(scenarios, 1):
        emoji = ResultReporter.CATEGORY_EMOJIS.get(s.category, "?")
        print(f"  [{i:2d}] {emoji}  {s.name}")
        print(f"        {s.description}")

    print(f"\n  [A]  Run all {len(scenarios)} scenarios")
    print("  [Q]  Quit\n")

    choice = input(f"Select (1-{len(scenarios)}, A, Q): ").strip().upper()
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
