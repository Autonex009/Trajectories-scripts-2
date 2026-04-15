# Trainline Coverage Documentation
## URL Patterns, Query Parameters & Verifier Reference
**thetrainline.com**
**Browser-Verified: April 2026**

---

## Overview

This document provides the authoritative reference for Trainline's URL structures, query parameter
encoding, and verifier matching logic. All patterns were validated through dedicated browser
deep-dive sessions against the live production site (April 2026).

> **Important:** Trainline is a modern JavaScript SPA (React-based). Search results render
> dynamically and the URL encodes all critical search parameters as query strings on the
> `/book/results` path. Unlike Expedia's compound `leg` parameters, Trainline uses standard
> query parameters with URN-based station identifiers and date-of-birth (DOB) passenger encoding.

> [!NOTE]
> **Travel class (Standard / 1st Class) is NOT encoded in the URL.** Class selection happens
> on the search results page via radio buttons next to each fare. This means class verification
> is out of scope for URL-based matching — it would require DOM-based verification.

---

## 1. Page Types

| Page Type | URL Pattern | Example |
| :--- | :--- | :--- |
| **Homepage** | `/` or `/en-us` | `thetrainline.com/en-us` |
| **Search Results** | `/book/results?...` | `/book/results?journeySearchType=single&origin=...` |
| **Train Times** | `/train-times/{route}` | `/train-times/london-to-manchester` |
| **Cheap Train Tickets** | `/trains/{route}` | `/trains/london-to-paris` |
| **My Bookings** | `/my-bookings` | `/my-bookings` |
| **Referrals** | `/refer-a-friend` | `/en-US/refer-a-friend` |

### Detection Rules

| Rule | Pattern Match | Page Type |
| :--- | :--- | :--- |
| `/book/results` in path | Train search results | Search |
| `/train-times/` in path | Route timetable | Informational |
| `/trains/` in path | Route marketing page | Informational |
| `/my-bookings` in path | User bookings | Account |
| `/` or `/en-us` | Homepage | Landing |

> [!IMPORTANT]
> The verifier only processes URLs containing `/book/results` — all other Trainline pages
> are ignored and will not produce a match even if they mention the correct route.

---

## 2. Train Search URLs

### URL Anatomy

**One-way (single):**
```
https://www.thetrainline.com/book/results?
  journeySearchType=single
  &origin=urn:trainline:generic:loc:EUS1444gb
  &destination=urn:trainline:generic:loc:MAN2968gb
  &outwardDate=2026-05-01T13:15:00
  &outwardDateType=departAfter
  &passengers[]=1990-01-15
  &lang=en-us
```

**Return:**
```
https://www.thetrainline.com/book/results?
  journeySearchType=return
  &origin=urn:trainline:generic:loc:MAN2968gb
  &destination=urn:trainline:generic:loc:EDB9328gb
  &outwardDate=2026-05-01T13:15:00
  &outwardDateType=departAfter
  &inwardDate=2026-05-05T14:30:00
  &inwardDateType=departAfter
  &passengers[]=1990-01-15
  &passengers[]=1985-06-20
  &lang=en-us
```

**Mixed adults & children:**
```
https://www.thetrainline.com/book/results?
  journeySearchType=single
  &origin=urn:trainline:generic:loc:BHM1127gb
  &destination=urn:trainline:generic:loc:GLC9813gb
  &outwardDate=2026-05-01T12:00:00
  &outwardDateType=departAfter
  &passengers[]=1990-01-15
  &passengers[]=2016-05-18
```

### Query Parameters

| Parameter | Key | Values / Format | Note |
| :--- | :--- | :--- | :--- |
| **Journey Type** | `journeySearchType` | `single`, `return`, `openReturn` | Required |
| **Origin** | `origin` | Station URN (see §2.1) | Required |
| **Destination** | `destination` | Station URN (see §2.1) | Required |
| **Outward Date** | `outwardDate` | `YYYY-MM-DDTHH:MM:SS` | Required |
| **Outward Type** | `outwardDateType` | `departAfter` | Time preference |
| **Inward Date** | `inwardDate` | `YYYY-MM-DDTHH:MM:SS` | Return trips only |
| **Inward Type** | `inwardDateType` | `departAfter` | Return trips only |
| **Passengers** | `passengers[]` | DOB per person (see §2.2) | Array, repeated |
| **Language** | `lang` | `en-us`, `en-gb`, `fr-fr`, etc. | **Ignored** |
| **Transport Mode** | `transportModes[]` | `mixed`, `train`, `bus` | **Ignored** |
| **Selected Tab** | `selectedTab` | `train`, `bus` | **Ignored** |
| **Split Save** | `splitSave` | `true`, `false` | **Ignored** |
| **Direct Search** | `directSearch` | `true`, `false` | **Ignored** |

