/**
 * SeatGeek Info Gathering - JavaScript DOM Scraper
 * 
 * Injected into SeatGeek pages via page.evaluate() to extract:
 * 1. URL parsing (page type, event ID, filters)
 * 2. LD+JSON structured data (event details, pricing, inventory)
 * 3. DOM elements (ticket listings, meta tags, filter state)
 * 
 * Returns an array of InfoDict objects for the Python verifier.
 * 
 * Last updated: 2026-03 (browser-verified against seatgeek.com)
 */
(() => {
    'use strict';

    // ==================== HELPERS ====================

    /**
     * Safely get text content from a selector.
     */
    function getText(selector) {
        const el = document.querySelector(selector);
        return el ? el.textContent.trim() : '';
    }

    /**
     * Safely get all text matches from querySelectorAll.
     */
    function getAllText(selector) {
        return Array.from(document.querySelectorAll(selector))
            .map(el => el.textContent.trim())
            .filter(Boolean);
    }

    /**
     * Safely get attribute value from a selector.
     */
    function getAttr(selector, attr) {
        const el = document.querySelector(selector);
        return el ? el.getAttribute(attr) : '';
    }

    /**
     * Safely get meta tag content.
     */
    function getMeta(name) {
        return getAttr(`meta[name="${name}"], meta[property="${name}"]`, 'content') || '';
    }

    // NOTE: parsePrice removed — was dead code (BUG 8 FIX).

    // ==================== URL PARSING ====================

    /**
     * Detect page type from URL.
     * Page types: event_listing, performer, search, category, homepage, unknown
     */
    function detectPageType(url) {
        try {
            const urlObj = new URL(url);
            const path = urlObj.pathname;
            const segments = path.split('/').filter(Boolean);

            // Event listing: /{team}-tickets/{date-venue}/{category}/{id}
            // Pattern: at least 4 path segments, last one is numeric
            if (segments.length >= 4 && /^\d+$/.test(segments[segments.length - 1]) &&
                segments[0].endsWith('-tickets')) {
                return 'event_listing';
            }

            // Search page
            if (path === '/search') return 'search';

            // BUG 6 FIX: Check category pages BEFORE performer pages
            // because /nba-tickets, /concert-tickets etc. have 1 segment ending
            // in -tickets but are category pages, not performer pages.
            const knownCategories = [
                'sports', 'concert', 'theater', 'comedy', 'festival',
                'nba', 'nfl', 'mlb', 'nhl', 'mls', 'ncaa',
                'boxing', 'wrestling', 'tennis', 'golf', 'soccer', 'wwe'
            ];
            if (segments.length === 1 && segments[0].endsWith('-tickets')) {
                const slug = segments[0].replace('-tickets', '');
                if (knownCategories.some(c => slug.includes(c))) {
                    return 'category';
                }
            }

            // Performer page: /{slug}-tickets (1 segment ending in -tickets,
            // NOT matching a known category)
            if (segments.length === 1 && segments[0].endsWith('-tickets')) {
                return 'performer';
            }

            // Homepage
            if (path === '/' || path === '') return 'homepage';

            return 'unknown';
        } catch (e) {
            return 'unknown';
        }
    }

    /**
     * Extract URL filter parameters.
     */
    function extractUrlFilters(url) {
        try {
            const urlObj = new URL(url);
            const filters = {};

            if (urlObj.searchParams.has('quantity')) {
                filters.quantity = parseInt(urlObj.searchParams.get('quantity'));
            }
            if (urlObj.searchParams.has('price_max')) {
                filters.price_max = parseFloat(urlObj.searchParams.get('price_max'));
            }
            if (urlObj.searchParams.has('price_min')) {
                filters.price_min = parseFloat(urlObj.searchParams.get('price_min'));
            }
            if (urlObj.searchParams.has('city')) {
                filters.city = urlObj.searchParams.get('city');
            }
            if (urlObj.searchParams.has('search')) {
                filters.search = urlObj.searchParams.get('search');
            }
            if (urlObj.searchParams.has('oq')) {
                filters.oq = urlObj.searchParams.get('oq');
            }
            if (urlObj.searchParams.has('perks')) {
                filters.perks = urlObj.searchParams.get('perks');
            }
            if (urlObj.searchParams.has('sc')) {
                filters.sc = urlObj.searchParams.get('sc');
            }

            return filters;
        } catch (e) {
            return {};
        }
    }

    /**
     * Extract event ID from URL path.
     */
    function extractEventId(url) {
        try {
            const path = new URL(url).pathname;
            const segments = path.split('/').filter(Boolean);
            const lastSegment = segments[segments.length - 1];
            if (/^\d+$/.test(lastSegment)) return lastSegment;
            return null;
        } catch (e) {
            return null;
        }
    }

    /**
     * Extract category from event URL path.
     */
    function extractCategory(url) {
        try {
            const path = new URL(url).pathname;
            const segments = path.split('/').filter(Boolean);
            // Category is the second-to-last segment in event URLs
            if (segments.length >= 4) {
                return segments[segments.length - 2];
            }
            // For category pages, extract from the slug
            if (segments.length === 1) {
                return segments[0].replace('-tickets', '');
            }
            return null;
        } catch (e) {
            return null;
        }
    }

    // ==================== LD+JSON EXTRACTION ====================

    /**
     * Extract all LD+JSON data from the page.
     */
    function extractLdJson() {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        const results = [];
        scripts.forEach(script => {
            try {
                const data = JSON.parse(script.textContent);
                if (Array.isArray(data)) {
                    results.push(...data);
                } else {
                    results.push(data);
                }
            } catch (e) {
                // Skip invalid JSON
            }
        });
        return results;
    }

    /**
     * Find events in LD+JSON data (handles nested structures).
     */
    function findEvents(ldJsonItems) {
        const events = [];
        for (const item of ldJsonItems) {
            if (!item) continue;
            const type = item['@type'];

            // Direct event types
            if (['SportsEvent', 'MusicEvent', 'TheaterEvent', 'ComedyEvent',
                'Event', 'DanceEvent', 'Festival'].includes(type)) {
                events.push(item);
            }

            // Events nested under SportsTeam, MusicGroup, etc.
            if (item.event) {
                const nested = Array.isArray(item.event) ? item.event : [item.event];
                events.push(...nested);
            }

            // Events in subEvent arrays
            if (item.subEvent) {
                const nested = Array.isArray(item.subEvent) ? item.subEvent : [item.subEvent];
                events.push(...nested);
            }
        }
        return events;
    }

    /**
     * Extract info from a single LD+JSON event object.
     */
    function extractEventInfo(event) {
        const info = {};

        info.eventName = event.name || '';
        info.eventType = event['@type'] || 'Event';

        // Map @type to category
        const typeMap = {
            'SportsEvent': 'sports',
            'MusicEvent': 'concerts',
            'TheaterEvent': 'theater',
            'ComedyEvent': 'comedy',
            'DanceEvent': 'concerts',
            'Festival': 'festivals',
            'Event': 'events'
        };
        info.eventCategory = typeMap[info.eventType] || 'events';

        // Date/Time
        if (event.startDate) {
            info.startDate = event.startDate;
            const datePart = event.startDate.split('T')[0];
            info.date = datePart;
            const timePart = event.startDate.split('T')[1];
            if (timePart) {
                info.time = timePart.substring(0, 5); // HH:MM
            }
        }

        if (event.endDate) {
            info.endDate = event.endDate.split('T')[0];
        }

        if (event.doorTime) {
            const doorTimePart = event.doorTime.split('T')[1];
            if (doorTimePart) {
                info.doorTime = doorTimePart.substring(0, 5);
            }
        }

        // Location
        if (event.location) {
            const loc = event.location;
            info.venue = loc.name || '';

            if (loc.address) {
                const addr = loc.address;
                info.city = addr.addressLocality || '';
                info.state = addr.addressRegion || '';
                info.country = addr.addressCountry || '';
                info.postalCode = addr.postalCode || '';
                if (addr.streetAddress) {
                    info.streetAddress = addr.streetAddress;
                }
            }

            if (loc.geo) {
                info.latitude = loc.geo.latitude;
                info.longitude = loc.geo.longitude;
            }
        }

        // Competitors / Performers
        if (event.competitor) {
            const competitors = Array.isArray(event.competitor) ? event.competitor : [event.competitor];
            info.competitors = competitors.map(c => c.name || '').filter(Boolean);
        }

        if (event.performer) {
            const performers = Array.isArray(event.performer) ? event.performer : [event.performer];
            info.performers = performers.map(p => p.name || '').filter(Boolean);
        }

        // Offers / Pricing
        if (event.offers) {
            const offers = event.offers;
            info.lowPrice = offers.lowPrice != null ? parseFloat(offers.lowPrice) : null;
            info.highPrice = offers.highPrice != null ? parseFloat(offers.highPrice) : null;
            info.inventoryLevel = offers.inventoryLevel != null ? parseInt(offers.inventoryLevel) : null;
            if (offers.url) info.offerUrl = offers.url;
            if (offers.priceCurrency) info.currency = offers.priceCurrency;
            if (offers.availability) info.offerAvailability = offers.availability;
        }

        // Event status
        if (event.eventStatus) {
            info.eventStatus = event.eventStatus;
        }

        return info;
    }

    // ==================== DOM LISTING EXTRACTION ====================

    /**
     * Parse a listing button's aria-label.
     * Format: "Section 110, Row 9, 1 to 3 tickets at $321 each, Deal Score 10"
     * Also handles: "Section GA, Row GA, 1 to 6 tickets at $85 each"
     */
    function parseListingLabel(label) {
        if (!label) return null;

        const match = label.match(
            /Section\s+(.+?),\s*Row\s+(.+?),\s*(\d+)\s+to\s+(\d+)\s+tickets?\s+at\s+\$?([\d,.]+)\s+each(?:,\s*Deal Score\s+(\d+))?/i
        );

        if (!match) return null;

        return {
            section: match[1].trim(),
            row: match[2].trim(),
            minQty: parseInt(match[3]),
            maxQty: parseInt(match[4]),
            price: parseFloat(match[5].replace(/,/g, '')),
            dealScore: match[6] ? parseInt(match[6]) : null
        };
    }

    /**
     * Extract listing tags from a listing button element.
     * Tags include: "Cheapest", "Best in section", "Aisle", "Save X%", "Amazing", "Great"
     */
    function extractListingTags(buttonEl) {
        if (!buttonEl) return [];
        const tags = [];
        const text = buttonEl.textContent || '';

        // Deal Score labels
        if (/\bAmazing\b/i.test(text)) tags.push('amazing');
        if (/\bGreat\b/i.test(text)) tags.push('great');
        if (/\bGood\b/i.test(text)) tags.push('good');

        // Special tags
        if (/\bCheapest\b/i.test(text)) tags.push('cheapest');
        if (/\bBest in section\b/i.test(text)) tags.push('best_in_section');
        if (/\bAisle\b/i.test(text)) tags.push('aisle');

        // Savings tag
        const saveMatch = text.match(/Save\s+(\d+)%/i);
        if (saveMatch) tags.push(`save_${saveMatch[1]}pct`);

        // Includes fees tag
        if (/incl\.\s*fees/i.test(text)) tags.push('incl_fees');

        return tags;
    }

    /**
     * Extract fee-inclusive price from a listing button element.
     * Looks for "$84 incl. fees" or price display text.
     */
    function extractFeeInclusivePrice(buttonEl) {
        if (!buttonEl) return null;
        const text = buttonEl.textContent || '';
        // Match "$84 incl. fees" or "$1,500 incl. fees"
        const match = text.match(/\$([\d,]+(?:\.\d{2})?)\s*incl\.\s*fees/i);
        if (match) return parseFloat(match[1].replace(/,/g, ''));
        return null;
    }

    /**
     * Extract all ticket listings from the DOM.
     */
    function extractListings() {
        const listings = [];

        // Method 1: Parse aria-label on listing buttons
        const buttons = document.querySelectorAll(
            'button[aria-label*="Section"], button[aria-label*="section"]'
        );
        buttons.forEach(btn => {
            const parsed = parseListingLabel(btn.getAttribute('aria-label'));
            if (parsed) {
                parsed.tags = extractListingTags(btn);
                parsed.priceWithFees = extractFeeInclusivePrice(btn);
                parsed.isAisle = parsed.tags.includes('aisle');
                listings.push(parsed);
            }
        });

        // Method 2: If no aria-label listings, try data-testid based
        if (listings.length === 0) {
            const testIdListings = document.querySelectorAll('[data-testid="all-listings"] button');
            testIdListings.forEach(btn => {
                const label = btn.getAttribute('aria-label');
                if (label) {
                    const parsed = parseListingLabel(label);
                    if (parsed) {
                        parsed.tags = extractListingTags(btn);
                        parsed.priceWithFees = extractFeeInclusivePrice(btn);
                        parsed.isAisle = parsed.tags.includes('aisle');
                        listings.push(parsed);
                    }
                }
            });
        }

        return listings;
    }

    /**
     * Count total listings visible on page.
     */
    function countListings() {
        const container = document.querySelector('[data-testid="all-listings"]');
        if (container) {
            return container.querySelectorAll('button[aria-label]').length;
        }
        return document.querySelectorAll('button[aria-label*="Section"]').length;
    }

    /**
     * Extract listing count from DOM text (e.g., "193 listings").
     */
    function extractListingCountText() {
        const bodyText = document.body ? document.body.innerText : '';
        const match = bodyText.match(/(\d+)\s+listings?/i);
        return match ? parseInt(match[1]) : null;
    }

    // ==================== FILTER STATE EXTRACTION ====================

    /**
     * Extract the current state of filter pills on the event page.
     * Filters: quantity, price, seat perks, instant delivery, sections.
     */
    function extractFilterState() {
        const state = {};

        // Quantity — look for the active quantity pill button text
        const quantityBtn = document.querySelector('button[aria-label*="ticket"]');
        if (quantityBtn) {
            const text = quantityBtn.textContent.trim();
            const qMatch = text.match(/(\d+)\s*tickets?/i);
            if (qMatch) state.quantity = parseInt(qMatch[1]);
        }

        // BUG 9 FIX: Scope button scan to filter area only
        // Filter pills live in a scrollable horizontal row near the top of listings.
        // Use specific selectors to target filter buttons, not ALL page buttons.
        const filterContainer = document.querySelector('[class*="FilterBar"], [class*="filter-bar"], [data-testid*="filter"]');
        const filterButtons = filterContainer
            ? filterContainer.querySelectorAll('button')
            : document.querySelectorAll('button[aria-label*="filter"], button[aria-label*="Filter"], button[aria-label*="delivery"], button[aria-label*="perk"]');
        filterButtons.forEach(btn => {
            const text = (btn.textContent || '').trim().toLowerCase();
            // Detect if "Instant delivery" filter is active
            if (text.includes('instant del') || text.includes('instant delivery')) {
                state.instantDelivery = true;
            }
            // Detect "Seat Perks" filter
            if (text.includes('seat perk')) {
                state.seatPerks = true;
            }
        });

        // Sort order from "Sort by deal" or similar dropdown
        const sortText = document.body ? document.body.innerText : '';
        const sortMatch = sortText.match(/Sort by\s+(\w+)/i);
        if (sortMatch) {
            state.sortOrder = sortMatch[1].toLowerCase();
        }

        // Price filter — check if price pill is active or has custom range
        const priceBtn = Array.from(document.querySelectorAll('button'))
            .find(b => /^Price/i.test(b.textContent.trim()));
        if (priceBtn) {
            const priceText = priceBtn.textContent.trim();
            if (priceText !== 'Price') {
                state.priceFilterActive = true;
                state.priceFilterText = priceText;
            }
        }

        return state;
    }

    // ==================== AVAILABILITY DETECTION ====================

    /**
     * Detect if the event is sold out or has other special statuses.
     */
    function detectAvailabilityStatus(totalListings, inventoryLevel) {
        // Check DOM for sold-out indicators
        const bodyText = document.body ? document.body.innerText.toLowerCase() : '';

        if (bodyText.includes('sold out') || bodyText.includes('no tickets available')) {
            return 'sold_out';
        }
        if (bodyText.includes('get notified') && totalListings === 0) {
            return 'sold_out';
        }
        if (bodyText.includes('cancelled') || bodyText.includes('canceled')) {
            return 'cancelled';
        }
        if (bodyText.includes('postponed') || bodyText.includes('rescheduled')) {
            return 'rescheduled';
        }

        if (totalListings > 0 || (inventoryLevel && inventoryLevel > 0)) {
            return 'available';
        }

        return 'unknown';
    }

    // ==================== MAIN SCRAPER ====================

    /**
     * Main entry point - scrape the current page and return InfoDict array.
     */
    function scrape() {
        const url = window.location.href;
        const pageType = detectPageType(url);
        const urlFilters = extractUrlFilters(url);
        const eventId = extractEventId(url);
        const category = extractCategory(url);
        const ldJsonItems = extractLdJson();
        const events = findEvents(ldJsonItems);

        const infos = [];

        // ===== Common fields =====
        const commonFields = {
            url: url,
            pageType: pageType,
            title: document.title || '',
            h1: getText('h1'),
            metaDescription: getMeta('description'),
            ogTitle: getMeta('og:title'),
            ogUrl: getMeta('og:url'),
            eventId: eventId,
            category: category,
            urlQuantity: urlFilters.quantity ?? null,
            urlMaxPrice: urlFilters.price_max ?? null,
            urlMinPrice: urlFilters.price_min ?? null,
            urlCity: urlFilters.city ?? null,
            urlSearch: urlFilters.search ?? null,
            urlPerks: urlFilters.perks ?? null,
            urlSection: urlFilters.sc ?? null,
            source: 'seatgeek'
        };

        // ===== Event listing page =====
        if (pageType === 'event_listing') {
            const listings = extractListings();
            const totalListingsDOM = countListings();
            const listingCountText = extractListingCountText();
            const filterState = extractFilterState();

            // Get primary event from LD+JSON
            if (events.length > 0) {
                const eventInfo = extractEventInfo(events[0]);
                const totalListings = listingCountText || totalListingsDOM;
                const availability = detectAvailabilityStatus(
                    totalListings, eventInfo.inventoryLevel
                );

                const info = {
                    ...commonFields,
                    ...eventInfo,
                    totalListings: totalListings,
                    listingCountText: listingCountText,
                    filterState: filterState,
                    availabilityStatus: availability,
                    info: availability,
                    source: 'ld+json'
                };

                // Add listing aggregate details
                if (listings.length > 0) {
                    const prices = listings.map(l => l.price).filter(p => p != null);
                    const feePrices = listings.map(l => l.priceWithFees).filter(p => p != null);
                    if (prices.length > 0) {
                        info.listingLowPrice = Math.min(...prices);
                        info.listingHighPrice = Math.max(...prices);
                    }
                    if (feePrices.length > 0) {
                        info.listingLowPriceWithFees = Math.min(...feePrices);
                        info.listingHighPriceWithFees = Math.max(...feePrices);
                    }

                    // Sections available
                    info.availableSections = [...new Set(listings.map(l => l.section))];

                    // All listing tags
                    const allTags = new Set();
                    listings.forEach(l => (l.tags || []).forEach(t => allTags.add(t)));
                    info.availableTags = [...allTags];

                    // Aisle seat availability
                    info.hasAisleSeats = listings.some(l => l.isAisle);

                    // First listing summary
                    info.section = listings[0].section;
                    info.row = listings[0].row;
                    info.price = listings[0].price;
                    info.priceWithFees = listings[0].priceWithFees;
                    info.dealScore = listings[0].dealScore;
                    info.ticketCount = listings[0].maxQty;
                    info.listingTags = listings[0].tags;
                }

                infos.push(info);
            } else {
                // No LD+JSON events — build from DOM + URL
                const totalListings = listingCountText || totalListingsDOM;
                const availability = detectAvailabilityStatus(totalListings, 0);
                infos.push({
                    ...commonFields,
                    eventName: getText('h1') || commonFields.ogTitle || commonFields.title,
                    totalListings: totalListings,
                    filterState: filterState,
                    availabilityStatus: availability,
                    info: availability,
                    source: 'dom'
                });
            }

            // Add individual listing infos (for section/row/tag matching)
            listings.forEach(listing => {
                infos.push({
                    ...commonFields,
                    eventName: infos[0]?.eventName || getText('h1'),
                    eventCategory: infos[0]?.eventCategory || category,
                    city: infos[0]?.city || '',
                    venue: infos[0]?.venue || '',
                    date: infos[0]?.date || '',
                    time: infos[0]?.time || '',
                    section: listing.section,
                    row: listing.row,
                    price: listing.price,
                    priceWithFees: listing.priceWithFees,
                    dealScore: listing.dealScore,
                    ticketCount: listing.maxQty,
                    availableQuantities: Array.from(
                        { length: listing.maxQty - listing.minQty + 1 },
                        (_, i) => listing.minQty + i
                    ),
                    listingTags: listing.tags,
                    isAisle: listing.isAisle,
                    availabilityStatus: 'available',
                    info: 'available',
                    source: 'dom_listing'
                });
            });
        }

        // ===== Performer page =====
        else if (pageType === 'performer') {
            // Extract all events from LD+JSON
            if (events.length > 0) {
                events.forEach(event => {
                    const eventInfo = extractEventInfo(event);
                    infos.push({
                        ...commonFields,
                        ...eventInfo,
                        pageType: 'performer',
                        source: 'ld+json'
                    });
                });
            }

            // Also push a summary info with performer data
            const performerTypes = ['SportsTeam', 'MusicGroup', 'PerformingGroup',
                'Person', 'Organization', 'TheaterGroup'];
            const teamData = ldJsonItems.find(item =>
                item && performerTypes.includes(item['@type'])
            );
            if (teamData) {
                infos.push({
                    ...commonFields,
                    eventName: teamData.name || '',
                    eventCategory: teamData['@type'] === 'SportsTeam' ? 'sports' :
                        teamData['@type'] === 'Person' ? 'concerts' :
                            'concerts',
                    totalListings: events.length,
                    source: 'ld+json_performer'
                });
            }
        }

        // ===== Search results page =====
        else if (pageType === 'search') {
            // Extract search result links
            const resultLinks = document.querySelectorAll('a[href*="-tickets"]');
            resultLinks.forEach(link => {
                const href = link.getAttribute('href');
                const text = link.textContent.trim().substring(0, 200);
                if (text && href) {
                    infos.push({
                        ...commonFields,
                        eventName: text,
                        pageType: 'search',
                        offerUrl: href,
                        source: 'dom_search'
                    });
                }
            });

            // Also add LD+JSON events if present
            events.forEach(event => {
                infos.push({
                    ...commonFields,
                    ...extractEventInfo(event),
                    pageType: 'search',
                    source: 'ld+json'
                });
            });
        }

        // ===== Category page =====
        else if (pageType === 'category') {
            // Extract events from LD+JSON
            events.forEach(event => {
                infos.push({
                    ...commonFields,
                    ...extractEventInfo(event),
                    pageType: 'category',
                    source: 'ld+json'
                });
            });

            // Fallback: extract from DOM
            if (infos.length === 0) {
                const eventLinks = document.querySelectorAll('a[href*="-tickets/"]');
                eventLinks.forEach(link => {
                    const text = link.textContent.trim().substring(0, 200);
                    if (text) {
                        infos.push({
                            ...commonFields,
                            eventName: text,
                            pageType: 'category',
                            source: 'dom_category'
                        });
                    }
                });
            }
        }

        // ===== Fallback: Unknown page =====
        else {
            infos.push({
                ...commonFields,
                eventName: getText('h1') || commonFields.title,
                source: 'dom_fallback'
            });
        }

        // Ensure we always return at least one info
        if (infos.length === 0) {
            infos.push({
                ...commonFields,
                eventName: commonFields.title || 'Unknown',
                source: 'empty_fallback'
            });
        }

        return infos;
    }

    // Execute and return
    return scrape();
})();
