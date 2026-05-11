StockX Filter Coverage Documentation

Overview

This document catalogs all filters available on StockX with actual URL examples as they appear in the search query string parameters.

## IMPORTANT: URL Format Rules

StockX uses TWO different mechanisms for filtering, depending on the filter type:

### Format 1: URL Path (Category)

https://stockx.com/search/{category}

https://stockx.com/search/{category}/{sub-page}

Categories like sneakers, apparel,accessories, etc. are part of the URL path, not query parameters.

### Format 2: Query String Parameters

https://stockx.com/search/{category}?param1=value1&param2=value2

Note: All filter values are URL-encoded. Spaces become %20 or +, and special characters use percent-encoding.

# 1\. SEARCH MODE & CATEGORY

### Category

Location: URL path (not in query string)

| Category | URL Path |
| --- | --- |
| All Products | /search |
| Sneakers | /category/sneakers |
| Apparel | /category/apparel |
| Accessories | /category/accessories |
| Electronics | /category/electronics |
| Trading Cards | /category/trading-cards |
| Collectibles | /category/collectibles |
| Handbags | /category/handbags |

  
  

### Search-Within-Category

https://stockx.com/search/sneakers?s=jordan

https://stockx.com/search/apparel?s=hoodie

https://stockx.com/search/watches?s=rolex

### Curated Sub-Pages

| Sub-Page | URL Path |
| --- | --- |
| Top Selling | /search/{category}/top-selling |
| Most Active | /search/{category}/most-active |
| Release Date | /search/{category}/release-date |
| New Releases | /search/{category}/new-releases |

# 2\. SEARCH QUERY / KEYWORD

### Example: Search for "yeezy"

https://stockx.com/search?s=yeezy

### Example: Multi-word query

https://stockx.com/search?s=air+jordan+1

https://stockx.com/search?s=air%20jordan%201

### Example: Brand-specific keyword in category

https://stockx.com/search/sneakers?s=nike+dunk

| Parameter | Description |
| --- | --- |
| s | Free-text search query (matches name, brand, SKU, colorway) |

# 3\. PRICE

### Example: Price Range $100 - $500

https://stockx.com/search/sneakers?s=jordan&priceMin=100&priceMax=500

### Example: Minimum Price Only

https://stockx.com/search/sneakers?lowest-ask-range=0-200&priceMin=200

  
  
  
  

### Example: Maximum Price Only

https://stockx.com/search/sneakers?priceMax=300

| Parameter | Description |
| --- | --- |
| priceMin | Minimum price (integer, in selected currency) |
| priceMax | Maximum price (integer, in selected currency) |

# 4\. SIZE (SNEAKERS)

### Example: US Men's Size 10

https://stockx.com/search/sneakers?size=10&country\_market\_us=1

### Example: Multiple Sizes

https://stockx.com/search/sneakers?size=9,9.5,10

### Sneaker Size Type Keys

| Region/Type | Parameter Key |
| --- | --- |
| US Men's | size_type_eu_men or size (default) |
| US Women's | size_type_us_w |
| UK | size_type_uk |
| EU | size_type_eu |
| JP (Japan) | size_type_jp |
| KR (Korea) | size_type_kr |
| Youth (GS) | size_type_youth |
| Toddler (TD) | size_type_td |

Note: When size is selected, the size\_type query string indicates the locale, and the size value is the numeric size.

# 5\. SIZE (APPAREL)

### Example: Size Large

https://stockx.com/search/apparel?size=L

### Example: Multiple Sizes

https://stockx.com/search/apparel?size=S,M,L

| Apparel Size | Value |
| --- | --- |
| Extra Small | XS |
| Small | S |
| Medium | M |
| Large | L |
| Extra Large | XL |
| XX-Large | XXL |
| One Size | OS |

# 6\. BRAND

### Example: Filter by Nike

https://stockx.com/search/sneakers?brand=Nike

### Example: Multiple Brands

https://stockx.com/search/sneakers?brand=Nike,Jordan,adidas

### Common Sneaker Brand Values

| Brand | Value |
| --- | --- |
| Nike | Nike |
| Jordan | Jordan |
| adidas | adidas |
| New Balance | New+Balance |
| Yeezy | Yeezy |
| ASICS | ASICS |
| Puma | Puma |
| Reebok | Reebok |
| Converse | Converse |
| Vans | Vans |

# 7\. COLOR

### Example: Filter by Black

https://stockx.com/search/sneakers?color=Black

### Example: Multiple Colors

https://stockx.com/search/sneakers?color=Black,White,Red

| Color | Value |
| --- | --- |
| Black | Black |
| White | White |
| Red | Red |
| Blue | Blue |
| Green | Green |
| Grey | Grey |
| Brown | Brown |
| Pink | Pink |
| Yellow | Yellow |
| Multi-Color | Multi-Color |

# 8\. RELEASE YEAR

### Example: Released in 2024

https://stockx.com/search/sneakers?releaseYear=2024

### Example: Multiple Years

https://stockx.com/search/sneakers?releaseYear=2023,2024,2025

| Parameter | Description |
| --- | --- |
| releaseYear | 4-digit year (single or comma-separated list) |

# 9\. CONDITION

### Example: New Items Only

https://stockx.com/search/sneakers?condition=new

### Example: Used Items

https://stockx.com/search/sneakers?condition=used

| Condition | Value |
| --- | --- |
| New (Default) | new |
| Used | used |

Note: The Used filter is primarily applicable to sneakers and certain apparel categories.

# 10\. GENDER

### Example: Men's Items Only

https://stockx.com/search/sneakers?gender=men

| Gender | Value |
| --- | --- |
| Men | men |
| Women | women |
| Child | child |
| Unisex | unisex |
| Infant | infant |
| Preschool | preschool |
| Toddler | toddler |

