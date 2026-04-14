"""Fix all 40 flight GT URLs in the Expedia benchmark CSV.

Fixes:
1. fromType:U,toType:U -> fromType:AIRPORT,toType:AIRPORT
2. Add flight-type=on&mode=search prefix
3. Infant tasks: include infant age in children array
"""
import csv
import json
import re
import io

CSV_PATH = r"navi_bench\expedia\expedia_benchmark_tasks.csv"

# Infant tasks: task_id -> infant_age_to_add
# These tasks have infantinlap:Y but the infant is NOT yet in the children array
INFANT_TASKS = {
    "expedia/flights/unreliable_narrator/6": 1,   # 9 months old
    "expedia/flights/family_math/1": 1,            # 4 months old
    "expedia/flights/family_math/7": 1,            # 9 months old
    "expedia/flights/ultra_complex/1": 1,          # 4 months old
    "expedia/flights/ultra_complex/3": 1,          # 10 months old
    "expedia/flights/update_chain/5": 1,           # 6 months old
}


def fix_flight_url(url: str, task_id: str) -> str:
    """Fix a single flight GT URL."""
    if "/Flights-Search" not in url:
        return url  # Not a flight URL, skip

    # Fix 1: Add flight-type=on&mode=search after Flights-Search?
    if "flight-type=on" not in url:
        url = url.replace("Flights-Search?", "Flights-Search?flight-type=on&mode=search&")

    # Fix 2: fromType:U,toType:U -> fromType:AIRPORT,toType:AIRPORT
    url = url.replace("fromType:U,toType:U", "fromType:AIRPORT,toType:AIRPORT")
    # Also handle mixed cases
    url = url.replace("fromType:U,", "fromType:AIRPORT,")
    url = url.replace(",toType:U", ",toType:AIRPORT")

    # Fix 3: Infant tasks - add infant age to children array
    if task_id in INFANT_TASKS:
        infant_age = INFANT_TASKS[task_id]
        url = _fix_infant_in_children(url, infant_age)

    return url


def _fix_infant_in_children(url: str, infant_age: int) -> str:
    """Add infant age to children count and bracket array."""
    # Match children:N[ages] pattern
    match = re.search(r"children:(\d+)\[([^\]]+)\]", url)
    if match:
        old_count = int(match.group(1))
        old_ages = match.group(2)
        new_count = old_count + 1
        # Add infant age to the sorted ages
        ages_list = old_ages.split(";")
        ages_list.append(str(infant_age))
        # Sort numerically
        ages_list.sort(key=lambda x: int(x))
        new_ages = ";".join(ages_list)
        old_str = f"children:{old_count}[{old_ages}]"
        new_str = f"children:{new_count}[{new_ages}]"
        url = url.replace(old_str, new_str)
    else:
        # No existing children - infant is the only child
        # Find passengers= section and add children
        # This shouldn't happen with current tasks but handle just in case
        if "children:" not in url:
            url = url.replace(
                f"infantinlap:Y",
                f"children:1[{infant_age}],infantinlap:Y"
            )
    return url


def main():
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    fieldnames = reader.fieldnames

    fixed_count = 0
    infant_fixed = 0

    for row in rows:
        task_id = row["task_id"]
        config = json.loads(row["task_generation_config"])
        gt_urls = config.get("gt_url", [])

        if not gt_urls:
            continue

        changed = False
        new_urls = []
        for url in gt_urls:
            if "/Flights-Search" in url:
                new_url = fix_flight_url(url, task_id)
                if new_url != url:
                    changed = True
                    if task_id in INFANT_TASKS:
                        infant_fixed += 1
                new_urls.append(new_url)
            else:
                new_urls.append(url)

        if changed:
            config["gt_url"] = new_urls
            row["task_generation_config"] = json.dumps(config)
            fixed_count += 1
            print(f"  FIXED: {task_id}")
            # Print the new URL for verification
            for u in new_urls:
                # Show just the key parts
                pax_match = re.search(r"passengers=([^&]+)", u)
                if pax_match:
                    print(f"         passengers: {pax_match.group(1)}")

    # Write back
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*60}")
    print(f"Fixed {fixed_count} flight URLs")
    print(f"Fixed {infant_fixed} infant-in-children issues")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
