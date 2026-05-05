#!/usr/bin/env python
"""
Quick demo: Toyota Camry vehicle search verification.
Run this, do the search manually, press ENTER, and it checks your URL.
"""
import asyncio
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright
from navi_bench.facebookmarketplace.facebookmarketplace_url_match import FbMarketplaceUrlMatch


GT_URL = [
    "https://www.facebook.com/marketplace/dallas/search/"
    "?query=toyota+camry&minPrice=15000&maxPrice=25000"
    "&minYear=2019&maxMileage=60000"
    "&topLevelVehicleType=car_truck&make=toyota&model=camry"
]

TASK = """
╔══════════════════════════════════════════════════════════════════╗
║  TASK: Toyota Camry — Dallas, $15K–$25K, 2019+, <60K miles     ║
╠══════════════════════════════════════════════════════════════════╣
║  STEPS:                                                         ║
║  1. Set location to Dallas, Texas                               ║
║  2. Search: "toyota camry"                                      ║
║  3. Set Price: Min $15,000 — Max $25,000                        ║
║  4. Category → Vehicles (car_truck)                             ║
║  5. Make → Toyota                                               ║
║  6. Model → Camry                                               ║
║  7. Min Year → 2019                                             ║
║  8. Max Mileage → 60,000                                        ║
║  9. Press ENTER here when done                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


async def main():
    print(TASK)
    print(f"GT URL:\n  {GT_URL[0]}\n")
    input("Press ENTER to launch browser...")

    visited_urls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()

        def on_nav(frame):
            if frame == page.main_frame:
                u = page.url
                if u and u not in visited_urls:
                    visited_urls.append(u)

        page.on("framenavigated", on_nav)
        await page.goto("https://www.facebook.com/marketplace/", timeout=60000)

        print("\n🌐 Browser is open — follow the steps above.")
        print("   If a login modal appears, click X to close it.\n")
        await asyncio.to_thread(input, "Press ENTER when you've applied all filters... ")

        final_url = page.url
        visited_urls.append(final_url)
        await context.close()
        await browser.close()

    # Verify against GT
    print("\n" + "=" * 70)
    print("VERIFYING...")
    print("=" * 70)

    verifier = FbMarketplaceUrlMatch(gt_url=GT_URL)
    best_score = 0.0

    for u in visited_urls:
        try:
            await verifier.reset()
            await verifier.update(url=u)
            result = await verifier.compute()
            if result.score > best_score:
                best_score = result.score
                best_url = u
        except Exception:
            pass

    print(f"\nYour final URL:\n  {final_url[:120]}")
    print(f"\nGT URL:\n  {GT_URL[0][:120]}")
    print()

    if best_score >= 1.0:
        print("✅  PASS — Score: 1.0 (100%)")
        print("   All filters matched correctly!")
    else:
        print(f"❌  FAIL — Score: {best_score}")
        print("\n   Check these common issues:")
        print("   • make= might be a numeric ID (e.g., make=2544043502) instead of 'toyota'")
        print("   • City slug might be wrong (need 'dallas' in path)")
        print("   • Missing a filter (year, mileage, vehicle type, model)")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
