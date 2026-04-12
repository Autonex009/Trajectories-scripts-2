# Recreation.gov URL Evaluator Coverage

This module implements a URL-based evaluator for Recreation.gov search tasks.
It checks whether the final URL is on `www.recreation.gov/search` and whether
the required filter query parameters are present.

This evaluator is a `UrlEvaluator` style implementation. It does not scrape or
validate DOM content; it only verifies URL query parameters.

The structure follows the same modular pattern used by other site-specific
evaluators in [`navi_bench/trip/`]and [`navi_bench/seatgeek/`]

# Recreation.gov Filter Parameters

This document provides a structured reference for the query parameters used on Recreation.gov.

## 1. Core Search Parameters
Define the primary location, radius, and date range for your search.

* [cite_start]**Location (Query):** `q=San%20Francisco%2C%20California` [cite: 1]
* [cite_start]**Latitude:** `lat=37.77923800000000` [cite: 1]
* [cite_start]**Longitude:** `lng=-122.41935900000000` [cite: 1]
* [cite_start]**Search Radius:** `radius=100` [cite: 1]
* [cite_start]**Check-in Date:** `checkin=04%2F08%2F2026` [cite: 1]
* [cite_start]**Check-out Date:** `checkout=04%2F11%2F2026` [cite: 1]

---

## 2. Booking Types (`inventory_type`)
Select the broad category of the reservation or interest point.

* [cite_start]**Camping:** `inventory_type=camping` [cite: 1]
* [cite_start]**Day Use:** `inventory_type=day%20use` [cite: 1]
* [cite_start]**Tickets & Tours:** `inventory_type=tickets%20%26%20tours` [cite: 1]
* [cite_start]**Permits:** `inventory_type=permits` [cite: 1]
* [cite_start]**Points of Interest:** `inventory_type=points%20%20of%20interest` [cite: 1]
* [cite_start]**Venues:** `inventory_type=venues` [cite: 1]
* [cite_start]**Rec Areas:** `inventory_type=rec%20areas` [cite: 1]

---

## 3. Camping Details
Specific filters for campsite requirements and equipment.

* **Campsite Type:**
    * [cite_start]**Tent:** `campsite_type=tent` [cite: 2]
    * [cite_start]**RV / Motorhome / Trailer:** `campsite_type=rv%2F%20motorhome%2F%20trailer` [cite: 2]
    * [cite_start]**Lodging (Cabins/Yurts/Lookouts):** `campsite_type=lodging%20(cabins%2Fyurts%2Flookouts)` [cite: 2]
* [cite_start]**Vehicle Length (0-99):** `vehicle-length=5` [cite: 2]
* **Electricity:**
    * [cite_start]**Electric Site:** `electricity=electric%20site` [cite: 2]
    * [cite_start]**Non-Electric Site:** `electricity=non-electric%20site` [cite: 2]
* **Electrical Hookup (`electrical_hookup`):**
    * [cite_start]**100 Amp:** `electrical_hookup=100%20amp` [cite: 2]
    * [cite_start]**50 Amp:** `electrical_hookup=50%20amp` [cite: 2]
    * [cite_start]**30 Amp:** `electrical_hookup=30%20amp` [cite: 2]
    * [cite_start]**20 Amp:** `electrical_hookup=20%20amp` [cite: 2]
    * [cite_start]**15 Amp:** `electrical_hookup=15%20amp` [cite: 2]
    * [cite_start]**5 Amp:** `electrical_hookup=5%20amp` [cite: 2]
* [cite_start]**Group Size (0-99):** `group-size=2` [cite: 3]

---

## 4. Amenities & Site Characteristics
Narrow down your search by specific site features.

* **Amenities:**
    * [cite_start]**Water Hookup:** `amenities=water%20hookup` [cite: 3]
    * [cite_start]**Waterfront:** `amenities=waterfront` [cite: 3]
    * [cite_start]**Sewer Hookup:** `amenities=sewer%20hookup` [cite: 3]
    * [cite_start]**Flush Toilet:** `amenities=flush%20toilet` [cite: 3]
    * [cite_start]**Electricity Hookup:** `amenities=electricity%20hookup` [cite: 3]
    * [cite_start]**Fire Pit:** `amenities=fire%20pit` [cite: 3]
    * [cite_start]**Showers:** `amenities=showers` [cite: 3]
    * [cite_start]**Shade:** `amenities=shade` [cite: 3]
