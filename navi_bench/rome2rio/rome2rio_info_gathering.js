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
        // Use textContent instead of innerText to bypass layout/visibility issues
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
      // MODE: Extract unique airline names from the image alt tags
      const airlineImgs = card.querySelectorAll('img[alt]');
      const airlines = Array.from(airlineImgs)
        .map(img => img.alt.trim())
        .filter(alt => alt && !alt.toLowerCase().includes("kayak")); 
      
      const uniqueAirlines = [...new Set(airlines)];
      const mode = uniqueAirlines.length > 0 ? uniqueAirlines.join(", ") : "Flight";

      // DURATION: Find the first duration time tag (e.g., PT28H55M)
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

      // PRICE: Find the price text within the brand color element or bold labels
      let min_price = null;
      let max_price = null;
      
      // Target elements that typically hold the price on this view
      const brandEls = card.querySelectorAll('.text-text-brand, .text-label-xl.font-bold');
      
      brandEls.forEach(el => {
        // textContent prevents empty strings if the element is off-screen
        const text = el.textContent || "";
        
        // Grab numbers safely without requiring a specific currency symbol
        const numbers = text.match(/[\d,]+/g);
        if (numbers && numbers.length > 0) {
          const values = numbers.map(n => parseInt(n.replace(/,/g, ""), 10)).filter(n => !isNaN(n));
          if (values.length > 0) {
             const elMin = Math.min(...values);
             const elMax = Math.max(...values);
             
             // In case there are multiple price elements, store the lowest/highest found
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

  return results;
};