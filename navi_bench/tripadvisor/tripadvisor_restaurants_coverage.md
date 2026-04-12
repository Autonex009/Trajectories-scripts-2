# **TripAdvisor "Restaurants" Selector Map:**

## **1\. Core Search & Booking Bar (Find a Table)**


| **Feature**       | **Data Automation Anchor**            | **Value Selector** | **Interaction Logic**                                   |
| ----------------- | ------------------------------------- | ------------------ | ------------------------------------------------------- |
| **Enter Date**    | \[data-automation="enterDate"\]       | button span span   | Click to open dialog. Format: Thu, 09 Apr.              |
| ---               | ---                                   | ---                | ---                                                     |
| **Enter Time**    | \[data-automation="enterTime"\]       | button span        | Click to open listbox. Default: 7:00 pm.                |
| ---               | ---                                   | ---                | ---                                                     |
| **Party Size**    | \[data-automation="enterGuests"\]     | button span span   | Click to open listbox. Default: 2.                      |
| ---               | ---                                   | ---                | ---                                                     |
| **Search Button** | \[data-automation="findARestaurant"\] | button             | **Action:** Click to refresh results with availability. |
| ---               | ---                                   | ---                | ---                                                     |

## **2\. Categorical Filter Groups (Sidebar)**

_Logic Pattern:_ Scope each group using the role="group" container that includes the specific h3 header text.

| **Group Name**           | **ID Prefix Hook**  | **Expansion Button Hook**                             |
| ------------------------ | ------------------- | ----------------------------------------------------- |
| **Establishment type**   | establishmentTypes. | \[aria-controls="filter-expando-establishmentTypes"\] |
| ---                      | ---                 | ---                                                   |
| **Meal type**            | mealTypes.          | N/A (Standard list)                                   |
| ---                      | ---                 | ---                                                   |
| **Cuisines**             | cuisines.           | button:has-text("Show all")                           |
| ---                      | ---                 | ---                                                   |
| **Dishes**               | dishes.             | button:has-text("Show all")                           |
| ---                      | ---                 | ---                                                   |
| **Awards**               | travelersChoice.    | \[aria-controls="awardCategories_filter_contents"\]   |
| ---                      | ---                 | ---                                                   |
| **Price**                | priceTypes.         | N/A (Standard list)                                   |
| ---                      | ---                 | ---                                                   |
| **Dietary restrictions** | diets.              | \[aria-controls="filter-expando-diets"\]              |
| ---                      | ---                 | ---                                                   |
| **MICHELIN Guide**       | michelinAwards.     | N/A (Standard list)                                   |
| ---                      | ---                 | ---                                                   |
| **Great for (Style)**    | styles.             | \[aria-controls="filter-expando-styles"\]             |
| ---                      | ---                 | ---                                                   |
| **Features**             | diningOptions.      | button:has-text("Show all")                           |
| ---                      | ---                 | ---                                                   |
| **Neighbourhood**        | neighbourhoods.     | button:has-text("Show all")                           |
| ---                      | ---                 | ---                                                   |
| **Airports**             | waypoints.          | N/A (Standard list)                                   |
| ---                      | ---                 | ---                                                   |

## **3\. State & Interaction Logic**

### **State Indicators**

- **Active Checkbox:** input\[aria-checked="true"\] or presence of the checked attribute.
- **Selected Broad Category:** In the Tier 1 Navbar, the active item is indicated by the class Dgygn.
- **Disabled State:** input\[disabled=""\]. (e.g., "High-octane rides" might be disabled if "Fine Dining" is selected).

### **Expanding Sections**

- **Accordion Toggle:** button.FSCFM (The arrow icon next to headers). Check aria-expanded="true/false".
- **"Show More" Inline:** Toggles the visibility of extra items within the same sidebar view.
- **"Show All" Modal:** May open a full-screen selection modal. The agent must handle the id="filter-modal" if it appears.

## **4\. Sort Order Component**

- **Main Anchor:** div.lOvTR button
- **Active Label:** span.biGQs.\_P.ezezH (e.g., "Featured").
- **Interaction:** Click the button to reveal the dropdown menu.
- **Heuristic Tooltip:** The sibling div.GRtXf contains an info icon that describes the sorting logic (e.g., "Restaurants ranked according to page views...").

## **5\. Result Scraper Data Points**

Target: div\[data-automation="cardWrapper"\]

- **Restaurant ID:** Scrape numeric ID from data-automation="trips-save-button-item-\[ID\]".
- **Title:** h3.biGQs (e.g., "1. Alinea").
- **Bubble Rating:** svg\[data-automation="bubbleRatingImage"\] title (e.g., "4.5 of 5 bubbles").
- **Review Count:** div\[data-automation="bubbleReviewCount"\] span.
- **Cuisine & Price Level:** Scrape the text string (e.g., "  
   • American • Contemporary").
- **Special Tags:** span.biGQs:text-is("Likely to Sell Out").

## **6\. Global Verification Flow**

- **Selection:** Click the label associated with the target input (e.g., id="cuisines.9908" for American).
- **Wait:** Wait for the results container to refresh.
- **ActionBar Check:** Verify that a pill with the text "American" exists in the data-automation="actionBar" container.
- **Count Sync:** Confirm that the results count (X results sorted by...) updated to a new number.