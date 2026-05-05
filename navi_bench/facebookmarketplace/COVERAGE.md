# Facebook Marketplace Coverage Documentation
## URL Patterns, Query Parameters & Verifier Reference
**facebook.com/marketplace**
**Browser-Verified: April 2026**

---

## Overview

This document provides the authoritative reference for Facebook Marketplace's URL structures, query parameter
encoding, and verifier matching logic. All patterns were validated through dedicated browser
deep-dive sessions against the live production site (April 2026).

> **Important:** Facebook Marketplace is a modern JavaScript SPA (React-based). Search results render
> dynamically and the URL encodes search filters as query parameters on various Marketplace paths.
> Marketplace supports three core verticals: **General Goods**, **Vehicles**, and **Property Rentals**,
> each with vertical-specific filter parameters and subcategory paths.

> [!NOTE]
> **Authentication:** Facebook Marketplace is partially accessible without login. Browsing,
> searching, and applying filters work for unauthenticated users. However, a persistent
> **"See more on Facebook"** login modal appears after a few interactions, overlaying the
> results. The verifier does NOT require authentication — it only compares URL parameters.
> The login modal is a cosmetic overlay and does NOT affect the URL state.

> [!CAUTION]
> **These URL patterns are NOT officially documented by Meta.** They are reverse-engineered
> from browser observation and community research. Facebook may change parameter names,
> values, or behavior without notice. All patterns documented here were browser-verified
> in April 2026 but may drift over time.

---

## 1. Page Types

| Page Type | URL Pattern | Example |
| :--- | :--- | :--- |
| **Homepage** | `/marketplace/` | `facebook.com/marketplace/` |
| **City Browse** | `/marketplace/{city_slug}/` | `/marketplace/sanfrancisco/` |
| **Search Results** | `/marketplace/{city_slug}/search/?query=...` | `/marketplace/newyork/search/?query=couch` |
| **Search (no city)** | `/marketplace/search/?query=...` | `/marketplace/search/?query=laptop` |
| **Category Browse** | `/marketplace/category/{category_slug}/` | `/marketplace/category/vehicles/` |
| **Vehicle Subcategory** | `/marketplace/category/{vehicle_type}/` | `/marketplace/category/cars/` |
| **Individual Listing** | `/marketplace/item/{numeric_id}/` | `/marketplace/item/1234567890/` |
| **Create Listing** | `/marketplace/create/` | `/marketplace/create/` |

### Detection Rules

| Rule | Pattern Match | Page Type |
| :--- | :--- | :--- |
| `/marketplace/{city}/search/` in path | Search results with city | Search |
| `/marketplace/search/` in path | Search results (no city) | Search |
| `/marketplace/category/{slug}/` in path | Category browse | Category |
| `/marketplace/item/{id}/` in path | Individual listing | Listing |
| `/marketplace/create/` in path | Create listing | Account |
| `/marketplace/{city}/` (no search) | City browse | Browse |
| `/marketplace/` only | Homepage | Landing |

> [!IMPORTANT]
> The verifier processes URLs containing `/marketplace/` and compares search parameters.
> Individual listing pages (`/marketplace/item/...`) will not match search GT URLs.
> Category pages (`/marketplace/category/...`) are matched by category slug comparison.

---

## 2. Homepage & Sidebar Navigation

### Homepage Layout (Browser-Verified Apr 2026)

```
┌──────────────────────────────────────────────────────────────────┐
│  facebook                              [Email] [Password] Login  │
├──────────────────────────────────────────────────────────────────┤
│  Marketplace                    Today's picks      📍 San Francisco │
│  ⚙                                                  · 65 km     │
│  🔍 Search Marketplace          ┌──────┬──────┬──────┬──────┐   │
│                                  │ IMG  │ IMG  │ IMG  │ IMG  │   │
│  🏠 Browse all                  │$FREE │$8000 │FREE  │$3000 │   │
│  👤 Your account                │Kayak │Trail │Fridge│BMW   │   │
│  + Create new listing           │Haywd │Valle │Fremt │Dubln │   │
│                                  └──────┴──────┴──────┴──────┘   │
│  Location                                                        │
│  San Francisco, California                                       │
│                                                                   │
│  Categories                                                       │
│  🚗 Vehicles                                                     │
│  💰 Property for rent                                            │
│  📋 Classifieds                                                  │
├──────────────────────────────────────────────────────────────────┤
│  Log in or sign up for Facebook to connect with friends...       │
│  [Log in]          or          [Create new account]              │
└──────────────────────────────────────────────────────────────────┘
```

