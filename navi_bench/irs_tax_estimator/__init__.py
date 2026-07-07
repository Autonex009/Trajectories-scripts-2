"""IRS Tax Withholding Estimator verifier module.

This module verifies AI agent form-filling on the IRS Tax Withholding
Estimator by comparing the agent's extracted query values against
expected ground truth queries (query-based verifier).
Covers all estimator steps: About You, Income, Adjustments, Deductions,
Additional Deductions, Credits, and Results.
"""

from navi_bench.irs_tax_estimator.irs_tax_estimator_verifier import (
    IrsTweQueryMatch,
    generate_task_config,
)

__all__ = [
    "IrsTweQueryMatch",
    "generate_task_config",
]
