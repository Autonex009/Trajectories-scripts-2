"""Comprehensive test suite for Facebook Marketplace URL verifier.

Tests cover:
- URL parsing (path segments, query parameters)
- Query text normalization (case, whitespace, URL-encoding)
- Price range matching (min-only, max-only, both, missing)
- Item condition normalization and matching
- Sort order normalization and matching
- Category slug/ID matching
- City slug extraction and matching
- Vehicle filters (year, mileage, make, model, type)
- Property filters (bedrooms, bathrooms, property type)
- Full URL matching integration (all field mismatches)
- Domain validation (facebook.com, m.facebook.com, rejection)
- Async lifecycle (reset/update/compute)
- Multi-GT URL OR semantics
- Edge cases (empty, non-marketplace, login redirects)
"""

import asyncio
import pytest

from navi_bench.fb_marketplace.fb_marketplace_url_match import (
    FbMarketplaceUrlMatch,
    _extract_category_slug,
    _extract_city_slug,
    _normalize_condition,
    _normalize_delivery,
    _normalize_property_type,
    _normalize_query_text,
    _normalize_sort_order,
    _normalize_vehicle_type,
    parse_marketplace_url,
)


# =============================================================================
# 1. URL Parsing
# =============================================================================


class TestUrlParsing:
    """Tests for parse_marketplace_url()."""

    def test_full_search_url_basic(self):
        url = (
            "https://www.facebook.com/marketplace/sanfrancisco/search/"
            "?query=iphone+15&minPrice=100&maxPrice=500"
        )
        parsed = parse_marketplace_url(url)
        assert parsed["city_slug"] == "sanfrancisco"
        assert parsed["query"] == "iphone 15"
        assert parsed["min_price"] == 100
        assert parsed["max_price"] == 500

    def test_full_search_url_all_filters(self):
        url = (
            "https://www.facebook.com/marketplace/newyork/search/"
            "?query=sofa&minPrice=50&maxPrice=800"
            "&sortBy=creation_time_descend&daysSinceListed=7"
            "&itemCondition=used_good&deliveryMethod=local_pick_up"
            "&exact=true"
        )
        parsed = parse_marketplace_url(url)
        assert parsed["city_slug"] == "newyork"
        assert parsed["query"] == "sofa"
        assert parsed["min_price"] == 50
        assert parsed["max_price"] == 800
        assert parsed["sort_by"] == "creation_time_descend"
        assert parsed["days_since_listed"] == 7
        assert parsed["item_condition"] == "used_good"
        assert parsed["delivery_method"] == "local_pick_up"
        assert parsed["exact"] is True

    def test_category_url(self):
        url = "https://www.facebook.com/marketplace/category/vehicles/"
        parsed = parse_marketplace_url(url)
        assert parsed["category_slug"] == "vehicles"
        assert parsed["city_slug"] == ""

    def test_search_without_city(self):
        url = "https://www.facebook.com/marketplace/search/?query=laptop"
        parsed = parse_marketplace_url(url)
        assert parsed["city_slug"] == ""
        assert parsed["query"] == "laptop"

    def test_missing_all_params(self):
        url = "https://www.facebook.com/marketplace/"
        parsed = parse_marketplace_url(url)
        assert parsed["query"] == ""
        assert parsed["min_price"] is None
        assert parsed["max_price"] is None
        assert parsed["sort_by"] == ""
        assert parsed["item_condition"] == ""

    def test_vehicle_params(self):
        url = (
            "https://www.facebook.com/marketplace/chicago/search/"
            "?query=toyota+camry&minYear=2018&maxYear=2023"
            "&minMileage=0&maxMileage=50000"
            "&topLevelVehicleType=car_truck&make=toyota&model=camry"
        )
        parsed = parse_marketplace_url(url)
        assert parsed["min_year"] == 2018
        assert parsed["max_year"] == 2023
        assert parsed["min_mileage"] == 0
        assert parsed["max_mileage"] == 50000
        assert parsed["vehicle_type"] == "car_truck"
        assert parsed["make"] == "toyota"
        assert parsed["model"] == "camry"

    def test_property_params(self):
        url = (
            "https://www.facebook.com/marketplace/boston/search/"
            "?minPrice=1000&maxPrice=3000"
            "&minBedrooms=2&maxBedrooms=4&minBathrooms=1"
            "&propertyType=apartment"
        )
        parsed = parse_marketplace_url(url)
        assert parsed["min_bedrooms"] == 2
        assert parsed["max_bedrooms"] == 4
        assert parsed["min_bathrooms"] == 1
        assert parsed["property_type"] == "apartment"

    def test_url_encoded_query(self):
        url = (
            "https://www.facebook.com/marketplace/search/"
            "?query=macbook%20pro%2016%20inch"
        )
        parsed = parse_marketplace_url(url)
        assert parsed["query"] == "macbook pro 16 inch"


