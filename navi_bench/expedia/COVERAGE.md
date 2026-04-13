# Expedia Coverage Documentation
## URL Patterns, Query Parameters & Verifier Reference
**expedia.com**
**Browser-Verified: April 2026**

---

## Overview

This document provides the authoritative reference for Expedia's URL structures, query parameter
encoding, and verifier matching logic. All patterns were validated through two dedicated browser
deep-dive sessions against the live production site (April 2026).

> **Important:** Expedia is a heavily JS-driven SPA. Results render dynamically and the URL
> encodes most search parameters. Flight URLs use compound `leg` parameters with multiple
> sub-fields separated by commas. Hotel URLs use standard query parameters but with unique
> children encoding.

---

## 1. Page Types

| Page Type | URL Pattern | Example |
| :--- | :--- | :--- |
| **Homepage** | `/` | `expedia.com` |
| **Flight Search** | `/Flights-Search?trip=...&leg1=...` | `/Flights-Search?trip=oneway&leg1=from:JFK,...` |
| **Hotel Search** | `/Hotel-Search?destination=...` | `/Hotel-Search?destination=New%20York&startDate=...` |
| **Car Rental** | `/Cars` | `/Cars` |
| **Packages** | `/Packages` | `/Packages` |
| **Cruises** | `/Cruises` | `/Cruises` |
| **Activities** | `/Things-To-Do` | `/Things-To-Do` |

### Detection Rules

| Rule | Pattern Match | Page Type |
| :--- | :--- | :--- |
| `/Flights-Search` in path | Flight search results | Flights |
| `/Hotel-Search` in path | Hotel search results | Hotels |
| `/Cars` in path | Car rental | Cars |
| `/Packages` in path | Flight+Hotel bundles | Packages |
| `/Cruises` in path | Cruise search | Cruises |
| `/Things-To-Do` in path | Activity/Tour search | Activities |

---

## 2. Flight Search URLs

### URL Anatomy

**One-way:**
```
https://www.expedia.com/Flights-Search?flight-type=on&mode=search&trip=oneway
  &leg1=from:New%20York,%20NY%20(JFK-John%20F.%20Kennedy%20Intl.),
         to:Los%20Angeles,%20CA%20(LAX-Los%20Angeles%20Intl.),
         departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT
  &options=cabinclass:economy
  &passengers=adults:2,children:2[10;5],infantinlap:N
```

**Round-trip:**
```
https://www.expedia.com/Flights-Search?trip=roundtrip
  &leg1=from:LAX,to:LHR,departure:4/16/2026TANYT,fromType:A,toType:A
  &leg2=from:LHR,to:LAX,departure:4/23/2026TANYT,fromType:A,toType:A
  &options=cabinclass:economy
  &passengers=adults:2,children:2[10;5],infantinlap:N
```

### Compound `leg` Parameter

The `leg1` and `leg2` parameters contain comma-separated `key:value` sub-fields:

| Sub-Field | Format | Example | Note |
| :--- | :--- | :--- | :--- |
| `from` | IATA or full city string | `JFK` or `New York, NY (JFK-...)` | Origin airport/city |
| `to` | IATA or full city string | `LAX` or `Los Angeles, CA (LAX-...)` | Destination airport/city |
| `departure` | `M/D/YYYYTANYT` | `4/16/2026TANYT` | `TANYT` = "Time Any Time" |
| `fromType` | `AIRPORT`, `A`, or `U` | `AIRPORT` | `AIRPORT`/`A` = specific, `U` = auto |
| `toType` | `AIRPORT`, `A`, or `U` | `AIRPORT` | Same as `fromType` |

> [!CAUTION]
> The `from` and `to` sub-fields can contain full city names with commas and parenthesized IATA
> codes: `New York, NY, United States of America (JFK-John F. Kennedy Intl.)`.
> The verifier extracts the 3-letter IATA code from within parentheses for comparison.

### Query Parameters

| Parameter | Key | Values / Format | Note |
| :--- | :--- | :--- | :--- |
| **Trip Type** | `trip` | `oneway`, `roundtrip`, `multicity` | Required |
| **Cabin Class** | `options` | `cabinclass:economy\|business\|first\|premium_economy` | Compound |
| **Passengers** | `passengers` | See §2.1 below | Compound |
| **Depart Date** | In `leg1` | `departure:M/D/YYYYTANYT` | Authoritative source |
| **Return Date** | In `leg2` | `departure:M/D/YYYYTANYT` | Authoritative source |