---

### §2.1 Station URN Encoding

Trainline identifies stations using **Uniform Resource Names (URNs)** with the following format:

```
urn:trainline:generic:loc:{STATION_ID}
```

Station IDs follow different patterns depending on the location:

| Type | Format | Example | Description |
| :--- | :--- | :--- | :--- |
| **UK Specific Station** | `{CRS}{NUMERIC}gb` | `EUS1444gb` | CRS code + Trainline ID + country |
| **UK City (Any)** | `{NUMERIC}gb` | `182gb` | City-level, routes to any station |
| **European** | `{NUMERIC}` | `4916` | Numeric-only, no country suffix |

> [!CAUTION]
> Station URNs are **URL-encoded** in the browser address bar:
> `urn%3Atrainline%3Ageneric%3Aloc%3AEUS1444gb`
>
> The verifier **decodes** these before comparison. Both encoded and raw forms are
> accepted and produce identical normalized results.

#### CRS (Computer Reservation System) Codes

UK stations use the National Rail **CRS code** as a prefix:

| Station | CRS | Example URN(s) |
| :--- | :---: | :--- |
| London Euston | EUS | `urn:trainline:generic:loc:EUS1444gb` |
| London St Pancras International | STP | `urn:trainline:generic:loc:STP1555gb` |
| London Kings Cross | KGX | `urn:trainline:generic:loc:KGX4832gb`, `KGX6121gb` |
| London Paddington | PAD | `urn:trainline:generic:loc:PAD2935gb` |
| London Victoria | VIC | `urn:trainline:generic:loc:VIC5426gb` |
| London Waterloo | WAT | `urn:trainline:generic:loc:WAT5598gb` |
| London Liverpool Street | LST | `urn:trainline:generic:loc:LST6965gb` |
| Manchester Piccadilly | MAN | `urn:trainline:generic:loc:MAN2968gb` |
| Edinburgh (Waverley) | EDB | `urn:trainline:generic:loc:EDB9328gb` |
| Birmingham New Street | BHM | `urn:trainline:generic:loc:BHM1127gb` |
| Leeds | LDS | `urn:trainline:generic:loc:LDS8487gb` |
| Glasgow Central | GLC | `urn:trainline:generic:loc:GLC9813gb` |
| York | YRK | `urn:trainline:generic:loc:YRK8263gb` |
| Bristol Temple Meads | BRI | `urn:trainline:generic:loc:BRI3231gb` |
| Liverpool Lime Street | LIV | `urn:trainline:generic:loc:LIV2246gb` |
| Newcastle | NCL | `urn:trainline:generic:loc:NCL7728gb` |
| Brighton | BTN | `urn:trainline:generic:loc:BTN5268gb` |
| Cambridge | CBG | `urn:trainline:generic:loc:CBG7022gb` |
| Oxford | OXF | `urn:trainline:generic:loc:OXF3115gb` |

> [!WARNING]
> **Numeric suffixes are NOT stable.** Trainline assigns varying numeric IDs to the same
> physical station. For example, Kings Cross has been observed as both `KGX4832gb` and
> `KGX6121gb` in different browser sessions. The verifier therefore matches on the
> **CRS letter prefix** only (e.g., `KGX`), ignoring the numeric suffix.
>
> This means `KGX4832gb`, `KGX6121gb`, and any future `KGX{nnnn}gb` all resolve to the
> same station and will match each other.

#### City-Level (Any Station) IDs

| City | URN | Browser-Verified |
| :--- | :--- | :---: |
| London (Any) | `urn:trainline:generic:loc:182gb` | ✅ |
| Manchester (Any) | `urn:trainline:generic:loc:115gb` | ✅ |
| Paris (Any) | `urn:trainline:generic:loc:4916` | ✅ |

