# Skyscanner Coverage Documentation
## URL Patterns, Query Parameters & Verifier Reference
**skyscanner.net | skyscanner.com**
**Browser-Verified: March 2026**

---

## Overview
This document outlines Skyscanner's page types, URL structures, and search parameters
for flights, hotels, and car hire. All patterns have been browser-verified.

> **Important:** Skyscanner is heavily JS-driven. Results render dynamically.
> The URL encodes most search parameters but **not** all filters — flight
> sorting (Best / Cheapest / Fastest) is DOM-only.

---

## 1. PAGE TYPES

| Page Type | URL Pattern | Example |
| :--- | :--- | :--- |
| **Homepage** | `/` | skyscanner.net |
| **Flight Search** | `/transport/flights/{org}/{dst}/{YYMMDD}[/{YYMMDD}]` | `/transport/flights/jfk/lax/260420/` |
| **Hotel Search** | `/hotels/search?entity_id=…` | `/hotels/search?entity_id=27544008` |
| **Car Hire** | `/carhire/results/{pickup}/{dropoff}/{ISO}/{ISO}[/{age}]` | `/carhire/results/BCN/BCN/2026-04-20T10:00/…/30` |
| **Browse View** | `/transport/flights-from/{code}/` | `/transport/flights-from/edi/` |
| **Multi-City** | `/transport/d/{org}/{YYMMDD}/{dst}/…` | `/transport/d/jfk/260420/lax/…` |

### Page Type Detection

| Rule | Pattern | Page Type |
| :--- | :--- | :--- |
| `/transport/d/` in path | Multi-leg segments | Multi-City |
| `/transport/flights-from/` in path | Origin-only | Browse View |
| `/transport/flights/` in path | Origin + Dest + Date | Flight Search |
| `/hotels/` in path | `entity_id` param | Hotel Search |
| `/carhire/` in path | Location + datetime | Car Hire |

---

## 2. FLIGHT SEARCH URLs

### URL Anatomy

**One-way:**
```
https://www.skyscanner.net/transport/flights/jfk/lax/260420/?adultsv2=1&cabinclass=economy&rtn=0
```

**Round-trip:**
```
https://www.skyscanner.net/transport/flights/jfk/lax/260420/260425/?adultsv2=2&cabinclass=business&rtn=1
```

### Path Components

| Component | Format | Example | Note |
| :--- | :--- | :--- | :--- |
| **Origin** | 2-5 letter code | `jfk` | IATA / City code, lowercase |
| **Destination** | 2-5 letter code | `lax` | IATA / City code, lowercase |
| **Depart Date** | **YYMMDD** | `260420` | ⚠️ NOT YYYYMMDD |
| **Return Date** | **YYMMDD** | `260425` | Optional (round-trip only) |

> [!CAUTION]
> Flight dates use **6-digit YYMMDD** format (e.g., `260420` = April 20, 2026),
> NOT the 8-digit YYYYMMDD format stated in some older documentation.

### Query Parameters

| Filter | Param | Values / Format | Note |
| :--- | :--- | :--- | :--- |
| **Trip Type** | `rtn` | `0` (one-way) or `1` (round-trip) | |
| **Adults** | `adultsv2` | Integer (default: 1) | |
| **Children** | `childrenv2` | Pipe-separated ages: `5\|8` | |
| **Cabin Class** | `cabinclass` | `economy`, `premiumeconomy`, `business`, `first` | |
| **Stops** | `stops` | Exclusion format: `!oneStop,!twoPlusStops` | ⚠️ Uses `!` prefix |
| **Airlines** | `airlines` | Internal numeric IDs: `-32593,-32596` | ⚠️ NOT IATA codes |
| **Alliances** | `alliances` | `Star Alliance`, `oneworld`, `SkyTeam` | ⚠️ May contain spaces |
| **Prefer Directs** | `preferdirects` | `true` / `false` | Legacy fallback |

### Stops Filter Details

The `stops` parameter uses **exclusion logic** with `!` prefix:

| UI Selection | URL Value | Meaning |
| :--- | :--- | :--- |
| Direct only | `stops=!oneStop,!twoPlusStops` | Exclude 1-stop and 2+ stops |
| Up to 1 stop | `stops=!twoPlusStops` | Exclude 2+ stops only |
| Any stops | (param absent) | No exclusion |

---

## 3. HOTEL SEARCH URLs

### URL Anatomy
```
https://www.skyscanner.net/hotels/search?entity_id=27544008&checkin=2026-04-20&checkout=2026-04-25&adults=2&rooms=1&sort=price
```

### Query Parameters

| Component | Param | Format | Note |
| :--- | :--- | :--- | :--- |
| **Location** | `entity_id` | Numeric ID | Skyscanner internal ID |
| **Check-in** | `checkin` | `YYYY-MM-DD` | |
| **Check-out** | `checkout` | `YYYY-MM-DD` | |
| **Adults** | `adults` | Integer | Default: 2 |
| **Rooms** | `rooms` | Integer | Default: 1 |
| **Sort** | `sort` | See below | |

### Sort Options

| Sort | Value | Note |
| :--- | :--- | :--- |
| Price (low→high) | `price` | |
| Price (high→low) | `-price` | |
| Distance | `distance` | |
| Rating (high→low) | `-hotel_rating` | |

---

## 4. CAR HIRE URLs

### URL Anatomy
```
https://www.skyscanner.net/carhire/results/95565085/95565085/2026-04-20T10:00/2026-04-25T10:00/30
```

### Path Components

| Component | Format | Example | Note |
| :--- | :--- | :--- | :--- |
| **Pickup Location** | Internal numeric ID | `95565085` | ⚠️ NOT IATA codes |
| **Dropoff Location** | Internal numeric ID | `95565085` | Same or different |
| **Pickup Datetime** | `YYYY-MM-DDTHH:MM` | `2026-04-20T10:00` | ISO 8601 |
| **Dropoff Datetime** | `YYYY-MM-DDTHH:MM` | `2026-04-25T10:00` | ISO 8601 |
| **Driver Age** | Integer | `30` | Optional, 21–99 |

> [!CAUTION]
> Car hire locations use **internal numeric IDs**, NOT IATA airport codes.
> Example: Barcelona = `95565085`, London Heathrow = `95565050`,
> London Gatwick = `95565051`.

---

## 5. DOM-ONLY FILTERS (Not in URL)

| Page | Filter | Detection Method |
| :--- | :--- | :--- |
| **Flights** | Sort (Best / Cheapest / Fastest) | Parse active tab via `aria-selected` |
| **Flights** | Departure/arrival time sliders | DOM slider state |
| **Car Hire** | Transmission (Auto/Manual) | DOM checkbox state |
| **Car Hire** | Car type (Small/Medium/Large) | DOM checkbox state |
| **Car Hire** | Supplier selection | DOM checkbox state |

---

## 6. DOMAIN VARIATIONS

| Domain | Type |
| :--- | :--- |
| `skyscanner.net` | Primary |
| `skyscanner.com` | Primary |
| `www.skyscanner.net` | Standard |
| `skyscanner.co.in` | India |
| `skyscanner.co.uk` | UK |
| `skyscanner.de` | Germany |
| `skyscanner.fr` | France |
| `skyscanner.jp` | Japan |
| `skyscanner.com.au` | Australia |

> The verifier accepts ALL valid regional domains. The URL path and
> parameter structure is consistent across all domains.

---

## 7. VERIFIER NOTES

* **Date format is YYMMDD** for flights — this is the most critical difference.
* **Stops use exclusion `!` prefix** — `!oneStop` means exclude 1-stop flights.
* **Airlines use numeric IDs** — match by exact ID, NOT by airline name.
* **Alliances may have spaces** — `Star Alliance` (with space), `oneworld`, `SkyTeam`.
* **Flight sort is DOM-only** — URL `sortby` param is unreliable; use JS scraper.
* **Hotel sort IS in the URL** — `sort=price`, `sort=-hotel_rating`.
* **Car hire locations use numeric IDs** — NOT IATA codes (e.g., BCN = `95565085`).
* **Car hire filters are DOM-only** — transmission, car type, supplier.
* **Bot detection is aggressive** — use direct search URLs, not homepage navigation.
