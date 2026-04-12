#!/usr/bin/env python
"""
Recreation.gov Search Verification Demo

Human-in-the-loop verification system for Recreation.gov search tasks.
This demo tracks navigation via URL matching only.

Features:
- Real-time URL tracking during navigation
- Stealth browser configuration
- Dynamic scenario loading from recreation_tasks.csv
- Ground-truth URL and expected filter display
"""

import asyncio
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright

from navi_bench.base import DatasetItem, instantiate
from navi_bench.recreation.recreation_url_match import RecreationUrlMatch


TASKS_CSV_PATH = Path(__file__).with_name("recreation_tasks.csv")


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
    launch_args: list[str] = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


@dataclass
class TaskScenario:
    """Defines a Recreation.gov verification scenario."""

    task_id: str
    name: str
    description: str
    task_prompt: str
    gt_url: str
    goal_params: dict[str, str | list[str]]
    location: str
    timezone: str
    start_url: str = "https://www.recreation.gov/search"
    tags: list[str] = field(default_factory=list)


def _derive_name(task_id: str, task_prompt: str) -> str:
    """Create a readable scenario name from task metadata."""
    suffix = task_id.split("/")[-1]
    prompt = task_prompt.strip().rstrip(".")
    if len(prompt) <= 72:
        return f"[{suffix}] {prompt}"
    return f"[{suffix}] {prompt[:69]}..."


def _derive_description(goal_params: dict[str, str | list[str]]) -> str:
    """Create a compact description from required goal params."""
    parts: list[str] = []
    for key, value in goal_params.items():
        if isinstance(value, list):
            rendered_value = ", ".join(value)
        else:
            rendered_value = value
        parts.append(f"{key}={rendered_value}")
    return "Required filters: " + "; ".join(parts)


def load_scenarios() -> list[TaskScenario]:
    """Load scenarios dynamically from recreation_tasks.csv."""
    scenarios: list[TaskScenario] = []

    with TASKS_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            dataset_item = DatasetItem.model_validate(row)
            task_config = dataset_item.generate_task_config()
            evaluator = instantiate(task_config.eval_config)

            if not isinstance(evaluator, RecreationUrlMatch):
                raise TypeError(f"Unexpected evaluator type for {dataset_item.task_id}: {type(evaluator)}")

            raw_config = json.loads(row["task_generation_config_json"])
            gt_url = raw_config.get("gt_url", "")
            goal_params = evaluator.goal_params

            scenarios.append(
                TaskScenario(
                    task_id=dataset_item.task_id,
                    name=_derive_name(dataset_item.task_id, task_config.task),
                    description=_derive_description(goal_params),
                    task_prompt=task_config.task,
                    gt_url=gt_url,
                    goal_params=goal_params,
                    location=task_config.user_metadata.location,
                    timezone=task_config.user_metadata.timezone,
                    start_url=task_config.url,
                )
            )

    return scenarios


