"""Pytest unit tests for TripAdvisor Things to Do info gathering."""

from navi_bench.tripadvisor.tripadvisor_info_gathering import (
    ThingsToDoInfoDict,
    TripAdvisorThingsToDoGathering,
)


def test_travelers_choice_curly_apostrophe_matches_and_is_not_extra():
    metric = TripAdvisorThingsToDoGathering(queries=[[
        {
            "cities": ["Chicago"],
            "navbar": ["Transportation"],
            "type_filters": ["Taxis & Shuttles"],
            "required_filters": ["Travelers' Choice"],
        }
    ]])

    info = ThingsToDoInfoDict(
        pageType="things_to_do_results",
        antiBotStatus="clear",
        citySlug="Chicago_Illinois",
        tierSelections={"navbar": "Transportation"},
        actionBarValues=["Transportation", "Taxis & Shuttles", "travelers’ choice"],
        activeFilters=["travelers’ choice"],
        selectedFiltersByGroup={
            "awards": ["travelers’ choice"],
            "typeLevel3": ["Taxis & Shuttles"],
        },
    )

    matches, misses = metric._diagnose_requested_fields(info)

    assert "Travelers' Choice" in matches
    assert "Travelers' Choice" not in misses
    assert "extra:travelers' choice" not in misses
