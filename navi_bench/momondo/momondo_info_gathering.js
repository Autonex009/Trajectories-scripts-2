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
            let match = text.match(/([$€£₹]|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)/i);
            if (match && match[2]) {
                let amount = parseFloat(match[2].replace(/,/g, ""));
                let symbol = (match[1] || "").toLowerCase();
                
                if (symbol === '$') amount *= 83.0; 
                else if (symbol === '€') amount *= 90.0; 
                else if (symbol === '£') amount *= 105.0; 
                
                return amount;
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
        urlMetadata: () => {
            let meta = {};
            if (url.includes('/flights/') || url.includes('/flight-search/')) {
                const match = url.match(/\/(?:flights|flight-search)\/([A-Za-z]{3})-([A-Za-z]{3})\/(\d{4}-\d{2}-\d{2})/i);
                if (match) meta = { origin: match[1], destination: match[2], departDate: match[3] };
            } else if (url.includes('/cars/')) {
                const match = url.match(/\/cars\/([^\/]+)\/([^\/]+)\/(\d{4}-\d{2}-\d{2})/i);
                if (match) meta = { pickUpLocation: match[1], dropOffLocation: match[2], pickUpDate: match[3] };
            } else if (url.includes('/hotels/')) {
                const match = url.match(/\/hotels\/([^\/]+)\/(\d{4}-\d{2}-\d{2})\/(\d{4}-\d{2}-\d{2})/i);
                if (match) meta = { city: match[1], checkIn: match[2], checkOut: match[3] };
            }
            return meta;
        },

        filters: () => {
            const f = { filterAirlines: [], filterStops: [], filterMaxPrice: null };
            if (!url.includes('/flights/') && !url.includes('/flight-search/')) return f; 
            
            try {
                // Helper to extract active filters from a specific region
                const getActiveFilters = (regionLabel) => {
                    const labels = [];
                    const region = document.querySelector(`div[role="region"][aria-label="${regionLabel}"]`);
                    if (!region) return labels;

                    // CRITICAL CHECK: Is this filter section actually active?
                    // Momondo hides the "Reset" button when a filter is default/inactive.
                    const resetBtn = region.querySelector('[class*="filters-reset"]');
                    if (resetBtn && (resetBtn.className.includes('hidden') || resetBtn.getAttribute('aria-disabled') === 'true')) {
                        return labels; // Filter is inactive, return empty array
                    }

                    // If active, gather the text of all checked boxes
                    const checkboxes = region.querySelectorAll('input[type="checkbox"]:checked');
                    checkboxes.forEach(cb => {
                        let text = '';
                        // Standard robust HTML routing: match input ID to label 'for' attribute
                        if (cb.id) {
                            const labelEl = document.querySelector(`label[for="${cb.id}"]`);
                            if (labelEl) text = getText(labelEl);
                        }
                        // Fallback to nearest container
                        if (!text) {
                            const outer = cb.closest('[class*="checkbox-outer"]');
                            if (outer) text = getText(outer);
                        }
                        if (text) labels.push(text.trim());
                    });
                    return labels;
                };

                f.filterAirlines = getActiveFilters("Airlines");
                f.filterStops = getActiveFilters("Stops");

                // Process Price Slider
                const priceRegion = document.querySelector('div[role="region"][aria-label="Price"]');
                if (priceRegion) {
                    const resetBtn = priceRegion.querySelector('[class*="filters-reset"]');
                    
                    // Only scrape the max price if the user has actually moved the slider
                    if (resetBtn && (!resetBtn.className.includes('hidden') && resetBtn.getAttribute('aria-disabled') !== 'true')) {
                        const priceNode = priceRegion.querySelector('[role="slider"]');
                        if (priceNode && priceNode.getAttribute('aria-valuenow')) {
                            let val = parseFloat(priceNode.getAttribute('aria-valuenow'));
                            let valueText = priceNode.getAttribute('aria-valuetext') || "";
                            
                            // Convert back to INR if it rendered in a foreign currency internally
                            if (valueText.includes('$')) val *= 83.0;
                            else if (valueText.includes('€')) val *= 90.0;
                            else if (valueText.includes('£')) val *= 105.0;
                            
                            f.filterMaxPrice = val;
                        }
                    }
                }
            } catch(e) { console.error("Momondo Filter parse error", e); }
            return f;
        },

        flightListings: () => {
            const collected = [];
            // Target the main container. Added fallback classes in case ARIA roles are stripped.
            const rows = document.querySelectorAll('div[role="group"][aria-label^="Result item"], .nrc6-wrapper');

            rows.forEach(row => {
                try {
                    const rowText = getText(row);
                    if (!rowText) return;

                    const priceNode = row.querySelector('[class*="price-text"], [data-test-id="price"], .price');
                    const extractedPrice = Parsers.price(priceNode ? getText(priceNode) : rowText);

                    if (!extractedPrice) return; // Skip empty/invalid rows

                    // 1. ROBUST TIME PARSING: Regex the raw text for HH:MM - HH:MM
                    // This ignores HTML structure entirely and looks for the time signature.
                    let departTime = null;
                    let arrivalTime = null;
                    const timeMatch = rowText.match(/(\d{1,2}:\d{2})\s*[-–\u2013\u2014]\s*(\d{1,2}:\d{2})/);
                    if (timeMatch) {
                        departTime = timeMatch[1];
                        arrivalTime = timeMatch[2];
                    }

                    // 2. ROBUST AIRLINE PARSING: Fallback to Logo Alt Tags
                    const airlineNode = row.querySelector('[class*="operator-text"], .codeshares-airline-names, [class*="name-only-text"]');
                    let airlineText = airlineNode ? getText(airlineNode) : '';
                    
                    if (!airlineText) {
                        // If the text class is hidden/obfuscated, grab the airline name from the logo images!
                        const logos = row.querySelectorAll('img[alt]');
                        const alts = [];
                        logos.forEach(img => {
                            const alt = (img.getAttribute('alt') || '').trim();
                            // Filter out generic image alts, keeping the airline names
                            if (alt && alt.length > 2 && !alt.toLowerCase().includes("logo")) {
                                alts.push(alt);
                            }
                        });
                        if (alts.length > 0) {
                            airlineText = [...new Set(alts)].join(', '); // Remove duplicates (e.g. for round trips)
                        }
                    }

                    let extractedStops = Parsers.stops(rowText);

                    // 3. Cabin Class Fallback
                    let cabinText = '';
                    const cabinNode = row.querySelector('[aria-label*="Cabin"], [class*="cabin"]');
                    if (cabinNode) cabinText = getText(cabinNode);
                    if (!cabinText) {
                        const matchCabin = rowText.match(/(premium economy|first class|business class|business|economy)/i);
                        if (matchCabin) cabinText = matchCabin[1];
                    }

                    collected.push({
                        source: "dom_flight_listing",
                        airline: airlineText.toLowerCase(),
                        price: extractedPrice,
                        stops: extractedStops,
                        departTime,
                        arrivalTime,
                        cabinClass: cabinText.toLowerCase()
                    });
                    
                } catch (e) {
                    console.error("Error parsing row:", e);
                }
            });

            // Deduplicate in case multiple selectors matched parent/child elements of the same result
            const unique = [];
            const seen = new Set();
            collected.forEach(item => {
                const key = `${item.price}-${item.departTime}-${item.arrivalTime}-${item.airline}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    unique.push(item);
                }
            });

            return unique;
        },

        carListings: () => {
            const collected = [];
            // Target generalized car result blocks
            const cards = document.querySelectorAll('[class*="car-result-item"], [data-resultid]');

            cards.forEach(card => {
                try {
                    const titleNode = card.querySelector('.js-title, [class*="title"]');
                    const categoryNode = card.querySelector('[class*="sub-title"]');
                    
                    const priceNode = card.querySelector('[class*="price-total"]');
                    const extractedPrice = Parsers.price(getText(priceNode));

                    const providerNode = card.querySelector('[class*="provider-name"]');
                    const agencyImg = card.querySelector('img[alt^="Car agency:"]');
                    const agencyName = agencyImg ? agencyImg.getAttribute('alt').replace('Car agency:', '').trim() : '';

                    let passengers = null, bags = null, doors = null, transmission = null;
                    const featureNodes = card.querySelectorAll('[role="listitem"]');
                    
                    featureNodes.forEach(f => {
                        const aria = f.getAttribute('aria-label') || '';
                        const text = getText(f);
                        if (aria.includes('Passengers')) passengers = parseInt(text);
                        if (aria.includes('Bags')) bags = parseInt(text);
                        if (aria.includes('doors')) doors = parseInt(text);
                        if (aria.includes('Transmission')) transmission = text;
                    });

                    if (extractedPrice) {
                        collected.push({
                            source: "dom_car_listing",
                            title: getText(titleNode),
                            category: getText(categoryNode),
                            price: extractedPrice,
                            provider: getText(providerNode),
                            agency: agencyName,
                            passengers,
                            bags,
                            doors,
                            transmission
                        });
                    }
                } catch (e) { console.error('Car card parse error', e); }
            });
            return collected;
        },

        hotelListings: () => {
            const collected = [];
            const cards = document.querySelectorAll('[role="group"][data-resultid], .yuAt[role="group"]');

            cards.forEach(card => {
                try {
                    const nameNode = card.querySelector('[class*="big-name"]');
                    const name = getText(nameNode);
                    if (!name) return;

                    const priceNode = card.querySelector('[data-target="price"], [class*="price"]');
                    const extractedPrice = Parsers.price(getText(priceNode));

                    const scoreNode = card.querySelector('[class*="rating"], [class*="score"]');
                    const score = scoreNode && getText(scoreNode) !== "-" ? parseFloat(getText(scoreNode)) : null;

                    const starNode = card.querySelector('[class*="stars"]');
                    const starsText = getText(starNode);
                    const starsMatch = starsText ? starsText.match(/(\d+)\s*stars?/i) : null;
                    const stars = starsMatch ? parseInt(starsMatch[1]) : 0;

                    const providerImg = card.querySelector('img[class*="provider-logo"]');
                    const provider = providerImg ? providerImg.getAttribute('alt') : '';

                    const freebies = [];
                    const freebieNodes = card.querySelectorAll('[class*="freebies"], [class*="amenities"]');
                    freebieNodes.forEach(n => {
                        const txt = getText(n) || n.getAttribute('title');
                        if (txt) {
                            txt.split(',').forEach(f => {
                                const clean = f.trim();
                                if (clean && !freebies.includes(clean)) freebies.push(clean);
                            });
                        }
                    });

                    const locNode = card.querySelector('[class*="location"], [class*="neighborhood"]');
                    const location = getText(locNode);

                    if (extractedPrice) {
                        collected.push({
                            source: "dom_hotel_listing",
                            title: name,
                            price: extractedPrice,
                            score: score,
                            stars: stars,
                            provider: provider,
                            freebies: freebies,
                            location: location
                        });
                    }
                } catch (e) { console.error('Hotel card parse error', e); }
            });
            return collected;
        }
    };

    try {
        let scraped = [];
        let pageType = 'other';

        if (url.includes('/flights/') || url.includes('/flight-search/')) {
            pageType = 'flight_results';
            scraped.push(...Scraper.flightListings());
        } else if (url.includes('/cars/')) {
            pageType = 'car_results';
            scraped.push(...Scraper.carListings());
        } else if (url.includes('/hotels/')) {
            pageType = 'hotel_results';
            scraped.push(...Scraper.hotelListings());
        }

        const antiBotStatus = document.body.innerText.toLowerCase().includes('challenge-running') ? 'blocked_cloudflare' : 'clear';
        const activeFilters = Scraper.filters();
        const urlData = Scraper.urlMetadata();

        scraped.forEach(item => {
            results.push({ ...item, ...activeFilters, ...urlData, pageType, antiBotStatus });
        });
    } catch (e) { console.error("Momondo Scraper failed", e); }

    return results;
})();