class BrowserManager:
    """Manages browser lifecycle with stealth configuration."""

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self.browser = None
        self.context = None
        self.page = None

    async def launch(self, playwright):
        """Launch browser with a realistic browsing profile."""
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
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)
        self.page = await self.context.new_page()
        return self.browser, self.context, self.page

    async def close(self) -> None:
        """Close browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


async def prepare_recreation_page(page) -> None:
    """Give the page time to settle and trigger lazy-loaded filter sections."""
    try:
        await page.wait_for_load_state("load", timeout=15000)
    except Exception:
        logger.debug("Page did not reach full load state within timeout; continuing.")

    await page.wait_for_timeout(3000)

    await page.evaluate("""
        async () => {
            const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const step = Math.max(window.innerHeight * 0.9, 500);
            const maxTop = Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight
            );

            for (let top = 0; top < maxTop; top += step) {
                window.scrollTo(0, top);
                await delay(350);
            }

            window.scrollTo(0, maxTop);
            await delay(500);
            window.scrollTo(0, 0);
            await delay(300);
        }
    """)


class ResultReporter:
    """Formats and displays verification results."""

    @staticmethod
    def print_header(scenario: TaskScenario) -> None:
        print("\n" + "=" * 80)
        print(f"RECREATION.GOV SEARCH VERIFICATION: {scenario.name}")
        print("=" * 80)
        print(f"Task ID:     {scenario.task_id}")
        print(f"Location:    {scenario.location}")
        print(f"Timezone:    {scenario.timezone}")
        print("-" * 80)
        print(f"TASK: {scenario.task_prompt}")
        print("-" * 80)
        print("Ground Truth URL:")
        print(f"  {scenario.gt_url}")
        print("-" * 80)
        print("Required URL parameters:")
        for key, value in scenario.goal_params.items():
            if isinstance(value, list):
                rendered_value = ", ".join(value)
            else:
                rendered_value = value
            print(f"  - {key}={rendered_value}")
        print("=" * 80)

    @staticmethod
    def print_instructions() -> None:
        print("\n" + "-" * 40)
        print("INSTRUCTIONS:")
        print("-" * 40)
        print("1. Use Recreation.gov to complete the search task")
        print("2. Apply the required search filters")
        print("3. The system tracks your URL automatically")
        print("4. Press ENTER when ready to verify")
        print("-" * 40 + "\n")

    @staticmethod
    def print_result(score: float, scenario: TaskScenario, final_url: str) -> None:
        status = "PASS" if score >= 1.0 else "FAIL"
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        print(f"Status:  {status}")
        print(f"Score:   {score * 100:.0f}%")
        print("-" * 80)
        if score >= 1.0:
            print("The final Recreation.gov URL matches the expected search filters.")
        else:
            print("The final Recreation.gov URL does not match the expected search filters.")
        print("-" * 80)
        print("Expected URL:")
        print(f"  {scenario.gt_url}")
        print("Final URL:")
        print(f"  {final_url}")
        print("=" * 80 + "\n")

    @staticmethod
    def print_summary(results: list[dict]) -> None:
        if not results:
            return

        print("\n" + "=" * 80)
        print("SESSION SUMMARY")
        print("=" * 80)

        total = len(results)
        passed = sum(1 for result in results if result["score"] >= 1.0)

        print(f"Total Scenarios:  {total}")
        print(f"Passed:           {passed}")
        print(f"Success Rate:     {passed / total * 100:.1f}%")
        print("-" * 80)
        for result in results:
            status = "PASS" if result["score"] >= 1.0 else "FAIL"
            print(f"  {status} {result['task_id']}")
        print("=" * 80 + "\n")


async def run_scenario(scenario: TaskScenario) -> dict:
    """Run a single verification scenario."""
    evaluator = RecreationUrlMatch(goal_params=scenario.goal_params)
    reporter = ResultReporter()

    reporter.print_header(scenario)
    reporter.print_instructions()

    input("Press ENTER to launch browser... ")

    async with async_playwright() as playwright:
        browser_mgr = BrowserManager()
        _, _, page = await browser_mgr.launch(playwright)

        await evaluator.reset()
        try:
            await page.goto(scenario.start_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as exc:
            logger.warning(f"Initial navigation did not fully settle: {exc}")
            await page.goto(scenario.start_url, timeout=60000, wait_until="commit")
        await prepare_recreation_page(page)
        await evaluator.update(url=page.url)

        async def on_navigation():
            try:
                current_url = page.url
                await evaluator.update(url=current_url)
                if "recreation.gov" in current_url:
                    display_url = current_url[:120] + "..." if len(current_url) > 120 else current_url
                    print(f"URL: {display_url}")
            except Exception as exc:
                logger.debug(f"Navigation tracking error: {exc}")

        page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))

        print("\nBrowser ready. Complete the task in the opened page.\n")
        await asyncio.to_thread(input, "Press ENTER when you've completed the task... ")

        final_url = page.url
        await evaluator.update(url=final_url)
        result = await evaluator.compute()
        await browser_mgr.close()

    reporter.print_result(result.score, scenario, final_url)

    return {
        "task_id": scenario.task_id,
        "score": result.score,
        "final_url": final_url,
    }


async def run_interactive_menu() -> None:
    """Run interactive scenario selection menu."""
    scenarios = load_scenarios()

    print("\n" + "=" * 80)
    print("RECREATION.GOV SEARCH VERIFICATION SYSTEM")
    print("=" * 80)
    print("\nAvailable scenarios:\n")

    for index, scenario in enumerate(scenarios, start=1):
        print(f"  [{index}] {scenario.name}")
        print(f"      {scenario.description}")
        print()

    print("  [A] Run all scenarios")
    print("  [Q] Quit")
    print()

    choice = input(f"Select scenario (1-{len(scenarios)}, A, or Q): ").strip().upper()

    results: list[dict] = []

    if choice == "Q":
        print("Goodbye!")
        return

    if choice == "A":
        for index, scenario in enumerate(scenarios):
            result = await run_scenario(scenario)
            results.append(result)

            if index < len(scenarios) - 1:
                cont = input("\nContinue to next scenario? (y/n): ").strip().lower()
                if cont != "y":
                    break

    elif choice.isdigit() and 1 <= int(choice) <= len(scenarios):
        result = await run_scenario(scenarios[int(choice) - 1])
        results.append(result)

    else:
        print("Invalid choice. Please try again.")
        return

    ResultReporter.print_summary(results)


async def main() -> None:
    """Main entry point."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    try:
        await run_interactive_menu()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
    except Exception as exc:
        logger.exception(f"Error: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
