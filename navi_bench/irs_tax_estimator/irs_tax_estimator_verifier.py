"""IRS Tax Withholding Estimator query-based verifier.

This module provides functionality to verify AI agent form-filling on the
IRS Tax Withholding Estimator (https://apps.irs.gov/app/tax-withholding-estimator/).

Unlike URL-based verifiers (Hotels.com, Expedia), the IRS TWE is a multi-step
form application. Verification is done by comparing the agent's extracted
query values against ground truth queries — field-by-field.

The verifier handles:
- Step 1 (About You): Filing status, age, blind, dependents, claimed
- Step 2 (Income): Jobs array, pensions array, self-employment, SSI,
                    investment income, unemployment, estimated tax payments
- Step 3 (Adjustments): Student loan, educator, IRA, HSA, etc.
- Step 4 (Deductions): Standard vs. itemized, with itemized sub-fields
- Step 5 (Additional Deductions): Senior deduction, QBI, car loan, tips, overtime
- Step 6 (Credits): CTC, ODC, CDCC, EITC, AOTC, LLC, adoption, etc.

Comparison rules (per client directives):
  1. Only fields present in ground truth are compared.
  2. If the model adds a field with value 0, false, null, or "" that is NOT
     in ground truth, the task still passes (lenient on extras).
  3. Currency values: exact numeric match.
  4. Boolean values: exact match.
  5. String/enum values: case-insensitive, underscore-normalized match.
  6. Date values: normalized to MM/DD/YYYY before comparison.
  7. Array fields (jobs, pensions, self_employment, ssi): matched by order.
"""

import asyncio
import functools
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel

from navi_bench.base import BaseMetric, BaseTaskConfig, UserMetadata, get_import_path


# =============================================================================
# RESULT MODELS
# =============================================================================


class FinalResult(BaseModel):
    score: float


class IrsTweVerifierResult(BaseModel):
    """Detailed verification result for IRS TWE query matching."""

    score: float
    match: bool
    field_results: dict = {}
    missing_fields: list[str] = []
    wrong_fields: list[str] = []
    extra_fields: list[str] = []
    details: str = ""


# =============================================================================
# CONSTANTS
# =============================================================================

# Fields that contain arrays of objects (each entry is a dict)
ARRAY_FIELDS = {"jobs", "pensions", "self_employment", "ssi"}

# Fields that are boolean type
BOOLEAN_FIELDS = {
    "user_age_65_or_older",
    "is_blind",
    "plan_to_claim_dependents",
    "claimed_as_dependent",
    "spouse_age_65_or_older",
    "spouse_is_blind",
    "spouse_plan_to_claim_dependents",
    "living_together",
    "pay_is_variable",
    "received_bonus",
    "additional_senior_deduction",
    "eitc_25_year_old",
    "withhold_federal_tax",
}

# Fields that are date type (MM/DD/YYYY)
DATE_FIELDS = {
    "recent_pay_period_end",
    "recent_pay_date",
    "start_date",
    "end_date",
    "pension_payment_date",
    "pension_start_date",
    "pension_end_date",
    "ss_start_date",
    "ss_end_date",
}

