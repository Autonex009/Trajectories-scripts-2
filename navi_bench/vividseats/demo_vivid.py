#!/usr/bin/env python
import asyncio
import sys
from dataclasses import dataclass, field
from playwright.async_api import async_playwright
from loguru import logger

# Import your new Vivid Seats evaluator
from vivid_info_gathering import VividSeatsInfoGathering

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
    url: str
    task_prompt: str
    queries: list

SCENARIOS: list[TaskScenario] = [
    TaskScenario(
        task_id="vividseats/concerts/taylor_swift",
        name="Taylor Swift - General Availability",
        url="https://www.vividseats.com/",
        task_prompt="Search for Taylor Swift concert tickets on Vivid Seats and check availability.",
        queries=[[{"event_names": ["taylor swift"], "require_available": True}]]
    ),
    TaskScenario(
        task_id="vividseats/sports/lakers/super_seller",
        name="LA Lakers - Super Seller Only",
        url="https://www.vividseats.com/",
        task_prompt="Search for a Los Angeles Lakers home game. Filter to only show 'Super Seller' tickets.",
        queries=[[{"event_names": ["lakers"], "require_super_seller": True, "require_available": True}]]
    ),
    TaskScenario(
        task_id="vividseats/theater/hamilton/budget",
        name="Hamilton - Under $200",
        url="https://www.vividseats.com/",
        task_prompt="Search for Hamilton theater tickets priced under $200.",
        queries=[[{"event_names": ["hamilton"], "max_price": 200.0, "require_available": True}]]
    )
]

class BrowserManager:
    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self.browser = None
        self.context = None
        self.page = None
    
    async def launch(self, playwright) -> tuple:
        self.browser = await playwright.chromium.launch(headless=self.config.headless, args=self.config.launch_args)
        self.context = await self.browser.new_context(viewport={"width": self.config.viewport_width, "height": self.config.viewport_height}, user_agent=self.config.user_agent)
        
        # Anti-detection scripts (crucial for Cloudflare/PX on Vivid Seats)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        return self.browser, self.context, self.page
    
    async def close(self) -> None:
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()

class ResultReporter:
    """Formats and displays verification results for Vivid Seats."""
    
    @staticmethod
    def print_result(result, evaluator, scenario) -> None:
        print("\n" + "=" * 80)
        print("VERIFICATION RESULT")
        print("=" * 80)
        
        score_pct = result.score * 100
        status = "✅ PASS" if result.score >= 1.0 else "⚠️ PARTIAL" if result.score > 0 else "❌ FAIL"
        
        print(f"Status:           {status}")
        print(f"Score:            {score_pct:.1f}%")
        print(f"Queries Matched:  {result.n_covered}/{result.n_queries}")
        print(f"Pages Navigated:  {len(evaluator._navigation_stack)}")
        print("-" * 80)
        
        # Check for bot blocks (Cloudflare or PX)
        bot_blocks = [p for p in evaluator._navigation_stack if p.get("anti_bot") in ["blocked_perimeterx", "blocked_cloudflare"]]
        if bot_blocks:
            print("🚨 WARNING: Anti-Bot Block Detected during session! 🚨")
            print("-" * 80)

        for i, covered in enumerate(result.is_query_covered):
            status_icon = "✓" if covered else "✗"
            print(f"  Query {i+1}: [{status_icon}] {'Matched' if covered else 'Not matched'}")
        
        # Show scraped events for debugging
        print("-" * 80)
        print("EVENTS SCRAPED DURING SESSION:")
        all_events = []
        for page_infos in evaluator._all_infos:
            for event in page_infos:
                if event.get("eventName") and event.get("eventName") != "unknown" and event not in all_events:
                    all_events.append(event)
        
        if all_events:
            for i, event in enumerate(all_events[:15], 1):  # Show up to first 15 to avoid console spam
                name = event.get("eventName", "unknown").title()
                city = event.get("city") or "?"
                date = event.get("date") or "?"
                price = event.get("price")
                is_super_seller = event.get("isSuperSeller", False)
                source = event.get("source") or "?"
                
                price_str = f"${price}" if price else "?"
                seller_str = "🌟 Super Seller" if is_super_seller else "🎫 Standard Seller"
                print(f"  {i}. {name}")
                print(f"     📍 {city} | 📅 {date} | 💰 {price_str} | {seller_str} | 🔗 {source}")
        else:
            print("  No usable events scraped (Check if blocked by anti-bot or if JS needs selector updates)")
        
        print("=" * 80 + "\n")


async def run_scenario(scenario: TaskScenario) -> dict:
    evaluator = VividSeatsInfoGathering(queries=scenario.queries)
    reporter = ResultReporter() # <-- Initialize reporter
    
    print(f"\n{'='*60}\nTASK: {scenario.task_prompt}\n{'='*60}")
    input("Press ENTER to launch browser...")
    
    async with async_playwright() as p:
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch(p)
        
        await evaluator.reset()
        evaluator.attach_to_context(context)
        
        try:
            await page.goto(scenario.url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning(f"Initial navigation warning: {e}")
            
        await asyncio.to_thread(input, "\nPress ENTER when you've completed the task... ")
        
        # Force a final scrape right before evaluation
        try:
            await evaluator.update(page=page)
        except Exception:
            pass
            
        result = await evaluator.compute()
        await browser_mgr.close()
    
    # <-- Print the detailed scraped results here
    reporter.print_result(result, evaluator, scenario) 
    return result

async def main():
    logger.remove()
    logger.add(sys.stderr, format="<level>{message}</level>", level="INFO")
    for i, s in enumerate(SCENARIOS, 1): print(f"[{i}] {s.name}")
    choice = input("\nSelect scenario index: ")
    if choice.isdigit() and 1 <= int(choice) <= len(SCENARIOS):
        await run_scenario(SCENARIOS[int(choice) - 1])

if __name__ == "__main__":
    asyncio.run(main())