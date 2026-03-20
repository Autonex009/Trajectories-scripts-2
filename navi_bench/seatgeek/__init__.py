"""SeatGeek verifier module.

This module verifies AI agent ticket search results on SeatGeek by gathering 
event information through JavaScript scraping and matching against expected queries.
"""

from navi_bench.seatgeek.seatgeek_info_gathering import (
    SeatGeekInfoGathering,
    generate_task_config_deterministic,
    generate_task_config_random,
)

__all__ = [
    "SeatGeekInfoGathering",
    "generate_task_config_deterministic",
    "generate_task_config_random",
]