### Sidebar Categories

The left sidebar on the homepage shows three primary categories:

| Icon | Label | URL Path |
| :--- | :--- | :--- |
| 🚗 | **Vehicles** | `/marketplace/category/vehicles/` |
| 💰 | **Property for rent** | `/marketplace/category/propertyrentals/` |
| 📋 | **Classifieds** | `/marketplace/category/classifieds/` |

> [!NOTE]
> Additional subcategories (Electronics, Furniture, Apparel, etc.) appear when
> searching or within the category hierarchy, but only these three are visible
> on the unauthenticated homepage sidebar.

---

## 3. Search URLs

### URL Anatomy

**Basic keyword search (with city):**
```
https://www.facebook.com/marketplace/sanfrancisco/search/
  ?query=iphone+15
```

**Basic keyword search (without city):**
```
https://www.facebook.com/marketplace/search/
  ?query=laptop
```

**Search with multiple filters:**
```
https://www.facebook.com/marketplace/newyork/search/
  ?query=sofa
  &minPrice=50
  &maxPrice=800
  &sortBy=creation_time_descend
  &daysSinceListed=7
  &itemCondition=used_good
  &deliveryMethod=local_pick_up
  &exact=true
```

### General Search Query Parameters

| Parameter | Key | Values / Format | Verifier Handling | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Search Query** | `query` | URL-encoded string | Case-insensitive, whitespace-normalized | Primary search term |
| **Min Price** | `minPrice` | Integer | Exact integer match | Lower price bound ($) |
| **Max Price** | `maxPrice` | Integer | Exact integer match | Upper price bound ($) |
| **Sort Order** | `sortBy` | See §3.1 | Alias-normalized exact match | Result ordering |
| **Days Listed** | `daysSinceListed` | `1`, `7`, `30` | Exact integer match | Recency filter |
| **Condition** | `itemCondition` | See §3.2 | Alias-normalized exact match | Item condition |
| **Delivery** | `deliveryMethod` | See §3.3 | Alias-normalized exact match | Delivery method |
| **Exact Match** | `exact` | `true`, `false` | Exact boolean match | Exact keyword toggle |
| **Category ID** | `category_id` | Numeric string | Case-insensitive exact | Internal FB category |

---

### §3.1 Sort Order

Facebook Marketplace offers five sort options accessible via the "Sort by" dropdown:

| UI Label | URL Value | Normalized Key | Behavior |
| :--- | :--- | :--- | :--- |
| Suggested | `best_match` | `best_match` | Algorithm-ranked (default) |
| Price: Lowest first | `price_ascend` | `price_ascend` | Ascending by price |
| Price: Highest first | `price_descend` | `price_descend` | Descending by price |
| Date listed: Newest first | `creation_time_descend` | `creation_time_descend` | Most recent first |
| Distance: Nearest first | `distance_ascend` | `distance_ascend` | Closest to user location |

The verifier also accepts these aliases from agent URLs:

| Alias(es) | Normalized To |
| :--- | :--- |
| `newest`, `date_listed`, `date_listed:_newest_first` | `creation_time_descend` |
| `nearest`, `distance:_nearest_first` | `distance_ascend` |
| `price_asc`, `price_low`, `priceascend`, `price:_lowest_first` | `price_ascend` |
| `price_desc`, `price_high`, `pricedescend`, `price:_highest_first` | `price_descend` |
| `bestmatch`, `default` | `best_match` |

> [!NOTE]
> **Browser-verified (Apr 2026):** The sort dropdown is visible on the left sidebar
> on search results pages. When `sortBy` is absent from the URL, Facebook uses its
> algorithmic "Suggested" (best_match) ordering which factors in user engagement,
> location proximity, and listing freshness.

---

### §3.2 Item Condition

