/**
 * Trainline Info Gathering — DOM Scraper
 *
 * Injected into Trainline search results pages via page.evaluate() to extract:
 * 1. Search header: origin station, destination station (rendered names)
 * 2. Passenger summary: e.g. "2 adults", "1 adult, 1 child"
 * 3. Journey metadata: date, journey type (single/return)
 * 4. Ticket listings: prices, departure/arrival times, duration, operator
 * 5. Anti-bot detection
 * 6. URL metadata parsing
 *
 * Returns an array of InfoDict objects for the Python verifier.
 *
 * Browser-verified against thetrainline.com (Apr 2026)
 *
 * Key DOM selectors (verified Apr 2026):
 *   Origin input:       document.getElementById('from.search')
 *   Destination input:  document.getElementById('to.search')
 *   Passenger summary:  #passenger-summary-btn innerText → "2 adults"
 *   Outbound date:      #page.journeySearchForm.outbound.title aria-label
 *   Journey cards:      div with price, time, operator info
 *
 * Last updated: 2026-04-19
 */
(() => {
    'use strict';

    const results = [];
    const url = window.location.href;
    const pageText = document.body ? document.body.innerText.toLowerCase() : '';

    // =========================================================================
    // 1. UTILITIES
    // =========================================================================

    const getText = (el) => {
        if (!el) return null;
        let text = el.innerText || el.textContent || '';
        return text.replace(/\u00A0/g, ' ').trim().replace(/\s+/g, ' ');
    };

    const getInputValue = (id) => {
        const el = document.getElementById(id);
        return el ? (el.value || '').trim() : '';
    };

    // =========================================================================
    // 2. PARSERS
    // =========================================================================

    const Parsers = {
        price: (text) => {
            if (!text) return null;
            try {
                // £42.50, $107.39, €89.00
                let match = text.match(/(?:[£$€₹])\s*([\d,]+(?:\.\d+)?)/);
                if (match) return parseFloat(match[1].replace(/,/g, ''));

                // 42.50 GBP, 107 USD
                match = text.match(/([\d,]+(?:\.\d+)?)\s*(?:GBP|USD|EUR)/i);
                if (match) return parseFloat(match[1].replace(/,/g, ''));

                // Fallback: bare number
                match = text.match(/(\d[\d,]*(?:\.\d{2})?)/);
                if (match) return parseFloat(match[1].replace(/,/g, ''));
            } catch (e) { return null; }
            return null;
        },

        duration: (text) => {
            if (!text) return null;
            const match = text.match(/(\d+)\s*h(?:\s*(\d+)\s*m)?/i);
            if (match) {
                const hours = parseInt(match[1]);
                const minutes = match[2] ? parseInt(match[2]) : 0;
                return hours * 60 + minutes;
            }
            const minOnly = text.match(/(\d+)\s*m(?:in)?/i);
            if (minOnly) return parseInt(minOnly[1]);
            return null;
        },

        time: (text) => {
            if (!text) return null;
            // 12-hour AM/PM
            let match = text.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
            if (match) {
                let h = parseInt(match[1]);
                if (match[3].toUpperCase() === 'PM' && h < 12) h += 12;
                if (match[3].toUpperCase() === 'AM' && h === 12) h = 0;
                return `${String(h).padStart(2, '0')}:${match[2]}`;
            }
            // 24-hour
            match = text.match(/(\d{1,2}):(\d{2})/);
            if (match) return `${match[1].padStart(2, '0')}:${match[2]}`;
            return null;
        },

        /**
         * Parse passenger summary text into structured counts.
         * Input: "2 adults", "1 adult, 1 child", "3 adults, 2 children"
         * Returns: { adults: N, children: N }
         */
        passengerSummary: (text) => {
            if (!text) return { adults: 0, children: 0 };
            const t = text.toLowerCase();
            let adults = 0, children = 0;

            const adultMatch = t.match(/(\d+)\s*adult/);
            if (adultMatch) adults = parseInt(adultMatch[1]);

            const childMatch = t.match(/(\d+)\s*child(?:ren)?/);
            if (childMatch) children = parseInt(childMatch[1]);

            // Default: if nothing parsed but we're on a results page, assume 1 adult
            if (adults === 0 && children === 0) adults = 1;

            return { adults, children };
        }
    };

    // =========================================================================
    // 3. ANTI-BOT DETECTION
    // =========================================================================

    const detectAntiBot = () => {
        if (pageText.includes('press & hold')) return 'blocked_captcha';
        if (pageText.includes('are you a person or a robot')) return 'blocked_captcha';
        if (pageText.includes('challenge-running')) return 'blocked_cloudflare';
        if (pageText.includes('just a moment')) return 'blocked_cloudflare';
        if (pageText.includes('verify you are human')) return 'blocked_captcha';
        if (pageText.includes('checking your browser')) return 'blocked_cloudflare';
        if (pageText.includes('security check')) return 'blocked_security';
        if (pageText.includes('access denied')) return 'blocked_access';
        if (document.querySelector('#challenge-running')) return 'blocked_cloudflare';
        if (document.querySelector('.cf-browser-verification')) return 'blocked_cloudflare';
        return 'clear';
    };

    // =========================================================================
    // 4. SEARCH HEADER EXTRACTION
    // =========================================================================

    const extractSearchHeader = () => {
        const header = {
            originStation: '',
            destinationStation: '',
            passengerSummary: '',
            adults: 0,
            children: 0,
            outwardDate: '',
            journeyType: '',  // 'single' or 'return'
        };

        // Origin & Destination from input fields
        header.originStation = getInputValue('from.search');
        header.destinationStation = getInputValue('to.search');

        // Fallback: try aria-labels or data attributes
        if (!header.originStation) {
            const fromEl = document.querySelector('[data-testid="origin-station"], [aria-label*="From"]');
            if (fromEl) header.originStation = getText(fromEl) || fromEl.getAttribute('aria-label') || '';
        }
        if (!header.destinationStation) {
            const toEl = document.querySelector('[data-testid="destination-station"], [aria-label*="To"]');
            if (toEl) header.destinationStation = getText(toEl) || toEl.getAttribute('aria-label') || '';
        }

        // Passenger summary
        const passengerBtn = document.getElementById('passenger-summary-btn');
        if (passengerBtn) {
            header.passengerSummary = getText(passengerBtn) || '';
        }
        // Fallback: look for passenger summary text in sidebar
        if (!header.passengerSummary) {
            const paxEl = document.querySelector('[class*="passenger"], [data-testid*="passenger"]');
            if (paxEl) header.passengerSummary = getText(paxEl) || '';
        }

        // Parse passenger counts
        const pax = Parsers.passengerSummary(header.passengerSummary);
        header.adults = pax.adults;
        header.children = pax.children;

        // Outward date from input
        const dateEl = document.getElementById('page.journeySearchForm.outbound.title');
        if (dateEl) {
            header.outwardDate = dateEl.getAttribute('aria-label') || dateEl.value || '';
        }

        // Journey type from URL
        const urlObj = new URL(url);
        header.journeyType = urlObj.searchParams.get('journeySearchType') || 'single';

        return header;
    };

    // =========================================================================
    // 5. URL METADATA EXTRACTION
    // =========================================================================

    const extractUrlMetadata = () => {
        const meta = {};
        try {
            const urlObj = new URL(url);
            meta.origin = urlObj.searchParams.get('origin') || '';
            meta.destination = urlObj.searchParams.get('destination') || '';
            meta.outwardDate = urlObj.searchParams.get('outwardDate') || '';
            meta.inwardDate = urlObj.searchParams.get('inwardDate') || '';
            meta.journeySearchType = urlObj.searchParams.get('journeySearchType') || '';
            meta.outwardDateType = urlObj.searchParams.get('outwardDateType') || '';
            meta.inwardDateType = urlObj.searchParams.get('inwardDateType') || '';

            // Count passengers from URL
            const passengers = urlObj.searchParams.getAll('passengers[]');
            meta.passengerCount = passengers.length;
            meta.passengerDOBs = passengers;
        } catch (e) { console.error('URL parse error', e); }
        return meta;
    };

    // =========================================================================
    // 6. JOURNEY CARD SCRAPER
    // =========================================================================

    const scrapeJourneyCards = () => {
        const collected = [];
        try {
            // Trainline renders journey options as card/row elements
            // Try multiple selector strategies
            const cards = document.querySelectorAll(
                '[data-testid*="journey"], [data-testid*="result"], ' +
                '[class*="journey-option"], [class*="JourneyOption"], ' +
                '[class*="result-card"], [class*="ResultCard"], ' +
                'li[class*="journey"], div[class*="journey-card"]'
            );

            // Fallback: look for any element with price and time info
            const candidateCards = cards.length > 0 ? cards :
                document.querySelectorAll('a[href*="selectedOutward"], div[role="listitem"]');

            candidateCards.forEach(card => {
                try {
                    const cardText = getText(card) || '';
                    if (!cardText || cardText.length < 15) return;

                    // Price
                    const priceNode = card.querySelector(
                        '[class*="price"], [class*="Price"], ' +
                        '[data-testid*="price"], [class*="amount"]'
                    );
                    const price = Parsers.price(priceNode ? getText(priceNode) : cardText);

                    // Departure time
                    const timeNodes = card.querySelectorAll(
                        '[class*="time"], [class*="Time"], time, ' +
                        '[data-testid*="time"], [class*="depart"], [class*="arrive"]'
                    );
                    let departTime = null, arrivalTime = null;
                    if (timeNodes.length >= 2) {
                        departTime = Parsers.time(getText(timeNodes[0]));
                        arrivalTime = Parsers.time(getText(timeNodes[timeNodes.length - 1]));
                    }
                    // Fallback: regex from text
                    if (!departTime) {
                        const timeMatch = cardText.match(/(\d{1,2}:\d{2})\s*[–\-→]\s*(\d{1,2}:\d{2})/);
                        if (timeMatch) {
                            departTime = timeMatch[1];
                            arrivalTime = timeMatch[2];
                        }
                    }

                    // Duration
                    const durationNode = card.querySelector(
                        '[class*="duration"], [class*="Duration"]'
                    );
                    const duration = Parsers.duration(
                        durationNode ? getText(durationNode) : cardText
                    );

                    // Operator / Train company
                    const operatorNode = card.querySelector(
                        '[class*="operator"], [class*="Operator"], ' +
                        '[class*="carrier"], [class*="Carrier"], ' +
                        'img[alt*="rail"], img[alt*="train"]'
                    );
                    let operator = '';
                    if (operatorNode) {
                        operator = getText(operatorNode) || operatorNode.getAttribute('alt') || '';
                    }

                    // Changes / Stops
                    let changes = null;
                    if (/\bdirect\b/i.test(cardText)) changes = 0;
                    else {
                        const changeMatch = cardText.match(/(\d+)\s*change/i);
                        if (changeMatch) changes = parseInt(changeMatch[1]);
                    }

                    if (price || departTime) {
                        collected.push({
                            source: 'dom_journey_listing',
                            price: price,
                            departTime: departTime,
                            arrivalTime: arrivalTime,
                            duration: duration,
                            operator: operator.toLowerCase(),
                            changes: changes,
                            info: cardText.substring(0, 300),
                        });
                    }
                } catch (e) { /* skip bad card */ }
            });
        } catch (e) { console.error('Journey card scraper error', e); }
        return collected;
    };

    // =========================================================================
    // 7. MAIN EXECUTION
    // =========================================================================

    try {
        const antiBotStatus = detectAntiBot();
        const searchHeader = extractSearchHeader();
        const urlMeta = extractUrlMetadata();
        const journeyCards = scrapeJourneyCards();

        // Determine page type
        let pageType = 'other';
        if (url.includes('/book/results')) {
            pageType = 'train_results';
        } else if (url.includes('thetrainline.com') || url.includes('trainline.')) {
            pageType = 'trainline_other';
        }

        // If we have journey cards, emit one entry per card (with header context)
        if (journeyCards.length > 0) {
            journeyCards.forEach(card => {
                results.push({
                    ...card,
                    ...searchHeader,
                    pageType: pageType,
                    antiBotStatus: antiBotStatus,
                    urlOrigin: urlMeta.origin,
                    urlDestination: urlMeta.destination,
                    urlOutwardDate: urlMeta.outwardDate,
                    urlInwardDate: urlMeta.inwardDate,
                    urlJourneyType: urlMeta.journeySearchType,
                    urlPassengerCount: urlMeta.passengerCount,
                });
            });
        } else {
            // No cards found — still emit the header info so verifier can match
            results.push({
                source: 'dom_search_header',
                ...searchHeader,
                pageType: pageType,
                antiBotStatus: antiBotStatus,
                urlOrigin: urlMeta.origin,
                urlDestination: urlMeta.destination,
                urlOutwardDate: urlMeta.outwardDate,
                urlInwardDate: urlMeta.inwardDate,
                urlJourneyType: urlMeta.journeySearchType,
                urlPassengerCount: urlMeta.passengerCount,
            });
        }
    } catch (e) { console.error('Trainline Scraper failed', e); }

    return results;
})();
