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
    price: float
    duration: int
    pageType: str


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

    @property
    def js_script(self):
        return (Path(__file__).parent / "rome2rio_info_gathering.js").read_text()

    async def update(self, **kwargs):
        page = kwargs["page"]

        try:
            data = await page.evaluate(self.js_script)

            if isinstance(data, list):
                print(f"\n[SCRAPED {len(data)} ROUTES]")

                for i, r in enumerate(data[:10], 1):
                    print(f"{i}. {r.get('mode')} | ₹{r.get('price')} | {r.get('duration')} min")

                self._infos.extend(data)

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

        print("[DEBUG] Final result:", result)

        return result

    def _match(self, query, info):

        if "modes" in query:
            mode = (info.get("mode") or "").lower()
            if not any(m.lower() in mode for m in query["modes"]):
                return False

        if "max_price" in query:
            price = info.get("min_price")  # use minimum price for matching

            if price is None or price > query["max_price"]:
                return False

        if "max_duration" in query:
            duration = info.get("duration")
            if duration is None or duration > query["max_duration"]:
                return False

        return True