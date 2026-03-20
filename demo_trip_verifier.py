"""
=================================================================
  Trip.com NaviBench Demo — How to run the benchmark verifier
=================================================================

This script shows the full pipeline for ONE task (Row 0):
  1. Load a task from the CSV
  2. Instantiate the task config (resolves dates, renders task text)
  3. Simulate an agent URL
  4. Run the verifier to score the agent

Usage:
  cd "c:/Users/HP/Desktop/autonex navibench"
  python demo_trip_verifier.py
=================================================================
"""
import asyncio
import csv
import json

from navi_bench.base import DatasetItem, instantiate


def main():
    # ─────────────────────────────────────────────────
    # STEP 1: Load a task from the CSV
    # ─────────────────────────────────────────────────
    csv_path = r"data/trip/trip_task_pairs.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    row = rows[0]  # First task
    print("=" * 70)
    print("  STEP 1: Raw CSV row")
    print("=" * 70)
    print(f"  task_id:    {row['task_id']}")
    print(f"  domain:     {row['domain']}")
    print(f"  difficulty: {row['suggested_difficulty']}")
    print(f"  max_steps:  {row['suggested_max_steps']}")
    print()

    # ─────────────────────────────────────────────────
    # STEP 2: Parse the task config JSON and instantiate
    # ─────────────────────────────────────────────────
    config = json.loads(row["task_generation_config_json"])
    print("=" * 70)
    print("  STEP 2: Raw task config (before date resolution)")
    print("=" * 70)
    print(f"  _target_:     {config['_target_']}")
    print(f"  Raw task:     {config['task']}")
    print(f"  Values:")
    for k, v in config.get("values", {}).items():
        print(f"    {k}: {v}")
    print(f"  Raw GT URL:   {config['gt_url'][0][:100]}...")
    print()

    # instantiate() calls generate_task_config() which:
    #   - Resolves {now() + timedelta(7)} → actual ISO date (e.g., 2026-03-26)
    #   - Renders {dateRange} in task text → "next Mar 26th"
    #   - Substitutes {checkinDate}, {checkoutDate} in GT URL
    task_config = instantiate(config)

    print("=" * 70)
    print("  STEP 3: Resolved task config (after date resolution)")
    print("=" * 70)
    print(f"  Rendered task:  {task_config.task}")
    print(f"  Start URL:      {task_config.url}")
    print(f"  User location:  {task_config.user_metadata.location}")
    print(f"  User timezone:  {task_config.user_metadata.timezone}")
    print(f"  Resolved GT URL:")
    for url in task_config.eval_config["gt_url"]:
        print(f"    {url}")
    print()

    # ─────────────────────────────────────────────────
    # STEP 4: Simulate an AI agent navigating to a URL
    # ─────────────────────────────────────────────────
    # In a real benchmark, the agent browses trip.com and lands on a URL.
    # Here we simulate 3 scenarios:
    gt_url = task_config.eval_config["gt_url"][0]

    test_cases = [
        ("✅ Exact match (agent got it right)", gt_url),
        ("❌ Wrong city (agent went to London)", gt_url.replace("cityId=633", "cityId=338").replace("New%20York", "London")),
        ("❌ Missing filter (agent forgot sort)", gt_url.replace(",17~3*17*3", "")),
    ]

    print("=" * 70)
    print("  STEP 4: Running the verifier against agent URLs")
    print("=" * 70)

    async def run_verifier():
        for label, agent_url in test_cases:
            print(f"\n  --- {label} ---")
            print(f"  Agent URL: {agent_url[:100]}...")

            # Create the verifier from eval_config
            verifier = instantiate(task_config.eval_config)

            # Feed the agent's URL to the verifier
            await verifier.update(url=agent_url)

            # Compute the score (1.0 = match, 0.0 = no match)
            result = await verifier.compute()
            score = result.score
            print(f"  Score:     {score}  {'✅ PASS' if score == 1.0 else '❌ FAIL'}")

    asyncio.run(run_verifier())

    print()
    print("=" * 70)
    print("  DONE! This is how the Trip.com benchmark works end-to-end.")
    print("=" * 70)


if __name__ == "__main__":
    main()
