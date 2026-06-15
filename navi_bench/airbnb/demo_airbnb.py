#!/usr/bin/env python

import asyncio
import sys
from dataclasses import dataclass, field

from playwright.async_api import async_playwright
from loguru import logger

from navi_bench.airbnb.airbnb_url_match import (
    AirbnbUrlMatch,
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

def print_resolved_task(task_config, resolved_gt_url):
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

SCENARIOS = [
    TaskScenario(
        task_id="airbnb/homes/paris/wifi",
        name="Paris Homes With Wifi",
        task=(
            "Search Airbnb homes in Paris for 2 adults "
            "with WiFi during the first week of next month."
        ),
        url="https://www.airbnb.com",
        location="France",
        timezone="Europe/Paris",
        gt_url=[
            "https://www.airbnb.com/s/Paris--France/homes?"
            "adults=2"
            "&amenities%5B%5D=4"
        ],
    ),
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

        evaluator = AirbnbUrlMatch(gt_url=resolved_gt_url)
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

                    if "airbnb.com" in current_url:
                        display_url = current_url[:100] + "..." if len(current_url) > 100 else current_url
                        print(f"📍 URL: {display_url}")

                except Exception as e:
                    logger.debug(f"Navigation tracking error: {e}")

            page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))

            print("\n🌐 Browser ready — you are now the agent!")
            print("Apply the required filters on Airbnb.com.\n")

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