# Fields that are currency (numeric) type
CURRENCY_FIELDS = {
    "gross_per_period",
    "second_gross_per_period",
    "third_gross_per_period",
    "bonus_this_period",
    "estimate_bonus_pay",
    "ytd_gross",
    "annual_tip_income",
    "annual_overtime_income",
    "fed_withholding_period",
    "fed_withholding_ytd",
    "retirement_401k_period",
    "retirement_401k_ytd",
    "health_insurance_period",
    "health_insurance_ytd",
    "hsa_period",
    "hsa_ytd",
    "pre_tax_period",
    "pre_tax_ytd",
    # Pension
    "pension_gross_per_payment",
    "pension_ytd_gross",
    "pension_withholding_per_payment",
    "pension_withholding_ytd",
    "pension_health_amount_per_period",
    "pension_health_amount_so_far",
    "pension_hsa_pay_period",
    "pension_hsa_amount_so_far",
    "pension_other_pay_period",
    "pension_other_amount_so_far",
    # Self-employment
    "gross_income",
    "business_expenses",
    # Social Security
    "monthly_benefit",
    # Other income
    "gross_unemployment_income",
    "pre_tax_total_distribution",
    "interest",
    "ordinary_dividends",
    "qualified_dividends",
    "short_term_capital_gain",
    "short_term_capital_loss",
    "long_term_capital_gain",
    "long_term_capital_loss",
    "rental_income",
    "royalty_income",
    "passive_income",
    "non_passive_income",
    "other_taxable_income",
    "other_taxable_withholding",
    "estimated_tax_paid",
    # Adjustments
    "student_loan_interest",
    "educator_expenses",
    "traditional_ira",
    "hsa_deduction",
    "moving_expenses",
    "alimony_paid",
    "early_withdrawal_penalty",
    "eligible_business_expenses",
    "se_health_insurance_premiums",
    "se_retirement_contributions",
    # Itemized deductions
    "salt",
    "charity_gifts",
    "mortgage_interest",
    "mortgage_insurance",
    "medical_expenses",
    "casualty_losses",
    "other_itemized",
    # Additional deductions
    "qbi_deduction",
    "cash_charitable_contributions",
    "car_loan_interest",
    # Credits
    "cdcc_annual_care_expenses",
    "retirement_savings_credit",
    "aotc_tuition_fees",
    "llc_total_tuition_fees",
    "adoption_expenses",
    "elderly_disabled_credit",
    "foreign_tax_credit",
    "business_credit",
    "mortgage_interest_credit",
    "amt_credit",
}

# Fields that are integer type (counts)
INTEGER_FIELDS = {
    "number_of_children",
    "odc_number_of_dependants",
    "cdcc_number_of_children",
    "aotc_number_of_college_students",
    "adoption_credit_number_of_children",
}

# Enum/value fields — case-insensitive comparison
ENUM_FIELDS = {
    "filing_status",
    "job_type",
    "job_duration",
    "pay_frequency",
    "person",
    "pension_paid_to",
    "pension_duration",
    "pension_payment_frequency",
    "ssi_pay_period",
    "withholding_percent",
    "overtime_rate",
    "deduction_type",
}

# Values that indicate "not specified" — if model adds these for a field
# not in GT, the field is treated as empty (lenient rule)
EMPTY_VALUES = {0, 0.0, False, None, "", "0", "false", "null", "none", "0.0"}


# =============================================================================
# QUERY FORMAT HELPERS
# =============================================================================


def _unwrap_queries(queries: Any) -> list[dict] | None:
    """Normalize query format — handles both single and double nesting.

    Team CSV convention:  queries = [[{field: value, ...}]]  (double list)
    Our CSV convention:   queries = [{field: value, ...}]    (single list)

    This function ensures both formats produce [dict, ...] for the verifier.
    """
    if queries is None:
        return None
    if not isinstance(queries, list):
        return queries
    if len(queries) == 0:
        return queries
    # Double-nested: [[{...}]] → [{...}]
    if isinstance(queries[0], list):
        return queries[0]
    # Already single-nested: [{...}]
    return queries


# =============================================================================
# NORMALIZATION HELPERS
# =============================================================================

def _normalize_string(value: Any) -> str:
    """Normalize a string value for comparison.

    - Lowercase
    - Strip whitespace
    - Replace spaces and hyphens with underscores
    """
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = s.replace(" ", "_").replace("-", "_")
    return s


