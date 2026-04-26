/**
 * Facebook Marketplace Info Gathering Script
 * 
 * Injected into the browser page to scrape DOM-level data from
 * Facebook Marketplace search results and individual listings.
 * 
 * Browser-Verified: April 2026
 * 
 * Returns an array of objects with scraped data from the current page.
 * Detects: search results, individual listings, category pages, homepage.
 * 
 * NOTE: This is a placeholder for future DOM-based verification.
 * The primary verifier is URL-based (fb_marketplace_url_match.py).
 */

(function () {
    "use strict";

    const results = [];
    const url = window.location.href;

    // ========================================================================
    // Page type detection
    // ========================================================================

    function detectPageType() {
        const path = window.location.pathname;
        if (path.includes("/marketplace/item/")) return "listing";
        if (path.includes("/marketplace/category/")) return "category";
        if (path.includes("/search")) return "search_results";
        if (path.match(/^\/marketplace\/?$/)) return "homepage";
        return "unknown";
    }

    // ========================================================================
    // Anti-bot / login modal detection
    // ========================================================================

    function detectAntiBotStatus() {
        const body = document.body ? document.body.innerHTML : "";
        if (body.includes("checkpoint") || body.includes("captcha")) {
            return "captcha";
        }
        // Check for login modal overlay
        const loginModal = document.querySelector('[role="dialog"]');
        if (loginModal) {
            const text = loginModal.textContent || "";
            if (text.includes("Log in") || text.includes("Sign Up") || 
                text.includes("Create new account")) {
                return "login_modal";
            }
        }
        return "clear";
    }

    // ========================================================================
    // Search results scraping  
    // ========================================================================

    function scrapeSearchResults() {
        const items = [];
        
        // Facebook Marketplace listing cards use various selectors
        // These are subject to change as Facebook updates their DOM
        const listingLinks = document.querySelectorAll(
            'a[href*="/marketplace/item/"]'
        );

        listingLinks.forEach((link) => {
            try {
                const card = link.closest('[class]') || link.parentElement;
                if (!card) return;

                // Try to extract price text
                const priceEl = card.querySelector('span[dir="auto"]');
                const priceText = priceEl ? priceEl.textContent.trim() : "";
                const priceMatch = priceText.match(/[\$£€]?([\d,]+)/);
                const price = priceMatch
                    ? parseFloat(priceMatch[1].replace(/,/g, ""))
                    : null;

                // Try to extract title
                const spans = card.querySelectorAll("span");
                let title = "";
                for (const span of spans) {
                    const text = span.textContent.trim();
                    if (text.length > 5 && text !== priceText && !text.match(/^\$/)) {
                        title = text;
                        break;
                    }
                }

                // Extract item ID from href
                const href = link.getAttribute("href") || "";
                const idMatch = href.match(/\/marketplace\/item\/(\d+)/);
                const itemId = idMatch ? idMatch[1] : "";

                items.push({
                    source: "search_card",
                    itemId: itemId,
                    title: title,
                    price: price,
                    priceText: priceText,
                    url: href,
                });
            } catch (e) {
                // Skip malformed cards
            }
        });

        return items;
    }

    // ========================================================================
    // Main execution
    // ========================================================================

    const pageType = detectPageType();
    const antiBotStatus = detectAntiBotStatus();

    if (pageType === "search_results" || pageType === "category") {
        const items = scrapeSearchResults();
        items.forEach((item) => {
            item.pageType = pageType;
            item.antiBotStatus = antiBotStatus;
            results.push(item);
        });
    }

    // If no items found, still return page metadata
    if (results.length === 0) {
        results.push({
            source: "page_metadata",
            pageType: pageType,
            antiBotStatus: antiBotStatus,
            url: url,
            title: document.title || "",
            info: "No listing cards found on page",
        });
    }

    return results;
})();
