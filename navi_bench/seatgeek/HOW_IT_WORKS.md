# How the SeatGeek Verifier Works

## Technical Deep Dive into the Verification Architecture

---

## 1. Overview

The SeatGeek verifier is a **DOM-based event ticket verification system** that determines whether an AI agent has navigated to the correct event on SeatGeek and applied the requested filters. Unlike URL-based verifiers (Realtor, Zillow, Redfin, StreetEasy), it uses a **3-layer extraction pipeline** combining URL parsing, LD+JSON extraction, and DOM scraping.

### 1.1 Core Philosophy

**"Scrape → Normalize → Match"**

1. **Scrape** the page using injected JavaScript (LD+JSON + DOM)
2. **Normalize** extracted data to canonical forms
3. **Match** normalized data against query criteria

This approach is necessary because SeatGeek:
- Blocks HTTP requests (403) — requires browser context
- Uses DOM-only filters (seat map, seat perks) not reflected in URL
- Encodes rich data in LD+JSON and listing `aria-label` attributes

### 1.2 Similarity to StubHub Verifier

This module follows the StubHub verifier pattern:
- JS scraper injected via `page.evaluate()`
- Navigation tracking via `attach_to_context()`
- Stack-based evidence collection
- Multi-candidate query matching

---

## 2. Architecture

### 2.1 High-Level Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        SEATGEEK VERIFICATION PIPELINE                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐     ┌────────────────┐     ┌────────────────┐           │
│  │  Browser Page   │────▶│  JS Scraper    │────▶│  InfoDict      │           │
│  │  (Playwright)   │     │  (injected)    │     │  (structured)  │           │
│  └────────────────┘     └────────────────┘     └───────┬────────┘           │
│                                                         │                    │
│                                                         ▼                    │
│                                                 ┌────────────────┐          │
│                                                 │  Navigation    │          │
│                                                 │     Stack      │          │
│                                                 │ [info1, info2] │          │
│                                                 └───────┬────────┘          │
│                                                         │                    │
│  ┌────────────────┐                                     │                    │
│  │  Query List    │─────────────────────────────────────┤                    │
│  │  [{event_names,│                                     ▼                    │
│  │    cities,...}] │                             ┌────────────────┐          │
│  └────────────────┘                             │    MATCHER     │          │
│                                                 │                │          │
│                                                 │ For each query:│          │
│                                                 │ Walk stack     │          │
│                                                 │ backwards,     │          │
│                                                 │ check match    │          │
│                                                 └───────┬────────┘          │
│                                                         │                    │
│                                              ┌──────────┴──────────┐        │
│                                              ▼                     ▼        │
│                                        ┌──────────┐         ┌──────────┐   │
│                                        │  MATCH   │         │ NO MATCH │   │
│                                        │ Score=1.0│         │ Score=0.0│   │
│                                        └──────────┘         └──────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 The 3-Layer Extraction

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: URL Parsing                                        │
│   • Event ID, category from path segments                   │
│   • quantity, max_price from query params                    │
│   • Page type detection (performer/event/category/search)   │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: LD+JSON Extraction                                 │
│   • Event name, date, venue, city, state                    │
│   • Teams/performers (competitor array)                     │
│   • Price range (lowPrice, highPrice)                       │
│   • Inventory level (total tickets)                         │
│   • Event type (@type: SportsEvent, MusicEvent, etc.)       │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: DOM Scraping                                       │
│   • Listing aria-label parsing (section, row, qty, price)   │
│   • Deal Score extraction                                   │
│   • Filter panel state                                      │
│   • Meta tags (og:title, og:url)                            │
│   • Page title                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. JavaScript Scraper (`seatgeek_info_gathering.js`)

### 3.1 What It Extracts

The JS scraper runs in the browser context via `page.evaluate()` and returns a structured object:

```javascript
{
  // Layer 1: URL
  url: "https://seatgeek.com/...",
  pageType: "event_listing",  // performer, event_listing, category, search, checkout
  eventId: "17669139",
  category: "nba",
  urlFilters: { quantity: "2", max_price: "100" },
  
  // Layer 2: LD+JSON
  eventName: "Phoenix Suns at Los Angeles Lakers",
  eventType: "SportsEvent",
  startDate: "2026-02-26T19:00",
  venue: "Arizona Mortgage Matchup Center",
  city: "Phoenix",
  state: "AZ",
  country: "US",
  competitors: ["Los Angeles Lakers", "Phoenix Suns"],
  lowPrice: 15,
  highPrice: 2500,
  inventoryLevel: 1847,
  
  // Layer 3: DOM
  title: "Lakers at Suns tickets...",
  h1: "Los Angeles Lakers at Phoenix Suns",
  listings: [
    { section: "110", row: "9", minQty: 1, maxQty: 3, price: 321, dealScore: 10 },
    { section: "GA", row: "GA", minQty: 1, maxQty: 6, price: 85, dealScore: 7 }
  ],
  totalListings: 47,
  metaDescription: "...",
  ogTitle: "...",
  ogUrl: "..."
}
```

