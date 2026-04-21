import re
from typing import Any, TypedDict
from urllib.parse import parse_qs, unquote, urlparse

from beartype import beartype
from loguru import logger
from pydantic import BaseModel
from datetime import datetime
from itertools import product

from navi_bench.base import BaseMetric, BaseTaskConfig, get_import_path
from navi_bench.dates import (
    initialize_placeholder_map,
    initialize_user_metadata,
    render_task_statement,
)

class InputDict(TypedDict, total=False):
    url: str


class FinalResult(BaseModel):
    score: float


class BookingVerifierResult(BaseModel):
    score: float
    match: bool
    agent_url: str = ""
    gt_url: str = ""
    details: dict = {}

# =====================================================================
# VERIFIER
# =====================================================================

@beartype
class BookingUrlMatch(BaseMetric):

    def __init__(self, gt_url: str | list[str]) -> None:
        super().__init__()

        if isinstance(gt_url, str):
            self.gt_urls = [gt_url]
        else:
            self.gt_urls = gt_url

        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details: dict = {}

    async def reset(self) -> None:
        self._found_match = False
        self._agent_url = ""
        self._matched_gt_url = ""
        self._match_details = {}

    async def update(self, **kwargs) -> None:
        inputs: InputDict = kwargs
        url = inputs.get("url", "")

        if not url:
            return

        parsed = urlparse(url.strip())
        domain = (parsed.hostname or "").lower()

        if not domain or not self._is_valid_booking_domain(domain):
            logger.debug(f"Ignoring non-Booking.com URL: {url}")
            return

        if self._found_match:
            return

        self._agent_url = url

        for gt_url in self.gt_urls:
            match, details = self._urls_match(url, gt_url)

            if match:
                self._found_match = True
                self._matched_gt_url = gt_url
                self._match_details = details
                return

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(gt_urls={self.gt_urls})"
    
    async def compute(self) -> FinalResult:
        return FinalResult(score=1.0 if self._found_match else 0.0)

    async def compute_detailed(self) -> BookingVerifierResult:
        return BookingVerifierResult(
            score=1.0 if self._found_match else 0.0,
            match=self._found_match,
            agent_url=self._agent_url,
            gt_url=self._matched_gt_url,
            details=self._match_details,
        )

    # =================================================================
    # DOMAIN CHECK
    # =================================================================

    @staticmethod
    def _is_valid_booking_domain(domain: str) -> bool:
        if not domain:
            return False
        domain = domain.lower()
        return domain == "booking.com" or domain.endswith(".booking.com")

    # =================================================================
    # MATCH LOGIC
    # =================================================================

    def _urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        parsed_gt = urlparse(gt_url)
        gt_path = (parsed_gt.path or "").lower()
        gt_host = (parsed_gt.hostname or "").lower()

        # Flights flow
        if "flights" in gt_path:
            return self._flights_urls_match(agent_url, gt_url)

        # Hotels flow
        if "searchresults" in gt_path:
            return self._hotel_urls_match(agent_url, gt_url)
        
        # Car-rental flow
        if gt_host.startswith("cars.booking.com"):
            return self._cars_urls_match(agent_url, gt_url)

        return False, {"mismatches": ["Unknown GT URL type"]}
    
    #****************HOTELS URL MATCH************************
    def _hotel_urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        details: dict[str, Any] = {"mismatches": []}

        try:
            agent = self._parse_hotel_url(agent_url)
            gt = self._parse_hotel_url(gt_url)

            # 1. Destination
            if gt["destination"]:
                if not agent["destination"]:
                    return False, {"mismatches": ["Destination missing"]}

                if agent["destination"] != gt["destination"]:
                    return False, {
                        "mismatches": [
                            f"destination: {agent['destination']} vs {gt['destination']}"
                        ]
                    }

            # 2. Dates
            for key in ("checkin", "checkout"):
                if gt[key]:
                    if not agent[key]:
                        return False, {"mismatches": [f"{key} missing"]}

                    if agent[key] != gt[key]:
                        return False, {
                            "mismatches": [f"{key}: {agent[key]} vs {gt[key]}"]
                        }

            # 3. Guests
            for key in ("adults", "children", "rooms"):
                if gt[key]:
                    if not agent[key]:
                        return False, {"mismatches": [f"{key} missing"]}

                    if agent[key] != gt[key]:
                        return False, {
                            "mismatches": [f"{key}: {agent[key]} vs {gt[key]}"]
                        }

            # 4. Ages
            if gt["ages"]:
                if not agent["ages"]:
                    return False, {"mismatches": ["ages missing"]}

                if sorted(agent["ages"]) != sorted(gt["ages"]):
                    return False, {
                        "mismatches": [f"ages: {agent['ages']} vs {gt['ages']}"]
                    }

            # 5. Price
            if gt["price_min"] is not None:
                if agent["price_min"] != gt["price_min"]:
                    return False, {"mismatches": ["price_min mismatch"]}

            if gt["price_max"] is not None:
                if agent["price_max"] != gt["price_max"]:
                    return False, {"mismatches": ["price_max mismatch"]}
            
            # 6. Sort Order
            if gt["order"]:
                if not agent["order"]:
                    return False, {"mismatches": ["order missing"]}

                if agent["order"] != gt["order"]:
                    return False, {
                        "mismatches": [f"order: {agent['order']} vs {gt['order']}"]
                    }

            # 7. Filters
            match, filter_details = self._compare_filters(
                agent["filters"], gt["filters"]
            )

            if not match:
                return False, filter_details

            return True, {}

        except Exception as e:
            logger.error(f"Error: {e}")
            return False, {"mismatches": [str(e)]}

    #****************FLIGHTS URL MATCH************************
    def _flights_urls_match(self, agent_url: str, gt_url: str)-> tuple[bool, dict]:
        agent = self._parse_flights_url(agent_url)
        gt = self._parse_flights_url(gt_url)

        mismatches = []

        # 1. Route
        if gt["origin"] and agent["origin"] != gt["origin"]:
            mismatches.append(f"origin: {agent['origin']} vs {gt['origin']}")

        if gt["destination"] and agent["destination"] != gt["destination"]:
            mismatches.append(f"destination: {agent['destination']} vs {gt['destination']}")

        # 2. Dates
        if gt["depart_date"] and agent["depart_date"] != gt["depart_date"]:
            mismatches.append("depart_date mismatch")

        if gt["return_date"] and agent["return_date"] != gt["return_date"]:
            mismatches.append("return_date mismatch")

        # 3. Trip type
        if gt["trip_type"] and agent["trip_type"] != gt["trip_type"]:
            mismatches.append("trip_type mismatch")

        # 4. Passengers
        if gt["adults"] and agent["adults"] != gt["adults"]:
            mismatches.append("adults mismatch")

        if gt["children"] and agent["children"] != gt["children"]:
            mismatches.append("children mismatch")

        # 5. Cabin class
        if gt["cabin_class"] and agent["cabin_class"] != gt["cabin_class"]:
            mismatches.append("cabin_class mismatch")

        # 6. Sorting 
        if gt["sort"] and agent["sort"] != gt["sort"]:
            mismatches.append("sort mismatch")

        # 7. Stops, Departure & Arrival time sidebar filters
        for f in ["stops", "depTimeInt", "arrTimeInt"]:
            if gt[f] and agent[f] != gt[f]:
                mismatches.append(f"{f} mismatch: {agent[f]} vs {gt[f]}")

        if mismatches:
            return False, {"mismatches": mismatches}

        return True, {}
    
    #****************CARS URL MATCH************************
    def _cars_urls_match(self, agent_url: str, gt_url: str) -> tuple[bool, dict]:
        agent = self._parse_cars_url(agent_url)
        gt = self._parse_cars_url(gt_url)

        mismatches = []

        for key in gt.keys():
            if gt[key] and agent[key] != gt[key]:
                mismatches.append(f"{key} mismatch: {agent[key]} vs {gt[key]}")

        if mismatches:
            return False, {"mismatches": mismatches}

        return True, {}

    # =================================================================
    # PARSING
    # =================================================================

    #************* STAYS URL PARSING*******************
    def _parse_hotel_url(self, url: str) -> dict:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        result = {
            "destination": "",
            "checkin": "",
            "checkout": "",
            "adults": "",
            "children": "",
            "ages": [],
            "rooms": "",
            "filters": {},
            "price_min": None,
            "price_max": None,
            "order": "",
        }

        # Destination 
        raw_dest = unquote(self._get_param(query, "ss")).lower()
        result["destination"] = raw_dest.split(",")[0].strip()

        # Dates
        result["checkin"] = self._get_param(query, "checkin")
        result["checkout"] = self._get_param(query, "checkout")

        # Guests
        result["adults"] = self._get_param(query, "group_adults")
        result["children"] = self._get_param(query, "group_children")
        result["rooms"] = self._get_param(query, "no_rooms")

        # Sort order
        result["order"] = self._get_param(query, "order")

        # Ages
        if "age" in query:
            result["ages"] = [a for a in query["age"] if a]

        # Filters 
        nflt = self._get_param(query, "nflt")        
        if nflt:
            nflt = unquote(nflt)

            result["filters"] = self._parse_nflt(nflt)

            price_min = None
            price_max = None

            range_match = re.search(r"price=[A-Z]+-(\d+)-(\d+)-\d+", nflt)
            if range_match:
                price_min = int(range_match.group(1))
                price_max = int(range_match.group(2))
            else:
                min_match = re.search(r"price=[A-Z]+-min-(\d+)-\d+", nflt)
                if min_match:
                    price_max = int(min_match.group(1))

                max_match = re.search(r"price=[A-Z]+-(\d+)-max-\d+", nflt)
                if max_match:
                    price_min = int(max_match.group(1))

            result["price_min"] = price_min
            result["price_max"] = price_max

        return result
    
    
    #************* FLIGHTS URL PARSING*******************
    def _parse_flights_url(self, url: str) -> dict:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        result = {
            "origin": "",
            "destination": "",
            "depart_date": "",
            "return_date": "",
            "trip_type": "",
            "adults": "",
            "children": "",
            "cabin_class": "",
            "sort": "",
            "stops": "",
            "depTimeInt": "",
            "arrTimeInt": "",
        }
        

        # Core route 
        result["origin"] = self._get_param(query, "from").lower()
        result["destination"] = self._get_param(query, "to").lower()

        # Dates
        result["depart_date"] = self._get_param(query, "depart")
        result["return_date"] = self._get_param(query, "return")

        # Trip type
        result["trip_type"] = self._get_param(query, "type")

        # Passengers
        result["adults"] = self._get_param(query, "adults")
        result["children"] = self._get_param(query, "children")

        # Cabin
        result["cabin_class"] = self._get_param(query, "cabinClass")

        # Sorting
        result["sort"] = self._get_param(query, "sort")

        # Stops Filter
        result["stops"] = self._get_param(query, "stops")

        # Departure-Arrival time 
        result["depTimeInt"] = self._get_param(query, "depTimeInt")
        result["arrTimeInt"] = self._get_param(query, "arrTimeInt")

        return result
    
    #************* CARS URL PARSING*******************
    def _parse_cars_url(self, url: str) -> dict:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        result = {
            "location_name": "",
            "drop_location_name": "",
            "pu_day": "",
            "pu_month": "",
            "pu_year": "",
            "pu_hour": "",
            "pu_minute": "",
            "do_day": "",
            "do_month": "",
            "do_year": "",
            "do_hour": "",
            "do_minute": "",
            "drivers_age": "",
            "filter_transmission": set(),
            "filter_supplier": set(),
            "filter_mileage": set(),
            "filter_car_category": set(),
            "filter_price_per_day": set(),
            "filter_seat_category": set(),
            "filter_minimum_supplier_rating": set(),
            "filter_has_air_conditioning": set(),
            "filter_provisional_extra": set(),
            "filter_sort_by": "",
            "filter_sort_ascending": "",
            "filter_fuel_type": set(),
            "filter_deposit_buckets": set(),
        }

        # Locations
        result["location_name"] = self._get_param(query, "locationName").lower()
        result["drop_location_name"] = self._get_param(query, "dropLocationName").lower()

        # Pick-up date & time
        result["pu_day"] = self._get_param(query, "puDay")
        result["pu_month"] = self._get_param(query, "puMonth")
        result["pu_year"] = self._get_param(query, "puYear")
        result["pu_hour"] = self._get_param(query, "puHour")
        result["pu_minute"] = self._get_param(query, "puMinute")

        # Drop-off date & time
        result["do_day"] = self._get_param(query, "doDay")
        result["do_month"] = self._get_param(query, "doMonth")
        result["do_year"] = self._get_param(query, "doYear")
        result["do_hour"] = self._get_param(query, "doHour")
        result["do_minute"] = self._get_param(query, "doMinute")

        # Driver & car type
        result["drivers_age"] = self._get_param(query, "driversAge")

        # Sidebar Filters
        result["filter_transmission"] = set(query.get("filterCriteria_transmission", []))
        result["filter_supplier"] = set(query.get("filterCriteria_supplier", []))
        result["filter_mileage"] = set(query.get("filterCriteria_mileage", []))
        result["filter_car_category"] = set(query.get("filterCriteria_carCategory", []))
        result["filter_price_per_day"] = set(query.get("filterCriteria_pricePerDayBuckets", []))
        result["filter_seat_category"] = set(query.get("filterCriteria_seatCategory", []))
        result["filter_minimum_supplier_rating"] = set(query.get("filterCriteria_minimumSupplierRating", []))
        result["filter_has_air_conditioning"] = set(query.get("filterCriteria_hasAirConditioning", []))
        result["filter_provisional_extra"] = set(query.get("filterCriteria_provisionalExtraType", []))
        result["filter_fuel_type"] = set(query.get("filterCriteria_fuelType", []))
        result["filter_deposit_buckets"] = set(query.get("filterCriteria_depositBuckets", []))
        result["filter_sort_by"] = self._get_param(query, "filterCriteria_sortBy")
        result["filter_sort_ascending"] = self._get_param(query, "filterCriteria_sortAscending")

        return result
    

    def _parse_nflt(self, raw: str) -> dict:
        filters = {}

        for item in raw.split(";"):
            if "=" not in item:
                continue

            key, value = item.split("=", 1)
            filters.setdefault(key, set()).add(value)

        return filters

    def _compare_filters(self, agent_filters, gt_filters):
        mismatches = []

        for key, gt_values in gt_filters.items():
            if key == "price":
                continue

            if key not in agent_filters:
                mismatches.append(f"Missing filter: {key}")
                continue

            agent_values = agent_filters[key]

            if not gt_values.issubset(agent_values):
                mismatches.append(
                    f"{key}: {agent_values} does not include {gt_values}"
                )

        return (False, {"mismatches": mismatches}) if mismatches else (True, {})

    @staticmethod
    def _get_param(query: dict, key: str) -> str:
        if key in query and query[key]:
            return query[key][0]
        return ""


