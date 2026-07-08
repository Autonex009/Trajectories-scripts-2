"""
Pytest unit tests for IRS Tax Withholding Estimator verifier - no browser required.

Tests cover:
- Verifier initialization, reset, compute
- Field comparison logic (currency, boolean, enum, date, integer, string)
- Lenient zero/empty handling (extra fields with 0/false/null tolerated)
- Array field comparison (jobs, pensions, self_employment, ssi)
- Normalization helpers (_normalize_string, _normalize_date, _normalize_currency)
- Wrong field detection
- Missing field detection
- Task config generation (generate_task_config)
- CSV benchmark file parsing and instantiation
- JS extraction script loading
- Edge cases (JSON string input, empty queries, no queries)
"""

import csv
import json
import pytest
from pathlib import Path

from navi_bench.irs_tax_estimator.irs_tax_estimator_verifier import (
    IrsTweQueryMatch,
    IrsTweVerifierResult,
    FinalResult,
    generate_task_config,
    ARRAY_FIELDS,
    BOOLEAN_FIELDS,
    CURRENCY_FIELDS,
    DATE_FIELDS,
    ENUM_FIELDS,
    INTEGER_FIELDS,
    EMPTY_VALUES,
    _normalize_string,
    _normalize_date,
    _normalize_number,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def simple_gt():
    """Simple single filer ground truth."""
    return [{
        "filing_status": "single",
        "user_age_65_or_older": False,
        "is_blind": False,
        "claimed_as_dependent": False,
        "plan_to_claim_dependents": False,
        "jobs": [{
            "job_type": "salary",
            "job_duration": "all_year",
            "pay_frequency": "biweekly",
            "recent_pay_period_end": "06/20/2026",
            "recent_pay_date": "06/25/2026",
            "gross_per_period": 3200,
            "ytd_gross": 41600,
            "fed_withholding_period": 384,
            "fed_withholding_ytd": 4992,
            "received_bonus": False,
            "retirement_401k_period": 200,
            "retirement_401k_ytd": 2600,
        }],
        "deduction_type": "standard",
    }]


@pytest.fixture
def mfj_gt():
    """Married filing jointly ground truth with dual income."""
    return [{
        "filing_status": "married_filing_jointly",
        "user_age_65_or_older": False,
        "is_blind": False,
        "plan_to_claim_dependents": True,
        "claimed_as_dependent": False,
        "spouse_age_65_or_older": False,
        "spouse_is_blind": False,
        "jobs": [
            {
                "person": "myself",
                "job_type": "salary",
                "job_duration": "all_year",
                "pay_frequency": "biweekly",
                "recent_pay_period_end": "03/08/2026",
                "recent_pay_date": "03/14/2026",
                "gross_per_period": 5385,
                "ytd_gross": 32310,
                "fed_withholding_period": 612,
                "fed_withholding_ytd": 3672,
                "received_bonus": False,
                "retirement_401k_period": 750,
                "health_insurance_period": 320,
                "hsa_period": 125,
                "pre_tax_period": 45,
            },
            {
                "person": "spouse",
                "job_type": "salary",
                "job_duration": "all_year",
                "pay_frequency": "biweekly",
                "recent_pay_period_end": "03/08/2026",
                "recent_pay_date": "03/14/2026",
                "gross_per_period": 1538,
                "ytd_gross": 9228,
                "fed_withholding_period": 108,
                "fed_withholding_ytd": 648,
                "annual_overtime_income": 3600,
                "overtime_rate": "1.5x",
                "received_bonus": False,
            },
        ],
        "interest": 1850,
        "qualified_dividends": 2200,
        "ordinary_dividends": 2200,
        "student_loan_interest": 1200,
        "deduction_type": "itemized",
        "salt": 10000,
        "charity_gifts": 3800,
        "mortgage_interest": 14200,
        "car_loan_interest": 1900,
        "number_of_children": 2,
        "cdcc_number_of_children": 1,
        "cdcc_annual_care_expenses": 8400,
    }]


@pytest.fixture
def simple_verifier(simple_gt):
    """Create verifier with simple ground truth."""
    return IrsTweQueryMatch(gt_queries=simple_gt)


@pytest.fixture
def mfj_verifier(mfj_gt):
    """Create verifier with MFJ ground truth."""
    return IrsTweQueryMatch(gt_queries=mfj_gt)


# =============================================================================
# 1. VERIFIER INITIALIZATION
# =============================================================================


class TestVerifierInitialization:

    def test_init_stores_queries(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        assert v.gt_queries == simple_gt
        assert v._agent_queries is None
        assert v._result is None

    def test_init_empty_queries(self):
        v = IrsTweQueryMatch(gt_queries=[{}])
        assert len(v.gt_queries) == 1

    def test_repr(self, simple_verifier):
        r = repr(simple_verifier)
        assert "IrsTweQueryMatch" in r
        assert "1 entries" in r


# =============================================================================
# 2. ASYNC LIFECYCLE
# =============================================================================


class TestAsyncLifecycle:

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, simple_verifier):
        await simple_verifier.update(queries=[{"filing_status": "single"}])
        assert simple_verifier._agent_queries is not None

        await simple_verifier.reset()
        assert simple_verifier._agent_queries is None
        assert simple_verifier._result is None

    @pytest.mark.asyncio
    async def test_compute_no_agent_data(self, simple_verifier):
        """Compute returns 0 when no agent data received."""
        result = await simple_verifier.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_compute_detailed_no_agent_data(self, simple_verifier):
        result = await simple_verifier.compute_detailed()
        assert isinstance(result, IrsTweVerifierResult)
        assert result.score == 0.0
        assert result.match is False
        assert "No agent queries" in result.details

    @pytest.mark.asyncio
    async def test_update_compute_match(self, simple_verifier, simple_gt):
        await simple_verifier.update(queries=simple_gt)
        result = await simple_verifier.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_update_compute_detailed_match(self, simple_verifier, simple_gt):
        await simple_verifier.update(queries=simple_gt)
        result = await simple_verifier.compute_detailed()
        assert result.score == 1.0
        assert result.match is True
        assert result.field_results["wrong_count"] == 0
        assert result.field_results["missing_count"] == 0

    @pytest.mark.asyncio
    async def test_reset_then_compute(self, simple_verifier, simple_gt):
        await simple_verifier.update(queries=simple_gt)
        await simple_verifier.reset()
        result = await simple_verifier.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_double_update_uses_latest(self, simple_verifier, simple_gt):
        """Second update should replace the first."""
        await simple_verifier.update(queries=[{"filing_status": "head_of_household"}])
        await simple_verifier.update(queries=simple_gt)
        result = await simple_verifier.compute()
        assert result.score == 1.0


# =============================================================================
# 3. NORMALIZATION HELPERS
# =============================================================================


class TestNormalizationHelpers:

    def test_normalize_string_basic(self):
        assert _normalize_string("Married Filing Jointly") == "married_filing_jointly"

    def test_normalize_string_with_hyphens(self):
        assert _normalize_string("head-of-household") == "head_of_household"

    def test_normalize_string_strips_whitespace(self):
        assert _normalize_string("  single  ") == "single"

    def test_normalize_string_non_string(self):
        assert _normalize_string(42) == "42"
        assert _normalize_string(True) == "true"

    def test_normalize_date_mm_dd_yyyy(self):
        assert _normalize_date("06/20/2026") == "06/20/2026"

    def test_normalize_date_yyyy_mm_dd(self):
        assert _normalize_date("2026-06-20") == "06/20/2026"

    def test_normalize_date_single_digit(self):
        assert _normalize_date("6/1/2026") == "06/01/2026"

    def test_normalize_date_passthrough(self):
        """Non-date strings returned as-is."""
        assert _normalize_date("all_year") == "all_year"

    def test_normalize_currency_int(self):
        assert _normalize_number(5385) == 5385.0

    def test_normalize_currency_float(self):
        assert _normalize_number(5385.50) == 5385.50

    def test_normalize_currency_string(self):
        assert _normalize_number("5385") == 5385.0

    def test_normalize_currency_string_with_commas(self):
        result = _normalize_number("1234567")
        assert result == 1234567.0

    def test_normalize_currency_zero(self):
        assert _normalize_number(0) == 0.0
        assert _normalize_number("0") == 0.0


# =============================================================================
# 4. PERFECT MATCH (SCORE = 1.0)
# =============================================================================


class TestPerfectMatch:

    @pytest.mark.asyncio
    async def test_simple_single_filer(self, simple_verifier, simple_gt):
        await simple_verifier.update(queries=simple_gt)
        result = await simple_verifier.compute_detailed()
        assert result.score == 1.0
        assert result.match is True

    @pytest.mark.asyncio
    async def test_mfj_dual_income(self, mfj_verifier, mfj_gt):
        await mfj_verifier.update(queries=mfj_gt)
        result = await mfj_verifier.compute_detailed()
        assert result.score == 1.0
        assert result.match is True


# =============================================================================
# 5. LENIENT ZERO/EMPTY HANDLING
# =============================================================================


class TestLenientEmptyHandling:

    @pytest.mark.asyncio
    async def test_extra_zero_fields_pass(self, simple_verifier, simple_gt):
        """Agent adds fields with value 0 — should still pass."""
        agent = [dict(simple_gt[0])]
        agent[0]["alimony_paid"] = 0
        agent[0]["foreign_tax_credit"] = 0
        agent[0]["moving_expenses"] = 0

        await simple_verifier.update(queries=agent)
        result = await simple_verifier.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_extra_false_fields_pass(self, simple_verifier, simple_gt):
        """Agent adds fields with value False — should still pass."""
        agent = [dict(simple_gt[0])]
        agent[0]["withhold_federal_tax"] = False

        await simple_verifier.update(queries=agent)
        result = await simple_verifier.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_extra_empty_string_pass(self, simple_verifier, simple_gt):
        """Agent adds fields with value '' — should still pass."""
        agent = [dict(simple_gt[0])]
        agent[0]["pension_paid_to"] = ""

        await simple_verifier.update(queries=agent)
        result = await simple_verifier.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_extra_null_field_pass(self, simple_verifier, simple_gt):
        """Agent adds fields with value None — should still pass."""
        agent = [dict(simple_gt[0])]
        agent[0]["qbi_deduction"] = None

        await simple_verifier.update(queries=agent)
        result = await simple_verifier.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_extra_nonzero_field_fails(self, simple_verifier, simple_gt):
        """Agent adds field with non-zero value NOT in GT — should fail."""
        agent = [dict(simple_gt[0])]
        agent[0]["interest"] = 5000  # not in simple_gt, and non-zero

        await simple_verifier.update(queries=agent)
        result = await simple_verifier.compute_detailed()
        # Extra non-zero fields should cause failure
        assert result.score == 0.0
        assert len(result.extra_fields) > 0


# =============================================================================
# 6. WRONG FIELD DETECTION
# =============================================================================


class TestWrongFieldDetection:

    @pytest.mark.asyncio
    async def test_wrong_filing_status(self, simple_verifier, simple_gt):
        agent = [dict(simple_gt[0])]
        agent[0]["filing_status"] = "head_of_household"

        await simple_verifier.update(queries=agent)
        result = await simple_verifier.compute_detailed()
        assert result.score == 0.0
        assert result.match is False
        assert any("filing_status" in w for w in result.wrong_fields)

    @pytest.mark.asyncio
    async def test_wrong_currency_value(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        agent = [dict(simple_gt[0])]
        agent[0]["jobs"] = [dict(simple_gt[0]["jobs"][0])]
        agent[0]["jobs"][0]["gross_per_period"] = 9999

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0
        assert any("gross_per_period" in w for w in result.wrong_fields)

    @pytest.mark.asyncio
    async def test_wrong_boolean_value(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        agent = [dict(simple_gt[0])]
        agent[0]["is_blind"] = True  # GT has False

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0
        assert any("is_blind" in w for w in result.wrong_fields)

    @pytest.mark.asyncio
    async def test_wrong_deduction_type(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        agent = [dict(simple_gt[0])]
        agent[0]["deduction_type"] = "itemized"  # GT has "standard"

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0
        assert any("deduction_type" in w for w in result.wrong_fields)


# =============================================================================
# 7. MISSING FIELD DETECTION
# =============================================================================


class TestMissingFieldDetection:

    @pytest.mark.asyncio
    async def test_missing_filing_status(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        agent = [dict(simple_gt[0])]
        del agent[0]["filing_status"]

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0
        assert any("filing_status" in m for m in result.missing_fields)

    @pytest.mark.asyncio
    async def test_missing_deduction_type(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        agent = [dict(simple_gt[0])]
        del agent[0]["deduction_type"]

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_missing_jobs_array(self, simple_gt):
        v = IrsTweQueryMatch(gt_queries=simple_gt)
        agent = [dict(simple_gt[0])]
        del agent[0]["jobs"]

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0


# =============================================================================
# 8. ARRAY FIELD COMPARISON
# =============================================================================


class TestArrayFieldComparison:

    @pytest.mark.asyncio
    async def test_jobs_match(self, mfj_verifier, mfj_gt):
        """Two-job MFJ should match perfectly."""
        await mfj_verifier.update(queries=mfj_gt)
        result = await mfj_verifier.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_jobs_wrong_count(self, mfj_gt):
        """Agent sends 1 job when GT expects 2 — should fail."""
        v = IrsTweQueryMatch(gt_queries=mfj_gt)
        agent = [dict(mfj_gt[0])]
        agent[0]["jobs"] = [mfj_gt[0]["jobs"][0]]  # only first job

        await v.update(queries=agent)
        result = await v.compute_detailed()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_pensions_match(self):
        """Pension array should match correctly."""
        gt = [{
            "filing_status": "single",
            "deduction_type": "standard",
            "pensions": [{
                "pension_paid_to": "myself",
                "pension_duration": "all_year",
                "pension_payment_frequency": "monthly",
                "pension_payment_date": "07/01/2026",
                "pension_gross_per_payment": 2200,
                "pension_ytd_gross": 13200,
            }],
        }]
        v = IrsTweQueryMatch(gt_queries=gt)
        await v.update(queries=gt)
        result = await v.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_self_employment_match(self):
        """Self-employment array should match correctly."""
        gt = [{
            "filing_status": "single",
            "deduction_type": "standard",
            "self_employment": [{
                "person": "myself",
                "gross_income": 72000,
                "business_expenses": 18000,
            }],
        }]
        v = IrsTweQueryMatch(gt_queries=gt)
        await v.update(queries=gt)
        result = await v.compute_detailed()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_ssi_match(self):
        """Social Security array should match correctly."""
        gt = [{
            "filing_status": "single",
            "deduction_type": "standard",
            "ssi": [{
                "ssi_pay_period": "all_year",
                "monthly_benefit": 1950,
                "withholding_percent": 7,
            }],
        }]
        v = IrsTweQueryMatch(gt_queries=gt)
        await v.update(queries=gt)
        result = await v.compute_detailed()
        assert result.score == 1.0


# =============================================================================
# 9. JSON STRING INPUT
# =============================================================================


class TestJsonStringInput:

    @pytest.mark.asyncio
    async def test_json_string_parsed(self, simple_verifier, simple_gt):
        """Agent passes queries as a JSON string instead of list — should auto-parse."""
        json_str = json.dumps(simple_gt)
        await simple_verifier.update(queries=json_str)
        result = await simple_verifier.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_invalid_json_string(self, simple_verifier):
        """Invalid JSON string should not crash."""
        await simple_verifier.update(queries="this is not json {{{")
        result = await simple_verifier.compute()
        assert result.score == 0.0


# =============================================================================
# 10. EMPTY VALUES CONSTANT
# =============================================================================


class TestEmptyValuesConstant:

    def test_zero_is_empty(self):
        assert 0 in EMPTY_VALUES
        assert 0.0 in EMPTY_VALUES

    def test_false_is_empty(self):
        assert False in EMPTY_VALUES

    def test_none_is_empty(self):
        assert None in EMPTY_VALUES

    def test_empty_string_is_empty(self):
        assert "" in EMPTY_VALUES

    def test_string_zero_is_empty(self):
        assert "0" in EMPTY_VALUES

    def test_nonzero_not_empty(self):
        assert 1 not in EMPTY_VALUES
        assert 5.5 not in EMPTY_VALUES
        assert "hello" not in EMPTY_VALUES
        assert True not in EMPTY_VALUES


# =============================================================================
# 11. FIELD TYPE SETS
# =============================================================================


class TestFieldTypeSets:

    def test_no_overlap_between_types(self):
        """Field types should not overlap."""
        all_sets = [BOOLEAN_FIELDS, DATE_FIELDS, CURRENCY_FIELDS,
                    INTEGER_FIELDS, ENUM_FIELDS, ARRAY_FIELDS]
        for i, s1 in enumerate(all_sets):
            for j, s2 in enumerate(all_sets):
                if i != j:
                    overlap = s1 & s2
                    assert overlap == set(), f"Sets {i} and {j} overlap: {overlap}"

    def test_filing_status_is_enum(self):
        assert "filing_status" in ENUM_FIELDS

    def test_gross_per_period_is_currency(self):
        assert "gross_per_period" in CURRENCY_FIELDS

    def test_is_blind_is_boolean(self):
        assert "is_blind" in BOOLEAN_FIELDS

    def test_recent_pay_date_is_date(self):
        assert "recent_pay_date" in DATE_FIELDS

    def test_number_of_children_is_integer(self):
        assert "number_of_children" in INTEGER_FIELDS

    def test_jobs_is_array(self):
        assert "jobs" in ARRAY_FIELDS


# =============================================================================
# 12. TASK CONFIG GENERATION
# =============================================================================


class TestTaskConfigGeneration:

    def test_basic_config(self):
        config = generate_task_config(
            url="https://apps.irs.gov/app/tax-withholding-estimator/",
            task="Fill out the form",
            queries=[{"filing_status": "single", "deduction_type": "standard"}],
        )
        assert config.url == "https://apps.irs.gov/app/tax-withholding-estimator/"
        assert config.task == "Fill out the form"
        assert "gt_queries" in config.eval_config

    def test_config_has_eval_target(self):
        config = generate_task_config(
            url="https://apps.irs.gov/app/tax-withholding-estimator/",
            task="Test",
            queries=[{"filing_status": "single"}],
        )
        assert "_target_" in config.eval_config

    def test_config_optional_fields(self):
        config = generate_task_config(
            url="https://apps.irs.gov/app/tax-withholding-estimator/",
            task="Test",
            queries=[{"filing_status": "single"}],
            location="United States",
            timezone="America/New_York",
        )
        assert config.user_metadata.location == "United States"
        assert config.user_metadata.timezone == "America/New_York"


# =============================================================================
# 13. JS SCRIPT LOADING
# =============================================================================


class TestJsScriptLoading:

    def test_js_script_loads(self, simple_verifier):
        js = simple_verifier.js_script
        assert isinstance(js, str)
        assert len(js) > 1000

    def test_js_script_has_session_storage(self, simple_verifier):
        js = simple_verifier.js_script
        assert "sessionStorage" in js

    def test_js_script_has_fact_graph(self, simple_verifier):
        js = simple_verifier.js_script
        assert "factGraph" in js

    def test_js_script_has_iife(self, simple_verifier):
        js = simple_verifier.js_script
        assert "(function" in js
        assert "})();" in js

    def test_js_script_has_field_mappings(self, simple_verifier):
        js = simple_verifier.js_script
        assert "filing_status" in js
        assert "gross_per_period" in js
        assert "deduction_type" in js


# =============================================================================
# 14. CSV BENCHMARK FILE
# =============================================================================


class TestCsvBenchmark:

    @pytest.fixture
    def csv_rows(self):
        csv_path = Path(__file__).parent.parent / "navi_bench" / "irs_tax_estimator" / "irs_tax_estimator_benchmark_tasks.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_csv_has_70_rows(self, csv_rows):
        assert len(csv_rows) == 70

    def test_csv_has_required_columns(self, csv_rows):
        required = {"task_id", "task_generation_config", "env", "domain",
                     "l1_category", "l2_category", "suggested_difficulty",
                     "suggested_hint", "suggested_max_steps",
                     "suggested_split", "metadata"}
        actual = set(csv_rows[0].keys())
        assert required.issubset(actual), f"Missing: {required - actual}"

    def test_csv_task_ids_unique(self, csv_rows):
        ids = [r["task_id"] for r in csv_rows]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_csv_all_rows_valid_json(self, csv_rows):
        for i, row in enumerate(csv_rows):
            try:
                config = json.loads(row["task_generation_config"])
                assert "_target_" in config, f"Row {i}: missing _target_"
                assert "queries" in config, f"Row {i}: missing queries"
            except json.JSONDecodeError:
                pytest.fail(f"Row {i}: Invalid JSON in task_generation_config")

    def test_csv_all_rows_have_filing_status(self, csv_rows):
        for i, row in enumerate(csv_rows):
            config = json.loads(row["task_generation_config"])
            q = config["queries"][0]
            assert "filing_status" in q, f"Row {i}: missing filing_status"

    def test_csv_valid_difficulties(self, csv_rows):
        valid = {"easy", "medium", "hard"}
        for row in csv_rows:
            assert row["suggested_difficulty"] in valid

    def test_csv_valid_splits(self, csv_rows):
        valid = {"train", "validation", "test"}
        for row in csv_rows:
            assert row["suggested_split"] in valid


# =============================================================================
# 15. CSV → VERIFIER E2E (sample rows)
# =============================================================================


class TestCsvToVerifierE2E:

    @pytest.fixture
    def csv_rows(self):
        csv_path = Path(__file__).parent.parent / "navi_bench" / "irs_tax_estimator" / "irs_tax_estimator_benchmark_tasks.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    @pytest.mark.asyncio
    async def test_first_row_perfect_match(self, csv_rows):
        """First CSV row with perfect agent response should score 1.0."""
        config = json.loads(csv_rows[0]["task_generation_config"])
        gt = config["queries"]
        v = IrsTweQueryMatch(gt_queries=gt)
        await v.update(queries=gt)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_last_row_perfect_match(self, csv_rows):
        """Last CSV row with perfect agent response should score 1.0."""
        config = json.loads(csv_rows[-1]["task_generation_config"])
        gt = config["queries"]
        v = IrsTweQueryMatch(gt_queries=gt)
        await v.update(queries=gt)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_all_70_rows_perfect_match(self, csv_rows):
        """Every CSV row with its own GT as agent response should score 1.0."""
        failed = []
        for i, row in enumerate(csv_rows):
            config = json.loads(row["task_generation_config"])
            gt = config["queries"]
            v = IrsTweQueryMatch(gt_queries=gt)
            await v.update(queries=gt)
            result = await v.compute()
            if result.score != 1.0:
                failed.append(f"Row {i} ({row['task_id']})")

        assert len(failed) == 0, f"Failed rows: {failed}"

    @pytest.mark.asyncio
    async def test_sample_row_wrong_response(self, csv_rows):
        """Sample row with wrong filing status should score 0.0."""
        config = json.loads(csv_rows[0]["task_generation_config"])
        gt = config["queries"]
        v = IrsTweQueryMatch(gt_queries=gt)

        agent = [dict(gt[0])]
        agent[0]["filing_status"] = "married_filing_separately"

        await v.update(queries=agent)
        result = await v.compute()
        assert result.score == 0.0


# =============================================================================
# 16. EDGE CASES
# =============================================================================


class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_agent_queries(self):
        v = IrsTweQueryMatch(gt_queries=[{"filing_status": "single"}])
        await v.update(queries=[])
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_none_queries(self):
        v = IrsTweQueryMatch(gt_queries=[{"filing_status": "single"}])
        await v.update(queries=None)
        result = await v.compute()
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_case_insensitive_enum_match(self):
        gt = [{"filing_status": "married_filing_jointly", "deduction_type": "standard"}]
        v = IrsTweQueryMatch(gt_queries=gt)
        agent = [{"filing_status": "Married Filing Jointly", "deduction_type": "Standard"}]
        await v.update(queries=agent)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_date_format_normalization(self):
        gt = [{"filing_status": "single", "jobs": [{
            "recent_pay_date": "06/25/2026",
            "gross_per_period": 3200,
        }]}]
        v = IrsTweQueryMatch(gt_queries=gt)
        agent = [{"filing_status": "single", "jobs": [{
            "recent_pay_date": "2026-06-25",  # YYYY-MM-DD format
            "gross_per_period": 3200,
        }]}]
        await v.update(queries=agent)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_currency_string_vs_number(self):
        gt = [{"filing_status": "single", "interest": 1850}]
        v = IrsTweQueryMatch(gt_queries=gt)
        agent = [{"filing_status": "single", "interest": "1850"}]
        await v.update(queries=agent)
        result = await v.compute()
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_computed_result_cached(self, simple_verifier, simple_gt):
        """Second compute should use cached result."""
        await simple_verifier.update(queries=simple_gt)
        r1 = await simple_verifier.compute_detailed()
        r2 = await simple_verifier.compute_detailed()
        assert r1 is r2  # Same object, cached
