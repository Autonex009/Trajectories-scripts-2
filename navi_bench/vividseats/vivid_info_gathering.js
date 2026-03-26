(() => {
    const results = [];
    const url = window.location.href;
    const pageText = document.body ? document.body.innerText.toLowerCase() : '';

    // ============================================================================
    // 1. UTILITIES
    // ============================================================================
    const getText = (el) => {
        if (!el) return null;
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
                
                // 1. Match full ISO dates (e.g., 2026-04-19)
                let match = clean.match(/(\d{4})-(\d{2})-(\d{2})/);
                if (match) return match[0];
                
                // 2. Match dates WITH a year (e.g., Oct 24, 2026)
                match = clean.match(/([a-z]{3})[a-z]*\s+(\d{1,2}),?\s*(\d{4})/i);
                const months = { jan:1, feb:2, mar:3, apr:4, may:5, jun:6, jul:7, aug:8, sep:9, oct:10, nov:11, dec:12 };
                
                if (match) {
                    const m = months[match[1].substring(0, 3)];
                    if (m) return `${match[3]}-${String(m).padStart(2,'0')}-${match[2].padStart(2,'0')}`;
                }

                // 3. FIX: Match dates WITHOUT a year (e.g., Sun, Apr 19 at 5:00pm)
                // We will infer the year. If the month has already passed in the current year, assume next year.
                match = clean.match(/([a-z]{3})[a-z]*\s+(\d{1,2})/i);
                if (match) {
                    const m = months[match[1].substring(0, 3)];
                    if (m) {
                        const today = new Date();
                        let targetYear = today.getFullYear();
                        
                        // If the parsed month is earlier than the current month, assume it's next year
                        if (m < (today.getMonth() + 1)) {
                            targetYear++;
                        }
                        return `${targetYear}-${String(m).padStart(2,'0')}-${match[2].padStart(2,'0')}`;
                    }
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
            if (url.includes('/production/')) return 'event_listing'; 
            if (url.includes('/search') || url.includes('?query=')) return 'search_results';
            if (url.includes('/concerts/') || url.includes('/theater/') || url.includes('/sports/')) return 'event_category';
            return 'other';
        },
        antiBotStatus: () => {
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
                let activeZones = [];

                const qtyBtn = document.querySelector('[data-testid="show-quantity-filter-button"], [data-testid="Quantity-filter-button"]');
                if (qtyBtn) {
                    const qtyText = getText(qtyBtn);
                    const qtyMatch = qtyText ? qtyText.match(/(\d+)/) : null;
                    if (qtyMatch) filterQuantity = parseInt(qtyMatch[1]);
                }

                const priceBtn = document.querySelector('[data-testid="show-price-filter-button"], [data-testid="Price-filter-button"]');
                if (priceBtn) {
                    const priceText = getText(priceBtn);
                    if (priceText) {
                        const priceMatches = [...priceText.matchAll(/[$£€₹]?\s*([\d,]+(?:\.\d{2})?)/g)];
                        if (priceMatches.length >= 1) filterMinPrice = parseFloat(priceMatches[0][1].replace(/,/g, ''));
                        if (priceMatches.length >= 2) filterMaxPrice = parseFloat(priceMatches[1][1].replace(/,/g, ''));
                    }
                }
                
                const underXBtn = document.querySelector('[data-testid="tickets-under-x-filter-button"]');
                if (underXBtn && !filterMaxPrice) { 
                    const underXText = getText(underXBtn);
                    if (underXText && underXText.toLowerCase().includes('under')) {
                        const match = underXText.match(/[$£€₹]?\s*([\d,]+(?:\.\d{2})?)/);
                        const isOutlined = underXBtn.className.includes('MuiChip-outlined');
                        if (match && !isOutlined) filterMaxPrice = parseFloat(match[1].replace(/,/g, ''));
                    }
                }

                const dateFilterBtn = document.querySelector('[data-testid="date-filter-button"]');
                if (dateFilterBtn) {
                    const dateText = getText(dateFilterBtn);
                    if (dateText && dateText.toLowerCase() !== 'date') {
                        filterDate = Parsers.date(dateText) || dateText;
                    }
                }

                const superSellerToggle = document.querySelector('[data-testid="super-seller-toggle"]');
                const isSuperSellerOnly = superSellerToggle ? superSellerToggle.getAttribute('aria-checked') === 'true' : false;

                const zoneBtns = document.querySelectorAll('[data-testid="zone-chip-container"] button');
                zoneBtns.forEach(btn => {
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
            
            const headerTitleNode = document.querySelector('[data-testid="production-detail-bar-performer-link"], h1, [data-testid="event-title"]');
            const eventNameContext = headerTitleNode ? getText(headerTitleNode).trim() : "";

            const locationElement = document.querySelector('[data-testid="event-location"], .event-location-text');
            let cityField = "";
            if (locationElement) {
                const locText = getText(locationElement);
                if (locText) cityField = locText.split(',')[0].trim();
            }

            const rows = document.querySelectorAll('div[data-rowid], [data-testid="listing-row-container"] > div, [data-testid="listing-card"], .listing-item, li[data-ticket-id]');

            rows.forEach(row => {
                try {
                    const dataPrice = row.getAttribute('data-price');
                    const priceNode = row.querySelector('[data-testid="listing-price"], .ticket-price');
                    const rawPrice = dataPrice || (priceNode ? getText(priceNode) : getText(row));
                    const extractedPrice = Parsers.price(rawPrice);

                    if (!extractedPrice) return;

                    const qtyElement = row.querySelector('[data-testid="listing-quantity"], .ticket-quantity');
                    let qtyVal = 1;
                    if (qtyElement) {
                        const qtyText = getText(qtyElement).replace(/[^0-9]/g, '');
                        qtyVal = parseInt(qtyText, 10) || 1;
                    }

                    let sectionText = "";
                    let rowText = "";
                    let zoneText = "";
                    
                    const seatingElement = row.querySelector('[data-testid="listing-seating"], .seating-info, [class*="sectionContent"] [class*="MuiTypography"], [class*="styles_sectionColumn"] [class*="styles_nowrap"]');
                    const seatInfo = seatingElement ? getText(seatingElement).toLowerCase() : getText(row).toLowerCase();

                    if (seatInfo.includes('zone:')) zoneText = seatInfo.split('zone:')[1].split('|')[0].trim();

                    if (seatInfo.includes('sec:')) sectionText = seatInfo.split('sec:')[1].split('|')[0].trim();
                    else if (seatInfo.includes('section')) sectionText = seatInfo.split('section')[1].split(',')[0].trim();
                    else {
                        sectionText = extractByPattern(getText(row), {s: /(?:\bSection\b|\bSec\b|Zone)\s+([A-Za-z0-9\s]+?)(?=\s*(?:[•·,:-]|\bRow\b|$))/i}) || "";
                        if(!sectionText && seatingElement && !seatInfo.includes('row')) sectionText = seatInfo.split(',')[0].trim();
                    }

                    const dataRow = row.getAttribute('data-rowid');
                    const rowNode = row.querySelector('[data-testid="row"]');
                    
                    if (dataRow) rowText = dataRow;
                    else if (rowNode) rowText = getText(rowNode).replace(/Row/i, '').trim();
                    else if (seatInfo.includes('row:')) rowText = seatInfo.split('row:')[1].split('|')[0].trim();
                    else if (seatInfo.includes('row')) rowText = seatInfo.split('row')[1].split('|')[0].trim();
                    else rowText = extractByPattern(getText(row), {r: /\bRow\s+([A-Za-z0-9]+)/i}) || "";
                    
                    if(rowText) rowText = rowText.replace(/[^a-z0-9]/gi, '');

                    const isSuperSeller = row.querySelector('[class*="superSellerIcon"], [class*="ticket-super-seller"], [data-testid="super-seller-badge"], img[alt*="Super Seller"]') !== null || Enrichment.isSuperSeller(getText(row));

                    collected.push({
                        source: "dom_ticket_listing",
                        eventName: eventNameContext.toLowerCase(), 
                        city: cityField.toLowerCase(),
                        price: extractedPrice,
                        ticketCount: qtyVal,
                        section: sectionText,
                        zone: zoneText || sectionText, 
                        row: rowText,
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
            const rows = document.querySelectorAll('a[data-testid^="production-listing-row-"]');
            
            rows.forEach(row => {
                try {
                    const href = row.getAttribute('href');
                    const titleNode = row.querySelector('.styles_titleColumn__T_Kfd > span:first-child, [class*="titleTruncate"]');
                    const eventName = titleNode ? getText(titleNode) : null;
                    const dateTimeNode = row.querySelector('[data-testid="date-time-left-element"]');
                    const rawDateText = dateTimeNode ? getText(dateTimeNode) : null; 
                    const subtitleNode = row.querySelector('[data-testid="subtitle"]');
                    const locationText = subtitleNode ? getText(subtitleNode) : null; 
                    const priceNode = row.querySelector('[data-testid="lead-in-price-mobile"], button');
                    const priceText = priceNode ? getText(priceNode) : null; 
                    
                    const info = [rawDateText, eventName, locationText, priceText].filter(Boolean).join(" | ");

                    if (eventName) {
                        collected.push({
                            source: "dom_event_card",
                            url: href || url,
                            eventName: eventName.toLowerCase() + (locationText ? ` - ${locationText.toLowerCase()}` : ""), 
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

        const filters = Scraper.pageFilters();

        if (scraped.length === 0) {
            const headerTitleNode = document.querySelector('h1') || document.querySelector('[data-testid="event-title"]');
            scraped.push({
                source: "fallback_metadata",
                url: url,
                eventName: headerTitleNode ? getText(headerTitleNode).toLowerCase() : 'unknown',
                filterDateRange: filters.filterDate, 
                info: "No specific elements found. Check antiBot state or search page."
            });
        }

        // FIX: Extract global Date and time but allow it to infer the current year
        // We look specifically at the header area where the date is displayed "Sun, Apr 19 at 5:00pm"
        let globalDateNode = document.querySelector('[data-testid="event-date"], .event-date-text') || document.querySelector('h1')?.nextElementSibling;
        let globalDateText = globalDateNode ? getText(globalDateNode) : pageText;
        
        const globalDate = Parsers.date(globalDateText);
        const globalTime = Parsers.time(globalDateText);

        const meta = {
            pageType: Enrichment.pageType(),
            antiBotStatus: Enrichment.antiBotStatus(),
            eventCategory: Enrichment.category(),
            globalStatus: Enrichment.status(pageText),
            globalDate: globalDate,
            globalTime: globalTime,
            filterLocation: filters.filterLocation, 
            ...filters
        };

        const seen = new Set();
        scraped.forEach(item => {
            const key = `${item.eventName}-${item.date}-${item.section}-${item.row}-${item.price}-${item.source}`;
            if (!seen.has(key)) {
                seen.add(key);
                
                // Merge JSON-LD dates and DOM cities so neither fails
                // If the DOM item is missing a date, give it the global date
                let finalDate = item.date;
                let finalTime = item.time;
                if (!finalDate && meta.pageType === 'event_listing') {
                    finalDate = meta.globalDate;
                    finalTime = meta.globalTime;
                }
                
                // If it's an ld+json source and it lacks city specificity, attempt to pull the DOM city
                let finalCity = item.city;
                if (item.source === "ld+json" && !finalCity) {
                   const domCityNode = document.querySelector('[data-testid="event-location"]');
                   if(domCityNode) finalCity = getText(domCityNode).split(',')[0].trim().toLowerCase();
                }

                results.push({
                    ...item,
                    ...meta, 
                    date: finalDate,
                    city: finalCity,
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