| UI Label | URL Value | Normalized Key |
| :--- | :--- | :--- |
| New | `new` | `new` |
| Used - Like new | `used_like_new` | `used_like_new` |
| Used - Good | `used_good` | `used_good` |
| Used - Fair | `used_fair` | `used_fair` |

The verifier accepts these aliases:

| Alias(es) | Normalized To |
| :--- | :--- |
| `like_new`, `likenew`, `like new` | `used_like_new` |
| `good` | `used_good` |
| `fair` | `used_fair` |
| `used` (generic) | `used_good` |

> [!IMPORTANT]
> The condition filter is a **single-select** dropdown. Only one condition can be
> active at a time in the URL. If no condition is specified, all conditions are shown.

---

### §3.3 Delivery Method

| UI Label | URL Value | Normalized Key |
| :--- | :--- | :--- |
| Local pickup | `local_pick_up` | `local_pick_up` |
| Shipping | `shipping` | `shipping` |

Aliases: `pickup`, `local_pickup` → `local_pick_up`; `shipped` → `shipping`

---

### §3.4 Days Since Listed (Recency Filter)

| UI Label | URL Value | Meaning |
| :--- | :--- | :--- |
| Last 24 hours | `1` | Posted today |
| Last 7 days | `7` | Posted this week |
| Last 30 days | `30` | Posted this month |

> [!WARNING]
> This is a **time-relative** filter. The verifier compares the exact integer value.
> Tasks referencing recency should use the integer value (1, 7, or 30), not the
> human-readable label. The filter is useful for benchmark hardening since agents
> must correctly interpret temporal language ("recent", "this week", "past 24 hours").

---

### §3.5 Exact Match Toggle

```
&exact=true     ← Only show listings matching the exact search term
&exact=false    ← Allow related/fuzzy results (default)
```

> [!NOTE]
> **Browser-verified (Apr 2026):** The `exact` parameter appears in URLs when
> the user toggles "Exact matches" in the search sidebar. When absent, the default
> behavior is `exact=false` (fuzzy matching). The verifier treats `exact=true` and
> `exact=false` as distinct values.

---

## 4. Location & City Slugs

### Location Encoding

Location is encoded in **two ways** on Facebook Marketplace:

1. **Path segment (city slug):** `/marketplace/{city_slug}/search/?...`
2. **Session-based:** Facebook auto-detects location from IP and stores it in the user session

The city slug appears in the URL path, NOT as a query parameter.

### City Slug Format

City slugs are **lowercase, concatenated** (no spaces, hyphens, or underscores):

| City | Slug | | City | Slug |
| :--- | :--- | --- | :--- | :--- |
| San Francisco | `sanfrancisco` | | Dallas | `dallas` |
| New York | `newyork` | | Austin | `austin` |
| Los Angeles | `losangeles` | | Seattle | `seattle` |
| Chicago | `chicago` | | Denver | `denver` |
| Houston | `houston` | | Boston | `boston` |
| Phoenix | `phoenix` | | Nashville | `nashville` |
| Philadelphia | `philadelphia` | | Portland | `portland` |
| San Antonio | `sanantonio` | | Miami | `miami` |
| San Diego | `sandiego` | | Atlanta | `atlanta` |
| Detroit | `detroit` | | Minneapolis | `minneapolis` |
| London | `london` | | Toronto | `toronto` |
| Vancouver | `vancouver` | | Sydney | `sydney` |

> [!WARNING]
> **City slugs are lowercase, no separators.** `newyork` NOT `new-york` or `new_york`.
> This is a common agent mistake when constructing URLs.
>
> Facebook may also use **numeric location IDs** (e.g., `/marketplace/112345678/`)
> for some regions. These are Facebook-internal identifiers and the verifier
> accepts both slug and numeric forms.

> [!IMPORTANT]
> The verifier compares city slugs **case-insensitively** when the GT specifies one.
> If the GT URL does not contain a city slug (e.g., just `/marketplace/search/`),
> the agent's city slug is ignored and the match still passes.

### Radius

**Browser-verified (Apr 2026):** The homepage displays a radius indicator:

```
📍 San Francisco · 65 km
```

> [!NOTE]
> **Radius is NOT encoded in the URL.** It is a session-level setting controlled
> by the Marketplace UI (clicking the location link). There is no `radius` or
> `radiusKM` query parameter. The verifier does NOT verify radius.