> [!NOTE]
> City-level URNs (e.g., `182gb` for "London Any", `115gb` for "Manchester Any") allow
> Trainline to route passengers via any station in the city. These are used when the user
> selects "London" or "Manchester" without specifying a particular terminal.
> For Eurostar, the specific station `STP{nnnn}gb` (St Pancras) is always used since it's
> the only Eurostar terminal.
>
> City-level IDs are **numeric-only** (no CRS prefix) and are compared with **exact match**
> since they don't follow the `{CRS}{NUMERIC}gb` pattern.

---

### §2.2 Passenger DOB Encoding

Trainline encodes each passenger as a **date-of-birth** string in the URL. Each passenger
gets their own `passengers[]` array element:

```
passengers[]=1990-01-15       ← Adult (born 1990, age ~36)
passengers[]=2018-03-25       ← Child (born 2018, age ~8)
```

For multiple passengers, the parameter is **repeated**:

```
&passengers[]=1990-01-15
&passengers[]=1985-06-20
&passengers[]=2018-03-25
```

This encodes: 2 adults + 1 child (age 8) = 3 passengers total.

> [!IMPORTANT]
> The verifier does **NOT** compare exact DOB values. Instead, it:
> 1. Calculates each passenger's age on the **outward travel date**
> 2. Classifies as **Adult** (16+) or **Child** (0-15)
> 3. Compares **adult count** and **child count** between agent and ground truth
>
> This means any adult DOB (producing age 16+) matches any other adult DOB.
> For example, `1990-01-15` and `1970-06-30` are equivalent for matching purposes.

**Passenger Categories on Trainline:**

| Category | Age Range | DOB Example (for 2026 travel) | URL Encoding |
| :--- | :--- | :--- | :--- |
| Adult | 16+ years | `1990-01-15` (age 36) | `passengers[]=1990-01-15` |
| Young Person | 16-25 | `2005-03-10` (age 21) | `passengers[]=2005-03-10` |
| Child | 0-15 | `2018-03-25` (age 8) | `passengers[]=2018-03-25` |
| Infant | <2 | `2025-01-10` (age 1) | `passengers[]=2025-01-10` |

> [!NOTE]
> Young Persons (16-25) are classified as **Adults** by the verifier since they
> are 16+. The age-based railcard discount is applied at checkout, not in the
> URL search parameters.

#### URL Encoding of Array Parameters

In the browser address bar, `passengers[]` appears URL-encoded:

```
passengers%5B%5D=1990-01-15&passengers%5B%5D=2018-03-25
```

The verifier handles both forms:
- `passengers[]=1990-01-15` (decoded)
- `passengers%5B%5D=1990-01-15` (encoded)

#### Missing `passengers[]` — Default Behavior

> [!CAUTION]
> **Browser-verified (Apr 2026):** When the default `1 adult (16+)` passenger setting is
> used without modification, Trainline **OMITS** the `passengers[]` parameter entirely from
> the URL. The URL contains no passenger information at all.
>
> The verifier handles this by assuming **1 adult, 0 children** when `passengers[]` is absent.
> This means an agent URL without `passengers[]` will correctly match a ground truth URL
> that specifies 1 adult DOB.

**Example — Default 1 Adult URL (no passengers key):**
```
https://www.thetrainline.com/book/results?
  journeySearchType=single
  &origin=urn%3Atrainline%3Ageneric%3Aloc%3AEUS1444gb
  &destination=urn%3Atrainline%3Ageneric%3Aloc%3AMAN2968gb
  &outwardDate=2026-04-13T20%3A15%3A00
  &outwardDateType=departAfter
  &lang=en-us
```
Note: No `passengers[]` key present — verifier assumes 1 adult.

---

### §2.3 Date Encoding

Trainline uses **ISO 8601 datetime** format for all dates:

| Parameter | Format | Example | Verifier Handling |
| :--- | :--- | :--- | :--- |
| `outwardDate` | `YYYY-MM-DDTHH:MM:SS` | `2026-05-01T13:15:00` | Date only (`2026-05-01`) |
| `inwardDate` | `YYYY-MM-DDTHH:MM:SS` | `2026-05-05T14:30:00` | Date only (`2026-05-05`) |

When URL-encoded, the colons become `%3A`:
```
outwardDate=2026-05-01T13%3A15%3A00
```

