#!/usr/bin/env python
"""IRS Tax Withholding Estimator Demo Verifier.

Demonstrates end-to-end query verification for IRS TWE tasks.
Supports three modes:
  1. Default: Runs built-in demo scenarios (no browser)
  2. --live: Opens a browser for manual testing
  3. --csv <path>: Loads tasks from a CSV/TSV file and verifies
"""

import asyncio
import csv
import json
import sys
from pathlib import Path

from loguru import logger

from navi_bench.base import instantiate
from navi_bench.irs_tax_estimator.irs_tax_estimator_verifier import (
    IrsTweQueryMatch,
    generate_task_config,
)


# =============================================================================
# DEFAULT DEMO SCENARIO (Marcus & Elena — MFJ)
# =============================================================================

DEMO_TASK = (
    "Please take care of the IRS Tax Withholding Estimator for my family and "
    "stop on the final results page. Use only the facts below. If the site "
    "asks for extra optional fields, rollups, or derived amounts that I have "
    "not explicitly given, leave those blank rather than estimating.\n\n"
    "My spouse Elena and I, Marcus Delano, are filing jointly. I am 38 and "
    "Elena is 35. We have two children, Sofia (7) and Lucas (14), and we "
    "will claim them as dependents. Neither of us is blind, and neither of "
    "us can be claimed on someone else's return.\n\n"
    "Marcus's job: Salaried, all year, paid biweekly. Most recent pay period "
    "ended March 8, 2026, pay date March 14, 2026. Gross $5,385. YTD $32,310. "
    "Fed withheld $612, YTD $3,672. No bonus. Pre-tax: $750 retirement, $320 "
    "health, $125 HSA, $45 other.\n\n"
    "Elena's job: Salaried, all year, paid biweekly. Pay period ended March 8, "
    "2026, pay date March 14, 2026. Gross $1,538. YTD $9,228. Fed withheld "
    "$108, YTD $648. Expected overtime: $3,600 at 1.5x. No bonus.\n\n"
    "Other income: Interest $1,850. Qualified dividends $2,200. Ordinary "
    "dividends $2,200.\n\n"
    "Adjustments: Student loan interest $1,200.\n\n"
    "Deductions: Itemized. SALT $10,000. Charity $3,800. Mortgage interest "
    "$14,200. Car loan interest $1,900.\n\n"
    "Credits: 2 children CTC. 1 qualifying CDCC with $8,400 expenses."
)

DEMO_QUERIES = [
    {
        "filing_status": "married_filing_jointly",
        "user_age_65_or_older": False,
        "is_blind": False,
        "plan_to_claim_dependents": True,
        "claimed_as_dependent": False,
        "spouse_age_65_or_older": False,
        "spouse_is_blind": False,
        "jobs": [
            {
                "person": "myself",
                "job_type": "salary",
                "job_duration": "all_year",
                "pay_frequency": "biweekly",
                "recent_pay_period_end": "03/08/2026",
                "recent_pay_date": "03/14/2026",
                "gross_per_period": 5385,
                "ytd_gross": 32310,
                "fed_withholding_period": 612,
                "fed_withholding_ytd": 3672,
                "received_bonus": False,
                "retirement_401k_period": 750,
                "health_insurance_period": 320,
                "hsa_period": 125,
                "pre_tax_period": 45,
            },
            {
                "person": "spouse",
                "job_type": "salary",
                "job_duration": "all_year",
                "pay_frequency": "biweekly",
                "recent_pay_period_end": "03/08/2026",
                "recent_pay_date": "03/14/2026",
                "gross_per_period": 1538,
                "ytd_gross": 9228,
                "fed_withholding_period": 108,
                "fed_withholding_ytd": 648,
                "annual_overtime_income": 3600,
                "overtime_rate": "1.5x",
                "received_bonus": False,
            },
        ],
        "interest": 1850,
        "qualified_dividends": 2200,
        "ordinary_dividends": 2200,
        "student_loan_interest": 1200,
        "deduction_type": "itemized",
        "salt": 10000,
        "charity_gifts": 3800,
        "mortgage_interest": 14200,
        "car_loan_interest": 1900,
        "number_of_children": 2,
        "cdcc_number_of_children": 1,
        "cdcc_annual_care_expenses": 8400,
    }
]