---

## 5. Category System

### Primary Categories (Path-Based)

Categories are browsed via URL path segments:

```
https://www.facebook.com/marketplace/category/{category_slug}/
```

### Category Hierarchy (Browser-Verified Apr 2026)

| Category | Slug | Description | Has Subcategories |
| :--- | :--- | :--- | :---: |
| **Vehicles** | `vehicles` | All vehicle types | ✅ |
| **Property for rent** | `propertyrentals` | Rental listings | ✅ |
| **Classifieds** | `classifieds` | Classified ads | ❌ |

### Vehicle Subcategories (Browser-Verified Apr 2026)

The Vehicles category page shows a "**Shop by category**" section with pill-style buttons:

| UI Label | Slug/Path | Note |
| :--- | :--- | :--- |
| **Boats** | `/marketplace/category/boats/` | Watercraft |
| **Cars** | `/marketplace/category/cars/` | Cars & trucks |
| **Motorcycles** | `/marketplace/category/motorcycles/` | Motorcycles & scooters |
| **Powersport vehicles** | `/marketplace/category/powersportvehicles/` | ATVs, snowmobiles |
| **Motorhomes/camper vans** | `/marketplace/category/motorhomescampervans/` | RVs & campers |
| **Trailers** | `/marketplace/category/trailers/` | Utility & cargo trailers |
| **Lorries** | `/marketplace/category/lorries/` | Commercial trucks |

> [!CAUTION]
> **The `topLevelVehicleType` parameter** uses different values than the URL slug:
> - `car_truck` (query param) vs `cars` (category slug)
> - `rv_camper` (query param) vs `motorhomescampervans` (slug)
> - `motorcycle` (query param) vs `motorcycles` (slug)
>
> The verifier normalizes both forms. Agent URLs may use either the category path
> or the query parameter.

### Property Rental Subcategories (Browser-Verified Apr 2026)

The Property page shows a "**Shop by category**" section:

| UI Label | Slug/Path | Note |
| :--- | :--- | :--- |
| **Apartments for rent** | `/marketplace/category/apartments/` | Apartment units |
| **Flats for rent** | `/marketplace/category/flats/` | UK-style "flats" |
| **Houses for rent** | `/marketplace/category/houses/` | Standalone houses |
| **Townhouses for rent** | `/marketplace/category/townhouses/` | Townhouse units |

### Additional Category Slugs (From Search Interface)

These additional categories appear when filtering in search results:

| Category | Slug | Description |
| :--- | :--- | :--- |
| Electronics | `electronics` | Phones, computers, cameras |
| Apparel | `apparel` | Clothing, shoes, accessories |
| Furniture | `furniture` | Tables, chairs, sofas |
| Home | `home` | Home goods, decor |
| Entertainment | `entertainment` | Games, movies, books |
| Garden | `garden` | Outdoor, plants, tools |
| Hobbies | `hobbies` | Crafts, collectibles |
| Sporting | `sporting` | Sports equipment |
| Toys | `toys` | Toys and games |
| Office | `office` | Office supplies, equipment |
| Free | `free` | Free items |
| Musical instruments | `musicalinstruments` | Instruments, gear |
| Family | `family` | Baby items, kids gear |
| Pets | `pets` | Pet-related (region-dependent) |

---

## 6. Vehicle-Specific Filters

### Vehicle Filter Sidebar (Browser-Verified Apr 2026)

When browsing the Vehicles category, the left sidebar shows these filters:

```
Filters
─────────────────
San Francisco, California
Sort by........................▼
Price
[Min.]  to  [Max.]
Categories
├── 🚗 Vehicles  (selected)
├── 💰 Property for rent
└── 📋 Classifieds
```

### Vehicle Query Parameters

| Parameter | Key | Values / Format | Verifier Handling | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Vehicle Type** | `topLevelVehicleType` | See §6.1 | Alias-normalized | Vehicle category |
| **Make** | `make` | **Numeric ID** | See §6.2 | Vehicle manufacturer |
| **Model** | `model` | String | Case-insensitive exact | Vehicle model name |
| **Min Year** | `minYear` | 4-digit integer | Exact integer | Manufacturing year min |
| **Max Year** | `maxYear` | 4-digit integer | Exact integer | Manufacturing year max |
| **Min Mileage** | `minMileage` | Integer | Exact integer | Odometer min |
| **Max Mileage** | `maxMileage` | Integer | Exact integer | Odometer max |