> [!IMPORTANT]
> The verifier extracts only the **date portion** (YYYY-MM-DD) and ignores the time.
> This means `2026-05-01T08:00:00` and `2026-05-01T23:59:00` are considered equal.
> The departure time is a preference, not a requirement for route matching.

---

### §2.4 Journey Types

| UI Label | URL Value | Normalized Key | Has Inward Date? |
| :--- | :--- | :--- | :--- |
| One-way | `single` | `single` | No |
| Return | `return` | `return` | Yes |
| Open Return | `openReturn` | `openReturn` | No (flexible) |

The verifier also accepts these aliases from agent URLs:

| Alias | Normalized To |
| :--- | :--- |
| `oneway`, `one-way` | `single` |
| `roundtrip`, `round-trip` | `return` |
| `open-return` | `openReturn` |

---

## 3. London Terminal Selection Guide

London has multiple mainline stations, each serving different rail operators and routes.
A key benchmark challenge is ensuring the agent selects the **correct London terminal**:

| Terminal | CRS | Primary Routes | Operator(s) |
| :--- | :--- | :--- | :--- |
| **Euston** | EUS | Manchester, Birmingham, Liverpool, Glasgow (West Coast) | Avanti West Coast |
| **Kings Cross** | KGX | Edinburgh, Leeds, York, Newcastle (East Coast) | LNER |
| **St Pancras Intl** | STP | Paris, Brussels, Amsterdam (Eurostar) | Eurostar |
| **Paddington** | PAD | Bristol, Bath, Oxford, Cardiff (Great Western) | GWR |
| **Victoria** | VIC | Brighton, Gatwick Airport (South Coast) | Southern, Gatwick Express |
| **Waterloo** | WAT | Southampton, Portsmouth, Oxford (South/West) | South Western Railway |
| **Liverpool Street** | LST | Cambridge, Norwich, Stansted (East Anglia) | Greater Anglia |

> [!WARNING]
> Selecting the wrong London terminal is a common agent error. For example:
> - London → Manchester should depart from **Euston** (not Kings Cross)
> - London → Edinburgh should depart from **Kings Cross** (not Euston)
> - London → Paris should depart from **St Pancras** (not Waterloo, despite historical usage)
> - London → Bristol should depart from **Paddington** (not Euston)
> - London → Cambridge should depart from **Liverpool Street** (not Kings Cross, despite some services)

---

## 4. Domain Variations

The verifier accepts **all** valid Trainline domains. URL path and parameter structure is
consistent across all variants:

| Domain | Region | | Domain | Region |
| :--- | :--- | --- | :--- | :--- |
| `thetrainline.com` | Primary (UK) | | `trainline.fr` | France |
| `www.thetrainline.com` | Standard | | `trainline.it` | Italy |
| `trainline.com` | Alternate (UK) | | `trainline.es` | Spain |
| `trainline.eu` | Pan-European | | `trainline.de` | Germany |

> [!NOTE]
> The primary domain is `thetrainline.com` with the `the-` prefix. This distinguishes
> it from the regional domains (`trainline.fr`, `trainline.it`, etc.) which do NOT
> have the `the-` prefix. The verifier accepts all variants.

---

## 5. Ignored Parameters

These parameters encode session state, UI preferences, or tracking data.
They do **not** affect search semantics and are excluded from comparison.

### Search Parameters (Ignored)
`lang`, `selectedTab`, `splitSave`, `directSearch`, `transportModes[]`,
`outwardDateType`, `inwardDateType`

### Session & Tracking (Ignored)
`dpiCookieId`, `partnershipType`, `partnershipSelection`, `selectedOutward`,
`selectedInward`, `searchId`, `wcid`, `source`, `cmpid`, `redirected`, `type`, `qd`

### Marketing & Attribution (Ignored)
`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`,
`gclid`, `msclkid`, `fbclid`, `ref`

---

## 6. Verifier Matching Rules

### Core Comparison Logic

| Field | Normalization | Comparison |
| :--- | :--- | :--- |
| Origin URN | URL-decode, strip prefix, extract CRS | CRS prefix match (see §2.1) |
| Destination URN | URL-decode, strip prefix, extract CRS | CRS prefix match (see §2.1) |
| Outward date | Extract `YYYY-MM-DD` from datetime | Exact string |
| Inward date | Extract `YYYY-MM-DD` from datetime | Exact string (return trips) |
| Journey type | Alias resolution (see §2.4) | Exact string |
| Adult count | DOB → age (16+) on travel date, count | Exact integer |
| Child count | DOB → age (0-15) on travel date, count | Exact integer |

