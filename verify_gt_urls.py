"""Self-match verification for all 70 Expedia GT URLs.

Parses each GT URL from the CSV, runs it through the verifier against itself,
and reports any that fail self-match (which would indicate a malformed URL).
"""
import csv
import json
import sys
from navi_bench.expedia.expedia_url_match import (
    parse_flight_url,
    parse_hotel_url,
    ExpediaUrlMatch,
)


def main():
    csv_path = "navi_bench/expedia/expedia_benchmark_tasks.csv"
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Total tasks: {len(rows)}\n")
    
    passed = 0
    failed = 0
    flight_count = 0
    hotel_count = 0
    infant_count = 0
    
    for i, row in enumerate(rows):
        task_id = row["task_id"]
        config = json.loads(row["task_generation_config"])
        gt_urls = config.get("gt_url", [])
        
        if not gt_urls:
            print(f"  SKIP {task_id}: no GT URL")
            continue
        
        for gt_url in gt_urls:
            # Check if it's a flight or hotel URL
            if "/Flights-Search" in gt_url:
                flight_count += 1
                parsed = parse_flight_url(gt_url)
                url_type = "flight"
            elif "/Hotel-Search" in gt_url:
                hotel_count += 1
                parsed = parse_hotel_url(gt_url)
                url_type = "hotel"
            else:
                print(f"  UNKNOWN URL TYPE: {task_id}")
                failed += 1
                continue
            
            # Self-match: URL should match itself
            matcher = ExpediaUrlMatch(gt_url=gt_urls)
            match, details = matcher._urls_match(gt_url, gt_url)
            
            if match:
                passed += 1
                # Check specific fields
                if url_type == "flight":
                    infant = parsed.get("infantinlap", "")
                    if infant == "Y":
                        infant_count += 1
                    
                    # Verify critical fields are populated
                    issues = []
                    if not parsed["origin"]:
                        issues.append("missing origin")
                    if not parsed["destination"]:
                        issues.append("missing destination")
                    if not parsed["trip_type"]:
                        issues.append("missing trip_type")
                    if not parsed["cabin_class"]:
                        issues.append("missing cabin_class")
                    if not parsed["adults"]:
                        issues.append("missing adults")
                    
                    if issues:
                        print(f"  WARN {task_id}: {', '.join(issues)}")
                    else:
                        children = parsed.get("children", "")
                        ages = parsed.get("children_ages", [])
                        infant_str = f", infant={'Y' if infant=='Y' else 'N'}" if infant else ""
                        kids_str = f", {children}C [{','.join(ages)}]" if children else ""
                        print(f"  OK   {task_id}: {parsed['origin']}->{parsed['destination']} "
                              f"{parsed['trip_type']} {parsed['cabin_class']} "
                              f"{parsed['adults']}A{kids_str}{infant_str}")
                else:
                    dest = parsed.get("destination", "???")
                    adults = parsed.get("adults", "???")
                    rooms = parsed.get("rooms", "1")
                    sort_val = parsed.get("sort", "none")
                    children = parsed.get("children", "")
                    kids_str = f", {children}C" if children else ""
                    print(f"  OK   {task_id}: {dest} {adults}A {rooms}R{kids_str} sort={sort_val}")
            else:
                failed += 1
                print(f"  FAIL {task_id}: {details.get('mismatches', [])}")
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(rows)} tasks")
    print(f"Flights: {flight_count}, Hotels: {hotel_count}")
    print(f"Tasks with lap infant (infantinlap:Y): {infant_count}")
    print(f"{'='*60}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
