"""TripAdvisor hotel URL helpers and lightweight URL verifier."""

import re
from typing import TypedDict
from urllib.parse import urlparse

from beartype import beartype
from pydantic import BaseModel

from navi_bench.base import BaseMetric


TRIPADVISOR_HOTEL_PATH_RE = re.compile(
    r"^/Hotels-(?P<geo_id>g\d+)-.*\.html$",
    re.IGNORECASE,
)


class InputDict(TypedDict, total=False):
    url: str


class FinalResult(BaseModel):
    score: float


class TripAdvisorUrlDetails(BaseModel):
    is_hotel_url: bool
    geographic_id: str | None = None
    normalized_url: str = ""


def is_tripadvisor_hotel_url(url: str) -> bool:
    """Return True when the URL points to a TripAdvisor hotel-results page."""
    parsed = urlparse(_normalize_url(url))
    host = (parsed.hostname or "").lower()
    if "tripadvisor.com" not in host:
        return False
    return bool(TRIPADVISOR_HOTEL_PATH_RE.match(parsed.path))


def extract_geographic_id(url: str) -> str | None:
    """Extract the TripAdvisor geographic ID such as ``g187791`` from the URL."""
    parsed = urlparse(_normalize_url(url))
    match = TRIPADVISOR_HOTEL_PATH_RE.match(parsed.path)
    return match.group("geo_id").lower() if match else None


def get_tripadvisor_url_details(url: str) -> TripAdvisorUrlDetails:
    normalized_url = _normalize_url(url)
    return TripAdvisorUrlDetails(
        is_hotel_url=is_tripadvisor_hotel_url(normalized_url),
        geographic_id=extract_geographic_id(normalized_url),
        normalized_url=normalized_url,
    )


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


@beartype
class TripAdvisorUrlMatch(BaseMetric):
    """Simple URL verifier for TripAdvisor hotel pages.

    A match succeeds when:
    - the visited URL is a TripAdvisor hotel-results page, and
    - its geographic ID matches the ground-truth geographic ID.
    """

    def __init__(self, gt_url: str) -> None:
        super().__init__()
        self.gt_url = gt_url
        self._matched = False

        gt_details = get_tripadvisor_url_details(gt_url)
        self._gt_geo_id = gt_details.geographic_id

    async def reset(self) -> None:
        self._matched = False

    async def update(self, **kwargs) -> None:
        inputs: InputDict = kwargs
        url = inputs.get("url", "")
        details = get_tripadvisor_url_details(url)
        if not details.is_hotel_url:
            return

        if self._gt_geo_id and details.geographic_id == self._gt_geo_id:
            self._matched = True

    async def compute(self) -> FinalResult:
        return FinalResult(score=1.0 if self._matched else 0.0)