* **Key Characteristics:**
    * [cite_start]**Accessibility:** `key_characteristics=accessibility` [cite: 3]
    * [cite_start]**Pet Friendly:** `key_characteristics=pet%20friendly` [cite: 3]
    * [cite_start]**Group Site:** `key_characteristics=group%20site` [cite: 3]
* **Site Access:**
    * [cite_start]**Walk/Hike To:** `access=Walk%2FHike%20To` [cite: 3]
    * [cite_start]**Boat-in:** `access=Boat-in` [cite: 3]
    * [cite_start]**Pull Through Driveway:** `access=Pull%20Through%20Driveway` [cite: 3]
* **Special Site Types:**
    * [cite_start]**Picnic:** `special_site=Picnic` [cite: 3]
    * [cite_start]**Shelter:** `special_site=Shelter` [cite: 3]
    * [cite_start]**Boat:** `special_site=Boat` [cite: 3]
    * [cite_start]**Equestrian:** `special_site=Equestrian` [cite: 3]
* **First-Come, First-Served (FCFS):**
    * [cite_start]**Only Show FCFS:** `fcfs=only%20show%20first-come%20first-served` [cite: 3]
    * [cite_start]**Scan & Pay (Mobile App):** `fcfs=credit%20%2F%20debit%20card%20only` [cite: 3]

---

## 5. Tickets & Tours
Filters for guided tours and timed entry.

* **Start Time (`tour-time`):**
    * [cite_start]**Early Morning (Midnight - 7:59 AM):** `tour-time=early%20morning` [cite: 3]
    * [cite_start]**Morning (8 AM - 11:59 AM):** `tour-time=morning` [cite: 3]
    * [cite_start]**Early Afternoon (12 PM - 2:59 PM):** `tour-time=early%20afternoon` [cite: 3]
    * [cite_start]**Afternoon (3 PM - 5:59 PM):** `tour-time=afternoon` [cite: 3]
    * [cite_start]**Evening (6 PM - 8:59 PM):** `tour-time=evening` [cite: 3]
    * [cite_start]**Late Night (9 PM - 11:59 PM):** `tour-time=late%20night` [cite: 3]
* **Tour Types (`tour-type`):**
    * [cite_start]**Historic:** `tour-type=historic%20tour` [cite: 3]
    * [cite_start]**Nature:** `tour-type=nature%20tour` [cite: 3]
    * [cite_start]**Cave:** `tour-type=cave%20tour` [cite: 3]
    * [cite_start]**Nature Hike:** `tour-type=nature%20hike` [cite: 3]
    * [cite_start]**Combo:** `tour-type=combo%20tour` [cite: 3]
    * [cite_start]**Cliff Dwelling:** `tour-type=cliff%20dwelling%20tour` [cite: 3]
    * [cite_start]**Boat:** `tour-type=boat%20tour` [cite: 3]
    * [cite_start]**Natural/Cultural Hike:** `tour-type=natural%20and%20cultural%20hike` [cite: 3]
    * [cite_start]**Hike:** `tour-type=hike` [cite: 3]
    * [cite_start]**Movie Tour:** `tour-type=movie%20tour` [cite: 3]

---

## 6. Federal Agencies (`agency`)
Filter by the agency managing the location.

* [cite_start]**Bureau of Land Management:** `agency=bureau%20of%20land%20management` [cite: 4]
* [cite_start]**Presidio Trust:** `agency=presidio%20trust` [cite: 4]
* [cite_start]**Bureau of Reclamation:** `agency=bureau%20of%20reclamation` [cite: 4]
* [cite_start]**US Army Corps of Engineers:** `agency=us%20army%20corps%20of%20engineers` [cite: 4]
* [cite_start]**National Archives:** `agency=national%20archives%20and%20records%20administration` [cite: 4]
* [cite_start]**Fish and Wildlife Service:** `agency=fish%20and%20wildlife%20service` [cite: 4]
* [cite_start]**National Park Service:** `agency=national%20park%20service` [cite: 4]
* [cite_start]**Forest Service:** `agency=forest%20service` [cite: 4]
* [cite_start]**Naval District Washington:** `agency=naval%20district%20washington` [cite: 4]
* [cite_start]**NOAA:** `agency=national%20oceanic%20and%20atmospheric%20administration` [cite: 4]
* [cite_start]**National Historic Landmark:** `agency=national%20historic%20landmark` [cite: 4]
* [cite_start]**National Register of Historic Places:** `agency=national%20register%20of%20historic%20places` [cite: 4]

