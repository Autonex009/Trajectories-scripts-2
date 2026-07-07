#!/usr/bin/env python
"""IRS Tax Withholding Estimator Demo Verifier.

Demonstrates end-to-end query verification for IRS TWE tasks.
Uses generate_task_config to create task configs, then runs the
verifier against perfect and imperfect agent responses.
"""

import asyncio
import json
import sys

from loguru import logger

from navi_bench.irs_tax_estimator.irs_tax_estimator_verifier import (
    IrsTweQueryMatch,
    generate_task_config,
)


# =============================================================================
# DEMO SCENARIOS
# =============================================================================

# Client's example task — Marcus & Elena Delano (MFJ, dual income, itemized)
DEMO_TASK = (
    "Please take care of the IRS Tax Withholding Estimator for my family and "
    "stop on the final results page. Use only the facts below. If the site "
    "asks for extra optional fields, rollups, or derived amounts that I have "
    "not explicitly given, leave those blank rather than estimating.\n\n"
    "My spouse Elena and I, Marcus Delano, are filing jointly. I am 38 and "
    "Elena is 35. We have two children, Sofia (7) and Lucas (14), and we "
    "will claim them as dependents. Neither of us is blind, and neither of "
    "us can be claimed on someone else's return.\n\n"
    "Marcus's job:\n"
    "- Salaried, not hourly\n"
    "- Works all year\n"
    "- Paid biweekly\n"
    "- Most recent pay period ended March 8, 2026\n"
    "- Most recent pay date was March 14, 2026\n"
    "- Last paycheck amount: $5,385\n"
    "- Year-to-date income: $32,310\n"
    "- Federal tax withheld from last paycheck: $612\n"
    "- Year-to-date federal withholding: $3,672\n"
    "- No bonus on the most recent paycheck\n"
    "- No future bonuses expected\n"
    "- Pre-tax deductions per pay period only: $750 retirement plan "
    "contribution, $320 health insurance contribution, $125 HSA/FSA "
    "contribution, and $45 other pre-tax contribution for dental/vision\n\n"
    "Elena's job:\n"
    "- Salaried, not hourly\n"
    "- Works all year\n"
    "- Paid biweekly\n"
    "- Most recent pay period ended March 8, 2026\n"
    "- Most recent pay date was March 14, 2026\n"
    "- Last paycheck amount: $1,538\n"
    "- Year-to-date income: $9,228\n"
    "- Federal tax withheld from last paycheck: $108\n"
    "- Year-to-date federal withholding: $648\n"
    "- Expected overtime compensation: $3,600 at 1.5x rate\n"
    "- No bonus on the most recent paycheck\n\n"
    "Other income:\n"
    "- Taxable interest income: $1,850\n"
    "- Qualified dividends: $2,200\n"
    "- Ordinary dividends: $2,200\n\n"
    "Adjustments:\n"
    "- Student loan interest deduction: $1,200\n\n"
    "Deductions:\n"
    "- We plan to itemize deductions\n"
    "- State and local tax payments: $10,000\n"
    "- Cash charitable contributions: $3,800\n"
    "- Qualified mortgage interest and investment interest expenses: $14,200\n\n"
    "Additional deductions:\n"
    "- Personal vehicle loan interest: $1,900\n\n"
    "Credits:\n"
    "- 2 children eligible for the Child Tax Credit\n"
    "- 1 qualifying person for the Child and Dependent Care Credit\n"
    "- Child and Dependent Care qualifying expenses: $8,400\n\n"
    "When the estimator asks whose job it is, enter Marcus as self/primary "
    "filer and Elena as spouse. Enter the information carefully and continue "
    "until you reach the final results page."
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
# DEMO RUNNER
# =============================================================================


async def run_demo():
    """Run the demo verification scenarios."""
    print("=" * 70)
    print("IRS TAX WITHHOLDING ESTIMATOR — DEMO VERIFIER")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Generate task config
    # ------------------------------------------------------------------
    print("\n--- Step 1: Generate Task Config ---")
    task_config = generate_task_config(
        task=DEMO_TASK,
        url="https://apps.irs.gov/app/tax-withholding-estimator/",
        queries=DEMO_QUERIES,
        location="United States",
        timezone="America/New_York",
    )
    print(f"  URL:  {task_config.url}")
    print(f"  Task: {task_config.task[:120]}...")
    print(f"  Eval: {task_config.eval_config['_target_']}")
    print(f"  GT queries: {len(task_config.eval_config['gt_queries'])} entry")

    # ------------------------------------------------------------------
    # 2. Perfect response — agent returns exact GT queries
    # ------------------------------------------------------------------
    print("\n--- Step 2: Perfect Agent Response ---")
    verifier = IrsTweQueryMatch(gt_queries=DEMO_QUERIES)
    await verifier.update(queries=DEMO_QUERIES)
    result = await verifier.compute_detailed()
    print(f"  Score:   {result.score}")
    print(f"  Match:   {result.match}")
    print(f"  Details: {result.details}")
    print(f"  Fields:  {result.field_results}")
    assert result.score == 1.0, "Perfect response should score 1.0!"
    print("  ✅ PASSED")

    # ------------------------------------------------------------------
    # 3. Perfect response with extra zero fields (should still pass)
    # ------------------------------------------------------------------
    print("\n--- Step 3: Agent Response with Extra Zero Fields ---")
    agent_with_extras = [dict(DEMO_QUERIES[0])]
    agent_with_extras[0]["moving_expenses"] = 0
    agent_with_extras[0]["alimony_paid"] = 0
    agent_with_extras[0]["foreign_tax_credit"] = 0

    await verifier.reset()
    await verifier.update(queries=agent_with_extras)
    result = await verifier.compute_detailed()
    print(f"  Score:   {result.score}")
    print(f"  Match:   {result.match}")
    print(f"  Details: {result.details}")
    assert result.score == 1.0, "Extra zero fields should still pass!"
    print("  ✅ PASSED (lenient on zero extras)")

    # ------------------------------------------------------------------
    # 4. Wrong response — wrong filing status
    # ------------------------------------------------------------------
    print("\n--- Step 4: Wrong Agent Response ---")
    wrong_agent = [dict(DEMO_QUERIES[0])]
    wrong_agent[0] = dict(wrong_agent[0])
    wrong_agent[0]["filing_status"] = "single"  # Wrong!
    wrong_agent[0]["interest"] = 999  # Wrong amount

    await verifier.reset()
    await verifier.update(queries=wrong_agent)
    result = await verifier.compute_detailed()
    print(f"  Score:   {result.score}")
    print(f"  Match:   {result.match}")
    print(f"  Wrong:   {result.wrong_fields}")
    print(f"  Details: {result.details}")
    assert result.score == 0.0, "Wrong response should score 0.0!"
    print("  ✅ PASSED (correctly detected errors)")

    # ------------------------------------------------------------------
    # 5. Missing response — no queries at all
    # ------------------------------------------------------------------
    print("\n--- Step 5: Empty Agent Response ---")
    await verifier.reset()
    await verifier.update(queries=[])
    result = await verifier.compute_detailed()
    print(f"  Score:   {result.score}")
    print(f"  Match:   {result.match}")
    assert result.score == 0.0, "Empty response should score 0.0!"
    print("  ✅ PASSED (correctly detected empty response)")

    # ------------------------------------------------------------------
    # 6. JSON string input (agent returns JSON as string)
    # ------------------------------------------------------------------
    print("\n--- Step 6: JSON String Input ---")
    await verifier.reset()
    json_str = json.dumps(DEMO_QUERIES)
    await verifier.update(queries=json_str)
    result = await verifier.compute_detailed()
    print(f"  Score:   {result.score}")
    print(f"  Match:   {result.match}")
    assert result.score == 1.0, "JSON string input should still work!"
    print("  PASSED (handles JSON string)")

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("ALL DEMO SCENARIOS PASSED")
    print("=" * 70)


async def run_live_demo():
    """Run a live browser test against the IRS website.

    Requires: pip install playwright && playwright install chromium
    Launches a real browser, navigates to the IRS TWE results page,
    and extracts the fact-graph to verify the JS extraction works.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run:")
        print("  pip install playwright && playwright install chromium")
        return

    print("=" * 70)
    print("IRS TWE - LIVE BROWSER EXTRACTION TEST")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("\n--- Navigating to IRS TWE ---")
        await page.goto("https://apps.irs.gov/app/tax-withholding-estimator/", timeout=30000)
        await page.wait_for_load_state("networkidle")
        print(f"  Page loaded: {page.url}")

        # Create a verifier with dummy GT queries (we just want to test extraction)
        verifier = IrsTweQueryMatch(gt_queries=[{}])

        # Attach tracking to context
        verifier.attach_to_context(context)
        print("  Tracking attached to context")

        # Try extraction on the landing page (should have empty/no fact-graph)
        print("\n--- Testing extraction on landing page ---")
        await verifier.update(page=page)
        result = await verifier.compute_detailed()
        print(f"  Score: {result.score}")
        print(f"  Details: {result.details}")
        print(f"  Agent queries: {verifier._agent_queries}")

        # If user already has data in sessionStorage from a previous session,
        # the extraction might return data
        if verifier._agent_queries and verifier._agent_queries[0]:
            extracted = verifier._agent_queries[0]
            print(f"\n  Found {len(extracted)} fields from existing session!")
            print("  Sample fields:")
            for key in list(extracted.keys())[:15]:
                val = extracted[key]
                if isinstance(val, list):
                    print(f"    {key}: [{len(val)} items]")
                else:
                    print(f"    {key}: {val}")
        else:
            print("  No existing session data (expected on fresh browser)")

        print("\n--- Instructions ---")
        print("  The browser is open. You can:")
        print("  1. Fill out the form manually")
        print("  2. Navigate to the results page")
        print("  3. The verifier will auto-extract on each navigation")
        print()
        input("  Press Enter to close the browser...")

        await browser.close()

    print("\nLIVE TEST COMPLETE")


def main():
    """Entry point for the demo."""
    import sys
    if "--live" in sys.argv:
        asyncio.run(run_live_demo())
    else:
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
