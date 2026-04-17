#!/usr/bin/env python
import asyncio
import sys
from dataclasses import dataclass
from playwright.async_api import async_playwright
from loguru import logger

from rome2rio_info_gathering import Rome2RioInfoGathering


# ---------------- CONFIG ----------------

@dataclass
class TaskScenario:
    task_id: str
    name: str
    description: str
    url: str
    task_prompt: str
    queries: list
    timezone: str = "Asia/Kolkata"


SCENARIOS = [
    TaskScenario(
        task_id="fast",
        name="Rome to Florence - Under 2h",
        description="",
        url="https://www.rome2rio.com/",
        task_prompt="Find transport options from Rome to Florence under 2 hours.",
        queries=[[{"max_duration": 120}]]
    ),
    TaskScenario(
        task_id="cheap",
        name="Cheapest route under ₹3000",
        description="",
        url="https://www.rome2rio.com/",
        task_prompt="Find the cheapest route under ₹3000.",
        queries=[[{"max_price": 3000}]]
    )
]


# ---------------- RESULT REPORT ----------------

class ResultReporter:
    @staticmethod
    def print_result(result):
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)

        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "⚠️ PARTIAL" if result.score > 0 else "❌ FAIL"

        print(f"Status:           {status}")
        print(f"Score:            {score_pct:.1f}%")
        print(f"Queries Matched:  {result.n_covered}/{result.n_queries}")
        print("-" * 80)


# ---------------- CORE ----------------

async def run_scenario(scenario):
    evaluator = Rome2RioInfoGathering(scenario.queries)
    reporter = ResultReporter()

    print(f"\n{'='*60}\nTASK: {scenario.task_prompt}\n{'='*60}")
    input("Press ENTER to launch browser...")

    async with async_playwright() as p:

        # ✅ Persistent context (KEY FIX)
        context = await p.chromium.launch_persistent_context(
            user_data_dir="rome2rio_user_data",  # saves cookies/session
            headless=False,
            channel="chrome",
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id=scenario.timezone,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # ✅ Go to site
        await page.goto(scenario.url, wait_until="domcontentloaded")

        print("[SYSTEM] Waiting for page load...")
        await page.wait_for_timeout(5000)

        # ✅ Human-like interaction
        await page.mouse.move(200, 300)
        await page.wait_for_timeout(1000)
        await page.mouse.move(400, 500)
        await page.wait_for_timeout(1000)

        print("\n👉 If Cloudflare appears, solve it once manually.")
        await asyncio.to_thread(
            input,
            "\nComplete search manually, then press ENTER... "
        )

        # ---------------- SCRAPING ----------------

        try:
            active_page = context.pages[-1]

            print(f"\n[SYSTEM] Scraping active tab: {active_page.url}")

            # relaxed wait (React rendering)
            await active_page.wait_for_timeout(5000)

            count = await active_page.locator('[data-testid^="trip-search-result"]').count()
            print(f"[DEBUG] Found {count} route cards")

            await evaluator.update(page=active_page)

        except Exception as e:
            print(f"[ERROR] scraping failed: {e}")

        result = await evaluator.compute()

        reporter.print_result(result)

        # ❗ DO NOT close context → keeps session (important)
        # await context.close()

    return result


# ---------------- MAIN ----------------

async def main():
    logger.remove()
    logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")

    for i, s in enumerate(SCENARIOS, 1):
        print(f"[{i}] {s.name}")

    choice = input("\nSelect scenario index: ")

    if choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        await run_scenario(SCENARIOS[int(choice) - 1])


if __name__ == "__main__":
    asyncio.run(main())