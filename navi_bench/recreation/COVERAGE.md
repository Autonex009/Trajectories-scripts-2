# Recreation.gov URL Evaluator Coverage

This module implements a URL-based evaluator for Recreation.gov search tasks.
It checks whether the final URL is on `www.recreation.gov/search` and whether
the required filter query parameters are present.

Supported filters:
- Location & Proximity: lat, lng, and radius.
- Date Range: checkin and checkout dates.
- Inventory Types: Camping, Day Use, Tickets & Tours, and Permits (inventory_type).
- Campsite Specifics: Tent, RV/Motorhome, and Lodging (campsite_type).
- Vehicle & Equipment: vehicle-length.
- Site Amenities: Electric vs. Non-Electric (electricity) and features like Waterfront or Showers (amenities).
- Key Characteristics: Accessibility and Pet Friendly (key_characteristics).
- Group Logistics: group-size and availability types like fcfs (First-Come, First-Served).

This evaluator is a `UrlEvaluator` style implementation. It does not scrape or
validate DOM content; it only verifies URL query parameters.

The structure follows the same modular pattern used by other site-specific
evaluators in [`navi_bench/trip/`]and [`navi_bench/seatgeek/`]