def _normalize_date(value: Any) -> str:
    """Normalize a date value to MM/DD/YYYY format.

    Handles:
      - MM/DD/YYYY (pass through)
      - M/D/YYYY
      - YYYY-MM-DD
      - YYYY-M-D
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    # YYYY-MM-DD or YYYY-M-D format
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{month:02d}/{day:02d}/{year:04d}"

    # MM/DD/YYYY or M/D/YYYY format
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{month:02d}/{day:02d}/{year:04d}"

    return s


def _normalize_number(value: Any) -> float | None:
    """Normalize a numeric value, stripping $ and commas."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _is_empty_value(value: Any) -> bool:
    """Check if a value is considered 'empty' for lenient comparison."""
    if value is None:
        return True
    if isinstance(value, bool):
        return value is False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        return value.strip().lower() in {"", "0", "false", "null", "none", "0.0"}
    if isinstance(value, list):
        return len(value) == 0
    return False


# =============================================================================
# FIELD COMPARISON
# =============================================================================


def _compare_field(field_name: str, gt_value: Any, agent_value: Any) -> tuple[bool, str]:
    """Compare a single field value between ground truth and agent.

    Returns:
        (match: bool, detail: str)
    """
    # Handle None agent value
    if agent_value is None:
        return False, f"Missing: expected {gt_value!r}, got None"

    # Boolean fields
    if field_name in BOOLEAN_FIELDS:
        gt_bool = bool(gt_value) if not isinstance(gt_value, bool) else gt_value
        if isinstance(agent_value, bool):
            agent_bool = agent_value
        elif isinstance(agent_value, str):
            agent_bool = agent_value.strip().lower() in {"true", "yes", "1"}
        else:
            agent_bool = bool(agent_value)
        if gt_bool == agent_bool:
            return True, "OK"
        return False, f"Boolean mismatch: expected {gt_bool}, got {agent_bool}"

    # Date fields
    if field_name in DATE_FIELDS:
        gt_date = _normalize_date(gt_value)
        agent_date = _normalize_date(agent_value)
        if gt_date == agent_date:
            return True, "OK"
        return False, f"Date mismatch: expected {gt_date}, got {agent_date}"

    # Currency / numeric fields
    if field_name in CURRENCY_FIELDS:
        gt_num = _normalize_number(gt_value)
        agent_num = _normalize_number(agent_value)
        if gt_num is not None and agent_num is not None and gt_num == agent_num:
            return True, "OK"
        return False, f"Number mismatch: expected {gt_num}, got {agent_num}"

    # Integer fields
    if field_name in INTEGER_FIELDS:
        try:
            gt_int = int(gt_value)
            agent_int = int(agent_value)
            if gt_int == agent_int:
                return True, "OK"
            return False, f"Integer mismatch: expected {gt_int}, got {agent_int}"
        except (ValueError, TypeError):
            return False, f"Integer parse error: expected {gt_value!r}, got {agent_value!r}"

    # Enum / string fields
    if field_name in ENUM_FIELDS:
        gt_str = _normalize_string(gt_value)
        agent_str = _normalize_string(agent_value)
        if gt_str == agent_str:
            return True, "OK"
        return False, f"Enum mismatch: expected {gt_str!r}, got {agent_str!r}"

    # Default: string comparison (case-insensitive)
    gt_str = _normalize_string(gt_value)
    agent_str = _normalize_string(agent_value)
    if gt_str == agent_str:
        return True, "OK"
    return False, f"Value mismatch: expected {gt_str!r}, got {agent_str!r}"


def _compare_object(gt_obj: dict, agent_obj: dict, prefix: str = "") -> tuple[int, int, list[str], list[str]]:
    """Compare two flat objects (dicts) field by field.

    Returns:
        (matched_count, total_gt_fields, wrong_fields, missing_fields)
    """
    matched = 0
    total = 0
    wrong = []
    missing = []

    for field_name, gt_value in gt_obj.items():
        # Skip array sub-fields (handled recursively)
        if field_name in ARRAY_FIELDS:
            continue

        total += 1
        full_name = f"{prefix}{field_name}" if prefix else field_name

        if field_name not in agent_obj:
            missing.append(full_name)
            continue

        agent_value = agent_obj[field_name]
        match, detail = _compare_field(field_name, gt_value, agent_value)
        if match:
            matched += 1
        else:
            wrong.append(f"{full_name}: {detail}")

    return matched, total, wrong, missing


