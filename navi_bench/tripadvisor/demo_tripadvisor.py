#!/usr/bin/env python
"""TripAdvisor benchmark demo backed by tasks.csv."""

import asyncio
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright

from navi_bench.base import DatasetItem, instantiate


TASKS_CSV_PATH = Path(__file__).with_name("tasks.csv")


@dataclass
class BrowserConfig:
    headless: bool = False
    viewport_width: int = 1366
    viewport_height: int = 768
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    locale: str = "en-US"
    timezone: str = "America/New_York"
    launch_args: list[str] = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-sandbox",
    ])


class BrowserManager:
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
            timezone_id=self.config.timezone,
            ignore_https_errors=True,
            java_script_enabled=True,
        )

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
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


class ResultReporter:
    @staticmethod
    def print_header(item: DatasetItem, task_prompt: str, location: str, timezone: str) -> None:
        print("\n" + "=" * 80)
        print(f"TRIPADVISOR VERIFICATION: {item.task_id}")
        print("=" * 80)
        print(f"Location:    {location}")
        print(f"Timezone:    {timezone}")
        print("-" * 80)
        print(f"TASK: {task_prompt}")
        print("=" * 80)

    @staticmethod
    def print_instructions() -> None:
        print("\n" + "-" * 40)
        print("INSTRUCTIONS:")
        print("-" * 40)
        print("1. Use TripAdvisor to complete the task")
        print("2. Apply the required dates, occupancy, categories, sort, and filters")
        print("3. Wait until the results finish refreshing and selected filters are visible")
        print("4. Press ENTER here when you are ready to verify")
        print("-" * 40 + "\n")

    @staticmethod
    def print_result(result, last_info: dict | None) -> None:
        status = "PASS" if result.score >= 1.0 else "FAIL"
        score_pct = result.score * 100

        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        print(f"Status:           {status}")
        print(f"Score:            {score_pct:.0f}%")
        print(f"Queries Matched:  {result.n_covered}/{result.n_queries}")
        print("-" * 80)

        if last_info:
            print(f"Page Type:         {last_info.get('pageType')}")
            print(f"Anti-Bot Status:   {last_info.get('antiBotStatus')}")
            print(f"URL:               {last_info.get('url')}")
            print(f"Requested Matches: {last_info.get('requestedMatches', [])}")
            print(f"Requested Misses:  {last_info.get('requestedMisses', [])}")
            if last_info.get("requestedExtras") is not None:
                print(f"Extra Filters:     {last_info.get('requestedExtras', [])}")
            print("-" * 80)

        print("=" * 80)


def summarize_task_variants(items: list[DatasetItem]) -> dict[str, set[str]]:
    summary = {
        "cities": set(),
        "brands": set(),
        "amenities": set(),
        "styles": set(),
        "required_filters": set(),
        "propertyTypes": set(),
        "star_levels": set(),
        "navbars": set(),
        "categories": set(),
        "type_filters": set(),
        "sort_orders": set(),
    }

    for item in items:
        task_cfg = json.loads(item.task_generation_config_json)
        for query_group in task_cfg.get("queries", []):
            for query in query_group:
                for city in query.get("cities", []) or []:
                    summary["cities"].add(city)
                for brand in query.get("brand", []) or []:
                    summary["brands"].add(brand)
                for amenity in query.get("amenities", []) or []:
                    summary["amenities"].add(amenity)
                for style in query.get("styles", []) or []:
                    summary["styles"].add(style)
                for required_filter in query.get("required_filters", []) or []:
                    summary["required_filters"].add(required_filter)
                for property_type in query.get("propertyTypes", []) or []:
                    summary["propertyTypes"].add(property_type)
                for navbar in query.get("navbar", []) or []:
                    summary["navbars"].add(navbar)
                for category in query.get("category", []) or []:
                    summary["categories"].add(category)
                for type_filter in query.get("type_filters", []) or []:
                    summary["type_filters"].add(type_filter)
                for sort_order in query.get("sort_orders", []) or []:
                    summary["sort_orders"].add(sort_order)
                if (min_stars := query.get("min_stars")) is not None:
                    summary["star_levels"].add(f"{min_stars} Star")

    return summary


def load_dataset_items() -> list[DatasetItem]:
    items: list[DatasetItem] = []
    with TASKS_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(DatasetItem.model_validate(row))
    return items


def choose_dataset_item(items: list[DatasetItem]) -> DatasetItem | None:
    print("\nTripAdvisor Tasks\n")
    variant_summary = summarize_task_variants(items)
    print("Catalog Summary")
    print("-" * 80)
    print(f"Tasks:            {len(items)}")
    print(f"Cities:           {', '.join(sorted(variant_summary['cities'])) or 'None'}")
    print(f"Brands:           {', '.join(sorted(variant_summary['brands'])) or 'None'}")
    print(f"Amenities:        {', '.join(sorted(variant_summary['amenities'])) or 'None'}")
    print(f"Styles:           {', '.join(sorted(variant_summary['styles'])) or 'None'}")
    print(f"Required Filters: {', '.join(sorted(variant_summary['required_filters'])) or 'None'}")
    print(f"Property Types:   {', '.join(sorted(variant_summary['propertyTypes'])) or 'None'}")
    print(f"Star Levels:      {', '.join(sorted(variant_summary['star_levels'])) or 'None'}")
    print(f"Navbar Options:   {', '.join(sorted(variant_summary['navbars'])) or 'None'}")
    print(f"Categories:       {', '.join(sorted(variant_summary['categories'])) or 'None'}")
    print(f"Type Filters:     {', '.join(sorted(variant_summary['type_filters'])) or 'None'}")
    print(f"Sort Orders:      {', '.join(sorted(variant_summary['sort_orders'])) or 'None'}")
    print("-" * 80)

    for idx, item in enumerate(items, 1):
        task_cfg = json.loads(item.task_generation_config_json)
        print(f"[{idx}] {item.task_id}")
        print(f"    {task_cfg.get('task', '')}")
        print(f"    Category: {item.l2_category or 'unknown'}")
    print("[Q] Quit\n")

    choice = input(f"Select task (1-{len(items)} or Q): ").strip().upper()
    if choice == "Q":
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(items):
        return items[int(choice) - 1]
    print("Invalid choice.")
    return None


async def run_dataset_item(item: DatasetItem) -> None:
    task_config = item.generate_task_config()
    evaluator = instantiate(task_config.eval_config)
    reporter = ResultReporter()
    browser_mgr: BrowserManager | None = None
    try:
        async with async_playwright() as p:
            browser_mgr = BrowserManager()
            _, context, page = await browser_mgr.launch(p)

            await evaluator.reset()
            if hasattr(evaluator, "attach_to_context"):
                evaluator.attach_to_context(context)

            logger.info(f"Opening {task_config.url}")
            await page.goto(
                task_config.url,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            reporter.print_header(
                item=item,
                task_prompt=task_config.task,
                location=task_config.user_metadata.location,
                timezone=task_config.user_metadata.timezone,
            )
            reporter.print_instructions()

            try:
                await asyncio.to_thread(input, "Press ENTER when you've completed the task... ")
            except KeyboardInterrupt:
                logger.warning("TripAdvisor search cancelled by user.")
                return
            except asyncio.CancelledError:
                logger.warning("TripAdvisor input was cancelled.")
                return

            active_page = next((p for p in reversed(context.pages) if not p.is_closed()), None)
            if active_page is None:
                logger.error("No active TripAdvisor page available for verification; the browser page was closed.")
            else:
                try:
                    await evaluator.update(page=active_page)
                except Exception as exc:
                    logger.warning(f"Final TripAdvisor scrape failed: {exc}")

            result = await evaluator.compute()
            display_info = getattr(evaluator, "_best_result_info", None)
            if display_info is None and hasattr(evaluator, "_all_infos") and evaluator._all_infos:
                display_info = evaluator._all_infos[-1]
            reporter.print_result(result, display_info)
    finally:
        if browser_mgr is not None:
            try:
                await browser_mgr.close()
            except Exception:
                pass


async def main() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    items = load_dataset_items()
    if not items:
        print("No TripAdvisor tasks found.")
        return

    selected = choose_dataset_item(items)
    if not selected:
        return

    await run_dataset_item(selected)


if __name__ == "__main__":
    asyncio.run(main())