---

### §6.1 Vehicle Types

| UI Subcategory | `topLevelVehicleType` Value | Normalized Key |
| :--- | :--- | :--- |
| Cars | `car_truck` | `car_truck` |
| Motorcycles | `motorcycle` | `motorcycle` |
| Motorhomes/camper vans | `rv_camper` | `rv_camper` |
| Boats | `boat` | `boat` |
| Powersport vehicles | `powersport` | `powersport` |
| Trailers | `trailer` | `trailer` |
| Lorries / Commercial | `commercial` | `commercial` |

Aliases: `car` / `truck` → `car_truck`; `rv` / `camper` → `rv_camper`

---

### §6.2 Vehicle Make — Numeric ID System

> [!CAUTION]
> **CRITICAL FINDING (Browser-Verified Apr 2026):** The `make` parameter uses
> **Facebook-internal numeric IDs**, NOT human-readable brand names. For example:
>
> ```
> make=25330325463    ← Tesla
> ```
>
> This was captured from:
> ```
> https://www.facebook.com/marketplace/category/cars?make=25330325463&exact=false
> ```
>
> These numeric IDs are **not stable, not documented, and may change.** They are
> assigned internally by Facebook's vehicle classification system.

**Impact on Verifier:**
Because make IDs are numeric and unstable, the verifier supports **both** formats:
1. **Numeric ID match:** `make=25330325463` vs `make=25330325463` → exact match
2. **String name match:** `make=toyota` vs `make=toyota` → case-insensitive match

When the benchmark CSV specifies a make as a string (e.g., `make=toyota`), the
verifier uses case-insensitive string comparison. This is a pragmatic choice since
the numeric IDs are not discoverable without interacting with the Facebook UI.

> [!NOTE]
> **Model** parameters appear to use plain strings (not numeric IDs) based on
> browser observation. Example: `model=camry`, `model=f150`.

### Example Vehicle Search URL (Browser-Verified)

```
https://www.facebook.com/marketplace/category/cars
  ?minYear=2020
  &maxYear=2024
  &exact=false
```

```
https://www.facebook.com/marketplace/category/cars
  ?make=25330325463
  &exact=false
```

---

## 7. Property Rental Filters

### Property Filter Sidebar (Browser-Verified Apr 2026)

When browsing Property for rent, the left sidebar shows these filters:

```
Filters
─────────────────
San Francisco, California
Price
[Min.]  to  [Max.]
Bedrooms...................▼
Bathrooms..................▼
Type of property for rent..▼
Square feet
[Min.]  to  [Max.]
```

### Property Query Parameters

| Parameter | Key | Values / Format | Verifier Handling | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Min Bedrooms** | `minBedrooms` | Integer (1-5+) | Exact integer | Bedroom count min |
| **Max Bedrooms** | `maxBedrooms` | Integer (1-5+) | Exact integer | Bedroom count max |
| **Min Bathrooms** | `minBathrooms` | Integer (1-5+) | Exact integer | Bathroom count min |
| **Property Type** | `propertyType` | See §7.1 | Alias-normalized | Property category |
| **Min Square Feet** | `minSquareFeet` | Integer | Exact integer | Square footage min |
| **Max Square Feet** | `maxSquareFeet` | Integer | Exact integer | Square footage max |

> [!NOTE]
> **Square feet** filter was observed in the sidebar (Apr 2026) with Min/Max fields.
> This is a newly observed parameter not present in all regions.

---

### §7.1 Property Types

| UI Label | `propertyType` Value | Normalized Key |
| :--- | :--- | :--- |
| House | `house` | `house` |
| Apartment | `apartment` | `apartment` |
| Condo | `condo` | `condo` |
| Townhouse | `townhouse` | `townhouse` |
| Studio | `studio` | `studio` |
| Room | `room` | `room` |

### Property Rental Subcategories (From "Shop by category")