### 3.2 Page Type Detection Logic

```javascript
function detectPageType(url) {
  const path = new URL(url).pathname;
  
  // Event page: /{team}-tickets/{date-venue}/{category}/{id}
  if (/\/.+-tickets\/.+\/.+\/\d+/.test(path)) return 'event_listing';
  
  // Performer page: /{performer}-tickets (no sub-paths)
  if (/\/.+-tickets$/.test(path)) return 'performer';
  
  // Search page: /search
  if (path === '/search') return 'search';
  
  // Category pages
  const categories = ['sports', 'concert', 'theater', 'comedy', 'nba', 'nfl', 'mlb', 'nhl', 'mls'];
  if (categories.some(c => path.includes(c))) return 'category';
  
  // Homepage
  if (path === '/') return 'homepage';
  
  return 'unknown';
}
```

### 3.3 Listing `aria-label` Parsing

```javascript
function parseListingAriaLabel(label) {
  const match = label.match(
    /Section\s+(.+?),\s*Row\s+(.+?),\s*(\d+)\s+to\s+(\d+)\s+tickets?\s+at\s+\$?([\d,.]+)\s+each(?:,\s*Deal Score\s+(\d+))?/i
  );
  if (!match) return null;
  return {
    section: match[1],
    row: match[2],
    minQty: parseInt(match[3]),
    maxQty: parseInt(match[4]),
    price: parseFloat(match[5].replace(/,/g, '')),
    dealScore: match[6] ? parseInt(match[6]) : null
  };
}
```

---

## 4. Python Verifier (`seatgeek_info_gathering.py`)

### 4.1 Query Model

```python
class MultiCandidateQuery(TypedDict, total=False):
    event_names: list[str]           # e.g., ["lakers", "los angeles lakers"]
    event_categories: list[str]      # e.g., ["sports", "basketball", "nba"]
    cities: list[str]                # e.g., ["los angeles", "la"]
    venues: list[str]                # e.g., ["crypto.com arena"]
    dates: list[str]                 # e.g., ["2026-02-26"]
    min_price: float                 # e.g., 50.0
    max_price: float                 # e.g., 200.0
    quantity: int                    # e.g., 2
    sections: list[str]              # e.g., ["110", "111"]
    require_available: bool          # Must have inventory
    require_page_type: str           # e.g., "event_listing"
```

### 4.2 Matching Logic

The matcher walks the navigation stack backwards (most recent page first):

```python
for evidence in reversed(navigation_stack):
    for query in queries:
        if _check_query(query, evidence):
            mark_query_covered(query)
```

### 4.3 Query Check Rules

| Field | Match Logic |
|-------|-------------|
| `event_names` | Any name appears in event name (case-insensitive, partial) |
| `event_categories` | Any category matches LD+JSON `@type` or URL category |
| `cities` | Any city matches LD+JSON city (case-insensitive) |
| `venues` | Any venue matches LD+JSON venue (case-insensitive, partial) |
| `dates` | Any date matches LD+JSON `startDate` (date part only) |
| `min_price` | LD+JSON `lowPrice` <= specified min |
| `max_price` | LD+JSON `highPrice` >= specified max OR URL `max_price` param |
| `quantity` | URL `quantity` param matches OR listings have matching qty range |
| `sections` | Any section appears in DOM listings |
| `require_available` | `inventoryLevel > 0` in LD+JSON |

---

## 5. Navigation Tracking

### 5.1 attach_to_context()

Auto-tracks all page navigations:

```python
async def attach_to_context(self, context):
    async def track_page(page):
        async def on_navigated(frame):
            if frame == page.main_frame:
                await self.update(page=page)
        page.on("framenavigated", on_navigated)
    
    context.on("page", track_page)
    for page in context.pages:
        await track_page(page)
```

### 5.2 Navigation Stack

Each `update()` appends to the stack:
```python
self._navigation_stack.append({
    'url': page.url,
    'page_type': detected_type,
    'info': scraped_info,
    'timestamp': time.time()
})
```

---

## 6. Example Walkthrough

### Task: "Find Lakers tickets for under $200"

**Query:**
```python
{
    "event_names": ["lakers", "los angeles lakers"],
    "max_price": 200,
    "require_available": True
}
```

**Agent Navigation:**
1. Goes to `/search?search=Lakers` → redirected to `/los-angeles-lakers-tickets?oq=Lakers`
2. Clicks first event → `/phoenix-suns-tickets/2-26-2026-.../nba/17669139?max_price=200`

**Verification:**
1. `update()` called on performer page → scrapes LD+JSON with Lakers events
2. `update()` called on event page → scrapes event LD+JSON + DOM listings
3. `compute()` walks stack backwards:
   - Event page: name contains "lakers" ✅, `lowPrice=15 <= 200` ✅, `inventoryLevel > 0` ✅
   - **MATCH** → Score = 1.0

---

**Last Updated:** 2026-02-25
**Implementation Version:** 1.0
