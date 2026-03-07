(() => {
    const results = [];
    const url = window.location.href;
    const pageText = document.body ? document.body.innerText.toLowerCase() : '';

    // ============================================================================
    // 1. UTILITIES
    // ============================================================================
    const getText = (el) => {
        if (!el) return null;
        // Prefer innerText to preserve visual spaces between squashed div/span tags
        let text = el.innerText || el.textContent || '';
        return text.trim().replace(/\s+/g, ' ');
    };
    
    const extractByPattern = (text, patterns) => {
        if (!text) return null;
        for (const regex of Object.values(patterns)) {
            try {
                const match = text.match(regex);
                if (match) return match[1] || match[0];
            } catch (e) { continue; }
        }
        return null;
    };

    // ============================================================================
    // 2. PARSERS
    // ============================================================================
    const Parsers = {
        price: (text) => {
            try {
                if (!text) return null;
                // Vivid Seats often shows "$150 / ea" or just "$150"
                let match = text.match(/(?:[$£€₹]|USD)\s*([\d,]+(?:\.\d{2})?)/i);
                if (match) return parseFloat(match[1].replace(/,/g, ""));
            } catch (e) { return null; }
            return null;
        },
        ticketCount: (text) => {
            try {
                if (!text) return null;
                return parseInt(text.match(/(\d+)\s*tickets?/i)?.[1] || text.match(/^(\d+)$/)?.[1]);
            } catch (e) { return null; }
        },
        date: (text) => {
            try {
                if (!text) return null;
                const clean = text.toLowerCase().trim();
                let match = clean.match(/(\d{4})-(\d{2})-(\d{2})/);
                if (match) return match[0];
                // Vivid Seats format: "Oct 24, 2026" or "Sat, Oct 24"
                match = clean.match(/([a-z]{3})[a-z]*\s+(\d{1,2}),?\s*(\d{4})/i);
                if (match) {
                    const months = { jan:1, feb:2, mar:3, apr:4, may:5, jun:6, jul:7, aug:8, sep:9, oct:10, nov:11, dec:12 };
                    const m = months[match[1].substring(0, 3)];
                    if (m) return `${match[3]}-${String(m).padStart(2,'0')}-${match[2].padStart(2,'0')}`;
                }
            } catch (e) { return null; }
            return null;
        },
        time: (text) => {
            try {
                if (!text) return null;
                const match = text.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
                if (match) {
                    let h = parseInt(match[1]);
                    if (match[3]?.toUpperCase() === 'PM' && h < 12) h += 12;
                    if (match[3]?.toUpperCase() === 'AM' && h === 12) h = 0;
                    return `${String(h).padStart(2, '0')}:${match[2]}`;
                }
            } catch (e) { return null; }
            return null;
        }
    };

    // ============================================================================
    // 3. ENRICHMENT HELPERS
    // ============================================================================
    const Enrichment = {
        pageType: () => {
            if (url.includes('/checkout') || url.includes('/secure/')) return 'checkout';
            // Vivid Seats event pages typically use /production/
            if (url.includes('/production/')) return 'event_listing'; 
            if (url.includes('/search') || url.includes('?query=')) return 'search_results';
            if (url.includes('/concerts/') || url.includes('/theater/') || url.includes('/sports/')) return 'event_category';
            return 'other';
        },
        antiBotStatus: () => {
            // Vivid Seats relies heavily on Cloudflare & PerimeterX/DataDome
            if (pageText.includes('just a moment') || document.querySelector('#challenge-running')) return 'blocked_cloudflare';
            if (pageText.includes('pardon the interruption') || document.querySelector('#px-captcha')) return 'blocked_perimeterx';
            return 'clear';
        },
        category: () => {
            if (url.includes('sports')) return 'sports';
            if (url.includes('concerts')) return 'concerts';
            if (url.includes('theater')) return 'theater';
            return null;
        },
        status: (t) => {
            const s = (t || pageText).toLowerCase();
            if (s.includes('no tickets available') || s.includes('sold out')) return 'sold_out';
            return 'available';
        },
        isSuperSeller: (t) => /super seller/i.test(t),
        obstructed: (t) => /obstructed|limited view|wheelchair/i.test(t),
    };

    // ============================================================================
    // 4. SCRAPERS
    // ============================================================================
    const Scraper = {
        pageFilters: () => {
            try {
                let filterQuantity = null;
                let filterMinPrice = null;
                let filterMaxPrice = null;
                let filterDate = null;

                // 1. Grab Quantity from the active filter button
                const qtyBtn = document.querySelector('[data-testid="show-quantity-filter-button"], [data-testid="Quantity-filter-button"]');
                if (qtyBtn) {
                    const qtyText = getText(qtyBtn);
                    const qtyMatch = qtyText ? qtyText.match(/(\d+)/) : null;
                    if (qtyMatch) filterQuantity = parseInt(qtyMatch[1]);
                }

                // 2. Grab Min and Max Price from the active price button
                const priceBtn = document.querySelector('[data-testid="show-price-filter-button"], [data-testid="Price-filter-button"]');
                if (priceBtn) {
                    const priceText = getText(priceBtn);
                    if (priceText) {
                        // Extract all dollar amounts in the string
                        const priceMatches = [...priceText.matchAll(/[$£€₹]?\s*([\d,]+(?:\.\d{2})?)/g)];
                        if (priceMatches.length >= 1) {
                            filterMinPrice = parseFloat(priceMatches[0][1].replace(/,/g, ''));
                        }
                        if (priceMatches.length >= 2) {
                            filterMaxPrice = parseFloat(priceMatches[1][1].replace(/,/g, ''));
                        }
                    }
                }
                
                // 3. NEW: "Tickets under X" Quick Filter (General Listing Page)
                const underXBtn = document.querySelector('[data-testid="tickets-under-x-filter-button"]');
                // Only use this if standard max price isn't already set, and check if it's not just a default label
                if (underXBtn && !filterMaxPrice) { 
                    const underXText = getText(underXBtn);
                    if (underXText && underXText.toLowerCase().includes('under')) {
                        const match = underXText.match(/[$£€₹]?\s*([\d,]+(?:\.\d{2})?)/);
                        // Make sure the button is actually active (Vivid removes 'MuiChip-outlined' when active)
                        const isOutlined = underXBtn.className.includes('MuiChip-outlined');
                        if (match && !isOutlined) {
                            filterMaxPrice = parseFloat(match[1].replace(/,/g, ''));
                        }
                    }
                }

                // 4. NEW: Date Filter (General Listing Page)
                const dateFilterBtn = document.querySelector('[data-testid="date-filter-button"]');
                if (dateFilterBtn) {
                    const dateText = getText(dateFilterBtn);
                    // If it says exactly "Date", the user hasn't selected a specific date yet
                    if (dateText && dateText.toLowerCase() !== 'date') {
                        filterDate = Parsers.date(dateText) || dateText;
                    }
                }

                // 5. Super Seller Toggle
                const superSellerToggle = document.querySelector('[data-testid="super-seller-toggle"]');
                const isSuperSellerOnly = superSellerToggle ? superSellerToggle.getAttribute('aria-checked') === 'true' : false;

                // 6. NEW: Zone Filters (e.g. "Upper Level", "Club Level")
                const activeZones = [];
                const zoneBtns = document.querySelectorAll('[data-testid="zone-chip-container"] button');
                zoneBtns.forEach(btn => {
                    // Look for the 'activated' substring in the class name
                    const isActivated = btn.className.includes('activated');
                    const isDisabled = btn.disabled || btn.className.includes('Mui-disabled');
                    
                    if (isActivated && !isDisabled) {
                        const zoneText = getText(btn);
                        if (zoneText) activeZones.push(zoneText.toLowerCase());
                    }
                });

                return {
                    filterQuantity: filterQuantity,
                    filterMinPrice: filterMinPrice,
                    filterMaxPrice: filterMaxPrice,
                    filterSuperSeller: isSuperSellerOnly,
                    filterDate: filterDate,
                    filterZones: activeZones
                };
            } catch (e) { 
                console.error("Error parsing filters", e);
                return {}; 
            }
        },

        ldJson: () => {
            try {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                const found = [];
                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);
                        const items = Array.isArray(data) ? data : [data];
                        for (const item of items) {
                            if (item["@type"] !== "Event" && item["@type"] !== "MusicEvent" && item["@type"] !== "SportsEvent") continue;
                            found.push({
                                source: "ld+json",
                                eventName: item.name?.toLowerCase(),
                                date: item.startDate?.split("T")[0],
                                time: item.startDate?.split("T")[1]?.substring(0, 5),
                                venue: item.location?.name,
                                city: item.location?.address?.addressLocality?.toLowerCase(),
                                price: item.offers?.lowPrice ? parseFloat(item.offers.lowPrice) : null,
                                currency: item.offers?.priceCurrency || "USD",
                                availabilityStatus: "available",
                                url: item.url || url
                            });
                        }
                    } catch (e) {}
                }
                return found;
            } catch (e) { return []; }
        },

        ticketListings: () => {
            const collected = [];
            
            // Grab the event name from the top header breadcrumb/title
            const headerTitleNode = document.querySelector('[data-testid="production-detail-bar-performer-link"], h1');
            const eventNameContext = headerTitleNode ? getText(headerTitleNode) : "";

            // Target the specific ticket rows using Vivid's data attributes
            const rows = document.querySelectorAll('div[data-rowid], [data-testid="listing-row-container"] > div');

            rows.forEach(row => {
                try {
                    // 1. Get Price (Prefer the data-attribute, fallback to the text node)
                    const dataPrice = row.getAttribute('data-price');
                    const priceNode = row.querySelector('[data-testid="listing-price"]');
                    const rawPrice = dataPrice || (priceNode ? getText(priceNode) : getText(row));
                    const extractedPrice = Parsers.price(rawPrice);

                    if (!extractedPrice) return;

                    // 2. Get Row (Prefer the data-attribute, fallback to the row node)
                    const dataRow = row.getAttribute('data-rowid');
                    const rowNode = row.querySelector('[data-testid="row"]');
                    const rowNum = dataRow || (rowNode ? getText(rowNode).replace(/Row/i, '').trim() : extractByPattern(getText(row), {r: /\bRow\s+([A-Za-z0-9]+)/i}));

                    // 3. Get Section (It's usually the first bold typography element in the section column)
                    const sectionNode = row.querySelector('[class*="sectionContent"] [class*="MuiTypography"], [class*="styles_sectionColumn"] [class*="styles_nowrap"]');
                    const section = sectionNode ? getText(sectionNode) : extractByPattern(getText(row), {s: /(?:\bSection\b|\bSec\b|Zone)\s+([A-Za-z0-9\s]+?)(?=\s*(?:[•·,:-]|\bRow\b|$))/i});

                    // 4. Check for Super Seller (Look for the specific green badge/icon class)
                    const isSuperSeller = row.querySelector('[class*="superSellerIcon"], [class*="ticket-super-seller"]') !== null || Enrichment.isSuperSeller(getText(row));

                    collected.push({
                        source: "dom_ticket_listing",
                        eventName: eventNameContext.toLowerCase(), 
                        price: extractedPrice,
                        section: section,
                        row: rowNum,
                        isSuperSeller: isSuperSeller,
                        availabilityStatus: 'available',
                        info: getText(row)
                    });
                } catch (e) { console.error('Ticket row parse error', e); }
            });
            
            return collected;
        },

        eventCards: () => {
            const collected = [];
            // Target the specific production row links
            const rows = document.querySelectorAll('a[data-testid^="production-listing-row-"]');
            
            rows.forEach(row => {
                try {
                    const href = row.getAttribute('href');
                    
                    // 1. Get Event Name
                    const titleNode = row.querySelector('.styles_titleColumn__T_Kfd > span:first-child, [class*="titleTruncate"]');
                    const eventName = titleNode ? getText(titleNode) : null;
                    
                    // 2. Get Date & Time
                    const dateTimeNode = row.querySelector('[data-testid="date-time-left-element"]');
                    const rawDateText = dateTimeNode ? getText(dateTimeNode) : null; // e.g., "Fri Apr 10 7:00pm"
                    
                    // 3. Get Venue & City
                    const subtitleNode = row.querySelector('[data-testid="subtitle"]');
                    const locationText = subtitleNode ? getText(subtitleNode) : null; // e.g., "Allegiant Stadium • Las Vegas, NV"
                    
                    // 4. Get Price
                    const priceNode = row.querySelector('[data-testid="lead-in-price-mobile"], button');
                    const priceText = priceNode ? getText(priceNode) : null; // e.g., "From $271"
                    
                    // Create a clean info string for debugging
                    const info = [rawDateText, eventName, locationText, priceText].filter(Boolean).join(" | ");

                    if (eventName) {
                        collected.push({
                            source: "dom_event_card",
                            url: href || url,
                            eventName: eventName.toLowerCase(),
                            // Vivid Seats URLs usually contain the date (e.g., ...-4-10-2026), so we parse the URL as a fallback if the text parse fails
                            date: Parsers.date(rawDateText) || Parsers.date(href), 
                            time: Parsers.time(rawDateText),
                            price: Parsers.price(priceText),
                            availabilityStatus: 'available',
                            info: info
                        });
                    }
                } catch (e) { console.error("Error parsing event card", e); }
            });
            return collected;
        }
    };

    // ============================================================================
    // 5. MAIN EXECUTION
    // ============================================================================
    try {
        let scraped = [];
        scraped.push(...Scraper.ldJson());
        scraped.push(...Scraper.ticketListings());
        scraped.push(...Scraper.eventCards());

        if (scraped.length === 0) {
            scraped.push({
                source: "fallback_metadata",
                url: url,
                eventName: getText(document.querySelector('h1'))?.toLowerCase() || 'unknown',
                info: "No specific elements found. Check antiBot state."
            });
        }

        const globalDate = Parsers.date(pageText);
        const globalTime = Parsers.time(pageText);
        const filters = Scraper.pageFilters();

        const meta = {
            pageType: Enrichment.pageType(),
            antiBotStatus: Enrichment.antiBotStatus(),
            eventCategory: Enrichment.category(),
            globalStatus: Enrichment.status(pageText),
            globalDate: globalDate,
            globalTime: globalTime,
            ...filters
        };

        const seen = new Set();
        scraped.forEach(item => {
            const key = `${item.eventName}-${item.date}-${item.section}-${item.row}-${item.price}-${item.source}`;
            if (!seen.has(key)) {
                seen.add(key);
                
                let finalDate = item.date;
                let finalTime = item.time;
                if (!finalDate && meta.pageType === 'event_listing') {
                    finalDate = meta.globalDate;
                    finalTime = meta.globalTime;
                }

                results.push({
                    ...item,
                    ...meta,
                    date: finalDate,
                    parsedTime: Parsers.time(finalTime || ''),
                    availabilityStatus: item.availabilityStatus || meta.globalStatus,
                    isSuperSeller: item.isSuperSeller !== undefined ? item.isSuperSeller : Enrichment.isSuperSeller(item.info),
                    obstructedView: Enrichment.obstructed(item.info),
                });
            }
        });
    } catch (e) { console.error("Vivid Seats Scraper failed", e); }

    return results;
})();