### §2.1 Passenger Encoding

Expedia uses **two formats** for children ages in the `passengers` parameter:

**Format A — Bracket-Semicolon (Live, Apr 2026):**
```
passengers=adults:2,children:2[10;5],infantinlap:N
```
Ages are semicolon-separated inside brackets, attached directly to the children count.

**Format B — Legacy:**
```
passengers=adults:2,children:2,childrenAge:5,8,infantinlap:N
```
Ages appear as comma-separated values after a separate `childrenAge:` key.

> [!IMPORTANT]
> The verifier normalizes both formats to the same internal representation.
> Ages are sorted and compared **order-independently**.

**Traveler Types:**

| Type | URL Encoding | Age Range |
| :--- | :--- | :--- |
| Adults | `adults:N` | 18+ |
| Children | `children:N[ages]` | 2–17 |
| Infants on Lap | `infantinlap:Y\|N` | Under 2 |
| Infants in Seat | Part of children count | Under 2 |

### Date Normalization

Expedia encodes the same date in up to 3 places with different formats:

| Parameter | Format | Example |
| :--- | :--- | :--- |
| `leg1` / `leg2` `departure` | `M/D/YYYYTANYT` | `4/16/2026TANYT` |
| `fromDate` / `toDate` | `M/D/YYYY` | `4/16/2026` |
| `d1` / `d2` | `YYYY-M-D` | `2026-4-16` |

> [!NOTE]
> The verifier normalizes all formats to `YYYY-MM-DD` (ISO 8601).
> Only the `leg` departure date is authoritative; `fromDate`/`d1` are redundant echoes.

### Cabin Class Reference

| UI Label | URL Value | Normalized Key |
| :--- | :--- | :--- |
| Economy | `cabinclass:economy` | `economy` |
| Premium Economy | `cabinclass:premium_economy` | `premium_economy` |
| Business | `cabinclass:business` | `business` |
| First | `cabinclass:first` | `first` |

---

## 3. Hotel Search URLs

### URL Anatomy

```
https://www.expedia.com/Hotel-Search?
  destination=New%20York%2C%20New%20York%2C%20United%20States%20of%20America
  &regionId=2621
  &latLong=40.712843%2C-74.005966
  &flexibility=0_DAY
  &d1=2026-04-16&startDate=2026-04-16
  &d2=2026-04-19&endDate=2026-04-19
  &adults=2
  &rooms=1
  &sort=RECOMMENDED
  [&children=1_10,1_5]
```

### Query Parameters

| Parameter | Key | Format | Note |
| :--- | :--- | :--- | :--- |
| **Destination** | `destination` | URL-encoded city string | Display name |
| **Region** | `regionId` | Numeric ID | Authoritative location identifier |
| **Check-in** | `startDate` / `d1` | `YYYY-MM-DD` | Both present in live URLs |
| **Check-out** | `endDate` / `d2` | `YYYY-MM-DD` | Both present in live URLs |
| **Adults** | `adults` | Integer or CSV | `2` or `2,1,1` for multi-room |
| **Rooms** | `rooms` | Integer | Inferred from `adults` list length |
| **Children** | `children` | See §3.1 below | |
| **Sort** | `sort` | See §3.3 below | |

### §3.1 Children Encoding

Expedia uses **two formats** for children in hotel URLs:

**Format A — RoomIndex_Age (Live, Apr 2026):**
```
children=1_10,1_5
```
Each entry is `RoomIndex_Age`. Both children are in Room 1, aged 10 and 5.
For multi-room: `children=1_10,2_5` places children in Rooms 1 and 2 respectively.

**Format B — Legacy:**
```
children=2&childrenAges=10,5
```
Separate count in `children`, ages in `childrenAges`.

> [!IMPORTANT]
> The verifier extracts ages from both formats and compares **order-independently**.
> Room index is used only for age extraction — per-room placement is not validated.

### §3.2 Multi-Room Encoding

```
adults=2,1,1    → 3 rooms, total 4 adults (2+1+1)
adults=2,2      → 2 rooms, total 4 adults (2+2)
adults=2        → 1 room, 2 adults
```

> [!WARNING]
> The `rooms` parameter may remain `1` in the URL even for multi-room searches.
> The verifier derives the true room count from the length of the `adults` comma-separated list.

### §3.3 Sort Options

