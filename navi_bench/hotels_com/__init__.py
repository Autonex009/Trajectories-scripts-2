"""Hotels.com verifier module for hotel search and car rental navigation.

This module verifies AI agent navigation on Hotels.com by comparing
the agent's final URL against expected ground truth URLs (URL-based verifier).
Covers both hotel search (/Hotel-Search) and car rental (/carsearch) paths.
"""

from navi_bench.hotels_com.hotels_com_url_match import (
    HotelsComCarUrlMatch,
    HotelsComUrlMatch,
    generate_car_task_config,
    generate_task_config,
)

__all__ = [
    "HotelsComCarUrlMatch",
    "HotelsComUrlMatch",
    "generate_car_task_config",
    "generate_task_config",
]
