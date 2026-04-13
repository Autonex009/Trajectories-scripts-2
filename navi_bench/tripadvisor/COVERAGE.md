# TripAdvisor Coverage

## Scope

This package adds verifiers for `tripadvisor.com` result pages.
The bundled task set currently covers hotel, thingstodo, cruises search flows. 

## Coverage

### 1. Hotels

### **1\. Check-In Date Picker**

- **Description:** The primary input for selecting the arrival date at a property.
- **Main Anchor (Button):** button\[data-automation="checkin"\]
- **Human-Readable Label:** "Check In" (Found via div.navcl).
- **Current Value Selector:** button\[data-automation="checkin"\] span > div > div > span
- **Accessibility Hook:** aria-label (Contains the full date string: "Enter the date. The selected date is Monday, April 20, 2026.")
- **State Indicators:**
  - **Expanded:** aria-expanded="false" (Changes to true when the calendar is open).
  - **Popup Type:** aria-haspopup="dialog".
- **Interaction Strategy:**
  - Click the button\[data-automation="checkin"\].
  - Verify the calendar dialog appears.
- **Verification Point (Heuristic):**
  - Check if the innerText of the button's child &lt;span&gt; matches the expected date format (e.g., "Mon, Apr 20").
  - Regex for verification: /\[A-Z\]\[a-z\]{2},\\s\[A-Z\]\[a-z\]{2}\\s\\d{1,2}/

### **2\. Check-Out Date Picker**

- **Description:** The primary input for selecting the departure date at a property.
- **Main Anchor (Button):** button\[data-automation="checkout"\]
- **Human-Readable Label:** "Check Out" (Found via div.navcl).
- **Current Value Selector:** button\[data-automation="checkout"\] span > div > div > span
- **Accessibility Hook:** aria-label (Contains the full date string: "Enter the date. The selected date is Tuesday, April 21, 2026.")
- **State Indicators:**
  - **Expanded:** aria-expanded="false" (Changes to true when the calendar is open).
  - **Popup Type:** aria-haspopup="dialog".
- **Interaction Strategy:**
  - Click the button\[data-automation="checkout"\].
  - Verify the calendar dialog appears.
- **Verification Point (Heuristic):**
  - Check if the innerText of the button's child &lt;span&gt; matches the expected date format (e.g., "Tue, Apr 21").
  - Regex for verification: /\[A-Z\]\[a-z\]{2},\\s\[A-Z\]\[a-z\]{2}\\s\\d{1,2}/

### **3\. Rooms and Guests Picker**

- **Description:** Input for selecting the number of rooms and the total count of guests (adults/children).
- **Main Anchor (Button):** button\[data-automation="roomsandguests"\]
- **Human-Readable Label:** "Guests" (Found via div.biGQs.\_P.navcl).
- **Current Value Selectors:**
  - **Room Count:** Found in the first div child of the oUhqQ container (associated with the bed/room SVG).
  - **Guest Count:** Found in the second div child of the oUhqQ container (associated with the person SVG).
- **Accessibility Hook:** aria-label (Directly provides the current state: "The selected number of rooms is 1 and the selected number of guests is 2.")
- **State Indicators:**
  - **Expanded:** aria-expanded="false" (Checks if the selection popover is active).
- **Interaction Strategy:**
  - Click the button\[data-automation="roomsandguests"\].
  - Verify the configuration dialog (steppers for rooms/adults/children) appears.
- **Verification Point (Heuristic):**
  - The UI uses SVG icons followed by text integers. Scrape the text nodes following the SVGs within the data-automation="roomsandguests" container.
  - Regex for room/guest pair: /\\d+\\s+\\d+/ (extracted from the numeric text nodes).

### **4\. Popular Filters (Grouped)**

- **Description:** A sidebar section containing frequently used filters such as amenities, star ratings, and property styles.
- **Section Anchor:** div:has(> h3:text-is("Popular")) or div\[role="group"\]:has(h3)
- **Individual Item Selector:** label.oTKjO
- **Data Points & Logic:**