| UI Label | Page Title | Note |
| :--- | :--- | :--- |
| Apartments for rent | Apartment listings | Standard apartments |
| Flats for rent | Flat listings | UK terminology for apartments |
| Houses for rent | House listings | Standalone houses |
| Townhouses for rent | Townhouse listings | Row houses |

### Map View

> [!NOTE]
> **Browser-verified (Apr 2026):** Property rental pages display an interactive
> **map view** alongside listings. The map shows numbered markers indicating
> listing clusters. This is unique to Property Rentals — general goods and
> vehicle searches do NOT show a map. The map view does NOT add URL parameters.

---

## 8. Listing Card Anatomy

### General Goods Listing Card (Browser-Verified Apr 2026)

```
┌──────────────────────┐
│                      │
│     [LISTING IMAGE]  │
│                      │
├──────────────────────┤
│  $3,000              │  ← Price (or "FREE")
│  2013 BMW x1         │  ← Title / item name
│  Dublin, CA          │  ← Location (city, state)
│  161K miles          │  ← Vehicle-specific: mileage
└──────────────────────┘
```

### Vehicle Listing Card

```
┌──────────────────────┐
│                      │
│     [VEHICLE IMAGE]  │
│                      │
├──────────────────────┤
│  $14,800             │  ← Price
│  2005 Arctic Fox...  │  ← Year + Title
│  Novato, CA          │  ← Location
│  (no mileage shown)  │  ← Mileage may be absent
└──────────────────────┘
```

### Key observations:
- Prices are shown in local currency with comma separators
- "FREE" items display "FREE" instead of a price
- Location shows `City, State` format (US) or `City` only (international)
- Mileage appears on vehicle listings when available (e.g., "161K miles", "102K miles")
- Strikethrough pricing appears for reduced items (e.g., `$3,600 ~~$3,800~~`)
- Images are lazy-loaded as the user scrolls (infinite scroll, no pagination)

---

## 9. Ignored Parameters

These parameters encode session state, UI preferences, or tracking data.
They do **not** affect search semantics and are excluded from comparison.

### Tracking & Attribution (Ignored)
`ref`, `referral_code`, `referral_story_type`, `referral_surface`, `tracking`,
`surface`, `section_token`, `__tn__`, `__cft__`, `contextRouterSourceType`

### Facebook Internal (Ignored)
`fb_dtsg_ag`, `jazoest`, `lsd`, `_rdr`

### Marketing & Click IDs (Ignored)
`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`,
`gclid`, `msclkid`, `fbclid`

### Session & UI State (Ignored)
`locale`, `surface_type`, `fs`, `_rdr`

> [!NOTE]
> **Browser-verified (Apr 2026):** The `_rdr` parameter was observed appended to the
> homepage URL (`/marketplace/?_rdr`). This is a Facebook redirect tracking parameter
> and is always ignored by the verifier.

---

## 10. Domain Variations

The verifier accepts **all** valid Facebook Marketplace domains:

| Domain | Accepted | Region/Purpose |
| :--- | :---: | :--- |
| `www.facebook.com` | ✅ | Primary desktop |
| `facebook.com` | ✅ | Without www prefix |
| `m.facebook.com` | ✅ | Mobile web |
| `web.facebook.com` | ✅ | Alternate web (used in some regions) |
| `*.facebook.com` | ✅ | Any subdomain |
| `instagram.com` | ❌ | Rejected (different platform) |
| `google.com` | ❌ | Rejected |
| `fakefacebook.com` | ❌ | Rejected (not a subdomain) |

> [!NOTE]
> All Facebook domains use identical URL structures for Marketplace. The path
> `/marketplace/...` and query parameters are consistent across `www.`, `m.`,
> and `web.` variants.

---

## 11. Verifier Matching Rules

### Core Comparison Logic