### Precedence Rules

1. If ground truth specifies a field and agent **omits** it → **mismatch**
2. If ground truth **omits** a field (e.g., no `passengers`) → agent value is **ignored** (pass)
3. **Missing `passengers[]` → default 1 adult, 0 children** (browser-verified)
4. **Station URNs match on CRS prefix** — `KGX4832gb` == `KGX6121gb` (browser-verified)
5. Journey type must match when GT specifies it — `return` ≠ `single`
6. Inward date is checked **only** when GT specifies one (return trips)
7. Adults and children counts are compared by **category**, not by exact DOB
8. First successful match across multi-GT URLs → **score = 1.0** (OR semantics)
9. Time portion of dates is **always ignored** — only the date matters

### Matching Flow

```
Agent URL → Parse → Normalize
  ↓
GT URL → Parse → Normalize
  ↓
Compare: origin → destination → outward_date → inward_date → journey_type → adults → children
  ↓
All match? → score = 1.0
Any mismatch? → score = 0.0 (with mismatch details logged)
```

---

## 7. Railcard & Discount System

Trainline supports numerous UK railcards, observable in the passenger selection dropdown
on the search results page:

| Railcard | Discount | Note |
| :--- | :--- | :--- |
| 16-25 Railcard | 1/3 off | Young person |
| 26-30 Railcard | 1/3 off | Young adult |
| Senior Railcard | 1/3 off | 60+ |
| Network Railcard | 1/3 off | SE England |
| Family & Friends Railcard | 1/3 off | Up to 4 adults + children |
| Two Together Railcard | 1/3 off | 2 named adults |
| Disabled Persons Railcard | 1/3 off | + companion |
| Veterans Railcard | 1/3 off | Armed forces |

> [!NOTE]
> Railcards are **NOT** encoded in the search URL. They are applied at the
> checkout/basket stage. The verifier does not validate railcard selection.
> Benchmark tasks may mention railcards as **red herrings** to test whether
> the agent correctly ignores them during the search phase.

---

## 8. Transport Modes

Trainline offers multiple transport modes on the results page:

| Mode | Tab Label | URL Parameter |
| :--- | :--- | :--- |
| Train | `Train • $XX.XX` | `selectedTab=train` |
| Bus | `Bus • $XX.XX` | `selectedTab=bus` |
| Mixed | (default) | `transportModes[]=mixed` |

> [!NOTE]
> Transport mode is **ignored** by the verifier. Benchmark tasks focus on
> origin, destination, dates, and passenger configuration only.

---

## 9. Test & Benchmark Coverage

### Unit Tests

**87 tests** across 11 test classes, covering:

| Category | Tests | Focus |
| :--- | :---: | :--- |
| Station URN Normalization | 9 | Full URN, URL-encoded, bare code, numeric-only, Manchester (Any) |
| CRS Prefix Matching | 14 | Prefix extraction, same-station different suffix, city-level exact |
| Date Extraction | 5 | ISO datetime → date-only, URL-encoded colons |
| Journey Type Normalization | 7 | `single`/`return`/`openReturn` + aliases |
| DOB → Age Classification | 9 | Adult/child threshold (16), edge cases, groups |
| URL Parsing | 6 | Full parse pipeline, browser-captured URLs, missing passengers |
| URL Matching | 16 | All mismatch scenarios + CRS matching + default passengers |
| Domain Validation | 8 | Primary, regional, subdomains, rejection |
| Async Lifecycle | 7 | `reset` → `update` → `compute`, match persistence |
| Multi-GT URLs | 3 | OR semantics (first/second/none match) |
| Edge Cases | 6 | Missing fields, empty URLs, non-search pages |

### Benchmark Dataset

**70 tasks** in `trainline_benchmark_tasks.csv` — **all hard difficulty**:

Tasks are designed with advanced difficulty strategies to challenge AI models:

