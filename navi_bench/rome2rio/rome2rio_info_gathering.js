() => {
  const results = [];

  // ==========================================
  // 1. ROUTE CARDS (The main search page)
  // ==========================================
  const routeCards = document.querySelectorAll('[data-testid^="trip-search-result"]');
  routeCards.forEach(card => {
    try {
      const titleEl = card.querySelector('h1');
      const mode = titleEl ? titleEl.textContent.trim() : null;

      const timeEl = card.querySelector('time');
      let duration = null;
      if (timeEl) {
        const raw = timeEl.getAttribute('datetime');
        if (raw) {
          const hMatch = raw.match(/(\d+)H/);
          const mMatch = raw.match(/(\d+)M/);
          const hours = hMatch ? parseInt(hMatch[1], 10) : 0;
          const minutes = mMatch ? parseInt(mMatch[1], 10) : 0;
          duration = (hours * 60) + minutes;
        }
      }

      const priceEl = card.querySelector('.text-text-brand');
      let min_price = null;
      let max_price = null;
      if (priceEl) {
        const text = priceEl.textContent.trim();
        const numbers = text.match(/[\d,]+/g);
        if (numbers && numbers.length > 0) {
          const values = numbers.map(n => parseInt(n.replace(/,/g, ""), 10)).filter(n => !isNaN(n));
          if(values.length > 0) {
            min_price = Math.min(...values);
            max_price = Math.max(...values);
          }
        }
      }

      results.push({ mode, duration, min_price, max_price, pageType: "results" });
    } catch (e) {
      console.error("Error parsing route card:", e);
    }
  });

  // ==========================================
  // 2. SCHEDULE CARDS (The flight details page)
  // ==========================================
  const scheduleCards = document.querySelectorAll('[aria-labelledby^="schedule-cell-times-"]');
  scheduleCards.forEach(card => {
    try {
      const airlineImgs = card.querySelectorAll('img[alt]');
      const airlines = Array.from(airlineImgs)
        .map(img => img.alt.trim())
        .filter(alt => alt && !alt.toLowerCase().includes("kayak")); 
      
      const uniqueAirlines = [...new Set(airlines)];
      const mode = uniqueAirlines.length > 0 ? uniqueAirlines.join(", ") : "Flight";

      let duration = null;
      const timeEls = card.querySelectorAll('time');
      timeEls.forEach(timeEl => {
         const raw = timeEl.getAttribute('datetime');
         if (raw && raw.startsWith('PT') && duration === null) { 
            const hMatch = raw.match(/(\d+)H/);
            const mMatch = raw.match(/(\d+)M/);
            const hours = hMatch ? parseInt(hMatch[1], 10) : 0;
            const minutes = mMatch ? parseInt(mMatch[1], 10) : 0;
            duration = (hours * 60) + minutes;
         }
      });

      let min_price = null;
      let max_price = null;
      const brandEls = card.querySelectorAll('.text-text-brand, .text-label-xl.font-bold');
      brandEls.forEach(el => {
        const text = el.textContent || "";
        const numbers = text.match(/[\d,]+/g);
        if (numbers && numbers.length > 0) {
          const values = numbers.map(n => parseInt(n.replace(/,/g, ""), 10)).filter(n => !isNaN(n));
          if (values.length > 0) {
             const elMin = Math.min(...values);
             const elMax = Math.max(...values);
             if (min_price === null || elMin < min_price) min_price = elMin;
             if (max_price === null || elMax > max_price) max_price = elMax;
          }
        }
      });

      results.push({ mode, duration, min_price, max_price, pageType: "schedule" });
    } catch (e) {
      console.error("Error parsing schedule card:", e);
    }
  });

  // ==========================================
  // 3. HOTEL CARDS (The accommodations page)
  // ==========================================
  const hotelCards = document.querySelectorAll('[data-testid="hotel-list-item"]');
  hotelCards.forEach(card => {
    try {
      const nameEl = card.querySelector('h3');
      let name = nameEl ? nameEl.textContent.trim() : "Unknown Hotel";

      let stars = null;
      const starsEl = card.querySelector('[aria-label$="stars"]');
      if (starsEl) {
         const match = starsEl.getAttribute('aria-label').match(/(\d+)/);
         if (match) stars = parseInt(match[1], 10);
      }

      const priceEl = card.querySelector('.text-heading-md');
      let min_price = null;
      let max_price = null;
      if (priceEl) {
         const text = priceEl.textContent.trim();
         const numbers = text.match(/[\d,]+/g);
         if (numbers && numbers.length > 0) {
             const val = parseInt(numbers[0].replace(/,/g, ""), 10);
             if (!isNaN(val)) {
                 min_price = val;
                 max_price = val;
             }
         }
      }

      let score = null;
      const scoreEl = card.querySelector('[data-testid="hotel-review-score"], [class*="reviewScore"], [class*="review-score"]');
      if (scoreEl) {
         const scoreVal = parseFloat(scoreEl.textContent.trim());
         if (!isNaN(scoreVal) && scoreVal >= 1 && scoreVal <= 10) score = scoreVal;
      }
      if (score === null) {
         const allTexts = Array.from(card.querySelectorAll('span, div'));
         for (const el of allTexts) {
            const t = el.textContent.trim();
            const m = t.match(/^(\d+(?:\.\d)?)\s*(?:\/\s*10)?$/);
            if (m) {
               const v = parseFloat(m[1]);
               if (v >= 5 && v <= 10 && el.children.length === 0) { score = v; break; }
            }
         }
      }

      results.push({ mode: "Hotel", name, stars, score, min_price, max_price, pageType: "hotels" });
    } catch (e) {
      console.error("Error parsing hotel card:", e);
    }
  });

  // ==========================================
  // 4. EXPERIENCE CARDS (The activities page)
  // ==========================================
  const experienceCards = document.querySelectorAll('article');
  experienceCards.forEach(card => {
    try {
      const nameEl = card.querySelector('h3');
      if (!nameEl) return; // Skip if not an experience card
      let name = nameEl.textContent.trim();

      // Convert "8 hours", "1 day", or "90 minutes" text to duration in minutes
      let duration = null;
      const durationEl = card.querySelector('.text-sm.text-text-secondary');
      if (durationEl) {
         const text = durationEl.textContent.trim();
         let mins = 0;
         const hMatch = text.match(/(\d+)\s*hour/i);
         if (hMatch) mins += parseInt(hMatch[1], 10) * 60;
         const dMatch = text.match(/(\d+)\s*day/i);
         if (dMatch) mins += parseInt(dMatch[1], 10) * 1440;
         const mMatch = text.match(/(\d+)\s*min/i);
         if (mMatch) mins += parseInt(mMatch[1], 10);
         if (mins > 0) duration = mins;
      }

      // Grab the numerical rating (e.g., 4.6)
      let rating = null;
      const ratingEl = card.querySelector('.text-label-md.font-semibold');
      if (ratingEl) rating = parseFloat(ratingEl.textContent.trim());

      // Grab the final price (targets both regular and discounted prices)
      const priceEl = card.querySelector('.text-base.font-bold');
      let min_price = null;
      let max_price = null;
      if (priceEl) {
         const text = priceEl.textContent.trim();
         const numbers = text.match(/[\d,]+/g);
         if (numbers && numbers.length > 0) {
             const val = parseInt(numbers[0].replace(/,/g, ""), 10);
             if (!isNaN(val)) {
                 min_price = val;
                 max_price = val;
             }
         }
      }

      results.push({ mode: "Experience", name, duration, rating, min_price, max_price, pageType: "experiences" });
    } catch (e) {
      console.error("Error parsing experience card:", e);
    }
  });

  return results;
};