# Technical Selector Map: Things to Do (Activities)

## 1\. Core Page Logic

*   **Context Detection:** Identify "Things to Do" mode via URL patterns: `/Attractions-` or `/Activities-`.
    
*   **State Source of Truth:** The **Action Bar** (`data-automation="actionBar"`) contains buttons/pills for every currently applied filter.
    
*   **Refresh Indicator:** Wait for `[data-automation="search_in_progress_message"]` to be **hidden** after every click.
    

* * *

## 2\. The Hierarchical Navigation Tree

The sidebar works as a three-tier funnel. Tiers 1 and 2 refresh the page/sidebar; Tier 3 updates results via AJAX.

### Tier 1: Global Category (Navbar)

*   **Container:** `div[data-filter-name="navbar"]`
    
*   **Selected State:** `div.XDHza:has(span.Dgygn)`
    
*   **Interaction:** Click `a.KoOWI` (e.g., "Attractions", "Tours", "Outdoor Activities").
    

### Tier 2: Sub-Category (Types of X)

*   **Container:** `div[data-filter-name="category"]`
    
*   **Selected State:** `div.XDHza:has(span.Dgygn)`
    
*   **Interaction:** Click `a.KoOWI` (e.g., "Sights & Landmarks", "Spas & Wellness").
    

### Tier 3: Specific Activity Type (Checkboxes)

*   **Container:** `div#type_filter_contents`
    
*   **Interaction:** Click `label[for^="main_type_"]`.
    
*   **State Hook:** Check `input.checked` or `aria-checked="true"`.
    

* * *

## 3\. Search Inputs & Sorting

| Feature | Primary Anchor | Value Selector | Logic |
| --- | --- | --- | --- |
| Date Range | button[aria-haspopup="dialog"] | button span span | Single button for range. Read aria-label for full date. |
| Sort Order | div[data-automation="actionBar"] button:has-text("Sort") | span.biGQs inside button | Click to open listbox; target role="option". |
| Clear All | button:has-text("Clear all filters") | N/A | Resets all sidebar and action bar selections. |

* * *

## 4\. Attribute Filter Groups (Sidebar)

Use unique ID prefixes to identify checkboxes within these specific containers.

| Group Name | Section Anchor (Text) | ID Prefix Hook | Expansion Button |
| --- | --- | --- | --- |
| Languages | "Languages" | main_language_ | [aria-controls="language_filter_options"] |
| Unique Exp. | "Unique Experiences" | main_themes_ | [aria-controls="themes_filter_options"] |
| Time of Day | "Time of Day" | main_timeOfDay_ | N/A (Standard list) |
| Duration | "Duration" | main_duration_ | N/A (Standard list) |
| Accessibility | "Accessibility" | main_accessibilityTag_ | N/A (Standard list) |
| Awards | "Awards" | main_awardCategories_ | [aria-controls="awardCategories_filter_contents"] |

* * *

## 5\. Specialized Selection Logic

### Price Range Slider

*   **Container:** `div#price_filter_contents`
    
*   **Handles:** `div[role="slider"]`
    
*   **Attributes:** Use `aria-valuenow` to get/set numeric limits.
    
*   **Labels:** Match `aria-label="Minimum price"` and `aria-label="Maximum price"`.
    

### Neighborhoods (Modal Interaction)

*   **Container:** `div:has(> div:text-is("Neighborhoods"))`
    
*   **Checkbox Prefix:** `main_neighborhood_`
    
*   **Expansion Logic:** Clicking "Show all" may open a **Modal** (`aria-controls="neighborhood_filter_modal"`). The agent must wait for the modal to be visible before scraping.
    

* * *

## 6\. Result Scraper Data Points

Target: `div[data-automation="cardWrapper"]` inside `div[data-automation="LeftRailMain"]`.

*   **Listing ID:** `data-automation="trips-save-button-item-[ID]"` (Unique numeric ID).
    
*   **Title:** `h3.biGQs div.ATCbm` (Ignore leading index numbers like "1.").
    
*   **Bubble Rating:** `svg[data-automation="bubbleRatingImage"] title`. Use regex `/(\d+(\.\d+)?) of 5/`.
    
*   **Review Count:** `div[data-automation="bubbleReviewCount"]`.
    
*   **Price:** `div[data-automation="cardPrice"]`.
    
*   **Offer Tags:** `div[data-automation="cardSpecialOfferTags"]` (e.g., "Likely to Sell Out").
    

* * *

## Interaction Strategy

1.  **Traversal:** To select a deep-level filter (e.g., "Yoga"), verify Tier 1 ("Attractions") and Tier 2 ("Spas & Wellness") are active first.
    
2.  **Compatibility:** If a checkbox is `disabled=""`, it cannot be combined with current Tier 1/2 selections.
    
3.  **Validation:** After any selection, verify the name of the selection appears as a button text in `div[data-automation="actionBar"]`.
    
4.  **Pagination:** Use `a[data-smoke-attr="pagination-next-arrow"]` to move through the tree's result leaves.