# =============================================================================
# CSV / TSV LOADER
# =============================================================================


def load_csv_tasks(csv_path: str) -> list[dict]:
    """Load tasks from a CSV or TSV file (auto-detects delimiter).

    Supports both our format (task_generation_config) and team format
    (task_generation_config_json, tab-separated).
    """
    path = Path(csv_path)
    if not path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        sample = f.read(2048)
        f.seek(0)

        # Auto-detect delimiter
        if "\t" in sample.split("\n")[0]:
            reader = csv.DictReader(f, delimiter="\t")
        else:
            reader = csv.DictReader(f)

        rows = list(reader)

    tasks = []
    for i, row in enumerate(rows):
        task_id = row.get("task_id", f"row_{i}")

        # Support both column names
        config_str = row.get("task_generation_config_json") or row.get("task_generation_config", "")
        if not config_str:
            print(f"  SKIP {task_id}: no config JSON found")
            continue

        try:
            config = json.loads(config_str)
        except json.JSONDecodeError as e:
            print(f"  SKIP {task_id}: invalid JSON: {e}")
            continue

        tasks.append({
            "task_id": task_id,
            "config": config,
        })

    return tasks


# =============================================================================
# DEMO: BUILT-IN SCENARIOS
# =============================================================================


async def run_demo():
    """Run built-in demo verification scenarios."""
    print("=" * 70)
    print("IRS TAX WITHHOLDING ESTIMATOR — DEMO VERIFIER")
    print("=" * 70)

    # 1. Generate task config
    print("\n--- Step 1: Generate Task Config ---")
    task_config = generate_task_config(
        task=DEMO_TASK,
        url="https://apps.irs.gov/app/tax-withholding-estimator/",
        queries=DEMO_QUERIES,
    )
    print(f"  URL:  {task_config.url}")
    print(f"  Task: {task_config.task[:100]}...")
    print(f"  GT queries: {len(task_config.eval_config['gt_queries'])} entry")

    # 2. Perfect response
    print("\n--- Step 2: Perfect Agent Response ---")
    verifier = IrsTweQueryMatch(gt_queries=DEMO_QUERIES)
    await verifier.update(queries=DEMO_QUERIES)
    result = await verifier.compute_detailed()
    print(f"  Score: {result.score}  Match: {result.match}")
    print(f"  Fields: {result.field_results}")
    assert result.score == 1.0, "Perfect response should score 1.0!"
    print("  ✅ PASSED")

    # 3. Extra zero fields (should still pass)
    print("\n--- Step 3: Agent Response with Extra Zero Fields ---")
    agent_with_extras = [dict(DEMO_QUERIES[0])]
    agent_with_extras[0]["moving_expenses"] = 0
    agent_with_extras[0]["alimony_paid"] = 0

    await verifier.reset()
    await verifier.update(queries=agent_with_extras)
    result = await verifier.compute_detailed()
    assert result.score == 1.0
    print(f"  Score: {result.score}  ✅ PASSED (lenient on zero extras)")

    # 4. Wrong response
    print("\n--- Step 4: Wrong Agent Response ---")
    wrong_agent = [dict(DEMO_QUERIES[0])]
    wrong_agent[0]["filing_status"] = "single"

    await verifier.reset()
    await verifier.update(queries=wrong_agent)
    result = await verifier.compute_detailed()
    assert result.score == 0.0
    print(f"  Score: {result.score}  Wrong: {result.wrong_fields[:3]}")
    print("  ✅ PASSED (correctly detected errors)")

    # 5. Empty response
    print("\n--- Step 5: Empty Agent Response ---")
    await verifier.reset()
    await verifier.update(queries=[])
    result = await verifier.compute_detailed()
    assert result.score == 0.0
    print(f"  Score: {result.score}  ✅ PASSED")

    # 6. JSON string input
    print("\n--- Step 6: JSON String Input ---")
    await verifier.reset()
    await verifier.update(queries=json.dumps(DEMO_QUERIES))
    result = await verifier.compute_detailed()
    assert result.score == 1.0
    print(f"  Score: {result.score}  ✅ PASSED")

    print("\n" + "=" * 70)
    print("ALL DEMO SCENARIOS PASSED")
    print("=" * 70)