# =====================================================================
# TASK CONFIG
# =====================================================================

def generate_task_config(
    task: str,
    location: str,
    timezone: str,
    gt_url: list[str] | None = None,
    ground_truth_url: str | None = None,
    timestamp: int | None = None,
    url: str = "https://www.booking.com",
    values: dict[str, str] | None = None,
) -> BaseTaskConfig:
    """Generate task configuration for Booking.com URL matching with multi-date + derived placeholder support."""

    # Resolve gt_url from either parameter
    if gt_url is None and ground_truth_url is not None:
        gt_url = [ground_truth_url]
    elif isinstance(gt_url, str):
        gt_url = [gt_url]
    elif gt_url is None:
        raise ValueError("Either 'gt_url' or 'ground_truth_url' must be provided.")

    values = values or {}
    user_metadata = initialize_user_metadata(timezone, location, timestamp)
    resolved_placeholders, _ = initialize_placeholder_map(user_metadata, values)

    rendered_task = render_task_statement(task, resolved_placeholders)

    # ----------------------------
    # Generate all GT URL combinations
    # ----------------------------
    all_gt_urls: list[str] = []

    for template in gt_url:
        placeholders_in_template = {
            k: dates
            for k, (_, dates) in resolved_placeholders.items()
            if any(token in template for token in [
                f"{{{k}}}",
                f"{{{k}Day}}",
                f"{{{k}Month}}",
                f"{{{k}Year}}",
            ])
        }

        if not placeholders_in_template:
            all_gt_urls.append(template)
            continue

        keys = list(placeholders_in_template.keys())
        date_lists = list(placeholders_in_template.values())

        for combination in product(*date_lists):
            rendered_u = template

            for k, v in zip(keys, combination):
                rendered_u = rendered_u.replace(f"{{{k}}}", v)

                try:
                    dt = datetime.strptime(v, "%Y-%m-%d")
                    replacements = {
                        f"{{{k}Day}}": str(dt.day),
                        f"{{{k}Month}}": str(dt.month),
                        f"{{{k}Year}}": str(dt.year),
                    }
                    for token, value in replacements.items():
                        if token in rendered_u:
                            rendered_u = rendered_u.replace(token, value)
                except Exception:
                    pass

            all_gt_urls.append(rendered_u)

    all_gt_urls = list(set(all_gt_urls))

    eval_target = get_import_path(BookingUrlMatch)
    eval_config = {"_target_": eval_target, "gt_url": all_gt_urls}

    # resolved_placeholders: dict[str, list[str]] | None = None

    return BaseTaskConfig(
        url=url,
        task=rendered_task,
        user_metadata=user_metadata,
        eval_config=eval_config,
        # resolved_placeholders=resolved_placeholders,
    )