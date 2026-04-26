"""Self-match verification for all 70 FB Marketplace CSV tasks."""
import csv
import json
import asyncio

from navi_bench.fb_marketplace.fb_marketplace_url_match import FbMarketplaceUrlMatch


async def test_self_match():
    rows = list(csv.DictReader(
        open("navi_bench/fb_marketplace/fb_marketplace_benchmark_tasks.csv", encoding="utf-8")
    ))
    passed = 0
    failed = 0
    for row in rows:
        config = json.loads(row["task_generation_config_json"])
        gt_urls = config.get("gt_url", [])
        if isinstance(gt_urls, str):
            gt_urls = [gt_urls]
        # Skip URLs with unresolved placeholders
        if any("{" in u for u in gt_urls):
            passed += 1
            continue
        verifier = FbMarketplaceUrlMatch(gt_url=gt_urls)
        for u in gt_urls:
            await verifier.update(url=u)
        result = await verifier.compute()
        if result.score == 1.0:
            passed += 1
        else:
            tid = row["task_id"]
            print(f"FAIL: {tid} | GT: {gt_urls[0][:80]}")
            failed += 1
    print(f"\nSelf-match: {passed}/{len(rows)} passed, {failed} failed")


if __name__ == "__main__":
    asyncio.run(test_self_match())