# =============================================================================
# CSV VERIFICATION
# =============================================================================


async def run_csv_demo(csv_path: str):
    """Load tasks from a CSV/TSV file and verify each one."""
    print("=" * 70)
    print(f"IRS TWE — CSV VERIFICATION: {csv_path}")
    print("=" * 70)

    tasks = load_csv_tasks(csv_path)
    print(f"\nLoaded {len(tasks)} tasks\n")

    passed = 0
    failed = 0
    errors = []

    for task_info in tasks:
        task_id = task_info["task_id"]
        config = task_info["config"]

        try:
            # Instantiate the task config via Hydra-style config
            task_config = instantiate(config)
            verifier = instantiate(task_config.eval_config)

            # Get GT queries from eval_config
            gt_queries = task_config.eval_config.get("gt_queries", [])

            # Feed GT as perfect response
            await verifier.update(queries=gt_queries)
            result = await verifier.compute_detailed()

            if result.score == 1.0:
                fields = result.field_results.get("total_fields", "?")
                print(f"  ✅ {task_id}: PASS ({fields} fields)")
                passed += 1
            else:
                print(f"  ❌ {task_id}: FAIL (score={result.score})")
                if result.missing_fields:
                    print(f"     Missing: {result.missing_fields[:5]}")
                if result.wrong_fields:
                    print(f"     Wrong:   {result.wrong_fields[:5]}")
                if result.extra_fields:
                    print(f"     Extra:   {result.extra_fields[:5]}")
                failed += 1
                errors.append(task_id)

        except Exception as e:
            print(f"  💥 {task_id}: ERROR: {e}")
            failed += 1
            errors.append(task_id)

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tasks)}")
    if errors:
        print(f"Failed tasks: {errors}")
    print("=" * 70)


# =============================================================================
# LIVE BROWSER TEST (Playwright) — Interactive Task Picker
# =============================================================================