| # | Field | Normalization | Comparison | Fail if GT has & Agent missing? |
| :---: | :--- | :--- | :--- | :---: |
| 1 | City slug | Extract from path, lowercase | Case-insensitive exact | ✅ Yes |
| 2 | Category slug | Extract from path, lowercase | Exact string | ✅ Yes |
| 3 | Category ID | From query param | Case-insensitive exact | ✅ Yes |
| 4 | Search query | URL-decode, lowercase, collapse whitespace | Exact string | ✅ Yes |
| 5 | Min price | Parse integer | Exact integer | ✅ Yes |
| 6 | Max price | Parse integer | Exact integer | ✅ Yes |
| 7 | Sort order | Alias resolution | Exact string | ✅ Yes |
| 8 | Item condition | Alias resolution | Exact string | ✅ Yes |
| 9 | Days since listed | Parse integer | Exact integer | ✅ Yes |
| 10 | Delivery method | Alias resolution | Exact string | ✅ Yes |
| 11 | Exact flag | Parse boolean | Exact boolean | ✅ Yes |
| 12 | Min year | Parse integer | Exact integer | ✅ Yes |
| 13 | Max year | Parse integer | Exact integer | ✅ Yes |
| 14 | Min mileage | Parse integer | Exact integer | ✅ Yes |
| 15 | Max mileage | Parse integer | Exact integer | ✅ Yes |
| 16 | Vehicle type | Alias resolution | Exact string | ✅ Yes |
| 17 | Make | Lowercase | Exact string | ✅ Yes |
| 18 | Model | Lowercase | Exact string | ✅ Yes |
| 19 | Min bedrooms | Parse integer | Exact integer | ✅ Yes |
| 20 | Max bedrooms | Parse integer | Exact integer | ✅ Yes |
| 21 | Min bathrooms | Parse integer | Exact integer | ✅ Yes |
| 22 | Property type | Alias resolution | Exact string | ✅ Yes |

### Precedence Rules (Hardened — No Auto-Pass Loopholes)

1. If ground truth specifies a field and agent **omits** it → **FAIL** (no auto-pass)
2. If ground truth **omits** a field → agent value is **ignored** (pass)
3. Search query is compared **case-insensitively** with whitespace normalization
4. All integer fields must match **exactly** (no tolerance, no rounding)
5. City slug is compared **only** when GT specifies one
6. First successful match across multi-GT URLs → **score = 1.0** (OR semantics)
7. Tracking/session parameters (§9) are always ignored
8. Extra agent parameters not in GT are **ignored** (agent can have more filters)
9. Category can match via **slug** (path) OR **category_id** (query param)

### Matching Flow

```
Agent URL → Parse → Normalize
  ↓
GT URL → Parse → Normalize
  ↓
Compare: city → category_slug → category_id → query → min_price → max_price
       → sort_by → item_condition → days_since_listed → delivery_method → exact
       → min_year → max_year → min_mileage → max_mileage → vehicle_type
       → make → model → min_bedrooms → max_bedrooms → min_bathrooms
       → property_type
  ↓
All match? → score = 1.0
Any mismatch? → score = 0.0 (with mismatch field logged)
```

---

## 12. Login Modal Behavior

> [!WARNING]
> **Browser-verified (Apr 2026):** After a few page interactions, Facebook overlays
> a modal dialog:
>
> ```
> ┌────────────────────────────────────┐
> │              ✕                     │
> │  See more on Facebook              │
> │                                    │
> │  [Email address or phone number]   │
> │  [Password]                        │
> │  [Log in]                          │
> │  Forgotten password?               │
> │        or                          │
> │  [Create new account]              │
> └────────────────────────────────────┘
> ```
>
> This modal is a **cosmetic overlay** that does NOT modify the URL or prevent
> URL changes. The verifier is unaffected by this modal because it only compares
> URL parameters, not visual page state. However, agents interacting with the DOM
> may need to dismiss this modal (click ✕) to continue.

---

## 13. Test & Benchmark Coverage

### Unit Tests

**102 tests** across 15 test classes, covering:

| Category | Tests | Focus |
| :--- | :---: | :--- |
| URL Parsing | 8 | Full parse pipeline, vehicles, property, URL-encoding |
| Query Normalization | 6 | Case, whitespace, URL-decode, special characters |
| Price Range | 6 | Min-only, max-only, both, missing, mismatch |
| Condition Matching | 7 | All condition values + aliases + missing |
| Sort Matching | 6 | All sort values + aliases + mismatch |
| Category Matching | 6 | Slug extraction, match, mismatch |
| City Slug Matching | 9 | Extract, match, mismatch, case-insensitive, numeric ID |
| Vehicle Filters | 8 | Year, mileage, type, make, model, normalization |
| Property Filters | 6 | Bedrooms, bathrooms, property type, normalization |
| URL Matching Integration | 12 | All mismatch + combination scenarios |
| Domain Validation | 8 | Valid domains, rejections |
| Async Lifecycle | 5 | reset → update → compute |
| Multi-GT URLs | 3 | OR semantics |
| Edge Cases | 6 | Non-marketplace, listing pages, mobile domain |
| Normalization Helpers | 6 | Delivery, sort, condition normalizer functions |