| **Filter Name**  | **Value Attribute** | **Checkbox Selector**         | **Heuristic Text Search**        |
| ---------------- | ------------------- | ----------------------------- | -------------------------------- |
| **Pets Allowed** | amenity:9167        | input\[value="amenity:9167"\] | label:has-text("Pets Allowed")   |
| ---              | ---                 | ---                           | ---                              |
| **5 Star**       | class:9572          | input\[value="class:9572"\]   | \[data-automation="5starsF"\]    |
| ---              | ---                 | ---                           | ---                              |
| **4+ Bubbles**   | rating:4            | input\[value="rating:4"\]     | \[data-automation="4stars&UpF"\] |
| ---              | ---                 | ---                           | ---                              |
| **Luxury**       | style:9650          | input\[value="style:9650"\]   | label:has-text("Luxury")         |
| ---              | ---                 | ---                           | ---                              |

- **State Indicators:**
  - **Applied:** The presence of the checked attribute on the nested &lt;input&gt; element.
  - **Visual Active State:** Look for the parent \`&lt;span&gt;orwithin the label for specific style classes (e.g.,bYExrorchecked=""\` attribute presence).
- **Accessibility Hook:** For ratings, the &lt;title&gt; within the SVG provides a precise string: "4 of 5 bubbles".
- **Interaction Strategy:**
  - Locate the label by text content or the input by value.
  - Perform a click on the label element (clicking the input directly can sometimes be blocked by the custom styled span).
- **Verification Point (Heuristic):**
  - Verify the checked property of the input.
  - Cross-verify by checking if the label text appears in the "Selected filters" summary at the top of the page.

### **5\. Deals Filter Group**

- **Description:** Filter section focusing on booking flexibility and promotional offers.
- **Section Anchor:** div:has(> h3:text-is("Deals"))
- **Common Structure:** Contains a mix of span\[role="menuitem"\] wrappers and standalone label elements.
- **Data Points & Logic:**

| **Filter Name**                    | **Value Attribute** | **Checkbox Selector** | **Data-Automation Hook**                |
| ---------------------------------- | ------------------- | --------------------- | --------------------------------------- |
| **Free cancellation**              | 2                   | input\[value="2"\]    | \[data-automation="freeCancellationF"\] |
| ---                                | ---                 | ---                   | ---                                     |
| **Reserve now, pay later**         | 3                   | input\[value="3"\]    | \[data-automation="reserveNowF"\]       |
| ---                                | ---                 | ---                   | ---                                     |
| **Properties with special offers** | 1                   | input\[value="1"\]    | \[data-automation="specialOffersF"\]    |
| ---                                | ---                 | ---                   | ---                                     |

- **State Indicators:**
  - **Applied:** Check for the checked property on the input. (Note: In your provided HTML, **Free cancellation** is currently checked).
- **Additional UI Elements:**
  - **Info Tooltips:** Buttons with aria-label="Learn more" are adjacent to the labels. The explanation text is found in the following span.ghINY.
- **Interaction Strategy:**
  - Target the label via the specific data-automation span to ensure precision.
  - Click the label.oTKjO parent.
- **Verification Point (Heuristic):**
  - For "Free cancellation" and "Reserve now, pay later," there is an informational tooltip. Verify that the input.checked state is the source of truth, but cross-reference the data-automation text to ensure the labels haven't shifted.

### **6\. Price Range and Display Type**

- **Description:** A dual-component filter allowing users to set a specific price budget via a slider and choose how prices are calculated (per night, total stay, including/excluding taxes).
- **Container Anchor:** div\[data-automation="pRange"\]

#### **A. Price Slider (Range)**

- **Slider Tracks:** div.syAmd (Visual representation of the selected range).
- **Handles (Thumbs):**
  - **Minimum:** div\[role="slider"\]\[aria-label="Minimum price"\]
  - **Maximum:** div\[role="slider"\]\[aria-label="Maximum price"\]
- **Numeric Values:**
  - **Current Min/Max:** Found via aria-valuenow on the respective slider handles.
  - **Absolute Bounds:** aria-valuemin="0" and aria-valuemax="1604".
- **Visual Display Text:** div.biGQs.\_P.ZNjnF (e.g., "\$0 - \$1,604 +").
- **Interaction Strategy:**
  - Drag handles using Playwright's mouse.move or dispatch keydown events (ArrowLeft/ArrowRight) on the slider handles to change values.

#### **B. Price Display Type (Radio Group)**

- **Container:** div\[role="radiogroup"\]
- **Data Points & Logic:**

| **Display Option**              | **Value Attribute** | **ID**                      | **Selection State**           |
| ------------------------------- | ------------------- | --------------------------- | ----------------------------- |
| **Price + Fees**                | BASE_PLUS_FEES      | price-type-BASE_PLUS_FEES   | aria-checked="true" / checked |
| ---                             | ---                 | ---                         | ---                           |
| **Price + taxes and fees**      | ALL_IN_RATE         | price-type-ALL_IN_RATE      | aria-checked="false"          |
| ---                             | ---                 | ---                         | ---                           |
| **Total stay + taxes and fees** | ALL_IN_FULL_STAY    | price-type-ALL_IN_FULL_STAY | aria-checked="false"          |
| ---                             | ---                 | ---                         | ---                           |

- **Interaction Strategy:** Click the label associated with the specific radio id.
- **Verification Point (Heuristic):**
  - Check input.checked or input.getAttribute('aria-checked').
  - Verify the text within span.biGQs.\_P.AWdfh matches the selected display mode.

### **7\. Awards Filter Group**

- **Description:** Filters that allow users to view properties recognized by Tripadvisor's excellence programs (Travelers' Choice and Best of the Best).
- **Section Anchor:** div\[role="group"\]:has(h3:text-is("Awards"))
- **Common Structure:** Checkbox-based labels containing custom SVG icons for each award type.
- **Data Points & Logic:**

| **Award Filter Name** | **Value Attribute** | **Checkbox Selector** | **Description**               |
| --------------------- | ------------------- | --------------------- | ----------------------------- |
| **Best of the Best**  | BOTB                | input\[value="BOTB"\] | Top 1% of listings globally.  |
| ---                   | ---                 | ---                   | ---                           |
| **Travelers' Choice** | TC                  | input\[value="TC"\]   | Top 10% of listings globally. |
| ---                   | ---                 | ---                   | ---                           |

- **State Indicators:**
  - **Applied:** Check the checked property on the specific input element.
- **Additional UI Elements:**
  - **Group Tooltip:** The section header (h3) contains a "Learn more" button. The explanation text is in span.ghINY (ID \_lithium-r*61g*), explaining that these winners are in the top 10% of global listings.
- **Interaction Strategy:**
  - Target the label.oTKjO containing the text "Travelers' Choice" or "Best of the Best".
  - Click the label element to toggle the checkbox.
- **Verification Point (Heuristic):**
  - The UI uses complex SVG paths for the award badges. Verification should rely on the value="BOTB" or value="TC" attributes of the &lt;input&gt; as they are the most stable identifiers.
  - Use the presence of the text "Travelers' Choice Best of the Best" within the label span for human-readable confirmation.

### **8\. Property Types Filter Group**

- **Description:** Categorical filter allowing users to narrow results by accommodation style (e.g., Hotels, Condos, Hostels).
- **Section Anchor:** div\[role="group"\]:has(h3:text-is("Property types"))
- **Common Structure:** A list of checkbox-controlled labels followed by a "Show more" expansion button.
- **Data Points & Logic:**

| **Property Type**      | **Value Attribute** | **Checkbox Selector**  | **Data-Automation Hook**             |
| ---------------------- | ------------------- | ---------------------- | ------------------------------------ |
| **Hotels**             | 21371               | input\[value="21371"\] | \[data-automation="hotelsF"\]        |
| ---                    | ---                 | ---                    | ---                                  |
| **Specialty lodgings** | 21373               | input\[value="21373"\] | label:has-text("Specialty lodgings") |
| ---                    | ---                 | ---                    | ---                                  |
| **Condos**             | 9250                | input\[value="9250"\]  | label:has-text("Condos")             |
| ---                    | ---                 | ---                    | ---                                  |
| **Hostels**            | 9261                | input\[value="9261"\]  | label:has-text("Hostels")            |
| ---                    | ---                 | ---                    | ---                                  |

- **State Indicators:**
  - **Applied:** Check for the checked property on the input element (In the provided HTML, **Hotels** is checked).
- **Expansion Logic ("Show more"):**
  - **Trigger Button:** button:has(span\[data-automation="showMore"\])
  - **State Attribute:** aria-expanded="false" (Checks if the full list of property types is visible).
  - **Controlled Element:** aria-controls="filter-expando-type".
- **Interaction Strategy:**
  - Check if the target property type is visible.
  - If not visible, click the "Show more" button.
  - Click the label.oTKjO parent of the desired checkbox.
- **Verification Point (Heuristic):**
  - Use the value attribute for the most stable verification, as text like "Specialty lodgings" can sometimes be truncated in mobile views.
  - Verify that the "Show more" button text changes or the aria-expanded attribute updates to true upon interaction.

### **9\. Amenities Filter Group**

- **Description**: A comprehensive list of property features (e.g., Free Wifi, Pool) that users can filter by.
- **Section Anchor**: div\[role="group"\]:has(h3:text-is("Amenities"))
- **Common Structure**: A vertical list of checkboxes within span.VWnYD wrappers, featuring a "Show all" expansion button.
- **Data Points & Logic**:

| **Amenity Name**       | **Value Attribute** | **Input ID** | **Data-Automation Hook**                     |
| ---------------------- | ------------------- | ------------ | -------------------------------------------- |
| **Free Wifi**          | 9176                | amenity.9176 | \[data-automation="freeWifiF"\]              |
| ---                    | ---                 | ---          | ---                                          |
| **Breakfast included** | 9179                | amenity.9179 | \[data-automation="breakfastIncludedAmenF"\] |
| ---                    | ---                 | ---          | ---                                          |
| **Pool**               | 6217                | amenity.6217 | label:has-text("Pool")                       |
| ---                    | ---                 | ---          | ---                                          |
| **Pets Allowed**       | 9167                | amenity.9167 | label:has-text("Pets Allowed")               |
| ---                    | ---                 | ---          | ---                                          |

- **State Indicators**:
  - **Applied**: Check for the checked property on the &lt;input&gt; element or the aria-checked="true" attribute. (Note: In the provided HTML, **Free Wifi** is currently checked).
- **Expansion Logic ("Show all")**:
  - **Trigger Button**: button:has(span\[data-automation="showMore"\])
  - **Button Text**: Uses "Show all" instead of "Show more" for this specific group.
- **Interaction Strategy**:
  - Identify the specific checkbox by its unique id (e.g., amenity.9176).
  - To toggle, click the associated &lt;label&gt; using the for attribute that matches the input id.
- **Verification Point (Heuristic)**:
  - The id and for relationship (amenity.XXXX) is the most reliable technical binding.
  - For a human-centric check, verify the text within the span\[data-automation\] hooks.

### **10\. Distance From Filter Group**

- **Description: A dual-input filter allowing users to set a maximum distance radius from specific landmarks or points of interest.**
- **Section Anchor: div\[role="group"\]:has(h3:text-is("Distance from"))**

#### **A. Distance Slider (Radius)**

- **Slider Handle: div\[role="slider"\]\[aria-label="Maximum distance"\]**
- **Numeric Values: \* Current Value: aria-valuenow="25" (Captured as "25 mi" in the visual display).**
  - **Range Bounds: aria-valuemin="0.5" to aria-valuemax="25".**
- **Visual Display Text: div.biGQs.\_P.ZNjnF (Shows the live miles count).**
- **Interaction Strategy:**
  - **Focus the slider handle and use keyboard arrow keys or Playwright's mouse.move for dragging.**

#### **B. Landmark Selection (Radio Group)**

- **Container: div.nMmRW**
- **Data Points & Logic:**

| **Landmark Name**         | **Value Attribute** | **Input ID**         | **Selection State**      |
| ------------------------- | ------------------- | -------------------- | ------------------------ |
| **Burj Khalifa**          | **676922**          | **distance-676922**  | **aria-checked="false"** |
| ---                       | ---                 | ---                  | ---                      |
| **The Dubai Fountain**    | **1936354**         | **distance-1936354** | **aria-checked="false"** |
| ---                       | ---                 | ---                  | ---                      |
| **Aquaventure Waterpark** | **1200463**         | **distance-1200463** | **aria-checked="false"** |
| ---                       | ---                 | ---                  | ---                      |
| **Dubai Aquarium**        | **1792285**         | **distance-1792285** | **aria-checked="false"** |
| ---                       | ---                 | ---                  | ---                      |

- **  
   Expansion Logic:**
  - **Show More Button: button:has-text("Show more")**
  - **State Attribute: aria-expanded="false".**
  - **Controlled Element: aria-controls="filter-expando-distFrom".**

#### **C. Section Reset**

- **Reset Button: button:has-text("Reset")**
- **State Indicator: Contains disabled="" attribute when no local changes have been made in this group.**

### **11\. Neighborhoods Filter Group**

- **Description: Geolocation-based filters allowing users to narrow results to specific districts or areas (e.g., Deira, Bur Dubai).**
- **Section Anchor: div\[role="group"\]:has(h3:text-is("Neighborhoods"))**
- **Common Structure: A list of checkbox-controlled labels within a scrollable or expandable menu.**
- **Data Points & Logic:**

| **Neighborhood Name** | **Value Attribute** | **Checkbox Selector**         | **Heuristic Text Search**       |
| --------------------- | ------------------- | ----------------------------- | ------------------------------- |
| **Deira**             | **15620622**        | **input\[value="15620622"\]** | **label:has-text("Deira")**     |
| ---                   | ---                 | ---                           | ---                             |
| **Bur Dubai**         | **15620620**        | **input\[value="15620620"\]** | **label:has-text("Bur Dubai")** |
| ---                   | ---                 | ---                           | ---                             |
| **Al Barsha**         | **15620543**        | **input\[value="15620543"\]** | **label:has-text("Al Barsha")** |
| ---                   | ---                 | ---                           | ---                             |
| **Naif**              | **15620661**        | **input\[value="15620661"\]** | **label:has-text("Naif")**      |
| ---                   | ---                 | ---                           | ---                             |

- **  
   State Indicators:**
  - **Applied: Check for the checked property on the &lt;input&gt; element.**
- **Expansion Logic ("Show all"):**
  - **Trigger Button: button:has(span\[data-automation="showMore"\])**
  - **Button Text: "Show all" (Matches the 'Amenities' group style).**
- **Interaction Strategy:**
  - **Identify the target neighborhood by its unique numeric value.**
  - **Click the parent label.oTKjO element.**
  - **If the neighborhood is not in the initial list, trigger the "Show all" button first.**
- **Verification Point (Heuristic):**
  - **Neighborhood IDs are high-precision values. Use the value attribute for verification to avoid issues with localized neighborhood names or spelling variations.**

### **12\. Traveler Rating Filter Group**

- **Description:** Filter that narrows results based on aggregate user review scores, represented by Tripadvisor's bubble rating system.
- **Section Anchor:** div\[role="group"\]:has(h3:text-is("Traveler rating"))
- **Common Structure:** Checkbox-controlled labels containing SVG bubble icons and "& up" text.
- **Data Points & Logic:**

| **Rating Level** | **Value Attribute** | **Checkbox Selector** | **SVG Title Hook (Heuristic)**  |
| ---------------- | ------------------- | --------------------- | ------------------------------- |
| **5 Bubbles**    | 50                  | input\[value="50"\]   | title:text-is("5 of 5 bubbles") |
| ---              | ---                 | ---                   | ---                             |
| **4+ Bubbles**   | 40                  | input\[value="40"\]   | title:text-is("4 of 5 bubbles") |
| ---              | ---                 | ---                   | ---                             |
| **3+ Bubbles**   | 30                  | input\[value="30"\]   | title:text-is("3 of 5 bubbles") |
| ---              | ---                 | ---                   | ---                             |
| **2+ Bubbles**   | 20                  | input\[value="20"\]   | title:text-is("2 of 5 bubbles") |
| ---              | ---                 | ---                   | ---                             |

- **State Indicators:**
  - **Applied:** Check for the checked property on the &lt;input&gt; element.
- **Accessibility Hook:**
  - Each rating SVG contains a &lt;title&gt; element (e.g., id="\_lithium-r*621*" with text "4 of 5 bubbles") which is the most reliable way to identify the rating level if the value attributes are obscured.
- **Interaction Strategy:**
  - Target the specific rating level using the input\[value\] (e.g., 40 for 4 stars).
  - Click the parent label.oTKjO to trigger the filter.
- **Verification Point (Heuristic):**
  - The values are multiples of 10 (20, 30, 40, 50).
  - Use a regex on the SVG title: /(\\d) of 5 bubbles/ to confirm the selected rating matches the user's intent.

### **13\. Hotel Class Filter Group**

- **Description:** Categorical filters based on the official star rating of a property (e.g., 5 Star, 4 Star).
- **Section Anchor:** div\[role="group"\]:has(h3:text-is("Hotel class"))
- **Common Structure:** A list of checkbox-controlled labels with numeric value attributes and a "Show more" expansion button.
- **Data Points & Logic:**

| **Star Rating** | **Value Attribute** | **Checkbox Selector** | **Data-Automation Hook**                |
| --------------- | ------------------- | --------------------- | --------------------------------------- |
| **5 Star**      | 9572                | input\[value="9572"\] | \[data-automation="5starsHotelClassF"\] |
| ---             | ---                 | ---                   | ---                                     |
| **4 Star**      | 9566                | input\[value="9566"\] | \[data-automation="4starsHotelClassF"\] |
| ---             | ---                 | ---                   | ---                                     |
| **3 Star**      | 9568                | input\[value="9568"\] | label:has-text("3 Star")                |
| ---             | ---                 | ---                   | ---                                     |
| **2 Star**      | 9569                | input\[value="9569"\] | label:has-text("2 Star")                |
| ---             | ---                 | ---                   | ---                                     |

- **State Indicators:**
  - **Applied:** Check for the checked property on the &lt;input&gt; element. (In the provided HTML, **5 Star** is checked).
- **Expansion Logic ("Show more"):**
  - **Trigger Button:** button:has(span\[data-automation="showMore"\])
  - **State Attribute:** aria-expanded="false" (Checks if the full range of star ratings is visible).
  - **Controlled Element:** aria-controls="filter-expando-class".
- **Interaction Strategy:**
  - Identify the target class by its unique numeric value (e.g., 9572 for 5 Star).
  - Click the parent label.oTKjO element.
  - If a specific lower rating is not visible, trigger the "Show more" button.
- **Verification Point (Heuristic):**
  - Note the difference between "Traveler rating" (bubble icons) and "Hotel class" (star text).
  - Verification should rely on the value attributes as they map directly to the property's official classification in the database.

### **14\. Style Filter Group**

- **Description:** Qualitative filters that categorize properties by their target demographic or vibe (e.g., Luxury, Budget, Family-friendly).
- **Section Anchor:** div\[role="group"\]:has(h3:text-is("Style"))
- **Common Structure:** Standard list of checkbox-controlled labels with a "Show more" expansion button.
- **Data Points & Logic:**

| **Style Category**  | **Value Attribute** | **Checkbox Selector** | **Heuristic Text Search**         |
| ------------------- | ------------------- | --------------------- | --------------------------------- |
| **Budget**          | 5184                | input\[value="5184"\] | label:has-text("Budget")          |
| ---                 | ---                 | ---                   | ---                               |
| **Mid-range**       | 9654                | input\[value="9654"\] | label:has-text("Mid-range")       |
| ---                 | ---                 | ---                   | ---                               |
| **Luxury**          | 9650                | input\[value="9650"\] | label:has-text("Luxury")          |
| ---                 | ---                 | ---                   | ---                               |
| **Family-friendly** | 6216                | input\[value="6216"\] | label:has-text("Family-friendly") |
| ---                 | ---                 | ---                   | ---                               |

- **State Indicators:**
  - **Applied:** Presence of the checked property on the &lt;input&gt; element. (In the provided HTML, **Luxury** is currently checked).
- **Expansion Logic ("Show more"):**
  - **Trigger Button:** button:has(span\[data-automation="showMore"\])
  - **State Attribute:** aria-expanded="false" (Checks if additional styles like 'Romantic' or 'Business' are hidden).
  - **Controlled Element:** aria-controls="filter-expando-style".
- **Interaction Strategy:**
  - Target the label.oTKjO that contains the specific style name.
  - If the style is not in the visible top 4, click the "Show more" button.
  - Verify the checked attribute of the nested input.
- **Verification Point (Heuristic):**
  - The value attributes (9650 for Luxury) are consistent across different cities and search results.
  - Cross-verify with the "Selected filters" pills at the top of the sidebar.

### **15\. Brands Filter Group**

- **Description:** Filter by specific hotel chains or hospitality groups (e.g., OYO, Millennium, Jumeirah).
- **Section Anchor:** div\[role="group"\]:has(h3:text-is("Brands"))
- **Common Structure:** A list of checkboxes wrapped in span.VWnYD, following a strict ID-to-Label relationship (brand.XXXX), with a "Show all" expansion button.
- **Data Points & Logic:**

| **Brand Name** | **Value Attribute** | **Input ID** | **Checkbox Selector** |
| -------------- | ------------------- | ------------ | --------------------- |
| **OYO**        | 11779               | brand.11779  | input#brand\\.11779   |
| ---            | ---                 | ---          | ---                   |
| **Millennium** | 9243                | brand.9243   | input#brand\\.9243    |
| ---            | ---                 | ---          | ---                   |
| **Jumeirah**   | 9611                | brand.9611   | input#brand\\.9611    |
| ---            | ---                 | ---          | ---                   |
| **B&B Hotels** | 12212               | brand.12212  | input#brand\\.12212   |
| ---            | ---                 | ---          | ---                   |

- **State Indicators:**
  - **Applied:** Check for the checked property on the &lt;input&gt; element or the aria-checked="true" attribute. (In the provided HTML, **OYO** is currently checked).
- **Expansion Logic ("Show all"):**
  - **Trigger Button:** button:has(span\[data-automation="showMore"\])
  - **Interaction Strategy:** Click the "Show all" button to load the full list of brands available for the current location.
- **Interaction Strategy:**
  - Identify the checkbox by the unique id (e.g., brand.11779).
  - Click the associated &lt;label&gt; using the for attribute that matches the input id.
- **Verification Point (Heuristic):**
  - The id pattern brand.{value} is the most reliable technical anchor.
  - Verify that the selected brand name appears as a "Selected filter" pill at the top of the results page.

### **16\. Sort Order Dropdown**

- **Description:** Controls the sorting logic of the property results (e.g., Best Value, Price, Traveler Ranked).
- **Main Anchor (Button):** div\[data-automation="sort"\] button
- **Current Value Selector:** div\[data-automation="sort"\] button div.biGQs (e.g., "Best Value").
- **Accessibility Hook:** aria-label on the button (e.g., "BEST_VALUE: Best Value") and aria-expanded to detect if the menu is open.
- **Menu Container:** div\[role="listbox"\] (often contains an ID like \_lithium-r*3a*).
- **Data Points & Logic:**

| **Sort Option**         | **Option ID**               | **Selection State Attribute** | **Text Label**            |
| ----------------------- | --------------------------- | ----------------------------- | ------------------------- |
| **Best Value**          | menu-item-BEST_VALUE        | aria-selected="true"          | "Best Value"              |
| ---                     | ---                         | ---                           | ---                       |
| **Traveler Ranked**     | menu-item-POPULARITY        | aria-selected="false"         | "Traveler Ranked"         |
| ---                     | ---                         | ---                           | ---                       |
| **Price (Low to High)** | menu-item-PRICE_LOW_TO_HIGH | aria-selected="false"         | "Price (low to high)"     |
| ---                     | ---                         | ---                           | ---                       |
| **Distance**            | menu-item-DISTANCE          | aria-selected="false"         | "Distance to city center" |
| ---                     | ---                         | ---                           | ---                       |

- **State Indicators:**
  - **Active Selection:** The div\[role="option"\] with aria-selected="true".
  - **Loading State:** The parent container div.xBHob contains a span\[data-automation="search_in_progress_message"\] ("Searching.") while results are refreshing.
- **Interaction Strategy:**
  - Click the sort button to expand the listbox (aria-expanded="true").
  - Click the role="option" or the inner span\[data-testid="menuitem"\] matching the desired sort ID.
- **Verification Point (Heuristic):**
  - The aria-activedescendant attribute on the listbox points to the id of the currently highlighted/selected option.
  - Verify the button text updates to the selected option label after the "Searching" message disappears.

### 2. Things To Do

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

### 3. **TripAdvisor "Restaurants" Selector Map:**

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

### 4. Cruises 

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
