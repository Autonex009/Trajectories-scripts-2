This document provides the technical mapping for the **Cruises (L2 Category)**. It includes specific selectors for the date picker, active filters (Action Bar), and the sidebar filter groups. 

### URL Structure Note

The Cruises category follows a specific geo-encoded pattern:

`https://www.tripadvisor.com/Cruises-[GeoID]-[Location_Name]-Cruises`

_Example:_ `https://www.tripadvisor.com/Cruises-g14114078-Mediterranean-Cruises`

* * *

# Technical Selector Map: Cruises (L2 Category)

## 1\. Date Selection (View Prices From)

This component triggers the availability search based on the month of departure.

| Feature | Selector | Value Location | Interaction |
| --- | --- | --- | --- |
| Date Trigger | div.btiUA._S | span.mHCeW.H4 | Click to open Month/Year picker. |
| Current Month | span.mHCeW.H4 | Text (e.g., "Jun 2026") | Scrape to verify active search window. |

* * *

## 2\. Active Selections (Action Bar)

Cruises use an "Action Bar" at the top of the filters to show what is currently applied.

*   **Main Container:** `div#filtersDiv ul.pKGCB`
    
*   **Clear All Button:** `div.LmeYj.S2`
    
*   **Individual Pills:** `li.oSjvu`
    
    *   **Port Selection:** `li[data-automation="filter-selection-li-departurePorts"]`
        
    *   **Cruise Line:** `li[data-automation="filter-selection-li-cruiseLines"]`
        
    *   **Ship Name:** `li[data-automation="filter-selection-li-ships"]`
        
    *   **Deal Type:** `li[data-automation="filter-selection-li-deals"]`
        

* * *

## 3\. Sidebar Filter Groups

_Logic Pattern:_ Each group is a `div.QClzD`. Inside, there is a header (`div.MDRRl`) and a content body (`div.content.tSmPf`).

| Group Name | Header Text (Selector) | Interaction Type | Input Selector |
| --- | --- | --- | --- |
| Deal Type | div:contains("Deal Type") | Checkbox | input[type="checkbox"] |
| Departing from | div:contains("Departing from") | Checkbox | input[type="checkbox"] |
| Cruise length | div:contains("Cruise length") | Checkbox | input[type="checkbox"] |
| Cruise line | div:contains("Cruise line") | Checkbox | input[type="checkbox"] |
| Price | div:contains("Price") | Range Slider | div[role="slider"] |
| Cruise Style | div:contains("Cruise Style") | Checkbox | input[type="checkbox"] |
| Ship | div:contains("Ship") | Checkbox | input[type="checkbox"] |
| Cabin type | div:contains("Cabin type") | Radio | input[type="radio"] |
| Port | div:contains("Port") | Checkbox | input[type="checkbox"] |

* * *

## 4\. Specific Interaction Logic

### Sort Order Component (Cruises)

Description: Controls the sorting logic for cruise search results (for example, Price or Best Value).

| Feature | Selector | Value Location | Interaction |
| --- | --- | --- | --- |
| Sort Container | `div.DYAfS` | Parent "Sort by:" wrapper | Use as the main anchor for locating the sort control. |
| Dropdown Trigger | `div.jvgKF.B1.Z.S4` | Interactive element inside the sort area | Click to expand the sort menu. |
| Current Value Selector | `div.jvgKF span` | Text shown inside the trigger | Scrape to verify the active sorting choice. |

Interaction Strategy:

*   Locate the button via the `div.jvgKF` class.
*   Click to expand the sort options.
*   Select the desired sorting criteria from the resulting list, usually `role="option"` or specific text-based `div` nodes.

### The "More" Toggle

Many cruise filter lists (like Ports or Ships) are long and truncated.

*   **Selector:** `div.oZjhe.more`
    
*   **Action:** Click to expand the list within the sidebar.
    

### Price Slider

Unlike Hotels, the Cruise price filter uses dual sliders and manual input fields.

*   **Min Input:** `input.krvDH:first-child`
    
*   **Max Input:** `input.krvDH:last-child`
    
*   **Min Slider:** `div[aria-label="Minimum price"]`
    
*   **Max Slider:** `div[aria-label="Maximum price"]`
    

### Radio Group (Cabin Type)

*   **Container:** `div[role="radiogroup"]`
    
*   **Constraint:** Only one can be active at a time. The agent must verify `aria-checked="true"` on the `input` tag.
    

* * *

## Coding Logic

> 1.  **URL Handling:** Target URLs containing `/Cruises-`.
> 2.  **Filter Logic:** Implement the sidebar scraper using the `div.QClzD` parent logic. Note that **Cabin Type** uses `type="radio"`, while others use `type="checkbox"`.  
> 3.  **Active State:** Use `li.oSjvu` to verify if a filter click was successful. 
> 4.  **Sort Logic:** Read the current sort value from `div.jvgKF span`, and interact with `div.jvgKF.B1.Z.S4` to validate sort changes.
> 5.  **Pagination/Loading:** After any filter interaction, wait for the results container (sibling to `div.PLbjs`) to update. Check for a loading overlay or the "Search in progress" toast.  
> 6.  **Expansion:** If a requested port/ship is not visible, the script must look for and click `div.oZjhe.more`.