# 11\. WATCHES-SPECIFIC FILTERS

### Example: Rolex Submariner Style

https://stockx.com/search/watches?brand=Rolex&style=Submariner

### Watch Filter Keys

| Filter | Parameter Key |
| --- | --- |
| Brand | brand |
| Style/Model | style |
| Material | material |
| Dial Color | dialColor |
| Case Size (mm) | caseSize |
| Movement | movement |
| Year | releaseYear |

# 12\. TRADING CARDS FILTERS

### Example: Pokemon Cards

https://stockx.com/search/trading-cards?game=Pokemon

### Trading Card Filter Keys

| Filter | Parameter Key |
| --- | --- |
| Game/League | game |
| Sport | sport |
| Player | player |
| Team | team |
| Card Set | set |
| Grade | grade |
| Year | year |

# 13\. ELECTRONICS FILTERS

### Example: PlayStation Consoles

https://stockx.com/search/electronics?type=Console&brand=Sony

### Electronics Filter Keys

| Filter | Parameter Key |
| --- | --- |
| Product Type | type |
| Brand | brand |
| Model | model |
| Storage | storage |
| Generation | generation |
| Color | color |

# 14\. SORT OPTIONS

### Example: Sort by Price (Low to High)

https://stockx.com/search?s=jordan&sort=lowest\_ask&order=ASC

### Example: Sort by Most Recently Released

https://stockx.com/search/sneakers?sort=release\_date&order=DESC

### Sort Parameter Values

| Sort Option | sort Value | order |
| --- | --- | --- |
| Featured (default) | featured | DESC |
| Most Active | most_active | DESC |
| Top Selling | deadstock_sold | DESC |
| Lowest Ask | lowest_ask | ASC |
| Highest Bid | highest_bid | DESC |
| Last Sale | last_sale | DESC |
| Release Date (Newest) | release_date | DESC |
| Release Date (Oldest) | release_date | ASC |
| Price Premium | price_premium | DESC |
| Annual High | annual_high | DESC |
| Annual Low | annual_low | ASC |
| 72 Hour Change | 72_hour_change | DESC |

# 15\. PAGINATION

### Example: Go to Page 3

https://stockx.com/search?s=nike&page=3

| Parameter | Description |
| --- | --- |
| page | Page number (integer, 1-based) |

# 16\. COUNTRY & CURRENCY (LOCALE)

### Example: UK Site (GBP)

https://stockx.com/en-gb/search?s=jordan

### Example: Japan Site (JPY)

https://stockx.com/ja-jp/search?s=jordan

Locale is set via URL prefix and affects currency, language, and default size types.

| Region | URL Prefix |
| --- | --- |
| United States (default) | / (no prefix) |
| United Kingdom | /en-gb |
| Germany | /de-de |
| France | /fr-fr |
| Italy | /it-it |
| Spain | /es-es |
| Mexico (Spanish) | /es-mx |
| Japan | /ja-jp |
| Korea | /ko-kr |
| China (Simplified) | /zh-cn |
| Taiwan | /zh-tw |
| Canada (French) | /fr-ca |

# 17\. AVAILABILITY & EXTRAS

### Example: In-Stock Items Only

https://stockx.com/search/sneakers?inStock=true

### Example: Items With Recent Sales

https://stockx.com/search/sneakers?hasRecentSales=true

| Filter | Parameter Key | Values |
| --- | --- | --- |
| In Stock | inStock | true / false |
| Has Recent Sales | hasRecentSales | true / false |
| Brand New | isBrandNew | true / false |
| Express Ship | expressShip | true / false |

# 18\. Complete Example URL

Task: Find Nike sneakers, size US 10, in black, priced $100-$300, sorted by lowest ask

Path + Query Components:

Base:        https://stockx.com

Category:    /search/sneakers

Brand:       brand=Nike

Size:        size=10

Color:       color=Black

Price Min:   priceMin=100

Price Max:   priceMax=300

Sort:        sort=lowest\_ask

Order:       order=ASC

Full URL:

https://stockx.com/search/sneakers?brand=Nike&size=10&color=Black

    &priceMin=100&priceMax=300&sort=lowest\_ask&order=ASC

# Coverage Summary

| Sr. No. | Category | Filters |
| --- | --- | --- |
| 1 | Search Mode & Category | 9 |
| 2 | Search Query / Keyword | 1 |
| 3 | Price | 2 |
| 4 | Size (Sneakers) | 8 |
| 5 | Size (Apparel) | 7 |
| 6 | Brand | 10 |
| 7 | Color | 10 |
| 8 | Release Year | 1 |
| 9 | Condition | 2 |
| 10 | Gender | 7 |
| 11 | Watches-Specific | 7 |
| 12 | Trading Cards | 7 |
| 13 | Electronics | 6 |
| 14 | Sort Options | 12 |
| 15 | Pagination | 1 |
| 16 | Country & Currency | 12 |
| 17 | Availability & Extras | 4 |
|  | TOTAL | 106 |

# Quick Reference: URL Parameter Format Rules

| Filter Type | Format | Example |
| --- | --- | --- |
| Single value | ?key=value | ?s=yeezy |
| Multi-value | ?key=v1,v2,v3 | ?size=9,10,11 |
| Range (min/max) | ?keyMin=X&keyMax=Y | ?priceMin=100&priceMax=500 |
| Boolean | ?key=true / ?key=false | ?inStock=true |
| Combined | ?k1=v1&k2=v2 | ?brand=Nike&color=Black |
| Path-based | /path/segment | /search/sneakers |
| Locale prefix | /{lang-region}/path | /en-gb/search |

  

End of document.
