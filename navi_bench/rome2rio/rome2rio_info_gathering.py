from pydantic import BaseModel
from typing import TypedDict, List
from pathlib import Path

from navi_bench.base import BaseMetric, BaseTaskConfig, get_import_path
from navi_bench.dates import initialize_user_metadata, initialize_placeholder_map, render_task_statement

# ---------------- TYPES ----------------

class Query(TypedDict, total=False):
    modes: List[str]
    max_price: float
    min_price: float
    max_duration: int
    min_duration: int
    min_stars: int
    min_score: float
    min_rating: float
    origins: List[str]
    destinations: List[str]
    cities: List[str]


class Info(TypedDict, total=False):
    mode: str
    min_price: float
    max_price: float
    duration: int
    pageType: str
    name: str
    stars: int
    score: float
    rating: float


class FinalResult(BaseModel):
    score: float
    n_queries: int
    n_covered: int


# ---------------- CORE CLASS ----------------

class Rome2RioInfoGathering(BaseMetric):

    def __init__(self, queries, mode: str = "any"):
        super().__init__()
        self.queries = queries
        self.mode = mode  # "any": one info matching one query covers a group
        self._infos = []
        self._covered = [False] * len(queries)
        self.seen_signatures = set()

    async def reset(self) -> None:
        self._infos = []
        self._covered = [False] * len(self.queries)
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
                        sig = f"{page_type}_{r.get('mode')}_{r.get('min_price')}_{r.get('duration')}"
                    
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
            page_type = info.get("pageType", "")
            check = all if self.mode == "all" else any
            if page_type in ("hotels", "experiences"):
                # Hotels and experiences: match modes against the name field
                # because JS emits static mode strings ("Hotel", "Experience")
                name = (info.get("name") or "").lower()
                if not check(m.lower() in name for m in query["modes"]):
                    return False
            else:
                mode = (info.get("mode") or "").lower()
                if not check(m.lower() in mode for m in query["modes"]):
                    return False

        if "max_price" in query:
            price = info.get("min_price")
            if price is None or price > query["max_price"]:
                return False

        if "min_price" in query:
            # Use max_price from the scraped range so a route like ₹30k–₹45k
            # correctly satisfies min_price: 33000 (some options exceed the floor).
            price = info.get("max_price")
            if price is None or price < query["min_price"]:
                return False

        if "max_duration" in query:
            duration = info.get("duration")
            if duration is None or duration > query["max_duration"]:
                return False

        if "min_duration" in query:
            duration = info.get("duration")
            if duration is None or duration < query["min_duration"]:
                return False

        if "min_stars" in query:
            stars = info.get("stars")
            if stars is None or stars < query["min_stars"]:
                return False

        if "min_score" in query:
            score = info.get("score")
            if score is None or score < query["min_score"]:
                return False

        if "min_rating" in query:
            rating = info.get("rating")
            if rating is None or rating < query["min_rating"]:
                return False

        return True


# ---------------- TASK CONFIG ----------------

def generate_task_config_deterministic(
    mode: str,
    task: str,
    queries: list,
    location: str,
    timezone: str,
    timestamp: int | None = None,
    url: str = "https://www.rome2rio.com/",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    user_metadata = initialize_user_metadata(timezone, location, timestamp)

    if values:
        placeholder_map, _ = initialize_placeholder_map(user_metadata, values)
        task = render_task_statement(task, placeholder_map)

    eval_config = {
        "_target_": get_import_path(Rome2RioInfoGathering),
        "queries": queries,
        "mode": mode,
    }
    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)