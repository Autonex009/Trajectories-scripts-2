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
        urlMetadata: () => {
            let meta = {};
            if (url.includes('/flights/')) {
                const match = url.match(/\/flights\/([A-Za-z]{3})-([A-Za-z]{3})\/(\d{4}-\d{2}-\d{2})/i);
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
            if (!url.includes('/flights/')) return f; 
            
            try {
                const airNodes = document.querySelectorAll('div[role="region"][aria-label="Airlines"] input[type="checkbox"]:checked:not([disabled])');
                airNodes.forEach(n => {
                    const lbl = n.closest('.hYzH-filter-checkbox-outer')?.querySelector('.hYzH-checkbox-label');
                    if (lbl) f.filterAirlines.push(getText(lbl));
                });
                
                const stopNodes = document.querySelectorAll('div[role="region"][aria-label="Stops"] input[type="checkbox"]:checked:not([disabled])');
                stopNodes.forEach(n => {
                    const lbl = n.closest('.hYzH-filter-checkbox-outer')?.querySelector('.hYzH-checkbox-label');
                    if (lbl) f.filterStops.push(getText(lbl));
                });
                
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
                        if (timeMatch) { departTime = timeMatch[1]; arrivalTime = timeMatch[2]; }
                    }

                    if (!departTime) {
                        const cb = row.querySelector('input[type="checkbox"]');
                        if (cb) {
                            const label = cb.getAttribute('aria-label') || "";
                            const timeMatch = label.match(/([A-Z]{3})\s+(\d{2}:\d{2})\s*-\s*([A-Z]{3})\s+(\d{2}:\d{2})/);
                            if (timeMatch) { departTime = timeMatch[2]; arrivalTime = timeMatch[4]; }
                        }
                    }

                    if (extractedPrice) {
                        collected.push({
                            source: "dom_flight_listing",
                            airline: airlineText.toLowerCase(),
                            price: extractedPrice,
                            stops: extractedStops,
                            departTime,
                            arrivalTime
                        });
                    }
                } catch (e) {}
            });
            return collected;
        },

        carListings: () => {
            const collected = [];
            const cards = document.querySelectorAll('.jo6g-car-result-item');

            cards.forEach(card => {
                try {
                    const titleNode = card.querySelector('.js-title');
                    const categoryNode = card.querySelector('.MseY-sub-title');
                    
                    const priceNode = card.querySelector('.c4nz8-price-total') || card.querySelector('[class*="price-total"]');
                    const extractedPrice = Parsers.price(getText(priceNode));

                    const providerNode = card.querySelector('.EuxN-provider-name');
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
            // Target the hotel card wrappers
            const cards = document.querySelectorAll('.yuAt[role="group"]');

            cards.forEach(card => {
                try {
                    // 1. Hotel Name
                    const nameNode = card.querySelector('.c9Hnq-big-name');
                    const name = getText(nameNode);
                    if (!name) return;

                    // 2. Price (Looks for the highlighted price element)
                    const priceNode = card.querySelector('[data-target="price"]') || card.querySelector('.c1XBO') || card.querySelector('.Ptt7-price');
                    const extractedPrice = Parsers.price(getText(priceNode));

                    // 3. Review Score
                    const scoreNode = card.querySelector('.c9kNN');
                    const score = scoreNode && getText(scoreNode) !== "-" ? parseFloat(getText(scoreNode)) : null;

                    // 4. Star Rating
                    const starNode = card.querySelector('.hEI8');
                    const starsText = getText(starNode);
                    const starsMatch = starsText ? starsText.match(/(\d+)\s*stars?/i) : null;
                    const stars = starsMatch ? parseInt(starsMatch[1]) : 0;

                    // 5. Provider / OTA
                    const providerImg = card.querySelector('img[class*="provider-logo"]');
                    const provider = providerImg ? providerImg.getAttribute('alt') : '';

                    // 6. Freebies / Amenities
                    const freebies = [];
                    const freebieNodes = card.querySelectorAll('.BNDX, .iyw8-freebies');
                    freebieNodes.forEach(n => {
                        const txt = getText(n) || n.getAttribute('title');
                        if (txt) {
                            txt.split(',').forEach(f => {
                                const clean = f.trim();
                                if (clean && !freebies.includes(clean)) freebies.push(clean);
                            });
                        }
                    });

                    // 7. Location 
                    const locNode = card.querySelector('.upS4-big-name');
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

        if (url.includes('/flights/')) {
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
    } catch (e) { console.error("Kayak Scraper failed", e); }

    return results;
})();