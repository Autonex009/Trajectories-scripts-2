from pydantic import BaseModel
from typing import TypedDict, List
from pathlib import Path

from navi_bench.base import BaseMetric

# ---------------- TYPES ----------------

class Query(TypedDict, total=False):
    modes: List[str]
    max_price: float
    max_duration: int


class Info(TypedDict, total=False):
    mode: str
    min_price: float
    max_price: float
    duration: int
    pageType: str
    name: str   
    stars: int  
    rating: float # Added for Experiences


class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int


# ---------------- CORE CLASS ----------------

class Rome2RioInfoGathering(BaseMetric):

    def __init__(self, queries):
        super().__init__()
        self.queries = queries
        self._infos = []
        self._covered = [False] * len(queries)
        self.seen_signatures = set() 

    @property
    def js_script(self):
        return (Path(__file__).parent / "rome2rio_info_gathering.js").read_text()

    async def update(self, **kwargs):
        page = kwargs["page"]

        try:
            data = await page.evaluate(self.js_script)

            if isinstance(data, list):
                new_data = []
                
                # Deduplication logic
                for r in data:
                    page_type = r.get("pageType")
                    if page_type in ["hotels", "experiences"]:
                        sig = f"{page_type}_{r.get('name')}_{r.get('min_price')}"
                    else:
                        sig = f"route_{r.get('mode')}_{r.get('min_price')}_{r.get('duration')}"
                    
                    if sig not in self.seen_signatures:
                        self.seen_signatures.add(sig)
                        new_data.append(r)
                        self._infos.append(r)

                if new_data:
                    print(f"\n[SCRAPED {len(new_data)} NEW ITEMS] -> {page.url}")

                    for i, r in enumerate(new_data[:10], 1):
                        price_display = f"₹{r.get('min_price')}" if r.get('min_price') is not None else "N/A"
                        duration_display = f"{r.get('duration')} min" if r.get('duration') is not None else "N/A"
                        
                        if r.get("pageType") == "hotels":
                            stars_display = f"{r.get('stars')}★" if r.get('stars') else "Unrated"
                            print(f"{i}. [HOTEL] {r.get('name')} ({stars_display}) | {price_display}")
                        elif r.get("pageType") == "experiences":
                            rating_display = f"{r.get('rating')}★" if r.get('rating') else "Unrated"
                            print(f"{i}. [EXPERIENCE] {r.get('name')} ({rating_display}) | {price_display} | {duration_display}")
                        else:
                            print(f"{i}. [ROUTE] {r.get('mode')} | {price_display} | {duration_display}")

        except Exception as e:
            print(f"[ERROR] scraping failed: {e}")

    async def compute(self):
        for info in self._infos:
            for i, query_group in enumerate(self.queries):
                if self._covered[i]:
                    continue
                for query in query_group:
                    if self._match(query, info):
                        self._covered[i] = True
                        break

        n_queries = len(self.queries)
        n_covered = sum(self._covered)

        result = FinalResult(
            score=n_covered / max(n_queries, 1),
            n_queries=n_queries,
            n_covered=n_covered
        )
        return result

    def _match(self, query, info):
        if "modes" in query:
            mode = (info.get("mode") or "").lower()
            if not any(m.lower() in mode for m in query["modes"]):
                return False

        if "max_price" in query:
            price = info.get("min_price") 
            if price is None or price > query["max_price"]:
                return False

        if "max_duration" in query:
            duration = info.get("duration")
            if duration is None or duration > query["max_duration"]:
                return False

        return True