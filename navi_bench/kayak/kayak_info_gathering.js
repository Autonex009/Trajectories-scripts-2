(() => {
    const results = [];
    const url = window.location.href;

    const getText = (el) => {
        if (!el) return null;
        let text = el.innerText || el.textContent || '';
        return text.replace(/\u00A0/g, ' ').trim().replace(/\s+/g, ' ');
    };

    const Parsers = {
        price: (text) => {
            if (!text) return null;
            let match = text.match(/(?:₹|rs\.?|inr|[$])?\s*([\d,]+)/i);
            if (match && match[1]) {
                return parseFloat(match[1].replace(/,/g, ""));
            }
            return null;
        },
        stops: (text) => {
            if (!text) return null;
            if (/direct|nonstop|non-stop/i.test(text)) return 0;
            let match = text.match(/(\d+)\s*stop/i);
            if (match) return parseInt(match[1]);
            return null;
        }
    };

    const Scraper = {
        // --- RESTORED: URL Metadata Extraction ---
        urlMetadata: () => {
            // Extracts origin, destination, and date from strings like /flights/BLR-DEL/2026-03-31
            const match = url.match(/\/flights\/([A-Za-z]{3})-([A-Za-z]{3})\/(\d{4}-\d{2}-\d{2})/i);
            if (match) {
                return { origin: match[1], destination: match[2], departDate: match[3] };
            }
            return {};
        },

        // --- NEW: Global Filter Extraction ---
        filters: () => {
            const f = { filterAirlines: [], filterStops: [], filterMaxPrice: null };
            try {
                // 1. Airlines 
                const airNodes = document.querySelectorAll('div[role="region"][aria-label="Airlines"] input[type="checkbox"]:checked:not([disabled])');
                airNodes.forEach(n => {
                    const lbl = n.closest('.hYzH-filter-checkbox-outer')?.querySelector('.hYzH-checkbox-label');
                    if (lbl) f.filterAirlines.push(getText(lbl));
                });
                
                // 2. Stops 
                const stopNodes = document.querySelectorAll('div[role="region"][aria-label="Stops"] input[type="checkbox"]:checked:not([disabled])');
                stopNodes.forEach(n => {
                    const lbl = n.closest('.hYzH-filter-checkbox-outer')?.querySelector('.hYzH-checkbox-label');
                    if (lbl) f.filterStops.push(getText(lbl));
                });
                
                // 3. Max Price Slider
                const priceNode = document.querySelector('div[role="region"][aria-label="Price"] span[role="slider"]');
                if (priceNode && priceNode.getAttribute('aria-valuenow')) {
                    f.filterMaxPrice = parseFloat(priceNode.getAttribute('aria-valuenow'));
                }
            } catch(e) { console.error("Filter parse error", e); }
            return f;
        },

        flightListings: () => {
            const collected = [];
            const rows = document.querySelectorAll('div[role="group"][aria-label^="Result item"]');

            rows.forEach(row => {
                try {
                    const rowText = getText(row);
                    if (!rowText) return;

                    const priceNode = row.querySelector('[class*="price-text"]');
                    const extractedPrice = Parsers.price(priceNode ? getText(priceNode) : rowText);

                    const airlineNode = row.querySelector('[class*="operator-text"]');
                    let airlineText = airlineNode ? getText(airlineNode) : '';

                    let extractedStops = Parsers.stops(rowText);
                    let departTime = null;
                    let arrivalTime = null;

                    const timeDiv = row.querySelector('[class*="variant-large"]');
                    if (timeDiv) {
                        const timeMatch = getText(timeDiv).match(/(\d{2}:\d{2})\s*.\s*(\d{2}:\d{2})/);
                        if (timeMatch) {
                            departTime = timeMatch[1];
                            arrivalTime = timeMatch[2];
                        }
                    }

                    if (!departTime) {
                        const cb = row.querySelector('input[type="checkbox"]');
                        if (cb) {
                            const label = cb.getAttribute('aria-label') || "";
                            const timeMatch = label.match(/([A-Z]{3})\s+(\d{2}:\d{2})\s*-\s*([A-Z]{3})\s+(\d{2}:\d{2})/);
                            if (timeMatch) {
                                departTime = timeMatch[2];
                                arrivalTime = timeMatch[4];
                            }
                        }
                    }

                    collected.push({
                        source: "dom_flight_listing",
                        airline: airlineText.toLowerCase(),
                        price: extractedPrice,
                        stops: extractedStops,
                        departTime: departTime,
                        arrivalTime: arrivalTime,
                        info: rowText.substring(0, 80)
                    });
                } catch (e) { console.error('Flight row parse error', e); }
            });
            
            return collected;
        }
    };

    try {
        let scraped = [];
        scraped.push(...Scraper.flightListings());

        const pageType = url.includes('/flights/') ? 'flight_results' : 'other';
        const antiBotStatus = document.body.innerText.toLowerCase().includes('challenge-running') ? 'blocked_cloudflare' : 'clear';
        
        // Fetch metadata and filters
        const activeFilters = Scraper.filters();
        const urlData = Scraper.urlMetadata();

        scraped.forEach(item => {
            results.push({ 
                ...item, 
                ...activeFilters, 
                ...urlData,  // Ensures origin, destination, and departDate are added!
                pageType, 
                antiBotStatus
            });
        });
    } catch (e) { console.error("Kayak Scraper failed", e); }

    return results;
})();