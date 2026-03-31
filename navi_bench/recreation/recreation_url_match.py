"""Recreation.gov URL match verifier for filtered search navigation."""

from datetime import datetime
from typing import TypedDict
from zoneinfo import ZoneInfo

from beartype import beartype
from loguru import logger
from pydantic import BaseModel

from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path


class InputDict(TypedDict, total=False):
    url: str


class FinalResult(BaseModel):
    score: float


IGNORED_LOCATION_PARAMS = {"lat", "lng", "radius", "start"}


def _normalize_url(url: str) -> str:
    """Ensure the URL is parseable even if the scheme is omitted."""
    cleaned = url.strip()
    if cleaned and not cleaned.startswith(("http://", "https://")):
        return f"https://{cleaned}"
    return cleaned


def _decode_query_component(value: str) -> str:
    """Decode a query-string component without urllib.parse."""
    decoded_bytes = bytearray()
    index = 0

    while index < len(value):
        char = value[index]
        if char == "+":
            decoded_bytes.append(32)
            index += 1
            continue

        if char == "%" and index + 2 < len(value):
            hex_part = value[index + 1:index + 3]
            if all(c in "0123456789abcdefABCDEF" for c in hex_part):
                decoded_bytes.append(int(hex_part, 16))
                index += 3
                continue

        decoded_bytes.extend(char.encode("utf-8"))
        index += 1

    return decoded_bytes.decode("utf-8", errors="replace")


def _parse_query_string(query: str) -> dict[str, list[str]]:
    """Parse a URL query string into a dict of key -> list of values."""
    query_params: dict[str, list[str]] = {}
    if not query:
        return query_params

    for pair in query.split("&"):
        if not pair:
            continue
        if "=" in pair:
            key, value = pair.split("=", 1)
        else:
            key, value = pair, ""

        decoded_key = _decode_query_component(key)
        decoded_value = _decode_query_component(value)
        query_params.setdefault(decoded_key, []).append(decoded_value)

    return query_params


def _split_url(url: str) -> tuple[str, str, dict[str, list[str]]]:
    """Return hostname, path, and parsed query params for a URL."""
    normalized_url = _normalize_url(url)
    url_without_scheme = normalized_url.split("://", 1)[-1]

    if "/" in url_without_scheme:
        hostname, remainder = url_without_scheme.split("/", 1)
        path_and_query = "/" + remainder
    else:
        hostname = url_without_scheme
        path_and_query = "/"

    path_and_query = path_and_query.split("#", 1)[0]
    if "?" in path_and_query:
        path, query = path_and_query.split("?", 1)
    else:
        path, query = path_and_query, ""

    return hostname.lower(), path, _parse_query_string(query)


def _normalize_goal_params(goal_params: dict) -> dict[str, list[str]]:
    """Normalize goal params so each key maps to a list of expected values."""
    normalized: dict[str, list[str]] = {}
    for key, value in goal_params.items():
        if value is None:
            continue
        if key in IGNORED_LOCATION_PARAMS:
            continue
        if isinstance(value, list):
            normalized[key] = [_decode_query_component(str(item)) for item in value]
        else:
            normalized[key] = [_decode_query_component(str(value))]
    return normalized


def verify_recreation_search(current_url: str, goal_params: dict) -> bool:
    """Return True when the URL matches recreation.gov search and required filters.

    Matching is order-independent because query parameters are compared by key/value
    membership rather than by raw query-string order. URL encoding is handled by
    ``parse_qs``, which decodes values like ``pet%20friendly`` to ``pet friendly``.
    """
    if not current_url:
        return False

    hostname, path, query_params = _split_url(current_url)
    if hostname != "www.recreation.gov":
        return False
    if path != "/search":
        return False

    normalized_goal_params = _normalize_goal_params(goal_params)

    for key, expected_values in normalized_goal_params.items():
        actual_values = query_params.get(key)
        if not actual_values:
            return False

        for expected_value in expected_values:
            if expected_value not in actual_values:
                return False

    return True


def _goal_params_from_gt_url(gt_url: str) -> dict[str, str | list[str]]:
    """Extract goal params from a ground-truth Recreation.gov search URL."""
    _, _, query_params = _split_url(gt_url)

    goal_params: dict[str, str | list[str]] = {}
    for key, values in query_params.items():
        if key in IGNORED_LOCATION_PARAMS:
            continue
        goal_params[key] = values[0] if len(values) == 1 else values
    return goal_params


@beartype
class RecreationUrlMatch(BaseMetric):
    """BaseMetric wrapper around ``verify_recreation_search``."""

    def __init__(self, goal_params: dict[str, str | list[str]]) -> None:
        super().__init__()
        self.goal_params = goal_params
        self._found_match = False
        self._last_url = ""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(goal_params={self.goal_params})"

    async def reset(self) -> None:
        self._found_match = False
        self._last_url = ""

    async def update(self, **kwargs) -> None:
        inputs: InputDict = kwargs
        url = inputs.get("url", "")
        if not url or self._found_match:
            return

        self._last_url = url
        self._found_match = verify_recreation_search(url, self.goal_params)
        logger.info(
            "RecreationUrlMatch.update: url='{}', matched={}",
            url,
            self._found_match,
        )

    async def compute(self) -> FinalResult:
        return FinalResult(score=1.0 if self._found_match else 0.0)


def generate_task_config(
    url: str,
    task: str,
    location: str,
    timezone: str,
    goal_params: dict[str, str | list[str]] | None = None,
    gt_url: str | None = None,
) -> BaseTaskConfig:
    """Generate a benchmark task config for Recreation.gov URL matching."""
    if goal_params is None:
        if gt_url is None:
            raise ValueError("Either 'goal_params' or 'gt_url' must be provided.")
        goal_params = _goal_params_from_gt_url(gt_url)

    tz_info = ZoneInfo(timezone)
    timestamp = int(datetime.now(tz_info).timestamp())
    user_metadata = UserMetadata(location=location, timezone=timezone, timestamp=timestamp)

    eval_target = get_import_path(RecreationUrlMatch)
    eval_config = {"_target_": eval_target, "goal_params": goal_params}

    return BaseTaskConfig(url=url, task=task, user_metadata=user_metadata, eval_config=eval_config)