### Benchmark Dataset

**70 tasks** in `fb_marketplace_benchmark_tasks.csv` — **all hard difficulty**:

| Category | Count | Difficulty Strategy |
| :--- | :---: | :--- |
| General Goods Search | 15 | Multi-filter combos (price + condition + sort + exact + delivery) |
| Vehicle Search | 15 | Year/mileage ranges, specific make/model, vehicle type |
| Property Rentals | 10 | Bedroom/bathroom counts, property type filters |
| Complex Price Math | 10 | Budget arithmetic (split costs, savings, exclusions) |
| Red Herring Tasks | 10 | Brand preferences, personal anecdotes, irrelevant details |
| City-Specific Tasks | 5 | Cross-city searches, destination vs. home city confusion |
| Ultra-Hard Combos | 5 | 6-7+ simultaneous filters, income math, contributor budgets |

---

## Appendix A: Live URL Examples (Browser-Verified Apr 2026)

### Basic General Goods Search (San Francisco)
```
https://www.facebook.com/marketplace/sanfrancisco/search/
  ?query=iphone+15+pro
  &minPrice=500
  &maxPrice=900
  &itemCondition=used_like_new
  &sortBy=price_ascend
```

### Vehicle Search — Cars with Year Filter
```
https://www.facebook.com/marketplace/category/cars
  ?minYear=2020
  &maxYear=2024
  &exact=false
```

### Vehicle Search — Tesla Make (Numeric ID)
```
https://www.facebook.com/marketplace/category/cars
  ?make=25330325463
  &exact=false
```

### Vehicle Search (Full Stack — Dallas)
```
https://www.facebook.com/marketplace/dallas/search/
  ?query=ford+f150
  &minPrice=15000
  &maxPrice=35000
  &minYear=2018
  &maxYear=2023
  &maxMileage=80000
  &topLevelVehicleType=car_truck
  &make=ford
  &model=f150
```

### Property Rental Search (Boston)
```
https://www.facebook.com/marketplace/boston/search/
  ?minPrice=1500
  &maxPrice=3000
  &minBedrooms=2
  &maxBedrooms=3
  &minBathrooms=1
  &propertyType=apartment
```

### Search with London City Slug + Sort
```
https://www.facebook.com/marketplace/london/search
  ?sortBy=price_ascend
  &query=bike
```

### Category Browse (Electronics)
```
https://www.facebook.com/marketplace/category/electronics/
```

### All Filters Active (Maximum Complexity)
```
https://www.facebook.com/marketplace/newyork/search/
  ?query=sofa+sectional
  &minPrice=200
  &maxPrice=1500
  &sortBy=creation_time_descend
  &daysSinceListed=7
  &itemCondition=used_good
  &deliveryMethod=local_pick_up
  &exact=true
```

---

## Appendix B: Comparison with Other Domains

| Feature | Facebook Marketplace | Trainline | Expedia |
| :--- | :--- | :--- | :--- |
| Filter encoding | Query params | Query params | Compound `leg` params |
| Location | Path slug + session | N/A (stations in params) | N/A (airports in params) |
| Category system | Path slugs + category_id | N/A (single domain) | N/A (hotel/flight) |
| IDs | Numeric make IDs | Station URN codes | Airport IATA codes |
| Date handling | `daysSinceListed` (recency) | ISO datetime | ISO date |
| Passengers/count | N/A | DOB-based encoding | Room/traveler counts |
| Class/condition | `itemCondition` param | Travel class (DOM-only) | Cabin class |
| Auth required | Partial (modal overlay) | No | No |
| Radius/distance | Session-only (not in URL) | N/A | N/A |

---
