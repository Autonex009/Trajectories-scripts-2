() => {
  const results = [];

  const cards = document.querySelectorAll('[data-testid^="trip-search-result"]');

  cards.forEach(card => {
    try {
      // -------- MODE --------
      const titleEl = card.querySelector('h1');
      const mode = titleEl ? titleEl.innerText.trim() : null;

      // -------- DURATION --------
      const timeEl = card.querySelector('time');
      let duration = null;

      if (timeEl) {
        const raw = timeEl.getAttribute('datetime'); // PT16H48M

        if (raw) {
          const h = raw.match(/(\d+)H/);
          const m = raw.match(/(\d+)M/);

          duration =
            (h ? parseInt(h[1]) * 60 : 0) +
            (m ? parseInt(m[1]) : 0);
        }
      }

      // -------- PRICE --------
      const priceEl = card.querySelector('div.text-text-brand span');

let min_price = null;
let max_price = null;

if (priceEl) {
    const text = priceEl.innerText.trim();

    console.log("[DEBUG PRICE RAW]", text);

    // Extract all numbers (handles ₹29,712–121,794)
    const numbers = text.match(/[\d,]+/g);

    if (numbers && numbers.length > 0) {
        const values = numbers.map(n => parseInt(n.replace(/,/g, "")));

        min_price = Math.min(...values);
        max_price = Math.max(...values);
    }
}
   
    results.push({
    mode,
    duration,
    min_price,
    max_price,
    pageType: "results"
});
    } catch (e) {
      console.error("Error parsing card:", e);
    }
  });

  return results;
};