async def run_live_demo(csv_path: str | None = None):
    """Run a live browser test with Playwright.

    Opens an interactive menu to pick a task from the CSV, loads the ground
    truth for that task, opens the IRS form in Playwright, extracts state
    on every page navigation, and prints verification results.

    Modeled after the Skyscanner demo_skyscanner.py pattern.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run:")
        print("  pip install playwright && python -m playwright install chromium")
        return

    # ---- Load tasks from CSV ----
    if csv_path is None:
        # Try irs_five_sample_tasks.csv first, then benchmark CSV
        team_csv = Path(__file__).parent / "irs_five_sample_tasks.csv"
        bench_csv = Path(__file__).parent / "irs_tax_estimator_benchmark_tasks.csv"
        if team_csv.exists():
            csv_path = str(team_csv)
        elif bench_csv.exists():
            csv_path = str(bench_csv)
        else:
            print("ERROR: No CSV found. Provide one with --csv <path>")
            return

    tasks = load_csv_tasks(csv_path)
    if not tasks:
        print("ERROR: No tasks loaded from CSV.")
        return

    # ---- Interactive menu ----
    print("\n" + "=" * 70)
    print("IRS TWE — LIVE BROWSER VERIFICATION")
    print("=" * 70)
    print(f"  CSV: {csv_path}")
    print(f"  Tasks loaded: {len(tasks)}\n")

    for i, t in enumerate(tasks, 1):
        config = t["config"]
        queries = config.get("queries", [[]])
        # Extract filing status for display
        gt = queries[0] if queries else {}
        if isinstance(gt, list):
            gt = gt[0] if gt else {}
        filing = gt.get("filing_status", "unknown")
        n_jobs = len(gt.get("jobs", []))
        n_se = len(gt.get("self_employment", []))
        print(f"  [{i:2d}] {t['task_id']}")
        print(f"       Filing: {filing} | Jobs: {n_jobs} | Self-employment: {n_se}")

    print(f"\n  [A]  Run all {len(tasks)} tasks")
    print("  [Q]  Quit\n")

    choice = input(f"Select (1–{len(tasks)}, A, Q): ").strip().upper()

    if choice == "Q":
        print("Goodbye!")
        return

    if choice == "A":
        selected = list(range(len(tasks)))
    elif choice.isdigit() and 1 <= int(choice) <= len(tasks):
        selected = [int(choice) - 1]
    else:
        print("Invalid choice.")
        return

    # ---- Run selected task(s) ----
    results = []

    for task_idx in selected:
        task_info = tasks[task_idx]
        task_id = task_info["task_id"]
        config = task_info["config"]

        # Instantiate to get ground truth
        try:
            task_config = instantiate(config)
            gt_queries = task_config.eval_config.get("gt_queries", [])
        except Exception as e:
            print(f"  💥 {task_id}: Failed to load config: {e}")
            results.append({"task_id": task_id, "score": 0.0})
            continue

        # Extract filing status + task text for display
        gt = gt_queries[0] if gt_queries else {}
        filing = gt.get("filing_status", "?")
        task_text = config.get("task", "")

        print("\n" + "=" * 70)
        print(f"TASK: {task_id}")
        print("=" * 70)
        print(f"Filing Status: {filing}")
        print("-" * 70)
        print("INSTRUCTIONS FOR THIS TASK:")
        # Print task text wrapped
        for line in task_text.split(". "):
            if line.strip():
                print(f"  • {line.strip()}.")
        print("-" * 70)

        input("\nPress ENTER to launch browser...")

        # Track whether browser is still open
        browser_open = True
        extraction_count = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
            )
            page = await context.new_page()

            # Create verifier with real ground truth
            verifier = IrsTweQueryMatch(gt_queries=gt_queries)

            # Navigation handler — extract on every page change
            async def on_navigate(frame):
                nonlocal extraction_count, browser_open
                if not browser_open:
                    return
                if frame != page.main_frame:
                    return
                url = page.url
                if "tax-withholding-estimator" not in url:
                    return

                try:
                    await page.wait_for_timeout(800)
                    if not browser_open:
                        return

                    extraction = await page.evaluate(verifier.js_script)
                    if extraction and extraction.get("error") is None:
                        extracted = extraction.get("extracted", {})
                        dom_count = extraction.get("dom_field_count", 0)

                        if extracted:
                            extraction_count += 1
                            # Update verifier with extracted data
                            verifier._agent_queries = [extracted]
                            verifier._result = None

                            # Compute score against ground truth
                            result = await verifier.compute_detailed()

                            page_name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
                            matched = result.field_results.get('matched', 0)
                            total = result.field_results.get('total_fields', 0)
                            pct = (matched / total * 100) if total > 0 else 0
                            status = "✅" if matched == total else "🔄"
                            print(
                                f"\n  📊 [{page_name}] Extraction #{extraction_count}: "
                                f"{len(extracted)} payload fields + {dom_count} DOM fields"
                            )
                            print(
                                f"     {status} {matched}/{total} fields match ({pct:.0f}%)"
                            )
                            if result.missing_fields:
                                print(f"     Missing: {result.missing_fields[:5]}")
                            if result.wrong_fields:
                                print(f"     Wrong: {result.wrong_fields[:3]}")
                        else:
                            page_name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
                            print(f"\n  ⏳ [{page_name}] No payload data yet (expected early in form)")

                except Exception as e:
                    if "closed" not in str(e).lower():
                        logger.debug(f"Extraction error: {e}")

            page.on("framenavigated", on_navigate)

            # Navigate to IRS
            url = config.get("url", "https://apps.irs.gov/app/tax-withholding-estimator/")
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle")

            print(f"\n  🌐 Browser ready at: {page.url}")
            print("  Fill out the form following the instructions above.")
            print("  Score updates will print here as you navigate pages.")
            print()

            # Wait for user to finish (proper async input)
            await asyncio.to_thread(input, "  Press ENTER when done (on the Results page)... ")

            # Mark browser as closing to prevent extraction errors
            browser_open = False

            # Final extraction
            try:
                final_extraction = await page.evaluate(verifier.js_script)
                if final_extraction and final_extraction.get("error") is None:
                    extracted = final_extraction.get("extracted", {})
                    dom_count = final_extraction.get("dom_field_count", 0)
                    if extracted:
                        verifier._agent_queries = [extracted]
                        verifier._result = None
            except Exception:
                pass  # Browser might already be closing

            # Compute final score
            final_result = await verifier.compute_detailed()

            await browser.close()

        # Print final result
        print("\n" + "=" * 70)
        print("VERIFICATION RESULT")
        print("=" * 70)
        status = "✅ PASS" if final_result.score >= 1.0 else "❌ FAIL"
        print(f"  Task:   {task_id}")
        print(f"  Status: {status}")
        print(f"  Score:  {final_result.score:.0%}")
        fr = final_result.field_results
        print(f"  Fields: {fr.get('matched', '?')}/{fr.get('total_fields', '?')} matched")
        if final_result.missing_fields:
            print(f"  Missing fields: {final_result.missing_fields}")
        if final_result.wrong_fields:
            print(f"  Wrong fields:   {final_result.wrong_fields}")
        if final_result.extra_fields:
            print(f"  Extra fields:   {final_result.extra_fields}")
        print("=" * 70)

        results.append({"task_id": task_id, "score": final_result.score})

        # If running multiple, ask to continue
        if len(selected) > 1 and task_idx != selected[-1]:
            cont = input("\nContinue to next task? (y/n): ").strip().lower()
            if cont != "y":
                break

    # ---- Session summary ----
    if results:
        total = len(results)
        passed = sum(1 for r in results if r["score"] >= 1.0)
        print("\n" + "=" * 70)
        print("SESSION SUMMARY")
        print("=" * 70)
        print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {total - passed}")
        for r in results:
            icon = "✅" if r["score"] >= 1.0 else "❌"
            print(f"  {icon}  {r['task_id']} — {r['score']:.0%}")
        print("=" * 70)


# =============================================================================
# ENTRY POINT
# =============================================================================


def main():
    """Entry point for the demo.

    Usage:
      python demo_irs_tax_estimator.py                     # Built-in demo
      python demo_irs_tax_estimator.py --live               # Live browser (uses irs_five_sample_tasks.csv)
      python demo_irs_tax_estimator.py --live --csv t.csv   # Live browser with specific CSV
      python demo_irs_tax_estimator.py --csv tasks.csv      # CSV verification (no browser)
    """
    if "--live" in sys.argv:
        csv_path = None
        if "--csv" in sys.argv:
            idx = sys.argv.index("--csv")
            if idx + 1 < len(sys.argv):
                csv_path = sys.argv[idx + 1]
        asyncio.run(run_live_demo(csv_path))
    elif "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        if idx + 1 < len(sys.argv):
            csv_path = sys.argv[idx + 1]
        else:
            csv_path = str(Path(__file__).parent / "irs_five_sample_tasks.csv")
        asyncio.run(run_csv_demo(csv_path))
    else:
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()