| UI Label | URL Value |
| :--- | :--- |
| Recommended | `RECOMMENDED` |
| Price: low to high | `PRICE_LOW_TO_HIGH` |
| Price: high to low | `PRICE_HIGH_TO_LOW` |
| Distance from downtown | `DISTANCE_FROM_LANDMARK` |
| Guest rating + our picks | `GUEST_RATING` |
| Star rating | `STAR_RATING_HIGHEST_FIRST` |

> [!NOTE]
> Legacy values `REVIEW` and `DISTANCE` are accepted by the verifier for backward
> compatibility but are not emitted by the current live site.

### §3.4 Known Region IDs

| City | `regionId` | | City | `regionId` |
| :--- | :---: | --- | :--- | :---: |
| New York | 2621 | | San Francisco | 5971 |
| Los Angeles | 2342 | | Chicago | 4497 |
| London | 2114 | | Miami | 6146 |
| Paris | 2734 | | Barcelona | 761 |
| Tokyo | 1962 | | Rome | 4284 |
| Dubai | 4846 | | Bangkok | 3625 |
| Singapore | 6139 | | Toronto | 1585 |
| Sydney | 1785 | | Amsterdam | 712 |
|  |  | | Berlin | 508 |

> [!NOTE]
> `regionId` is the authoritative location identifier. The `destination` string
> is a display name only. When matching, `regionId` takes absolute precedence.
> If no `regionId` is present, the verifier falls back to fuzzy destination string matching.

---

## 4. Domain Variations

The verifier accepts **all** valid Expedia regional domains. URL path and parameter
structure is consistent across all variants.

| Domain | Region | | Domain | Region |
| :--- | :--- | --- | :--- | :--- |
| `expedia.com` | Primary (US) | | `expedia.co.in` | India |
| `www.expedia.com` | Standard | | `expedia.co.jp` | Japan |
| `expedia.co.uk` | United Kingdom | | `expedia.com.au` | Australia |
| `expedia.de` | Germany | | `expedia.ca` | Canada |
| `expedia.fr` | France | | `expedia.co.kr` | South Korea |

---

## 5. Ignored Parameters

These parameters encode session state, UI hints, or tracking data.
They do **not** affect search semantics and are excluded from comparison.

### Flights
`flight-type`, `mode`, `fromType`, `toType`, `fromDate`, `toDate`, `d1`, `d2`,
`infantinlap`, `filters`, `locale`, `currency`, `siteid`, `rfrr`, `tpid`, `eapid`,
`utm_source`, `utm_medium`, `utm_campaign`, `gclid`, `msclkid`, `semcid`, `semdtl`,
`selectedOfferToken`, `newFlightSearch`, `previousDateful`

### Hotels
`locale`, `currency`, `siteid`, `rfrr`, `tpid`, `eapid`, `utm_source`,
`latLong`, `theme`, `userIntent`, `searchId`, `propertyId`, `gclid`,
`msclkid`, `pwaDialogNested`, `mapBounds`, `neighborhood`, `flexibility`

---

## 6. Verifier Matching Rules

### Core Comparison Logic

| Field | Normalization | Comparison |
| :--- | :--- | :--- |
| Origin / Destination | IATA extraction from city strings | Case-insensitive exact |
| Dates | All formats → `YYYY-MM-DD` | Exact string |
| Cabin Class | Alias resolution (e.g. `premiumeconomy` → `premium_economy`) | Exact string |
| Adults / Children count | Raw string | Exact string |
| Children ages | Sorted list | Order-independent |
| Hotel destination | URL-decoded, lowercased | Substring containment |
| Hotel `regionId` | Raw string | Exact (takes precedence over destination) |
| Hotel sort | Alias resolution | Exact string |
| Trip type | Raw string | Exact string |
| Hotel rooms | Derived from `adults` CSV length | Exact string |

### Precedence Rules

1. If ground truth specifies a field and agent omits it → **mismatch**
2. If ground truth omits a field (e.g., no `passengers`) → agent value is **ignored** (pass)
3. Both `regionId` and destination present → `regionId` match is **sufficient**
4. Children ages from either bracket or legacy format → **normalized before comparison**
5. First successful match across multi-GT URLs → **score = 1.0** (OR semantics)

---

## 7. Test & Benchmark Coverage

### Unit Tests

**122 tests** across 17 test classes, covering:

| Category | Tests | Focus |
| :--- | :---: | :--- |
| Page Type Detection | 10 | Path-based routing |
| Date Normalization | 7 | 3 date format variants |
| IATA Code Extraction | 7 | Full city string → 3-letter code |
| Leg Parameter Parsing | 2 | Compound `key:value` extraction |
| Flight URL Parsing | 6 | Full parse pipeline |
| Hotel URL Parsing | 5 | Standard query params |
| Cabin Class Normalization | 6 | 4 cabin classes + aliases |
| Hotel Sort Normalization | 4 | 6 sort values |
| Flight Matching | 14 | All mismatch scenarios |
| Hotel Matching | 15 | Region, destination, sort, children |
| Domain Validation | 11 | 20+ regional domains |
| Async Lifecycle | 8 | `reset` → `update` → `compute` |
| Multi-GT URLs | 3 | OR semantics |
| Edge Cases | 3 | Cross-page type, empty URLs |
| Bracket-Semicolon Children | 7 | `children:2[10;5]` format |
| Live Browser-Verified URLs | 4 | Actual captured Expedia URLs |
| Hotel Browser-Verified | 12 | RoomIndex_Age, multi-room, sorts |

### Benchmark Dataset

**70 tasks** in `expedia_benchmark_tasks.csv` — **all hard difficulty**:

Tasks are designed with advanced difficulty strategies to challenge AI models:

| Category | Count | Difficulty Strategy |
| :--- | :---: | :--- |
| Buried Traveler Counts | 8 | Adults/children hidden in prose ("my wife, myself, our twins") |
| Indirect Cabin Class | 8 | Natural language cabin refs ("flatbed seats" = business) |
| Tricky Children + Red Herrings | 8 | Ages in narrative, irrelevant details mixed in |
| Complex Combinations | 8 | Multiple tricky elements combined (airport names + buried pax) |
| Natural Language Sort | 6 | Sort described naturally ("what guests liked most" = GUEST_RATING) |
| Multi-Room Tricky | 6 | Children distributed across rooms in narrative prose |
| Red Herring Hotels | 10 | Extra details that don't affect URL (loyalty status, room type) |
| Multi-GT Hotels | 8 | 2 valid destination URL encodings per task |
| Ultra-Complex | 8 | Maximum difficulty — all tricks combined (11-person groups, lap infants) |

---

## Appendix: Live URL Examples

### Flight — One-way Business, Full City Strings
```
https://www.expedia.com/Flights-Search?flight-type=on&mode=search&trip=oneway
  &leg1=from:San%20Francisco,%20CA,%20United%20States%20of%20America%20
    (SFO-San%20Francisco%20Intl.),
    to:Tokyo,%20Japan%20(NRT-Narita%20Intl.),
    departure:4/16/2026TANYT,fromType:AIRPORT,toType:AIRPORT
  &options=cabinclass:business
  &passengers=adults:2,infantinlap:N
```

### Flight — Round-trip with Children, Bracket-Semicolon
```
https://www.expedia.com/Flights-Search?trip=roundtrip
  &leg1=from:Los%20Angeles,%20CA%20(LAX-Los%20Angeles%20Intl.),
    to:London%20(LHR-Heathrow),
    departure:4/16/2026TANYT,fromType:A,toType:A
  &leg2=from:London%20(LHR-Heathrow),
    to:Los%20Angeles,%20CA%20(LAX-Los%20Angeles%20Intl.),
    departure:4/23/2026TANYT,fromType:A,toType:A
  &options=cabinclass:economy
  &passengers=adults:2,children:2[10;5],infantinlap:N
```

### Hotel — Basic with Region ID
```
https://www.expedia.com/Hotel-Search?
  destination=New%20York%2C%20New%20York%2C%20United%20States%20of%20America
  &regionId=2621&latLong=40.712843%2C-74.005966
  &flexibility=0_DAY
  &d1=2026-04-16&startDate=2026-04-16
  &d2=2026-04-19&endDate=2026-04-19
  &adults=2&rooms=1&sort=RECOMMENDED
```

### Hotel — Children with RoomIndex_Age
```
https://www.expedia.com/Hotel-Search?
  destination=London%2C%20England%2C%20United%20Kingdom
  &regionId=2114
  &d1=2026-04-16&d2=2026-04-19
  &adults=2&rooms=1
  &children=1_10,1_5
```

### Hotel — Multi-Room
```
https://www.expedia.com/Hotel-Search?
  destination=London%2C%20England%2C%20United%20Kingdom
  &regionId=2114
  &d1=2026-04-16&d2=2026-04-19
  &adults=2,1,1&rooms=1
  &children=1_10,1_5
```