def _compare_array_field(
    field_name: str,
    gt_array: list[dict],
    agent_array: list[dict],
) -> tuple[int, int, list[str], list[str]]:
    """Compare two arrays of objects by order (index-matched).

    Returns:
        (matched_count, total_gt_fields, wrong_fields, missing_fields)
    """
    total_matched = 0
    total_fields = 0
    all_wrong = []
    all_missing = []

    if len(agent_array) < len(gt_array):
        all_missing.append(
            f"{field_name}: expected {len(gt_array)} entries, got {len(agent_array)}"
        )

    for i, gt_entry in enumerate(gt_array):
        if i >= len(agent_array):
            # Agent didn't provide enough entries
            for k in gt_entry:
                if k not in ARRAY_FIELDS:
                    total_fields += 1
                    all_missing.append(f"{field_name}[{i}].{k}")
            continue

        agent_entry = agent_array[i]
        m, t, w, mi = _compare_object(
            gt_entry, agent_entry, prefix=f"{field_name}[{i}]."
        )
        total_matched += m
        total_fields += t
        all_wrong.extend(w)
        all_missing.extend(mi)

    return total_matched, total_fields, all_wrong, all_missing


# =============================================================================
# MAIN VERIFIER CLASS
# =============================================================================


class IrsTweQueryMatch(BaseMetric):
    """Query-based verifier for IRS Tax Withholding Estimator.

    Compares the agent's extracted query values against ground truth
    queries field-by-field. Supports lenient comparison where extra
    fields with empty/zero values are tolerated.

    Supports two input modes:
      1. page=<Playwright Page> — extracts fact-graph from browser via JS injection
      2. queries=<list[dict]>  — direct query input (for testing/demo)
    """

    def __init__(self, gt_queries: list[dict]) -> None:
        """Initialize with ground truth queries.

        Args:
            gt_queries: List of ground truth query dicts. Typically
                contains a single dict with all form field values.
                Also handles double-nested [[{...}]] format (team CSV convention).
        """
        self.gt_queries = _unwrap_queries(gt_queries)
        self._agent_queries: list[dict] | None = None
        self._result: IrsTweVerifierResult | None = None
        self._tracked_pages: set = set()

    def __repr__(self) -> str:
        return f"IrsTweQueryMatch(gt_queries={len(self.gt_queries)} entries)"

    @functools.cached_property
    def js_script(self) -> str:
        """Load the JavaScript fact-graph extraction script."""
        js_path = Path(__file__).parent / "irs_tax_estimator_info_gathering.js"
        with open(js_path, "r") as f:
            return f.read()

    def attach_to_context(self, context) -> None:
        """Attach automatic navigation tracking to a Playwright BrowserContext.

        Listens for page navigations to the IRS results page and
        automatically extracts fact-graph state when detected.

        Usage:
            verifier = IrsTweQueryMatch(gt_queries=queries)
            await verifier.reset()
            verifier.attach_to_context(context)
            # ... agent navigates ...
            result = await verifier.compute()
        """

        async def track_page(page) -> None:
            """Attach navigation tracking to a single page."""
            page_id = id(page)
            if page_id in self._tracked_pages:
                return
            self._tracked_pages.add(page_id)

            async def on_frame_navigated(frame):
                if frame != page.main_frame:
                    return
                try:
                    url = page.url
                    if "tax-withholding-estimator" in url:
                        logger.info(f"[IRS TWE NAV] {url[:80]}...")
                        await self.update(page=page)
                except Exception as e:
                    logger.warning(f"IRS TWE update failed: {e}")

            page.on("framenavigated", lambda f: asyncio.create_task(on_frame_navigated(f)))
            logger.info(f"IRS TWE tracking attached to page: {page.url[:60]}...")

        # Track existing pages
        for page in context.pages:
            asyncio.create_task(track_page(page))

        # Track new pages (tabs/popups)
        context.on("page", lambda p: asyncio.create_task(track_page(p)))

    async def reset(self) -> None:
        """Reset the verifier state."""
        self._agent_queries = None
        self._result = None
        self._tracked_pages = set()

    async def update(self, **kwargs) -> None:
        """Receive agent data from either a Playwright page or direct queries.

        Supported kwargs:
            page: Playwright Page — extracts fact-graph via JS injection
            queries: list[dict] — direct query input (for testing)
        """
        page = kwargs.get("page")
        queries = kwargs.get("queries")

        # ----- Mode 1: Page-based extraction (production) -----
        if page is not None:
            url = page.url
            if "tax-withholding-estimator" not in url:
                logger.debug(f"Ignoring non-IRS-TWE URL: {url[:60]}")
                return

            # Extract from both factGraph (payload) and DOM
            try:
                # Wait briefly for sessionStorage to be populated
                await page.wait_for_timeout(500)

                # Inject JS to extract fact-graph + DOM inputs
                extraction = await page.evaluate(self.js_script)

                if extraction and extraction.get("error") is None:
                    extracted = extraction.get("extracted", {})
                    dom_extracted = extraction.get("dom_extracted", {})
                    dom_count = extraction.get("dom_field_count", 0)

                    if extracted:
                        self._agent_queries = [extracted]
                        self._result = None  # Clear cached result
                        logger.info(
                            f"IrsTweQueryMatch: Extracted {len(extracted)} fields "
                            f"from payload ({extraction.get('raw_key_count', 0)} raw keys) "
                            f"+ {dom_count} DOM fields "
                            f"on {url[:60]}"
                        )
                    else:
                        logger.warning(f"IRS TWE: payload extraction returned empty on {url[:60]}")

                    # Log DOM extraction for cross-verification
                    if dom_extracted and dom_count > 0:
                        logger.debug(
                            f"IRS TWE DOM cross-check: {dom_count} visible inputs "
                            f"on {url[:60]}"
                        )
                else:
                    error = extraction.get("error", "unknown") if extraction else "null response"
                    logger.warning(f"IRS TWE: extraction error: {error}")
            except Exception as e:
                logger.error(f"IRS TWE: JS extraction failed: {e}")
            return

        # ----- Mode 2: Direct queries (testing/demo) -----
        if queries is not None:
            if isinstance(queries, str):
                try:
                    queries = json.loads(queries)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse agent queries as JSON: {queries[:200]}")
                    queries = None

            self._agent_queries = _unwrap_queries(queries)
            self._result = None  # Clear cached result
            logger.info(f"IrsTweQueryMatch: Received agent queries ({len(self._agent_queries) if self._agent_queries else 0} entries)")

    async def compute(self) -> FinalResult:
        """Compute the final score (0.0 or 1.0)."""
        result = await self.compute_detailed()
        return FinalResult(score=result.score)

    async def compute_detailed(self) -> IrsTweVerifierResult:
        """Compute detailed verification result with field-level breakdown."""
        if self._result is not None:
            return self._result

        if self._agent_queries is None:
            self._result = IrsTweVerifierResult(
                score=0.0,
                match=False,
                details="No agent queries received.",
            )
            return self._result

        self._result = self._queries_match(self._agent_queries)
        return self._result

    def _queries_match(self, agent_queries: list[dict]) -> IrsTweVerifierResult:
        """Compare agent queries against ground truth.

        Uses index-based matching: gt_queries[0] vs agent_queries[0], etc.
        """
        if not self.gt_queries:
            return IrsTweVerifierResult(
                score=1.0, match=True, details="No ground truth queries to compare."
            )

        if not agent_queries:
            return IrsTweVerifierResult(
                score=0.0, match=False, details="Agent returned no queries."
            )

        # Compare each GT query against corresponding agent query
        total_matched = 0
        total_fields = 0
        all_wrong: list[str] = []
        all_missing: list[str] = []
        all_extra: list[str] = []
        field_results: dict[str, Any] = {}

        for qi, gt_query in enumerate(self.gt_queries):
            if qi >= len(agent_queries):
                # Agent didn't provide enough query entries
                for k, v in gt_query.items():
                    if k in ARRAY_FIELDS:
                        for entry in v:
                            for ek in entry:
                                if ek not in ARRAY_FIELDS:
                                    total_fields += 1
                                    all_missing.append(f"queries[{qi}].{k}[*].{ek}")
                    else:
                        total_fields += 1
                        all_missing.append(f"queries[{qi}].{k}")
                continue

            agent_query = agent_queries[qi]

            # Compare flat fields
            m, t, w, mi = _compare_object(gt_query, agent_query, prefix=f"q{qi}.")
            total_matched += m
            total_fields += t
            all_wrong.extend(w)
            all_missing.extend(mi)

            # Compare array fields (jobs, pensions, self_employment, ssi)
            for array_field in ARRAY_FIELDS:
                if array_field in gt_query:
                    gt_arr = gt_query[array_field]
                    agent_arr = agent_query.get(array_field, [])
                    if isinstance(agent_arr, dict):
                        agent_arr = [agent_arr]  # Auto-wrap single dict
                    if not isinstance(agent_arr, list):
                        agent_arr = []

                    am, at, aw, ami = _compare_array_field(
                        f"q{qi}.{array_field}", gt_arr, agent_arr
                    )
                    total_matched += am
                    total_fields += at
                    all_wrong.extend(aw)
                    all_missing.extend(ami)

            # Check for extra fields (lenient — only flag if non-empty)
            for field_name, agent_value in agent_query.items():
                if field_name in ARRAY_FIELDS:
                    continue
                if field_name not in gt_query:
                    if not _is_empty_value(agent_value):
                        all_extra.append(
                            f"q{qi}.{field_name}={agent_value!r} (extra, non-empty)"
                        )
                    # Empty extras are silently ignored per Mustafa's rule

        # Calculate score
        if total_fields == 0:
            score = 1.0
            match = True
        else:
            # Binary: all fields must match
            match = total_matched == total_fields and len(all_wrong) == 0 and len(all_missing) == 0
            score = 1.0 if match else 0.0

        # Build detail string
        detail_parts = [
            f"Matched {total_matched}/{total_fields} fields.",
        ]
        if all_wrong:
            detail_parts.append(f"Wrong: {all_wrong}")
        if all_missing:
            detail_parts.append(f"Missing: {all_missing}")
        if all_extra:
            detail_parts.append(f"Extra (non-empty): {all_extra}")

        field_results = {
            "total_fields": total_fields,
            "matched": total_matched,
            "wrong_count": len(all_wrong),
            "missing_count": len(all_missing),
            "extra_count": len(all_extra),
        }

        return IrsTweVerifierResult(
            score=score,
            match=match,
            field_results=field_results,
            missing_fields=all_missing,
            wrong_fields=all_wrong,
            extra_fields=all_extra,
            details=" | ".join(detail_parts),
        )


# =============================================================================
# TASK CONFIG GENERATOR
# =============================================================================


def generate_task_config(
    task: str,
    url: str,
    queries: list[dict],
    location: str = "United States",
    timezone: str = "America/New_York",
) -> BaseTaskConfig:
    """Generate task configuration for IRS TWE query matching.

    Args:
        task: The narrative prompt describing the tax scenario.
        url: Starting URL (https://apps.irs.gov/app/tax-withholding-estimator/).
        queries: Ground truth query dicts — the expected form field values.
        location: User location string.
        timezone: IANA timezone string.

    Returns:
        BaseTaskConfig with eval_config pointing to IrsTweQueryMatch.
    """
    user_metadata = UserMetadata(
        location=location,
        timezone=timezone,
    )

    eval_target = get_import_path(IrsTweQueryMatch)
    eval_config = {
        "_target_": eval_target,
        "gt_queries": _unwrap_queries(queries),
    }

    return BaseTaskConfig(
        url=url,
        task=task,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )

