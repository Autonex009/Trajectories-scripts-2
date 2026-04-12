# TripAdvisor Coverage

## Scope

This package adds verifiers for `tripadvisor.com` result pages.
The bundled task set currently covers hotel search flows and a starter Things to Do task.

## Coverage

### Hotels

- URL recognition for hotel result pages such as `https://www.tripadvisor.com/Hotels-g187791-Rome_Lazio-Hotels.html`
- Geographic ID extraction from the hotel URL path
- LD+JSON extraction for hotel name, price, and rating
- DOM-state extraction for:
  - Check-in date via `button[data-automation="checkin"]`
  - Check-out date via `button[data-automation="checkout"]`
  - Active filter pills via `button[data-automation="filter-pill-active"]`
  - Selected filter groups including `propertyTypes`, `hotelClasses`, `brands`, `amenities`, and `styles`
  - Current sort label via `div[data-automation="sort"] button div.biGQs`

### Things To Do

- URL recognition for Things to Do result pages such as `https://www.tripadvisor.com/Attractions-g...`
- DOM-state extraction for:
  - Selected action-bar filter pills via `div[data-automation="actionBar"]`
  - Tier selections for navbar/category via `div[data-filter-name="navbar"]` and `div[data-filter-name="category"]`
  - Type, duration, time-of-day, awards, accessibility, neighborhoods, and traveler-rating selections
  - Date range via `button[aria-haspopup="dialog"]`
  - Sort label from the action bar
  - Price slider min/max values via `div#price_filter_contents div[role="slider"]`
  - Result-card sampling from `div[data-automation="LeftRailMain"] div[data-automation="cardWrapper"]`

## Notes

- Hotel and Things to Do extraction are intentionally split into separate evaluators so each page type can evolve without mixing selectors.
- Date extraction prefers `aria-label` because TripAdvisor exposes the full selected date there, with DOM text as fallback.
- Filter verification uses visible labels and normalized text matching so amenities, property types, brands, and star filters can be checked without hard-coding filter IDs.
- Pages flagged as access-restricted can still count for scoring when the required fields were fully extracted and `requestedMisses` is empty.