# =============================================================================
# 2. Query Text Normalization
# =============================================================================


class TestQueryNormalization:
    """Tests for _normalize_query_text()."""

    def test_lowercase(self):
        assert _normalize_query_text("iPhone 15 Pro") == "iphone 15 pro"

    def test_whitespace_collapse(self):
        assert _normalize_query_text("  iphone   15   pro  ") == "iphone 15 pro"

    def test_url_decode(self):
        assert _normalize_query_text("macbook%20pro") == "macbook pro"

    def test_plus_decoding(self):
        # URL form-encoded plus signs aren't decoded by unquote alone
        # but our parser handles them via parse_qs
        assert _normalize_query_text("iphone+15") == "iphone+15"

    def test_empty(self):
        assert _normalize_query_text("") == ""

    def test_special_characters(self):
        assert _normalize_query_text("32\" Monitor") == '32" monitor'


# =============================================================================
# 3. Price Range Matching
# =============================================================================


class TestPriceRange:
    """Tests for price range field matching."""

    def test_both_prices_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100&maxPrice=500"
        agent = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100&maxPrice=500"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_min_price_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100&maxPrice=500"
        agent = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=200&maxPrice=500"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Min price" in details["mismatches"][0]

    def test_max_price_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100&maxPrice=500"
        agent = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100&maxPrice=800"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Max price" in details["mismatches"][0]

    def test_missing_min_price_when_required(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100"
        agent = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "missing" in details["mismatches"][0].lower()

    def test_min_only(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50"
        agent = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_max_only(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&maxPrice=300"
        agent = "https://www.facebook.com/marketplace/search/?query=desk&maxPrice=300"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True


# =============================================================================
# 4. Item Condition Matching
# =============================================================================


class TestConditionMatching:
    """Tests for _normalize_condition() and condition field matching."""

    def test_new(self):
        assert _normalize_condition("new") == "new"

    def test_used_like_new(self):
        assert _normalize_condition("used_like_new") == "used_like_new"

    def test_used_good(self):
        assert _normalize_condition("used_good") == "used_good"

    def test_used_fair(self):
        assert _normalize_condition("used_fair") == "used_fair"

    def test_alias_like_new(self):
        assert _normalize_condition("like_new") == "used_like_new"

    def test_condition_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=phone&itemCondition=new"
        agent = "https://www.facebook.com/marketplace/search/?query=phone&itemCondition=used_good"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Condition" in details["mismatches"][0]

    def test_condition_missing_when_required(self):
        gt = "https://www.facebook.com/marketplace/search/?query=phone&itemCondition=new"
        agent = "https://www.facebook.com/marketplace/search/?query=phone"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "missing" in details["mismatches"][0].lower()


# =============================================================================
# 5. Sort Order Matching
# =============================================================================


class TestSortMatching:
    """Tests for _normalize_sort_order() and sort field matching."""

    def test_creation_time_descend(self):
        assert _normalize_sort_order("creation_time_descend") == "creation_time_descend"

    def test_alias_newest(self):
        assert _normalize_sort_order("newest") == "creation_time_descend"

    def test_price_ascend(self):
        assert _normalize_sort_order("price_ascend") == "price_ascend"

    def test_price_descend(self):
        assert _normalize_sort_order("price_descend") == "price_descend"

    def test_best_match(self):
        assert _normalize_sort_order("best_match") == "best_match"

    def test_sort_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=chair&sortBy=price_ascend"
        agent = "https://www.facebook.com/marketplace/search/?query=chair&sortBy=price_descend"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Sort order" in details["mismatches"][0]


# =============================================================================
# 6. Category Matching
# =============================================================================


class TestCategoryMatching:
    """Tests for category slug and category_id matching."""

    def test_category_slug_vehicles(self):
        assert _extract_category_slug("/marketplace/category/vehicles/") == "vehicles"

    def test_category_slug_electronics(self):
        assert _extract_category_slug("/marketplace/category/electronics/") == "electronics"

    def test_category_slug_propertyrentals(self):
        assert _extract_category_slug("/marketplace/category/propertyrentals/") == "propertyrentals"

    def test_no_category_in_search(self):
        assert _extract_category_slug("/marketplace/sanfrancisco/search/") == ""

    def test_category_slug_match(self):
        gt = "https://www.facebook.com/marketplace/category/vehicles/"
        agent = "https://www.facebook.com/marketplace/category/vehicles/"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_category_slug_mismatch(self):
        gt = "https://www.facebook.com/marketplace/category/vehicles/"
        agent = "https://www.facebook.com/marketplace/category/electronics/"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Category slug" in details["mismatches"][0]


# =============================================================================
# 7. City Slug Matching
# =============================================================================


class TestCitySlugMatching:
    """Tests for _extract_city_slug() and city slug matching."""

    def test_city_slug_san_francisco(self):
        assert _extract_city_slug("/marketplace/sanfrancisco/search/") == "sanfrancisco"

    def test_city_slug_new_york(self):
        assert _extract_city_slug("/marketplace/newyork/search/") == "newyork"

    def test_no_city_homepage(self):
        assert _extract_city_slug("/marketplace/") == ""

    def test_no_city_category(self):
        assert _extract_city_slug("/marketplace/category/electronics/") == ""

    def test_no_city_item(self):
        assert _extract_city_slug("/marketplace/item/1234567890/") == ""

    def test_numeric_location_id(self):
        result = _extract_city_slug("/marketplace/112345678/search/")
        assert result == "112345678"

    def test_city_match(self):
        gt = "https://www.facebook.com/marketplace/chicago/search/?query=couch"
        agent = "https://www.facebook.com/marketplace/chicago/search/?query=couch"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_city_mismatch(self):
        gt = "https://www.facebook.com/marketplace/chicago/search/?query=couch"
        agent = "https://www.facebook.com/marketplace/losangeles/search/?query=couch"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "City slug" in details["mismatches"][0]

    def test_city_case_insensitive(self):
        gt = "https://www.facebook.com/marketplace/SanFrancisco/search/?query=test"
        agent = "https://www.facebook.com/marketplace/sanfrancisco/search/?query=test"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True


# =============================================================================
# 8. Vehicle Filter Matching
# =============================================================================


class TestVehicleFilters:
    """Tests for vehicle-specific filter matching."""

    def test_year_range_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=car&minYear=2018&maxYear=2023"
        agent = "https://www.facebook.com/marketplace/search/?query=car&minYear=2018&maxYear=2023"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_year_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=car&minYear=2018"
        agent = "https://www.facebook.com/marketplace/search/?query=car&minYear=2020"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Min year" in details["mismatches"][0]

    def test_mileage_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=car&maxMileage=50000"
        agent = "https://www.facebook.com/marketplace/search/?query=car&maxMileage=50000"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_mileage_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=car&maxMileage=50000"
        agent = "https://www.facebook.com/marketplace/search/?query=car&maxMileage=100000"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False

    def test_vehicle_type_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=truck&topLevelVehicleType=car_truck"
        agent = "https://www.facebook.com/marketplace/search/?query=truck&topLevelVehicleType=car_truck"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_vehicle_type_normalization(self):
        assert _normalize_vehicle_type("car") == "car_truck"
        assert _normalize_vehicle_type("motorcycle") == "motorcycle"
        assert _normalize_vehicle_type("rv") == "rv_camper"

    def test_make_model_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=honda+civic&make=honda&model=civic"
        agent = "https://www.facebook.com/marketplace/search/?query=honda+civic&make=honda&model=civic"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_make_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=car&make=honda"
        agent = "https://www.facebook.com/marketplace/search/?query=car&make=toyota"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Make" in details["mismatches"][0]


# =============================================================================
# 9. Property Filter Matching
# =============================================================================


class TestPropertyFilters:
    """Tests for property-specific filter matching."""

    def test_bedrooms_match(self):
        gt = "https://www.facebook.com/marketplace/search/?minBedrooms=2&maxBedrooms=4"
        agent = "https://www.facebook.com/marketplace/search/?minBedrooms=2&maxBedrooms=4"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_bedrooms_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?minBedrooms=2"
        agent = "https://www.facebook.com/marketplace/search/?minBedrooms=3"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "bedrooms" in details["mismatches"][0].lower()

    def test_bathrooms_match(self):
        gt = "https://www.facebook.com/marketplace/search/?minBathrooms=2"
        agent = "https://www.facebook.com/marketplace/search/?minBathrooms=2"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_property_type_match(self):
        gt = "https://www.facebook.com/marketplace/search/?propertyType=apartment"
        agent = "https://www.facebook.com/marketplace/search/?propertyType=apartment"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_property_type_normalization(self):
        assert _normalize_property_type("house") == "house"
        assert _normalize_property_type("apartment") == "apartment"
        assert _normalize_property_type("condo") == "condo"
        assert _normalize_property_type("townhouse") == "townhouse"

    def test_property_type_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?propertyType=house"
        agent = "https://www.facebook.com/marketplace/search/?propertyType=apartment"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Property type" in details["mismatches"][0]


# =============================================================================
# 10. Full URL Matching Integration
# =============================================================================


class TestUrlMatchingIntegration:
    """Integration tests: full URL matching with all field combinations."""

    def test_identical_urls(self):
        url = (
            "https://www.facebook.com/marketplace/sanfrancisco/search/"
            "?query=desk&minPrice=50&maxPrice=300"
            "&sortBy=price_ascend&itemCondition=used_good"
        )
        v = FbMarketplaceUrlMatch(gt_url=url)
        match, _ = v._urls_match(url, url)
        assert match is True

    def test_query_case_insensitive_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=iPhone+15+Pro"
        agent = "https://www.facebook.com/marketplace/search/?query=iphone+15+pro"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_query_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=iphone+15"
        agent = "https://www.facebook.com/marketplace/search/?query=samsung+galaxy"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "Query" in details["mismatches"][0]

    def test_query_missing_when_required(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        agent = "https://www.facebook.com/marketplace/search/"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False
        assert "missing" in details["mismatches"][0].lower()

    def test_extra_agent_params_ignored(self):
        """Agent has extra filters not in GT — should still match."""
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        agent = (
            "https://www.facebook.com/marketplace/search/"
            "?query=desk&sortBy=price_ascend&daysSinceListed=7"
        )
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_tracking_params_ignored(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50"
        agent = (
            "https://www.facebook.com/marketplace/search/"
            "?query=desk&minPrice=50&ref=bookmark&fbclid=abc123"
        )
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_days_since_listed_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=bike&daysSinceListed=1"
        agent = "https://www.facebook.com/marketplace/search/?query=bike&daysSinceListed=1"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_days_since_listed_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=bike&daysSinceListed=1"
        agent = "https://www.facebook.com/marketplace/search/?query=bike&daysSinceListed=7"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False

    def test_delivery_method_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=shoe&deliveryMethod=local_pick_up"
        agent = "https://www.facebook.com/marketplace/search/?query=shoe&deliveryMethod=local_pick_up"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_exact_flag_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=macbook&exact=true"
        agent = "https://www.facebook.com/marketplace/search/?query=macbook&exact=true"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True

    def test_exact_flag_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=macbook&exact=true"
        agent = "https://www.facebook.com/marketplace/search/?query=macbook&exact=false"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, details = v._urls_match(agent, gt)
        assert match is False

    def test_combined_vehicle_filters(self):
        gt = (
            "https://www.facebook.com/marketplace/dallas/search/"
            "?query=ford+f150&minYear=2018&maxYear=2023"
            "&maxMileage=80000&topLevelVehicleType=car_truck"
            "&make=ford&model=f150&minPrice=15000&maxPrice=35000"
        )
        agent = (
            "https://www.facebook.com/marketplace/dallas/search/"
            "?query=ford+f150&minYear=2018&maxYear=2023"
            "&maxMileage=80000&topLevelVehicleType=car_truck"
            "&make=ford&model=f150&minPrice=15000&maxPrice=35000"
        )
        v = FbMarketplaceUrlMatch(gt_url=gt)
        match, _ = v._urls_match(agent, gt)
        assert match is True


# =============================================================================
# 11. Domain Validation
# =============================================================================


class TestDomainValidation:
    """Tests for _is_valid_marketplace_domain()."""

    def test_www_facebook(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("www.facebook.com") is True

    def test_facebook(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("facebook.com") is True

    def test_mobile_facebook(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("m.facebook.com") is True

    def test_web_facebook(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("web.facebook.com") is True

    def test_subdomain_facebook(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("xx.facebook.com") is True

    def test_reject_non_facebook(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("google.com") is False

    def test_reject_similar_domain(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("fakefacebook.com") is False

    def test_reject_instagram(self):
        assert FbMarketplaceUrlMatch._is_valid_marketplace_domain("instagram.com") is False


# =============================================================================
# 12. Async Lifecycle
# =============================================================================


class TestAsyncLifecycle:
    """Tests for async reset / update / compute cycle."""

    @pytest.mark.asyncio
    async def test_match_lifecycle(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.reset()
        await v.update(url=gt)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_no_match_lifecycle(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50"
        agent = "https://www.facebook.com/marketplace/search/?query=chair&minPrice=50"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.reset()
        await v.update(url=agent)
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_reset_clears_match(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url=gt)
        result1 = await v.compute()
        assert result1.score == 1.0

        await v.reset()
        result2 = await v.compute()
        assert result2.score == 0.0

    @pytest.mark.asyncio
    async def test_match_persists_across_updates(self):
        """Once matched, subsequent non-matching URLs don't overwrite."""
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url=gt)
        await v.update(url="https://www.facebook.com/marketplace/search/?query=chair")
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_empty_url_ignored(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url="")
        result = await v.compute()
        assert result.score == 0.0


# =============================================================================
# 13. Multi-GT URL OR Semantics
# =============================================================================


class TestMultiGtUrls:
    """Tests for multi-GT URL OR semantics."""

    @pytest.mark.asyncio
    async def test_match_first_gt(self):
        gt_urls = [
            "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50",
            "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100",
        ]
        v = FbMarketplaceUrlMatch(gt_url=gt_urls)
        await v.update(url=gt_urls[0])
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_match_second_gt(self):
        gt_urls = [
            "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50",
            "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100",
        ]
        v = FbMarketplaceUrlMatch(gt_url=gt_urls)
        await v.update(url=gt_urls[1])
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_match_none_gt(self):
        gt_urls = [
            "https://www.facebook.com/marketplace/search/?query=desk&minPrice=50",
            "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100",
        ]
        v = FbMarketplaceUrlMatch(gt_url=gt_urls)
        await v.update(
            url="https://www.facebook.com/marketplace/search/?query=chair"
        )
        result = await v.compute()
        assert result.score == 0.0


# =============================================================================
# 14. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases & unusual inputs."""

    @pytest.mark.asyncio
    async def test_non_marketplace_facebook_url(self):
        """Non-marketplace Facebook URL should be ignored."""
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url="https://www.facebook.com/profile/12345")
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_non_facebook_url_ignored(self):
        """Non-Facebook URL should be ignored entirely."""
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url="https://www.google.com/search?q=desk")
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_listing_page_url(self):
        """Item listing page should not match a search GT."""
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(
            url="https://www.facebook.com/marketplace/item/1234567890/"
        )
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_mobile_domain_match(self):
        """m.facebook.com should be treated as valid."""
        gt = "https://www.facebook.com/marketplace/search/?query=desk"
        agent = "https://m.facebook.com/marketplace/search/?query=desk"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url=agent)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_detailed_result_on_mismatch(self):
        gt = "https://www.facebook.com/marketplace/search/?query=desk&minPrice=100"
        agent = "https://www.facebook.com/marketplace/search/?query=chair&minPrice=200"
        v = FbMarketplaceUrlMatch(gt_url=gt)
        await v.update(url=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0
        assert result.match is False
        assert result.agent_url == agent
        assert result.gt_url == ""  # No match found, so gt_url stays empty

    def test_repr(self):
        v = FbMarketplaceUrlMatch(gt_url="https://example.com")
        assert "FbMarketplaceUrlMatch" in repr(v)


# =============================================================================
# 15. Normalization Helpers
# =============================================================================


class TestNormalizationHelpers:
    """Tests for normalization helper functions."""

    def test_delivery_local_pickup(self):
        assert _normalize_delivery("local_pick_up") == "local_pick_up"
        assert _normalize_delivery("pickup") == "local_pick_up"

    def test_delivery_shipping(self):
        assert _normalize_delivery("shipping") == "shipping"
        assert _normalize_delivery("shipped") == "shipping"

    def test_delivery_empty(self):
        assert _normalize_delivery("") == ""

    def test_sort_distance(self):
        assert _normalize_sort_order("distance_ascend") == "distance_ascend"
        assert _normalize_sort_order("nearest") == "distance_ascend"

    def test_condition_generic_used(self):
        assert _normalize_condition("used") == "used_good"

    def test_condition_empty(self):
        assert _normalize_condition("") == ""