---

## 7. Activities Nearby (`activity`)
Filter locations by the activities available in the vicinity.

* [cite_start]**Auto Touring:** `activity=auto%20touring` [cite: 4]
* [cite_start]**Biking:** `activity=biking` [cite: 4]
* [cite_start]**Boating:** `activity=boating` [cite: 4]
* [cite_start]**Camping:** `activity=camping` [cite: 4]
* [cite_start]**Climbing:** `activity=climbing` [cite: 4]
* [cite_start]**Day Use Area:** `activity=day%20use%20area` [cite: 4]
* [cite_start]**Diving:** `activity=diving` [cite: 4]
* [cite_start]**Documentary Site:** `activity=documentary%20site` [cite: 4]
* [cite_start]**Environmental Education:** `activity=environmental%20education` [cite: 4]
* [cite_start]**Fire Lookouts/Cabins:** `activity=fire%20lookouts%2Fcabins%20overnight` [cite: 4]
* [cite_start]**Fish Hatchery:** `activity=fish%20hatchery` [cite: 4]
* [cite_start]**Fish Viewing:** `activity=fish%20viewing%20site` [cite: 4]
* [cite_start]**Fishing:** `activity=fishing` [cite: 4]
* [cite_start]**Hiking:** `activity=hiking` [cite: 4]
* [cite_start]**Historic/Cultural Site:** `activity=historic%20%26%20cultural%20site` [cite: 4]
* [cite_start]**Horse Camping:** `activity=horse%20camping` [cite: 4]
* [cite_start]**Horseback Riding:** `activity=horseback%20riding` [cite: 4]
* [cite_start]**Hotel (FS Owned):** `activity=hotel%2Flodge%2Fresort%20fs%20owned` [cite: 4]
* [cite_start]**Hotel (Private):** `activity=hotel%2Flodge%2Fresort%20privately%20owned` [cite: 4]
* [cite_start]**Hunting:** `activity=hunting` [cite: 4]
* [cite_start]**Information Site:** `activity=information%20site` [cite: 4]
* [cite_start]**Interpretive Programs:** `activity=interpretive%20programs` [cite: 4]
* [cite_start]**Observation Site:** `activity=observation%20site` [cite: 4]
* [cite_start]**Off Highway Vehicle:** `activity=off%20highway%20vehicle` [cite: 4]
* [cite_start]**Other Rec Concession:** `activity=other%20recreation%20concession%20site` [cite: 4]
* [cite_start]**Paddling:** `activity=paddling` [cite: 4]
* [cite_start]**Photography:** `activity=photography` [cite: 4]
* [cite_start]**Picnicking:** `activity=picnicking` [cite: 4]
* [cite_start]**Playground/Sport Site:** `activity=playground%20park%20specialized%20sport%20site` [cite: 4]
* [cite_start]**Recreational Shooting:** `activity=recreational%20shooting` [cite: 4]
* [cite_start]**Recreational Vehicles:** `activity=recreational%20vehicles` [cite: 4]
* [cite_start]**Snorkeling:** `activity=snorkeling` [cite: 4]
* [cite_start]**Snowpark:** `activity=snowpark` [cite: 4]
* [cite_start]**Swimming:** `activity=swimming` [cite: 4]
* [cite_start]**Visitor Center:** `activity=visitor%20center` [cite: 4]
* [cite_start]**Water Sports:** `activity=water%20sports` [cite: 4]
* [cite_start]**Wilderness:** `activity=wilderness` [cite: 4]
* [cite_start]**Wildlife Viewing:** `activity=wildlife%20viewing` [cite: 4]
* [cite_start]**Winter Sports:** `activity=winter%20sports` [cite: 4]

---

## 8. Sorting (`sort`)
Determine the order of your results.

* [cite_start]**Best Match:** `sort=score` [cite: 4]
* [cite_start]**Distance:** `sort=distance` [cite: 4]
* [cite_start]**Rating:** `sort=average_rating` [cite: 4]
* [cite_start]**Price:** `sort=price%20asc` [cite: 4]
* [cite_start]**Mobile Coverage:** `sort=aggregate_cell_coverage` [cite: 4]