| Category | Count | Difficulty Strategy |
| :--- | :---: | :--- |
| UK Domestic Singles | 15 | Correct terminal selection, implicit passenger counts |
| UK Domestic Returns | 15 | Return date extraction, complex narratives |
| Eurostar International | 10 | St Pancras requirement, family groups with children |
| Complex Passengers | 10 | Extended families, group maths (6 adults + 5 children) |
| Red Herring Tasks | 10 | Irrelevant details: weather, restaurants, loyalty cards |
| Multi-Station Tasks | 5 | Explicit terminal constraints (Euston vs Kings Cross) |
| Ultra-Hard Combos | 5 | Maximum difficulty — 11+ passengers, nested family counts |

---

## Appendix A: Live URL Examples

### One-way Single (London Euston → Manchester)
```
https://www.thetrainline.com/book/results?
  journeySearchType=single
  &origin=urn%3Atrainline%3Ageneric%3Aloc%3AEUS1444gb
  &destination=urn%3Atrainline%3Ageneric%3Aloc%3AMAN2968gb
  &outwardDate=2026-05-01T13%3A15%3A00
  &outwardDateType=departAfter
  &passengers%5B%5D=1991-04-13
  &lang=en-us
  &selectedTab=train
```

### Return Trip (Manchester → Edinburgh, 2 adults)
```
https://www.thetrainline.com/book/results?
  journeySearchType=return
  &origin=urn%3Atrainline%3Ageneric%3Aloc%3AMAN2968gb
  &destination=urn%3Atrainline%3Ageneric%3Aloc%3AEDB9328gb
  &outwardDate=2026-05-01T13%3A15%3A00
  &outwardDateType=departAfter
  &inwardDate=2026-05-05T14%3A30%3A00
  &inwardDateType=departAfter
  &passengers%5B%5D=1991-04-13
  &passengers%5B%5D=1993-03-13
  &lang=en-us
```

### Eurostar (London St Pancras → Paris, 1 adult + 1 child)
```
https://www.thetrainline.com/book/results?
  journeySearchType=single
  &origin=urn%3Atrainline%3Ageneric%3Aloc%3ASTP1555gb
  &destination=urn%3Atrainline%3Ageneric%3Aloc%3A4916
  &outwardDate=2026-05-15T09%3A00%3A00
  &outwardDateType=departAfter
  &passengers%5B%5D=1990-01-15
  &passengers%5B%5D=2018-03-25
  &lang=en-us
```

### Large Group (4 adults + 3 children)
```
https://www.thetrainline.com/book/results?
  journeySearchType=single
  &origin=urn%3Atrainline%3Ageneric%3Aloc%3APAD2935gb
  &destination=urn%3Atrainline%3Ageneric%3Aloc%3ABRI3231gb
  &outwardDate=2026-06-01T12%3A00%3A00
  &outwardDateType=departAfter
  &passengers%5B%5D=1990-01-15
  &passengers%5B%5D=1985-06-20
  &passengers%5B%5D=1992-03-10
  &passengers%5B%5D=1988-11-05
  &passengers%5B%5D=2019-08-15
  &passengers%5B%5D=2017-07-12
  &passengers%5B%5D=2013-04-08
```

---

## Appendix B: Search Results Page Anatomy

The Trainline search results page displays the following information:

```
┌──────────────────────────────────────────────────────────┐
│  From: Manchester Piccadilly  →  To: Edinburgh (Waverley)│
│  Out: Fr 1 May • 13:15    Return: Tu 5 May • 14:30      │
│  2 adults • Add railcards                                │
├──────────────────────────────────────────────────────────┤
│  [Train • $90.68]  [No buses available]  [Add via/avoid] │
├──────────────────────────────────────────────────────────┤
│  OUT                              RETURN                 │
│  Fri, May 1, 2026                 Tue, May 5, 2026       │
│  Manchester Piccadilly            Edinburgh (Waverley)    │
│  to Edinburgh (Waverley)          to Manchester Piccadilly│
│                                                          │
│   Depart → Arrive   Standard   1st class                 │
│   1:13pm → 5:31pm   $103.07    $199.24                  │
│   1:18pm → 5:38pm   $93.92     $167.56                  │
│   ...                                                    │
└──────────────────────────────────────────────────────────┘
```

Key observations:
- **Standard** and **1st class** fares are shown side by side
- Class selection happens by clicking the fare radio button (not in URL)
- **"Cheapest"** badge highlights the lowest-fare option
- **"Limited availability"** and **"Only X left"** indicators appear for scarce fares
- **"Non-rail legs on some routes"** warning appears for indirect routes
