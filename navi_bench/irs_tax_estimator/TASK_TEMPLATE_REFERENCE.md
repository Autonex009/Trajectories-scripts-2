# IRS Tax Withholding Estimator — Task Template Reference

> **For**: Team task creation  
> **Updated**: July 7, 2026  
> **Reference file**: `irs_tax_estimator_benchmark_tasks.csv` (in this folder)  
> **Target**: 70 tasks total  

---

## CSV Column Format (Same as all navi_bench benchmarks)

| Column | Description | IRS-Specific Value |
|--------|-------------|-------------------|
| `task_id` | `irs_tax_estimator/{l2_category}/{index}` | Sequential: 0, 1, 2, ... |
| `task_generation_config` | JSON blob (minified) | See structure below |
| `env` | `real` | Always `real` |
| `domain` | `irs_tax_estimator` | Always `irs_tax_estimator` |
| `l1_category` | `government` | New category for this domain |
| `l2_category` | Per task type | E.g., `single_w2`, `mfj_dual_jobs`, `itemized_deductions`, etc. |
| `suggested_difficulty` | `easy` / `medium` / `hard` | See difficulty guide below |
| `suggested_hint` | Short hint describing the key challenge | E.g., "MFJ with dual jobs. Agent must expand accordion sections." |
| `suggested_max_steps` | Estimated agent step count | 40–150 depending on difficulty |
| `suggested_split` | `train` / `validation` / `test` | Distribute across splits |
| `metadata` | `null` | Always `null` |

---

## task_generation_config JSON Structure

```json
{
  "_target_": "navi_bench.irs_tax_estimator.irs_tax_estimator_verifier.generate_task_config",
  "url": "https://apps.irs.gov/app/tax-withholding-estimator/",
  "task": "[NARRATIVE PROMPT]",
  "queries": [
    {
      // --- STEP 1: ABOUT YOU ---
      "filing_status": "single",
      "user_age_65_or_older": false,
      "is_blind": false,
      "plan_to_claim_dependents": false,
      "claimed_as_dependent": false,

      // MFJ only:
      "spouse_age_65_or_older": false,
      "spouse_is_blind": false,
      "spouse_plan_to_claim_dependents": false,

      // MFS only:
      "living_together": false,

      // Dependents (only if plan_to_claim_dependents = true):
      "qualifying_children": 2,
      "children_ages": [7, 14],
      "other_dependents": 1,

      // --- STEP 2: JOBS (array — supports multiple) ---
      "jobs": [
        {
          "person": "myself",
          "job_type": "salary",
          "job_duration": "all_year",
          "pay_frequency": "biweekly",
          "recent_pay_period_end": "03/08/2026",
          "recent_pay_date": "03/14/2026",
          "pay_is_variable": false,
          "gross_per_period": 5385,
          "second_gross_per_period": 5200,
          "third_gross_per_period": 5100,
          "received_bonus": false,
          "bonus_this_period": 500,
          "estimate_bonus_pay": 1000,
          "ytd_gross": 32310,
          "annual_tip_income": 10000,
          "annual_overtime_income": 5000,
          "overtime_rate": "1.5x",
          "fed_withholding_period": 612,
          "fed_withholding_ytd": 3672,
          "retirement_401k_period": 750,
          "retirement_401k_ytd": 4500,
          "health_insurance_period": 320,
          "health_insurance_ytd": 1920,
          "hsa_period": 125,
          "hsa_ytd": 750,
          "pre_tax_period": 45,
          "pre_tax_ytd": 270
        }
      ],

      // --- STEP 2: PENSIONS (array — supports multiple) ---
      "pensions": [
        {
          "pension_paid_to": "myself",
          "pension_duration": "all_year",
          "pension_start_date": "01/01/2026",
          "pension_end_date": "12/31/2026",
          "pension_payment_frequency": "monthly",
          "pension_payment_date": "03/15/2026",
          "pension_gross_per_payment": 2500,
          "pension_ytd_gross": 7500,
          "pension_withholding_per_payment": 300,
          "pension_withholding_ytd": 900,
          "pension_health_amount_per_period": 150,
          "pension_health_amount_so_far": 450,
          "pension_hsa_pay_period": 100,
          "pension_hsa_amount_so_far": 300,
          "pension_other_pay_period": 50,
          "pension_other_amount_so_far": 150
        }
      ],

      // --- STEP 2: SELF-EMPLOYMENT (array — supports multiple) ---
      "self_employment": [
        {
          "person": "myself",
          "gross_income": 18000,
          "business_expenses": 3000
        }
      ],

      // --- STEP 2: SOCIAL SECURITY (array — supports multiple) ---
      "ssi": [
        {
          "ssi_pay_period": "all_year",
          "monthly_benefit": 1500,
          "withholding_percent": 7,
          "ss_start_date": "01/01/2026",
          "ss_end_date": "12/31/2026"
        }
      ],

      // --- STEP 2: OTHER INCOME SECTIONS ---
      // Unemployment:
      "gross_unemployment_income": 5000,
      "withhold_federal_tax": true,

      // Pre-tax retirement account:
      "pre_tax_total_distribution": 10000,

      // Investment income:
      "interest": 1850,
      "ordinary_dividends": 2200,
      "qualified_dividends": 2200,
      "short_term_capital_gain": 5000,
      "short_term_capital_loss": 1000,
      "long_term_capital_gain": 3000,
      "long_term_capital_loss": 500,

      // Rental/Royalty:
      "rental_income": 12000,
      "royalty_income": 0,
      "passive_income": 0,
      "non_passive_income": 0,

      // Other taxable income:
      "other_taxable_income": 2000,
      "other_taxable_withholding": 500,

      // Estimated tax payments:
      "estimated_tax_paid": 5000,

      // --- STEP 3: ADJUSTMENTS ---
      "student_loan_interest": 1200,
      "educator_expenses": 350,
      "traditional_ira": 2000,
      "hsa_deduction": 1000,
      "moving_expenses": 5000,
      "alimony_paid": 3500,
      "early_withdrawal_penalty": 0,
      "eligible_business_expenses": 2000,
      "se_health_insurance_premiums": 1500,
      "se_retirement_contributions": 4000,

      // --- STEP 4: DEDUCTIONS ---
      "deduction_type": "standard",

      // Itemized fields (only if deduction_type = "itemized"):
      "salt": 10000,
      "charity_gifts": 3800,
      "mortgage_interest": 14200,
      "mortgage_insurance": 500,
      "medical_expenses": 15000,
      "casualty_losses": 0,
      "other_itemized": 0,

      // --- STEP 5: ADDITIONAL DEDUCTIONS ---
      "qbi_deduction": 5000,
      "additional_senior_deduction": true,
      "cash_charitable_contributions": 500,
      "car_loan_interest": 1900,

      // --- STEP 6: CREDITS ---
      "number_of_children": 2,
      "odc_number_of_dependants": 1,
      "cdcc_number_of_children": 1,
      "cdcc_annual_care_expenses": 3000,
      "eitc_25_year_old": true,
      "retirement_savings_credit": 500,
      "aotc_number_of_college_students": 1,
      "aotc_tuition_fees": 4000,
      "llc_total_tuition_fees": 5000,
      "adoption_credit_number_of_children": 1,
      "adoption_expenses": 5000,
      "elderly_disabled_credit": 1000,
      "foreign_tax_credit": 2000,
      "business_credit": 500,
      "mortgage_interest_credit": 1500,
      "amt_credit": 1000
    }
  ],
  "location": "United States",
  "timezone": "America/New_York"
}
```

> **RULE**: Only include fields that are relevant to the scenario. Omit fields not mentioned in the prompt. Per Mustafa: if the model adds 0 for an unmentioned field (e.g., bonus), that's still acceptable — the scenario should pass.

---

## Allowed Values Reference

### Filing Status
`single` · `married_filing_jointly` · `married_filing_separately` · `head_of_household` · `qualifying_surviving_spouse`

### Job Type
`hourly` · `salary`

### Job Duration / Pension Duration / SSI Pay Period
`all_year` · `part_year`

### Pay Frequency / Pension Payment Frequency
`weekly` · `biweekly` · `twice_monthly` · `monthly`

### Person / Pension Paid To
`myself` · `spouse`

### Overtime Rate
`1.5x` · `2.0x`

### Deduction Type
`standard` · `itemized`

---

## Prompt Writing Guide

### Style (from client example)

- **Use fictional character names** — "Marcus Delano and his spouse Elena"
- **Family story** — Children with names and ages: "Sofia (7) and Lucas (14)"
- **Extremely precise values** — Every dollar amount, every date, every field
- **Structured sections** — Personal info → Job(s) → Other income → Adjustments → Deductions → Credits
- **Explicit blank instruction** — *"If the site asks for extra optional fields, rollups, or derived amounts that I have not explicitly given, leave those blank rather than estimating."*
- **Role assignment for MFJ** — *"Enter Marcus as self/primary filer and Elena as spouse"*
- **Clear stop point** — *"Enter the information carefully and continue until you reach the final results page."*

### Template Prompt Structure

```
Please complete the IRS Tax Withholding Estimator for [my / my family's] 2026 tax 
situation and stop on the final results page. Use only the information provided below. 
If the estimator asks for optional information, calculated totals, confirmation values, 
or anything I have not explicitly provided, leave those fields blank rather than estimating.

About Me:
[Filing status, age, blind, dependents, claimed as dependent]

Income & Tax Payments:
[Job 1 details — type, duration, frequency, dates, gross, YTD, withholding, pre-tax]
[Job 2 details — if applicable]
[Pension — if applicable]
[Self-employment — if applicable]
[Other income — investments, SS, rental, etc.]
[Estimated tax payments — if applicable]

Adjustments:
[Student loan, educator, IRA, HSA, etc. — or "I do not plan to claim any adjustments"]

Deductions:
[Standard or Itemized with specific amounts]

Additional Deductions:
[Senior deduction, car loan interest, QBI, etc. — if applicable]

Credits:
[CTC, CDCC, AOTC, etc. — if applicable]

Please complete the estimator using only the information above and stop once the final 
results page is displayed.
```

---

## Difficulty Guide

| Difficulty | Steps | Characteristics | Target Count |
|-----------|-------|----------------|-------------|
| **easy** | 40–60 | Single filer, 1 job (salary), standard deduction, no adjustments. | ~10 tasks |
| **medium** | 60–90 | 1–2 jobs, some other income, adjustments, standard or basic itemized. Variable pay. | ~25 tasks |
| **hard** | 90–150+ | MFJ dual jobs, itemized, OB3 provisions, multiple credits, pension + SE + investments. | ~35 tasks |

> **Client directive**: "Please make the tasks complicated and difficult." Focus on **medium and hard**.

---

## Kisan's Example Task (Validated Format)

```json
{
  "_target_": "navi_bench.irs_tax_estimator.irs_tax_estimator_verifier.generate_task_config",
  "url": "https://apps.irs.gov/app/tax-withholding-estimator/",
  "task": "Please complete the IRS Tax Withholding Estimator for my 2026 tax situation and stop on the final results page. Use only the information provided below. If the estimator asks for optional information, calculated totals, confirmation values, or anything I have not explicitly provided, leave those fields blank rather than estimating. About Me: I am filing as Single. I will be 65 years old or older on January 1, 2027. I am not blind. I can be claimed as a dependent on someone else's 2026 tax return. I do not plan to claim any dependents. Income & Tax Payments: I have one hourly job that I expect to work for the entire 2026 tax year. I am paid weekly. My most recent pay period ended on July 30, 2026, and I received my paycheck on August 3, 2026. My pay varies significantly from paycheck to paycheck. My three most recent gross pay amounts were $1,126, $1,284, and $1,198. None of these paychecks included a bonus, and I do not expect any bonus for the remainder of 2026. My year-to-date gross income is $34,965. Federal income tax withheld from my most recent paycheck was $118, and my year-to-date federal income tax withheld is $3,546. I have made estimated federal tax payments totaling $2,850 during 2026. Adjustments: I do not plan to claim any adjustments. Deductions: I plan to use the standard deduction. Additional Deductions: I plan to claim the additional senior deduction. Please complete the estimator using only the information above and stop once the final results page is displayed.",
  "queries": [
    {
      "filing_status": "single",
      "user_age_65_or_older": true,
      "is_blind": false,
      "plan_to_claim_dependents": false,
      "claimed_as_dependent": true,
      "jobs": [
        {
          "job_type": "hourly",
          "job_duration": "all_year",
          "pay_frequency": "weekly",
          "recent_pay_period_end": "07/30/2026",
          "recent_pay_date": "08/03/2026",
          "pay_is_variable": true,
          "gross_per_period": 1126,
          "second_gross_per_period": 1284,
          "third_gross_per_period": 1198,
          "received_bonus": false,
          "ytd_gross": 34965,
          "fed_withholding_period": 118,
          "fed_withholding_ytd": 3546
        }
      ],
      "estimated_tax_paid": 2850,
      "deduction_type": "standard",
      "additional_senior_deduction": true
    }
  ],
  "location": "United States",
  "timezone": "America/New_York"
}
```

**Why this is a good medium task:**
- Hourly job (not salary) — different flow
- Variable pay → triggers 3-paystub entry
- 65+ → triggers additional senior deduction in Step 5
- Claimed as dependent → limits standard deduction
- Estimated tax payments → separate section in Step 2
- ~60 agent steps

---

## Scenario Checklist (for 70-task coverage)

### Filing Status
- [ ] Single — ~15 tasks
- [ ] Married Filing Jointly — ~25 tasks
- [ ] Head of Household — ~10 tasks
- [ ] Married Filing Separately — ~5 tasks (include `living_together`)
- [ ] Qualifying Surviving Spouse — ~2 tasks

### Job Variations
- [ ] Salary, all year
- [ ] Hourly, all year
- [ ] Salary, part year (start/end dates)
- [ ] Variable pay (3 paystubs)
- [ ] Multiple jobs (2–4 in `jobs` array)
- [ ] With bonus (received_bonus + estimate_bonus_pay)
- [ ] With tips (annual_tip_income)
- [ ] With overtime (annual_overtime_income + overtime_rate)
- [ ] With pre-tax deductions (401k, health, HSA, other)

### Other Income Types
- [ ] Pension (`pensions` array)
- [ ] Self-employment (`self_employment` array)
- [ ] Social Security (`ssi` array)
- [ ] Investment income (interest, dividends, cap gains)
- [ ] Rental/royalty income
- [ ] Unemployment income
- [ ] Pre-tax retirement distribution
- [ ] Other taxable income
- [ ] Estimated tax payments

### Deductions
- [ ] Standard deduction — ~30 tasks
- [ ] Itemized deduction — ~20 tasks (SALT, mortgage, charity, medical, car loan)

### Special Features
- [ ] 65+ senior (additional_senior_deduction)
- [ ] Blind filer
- [ ] Claimed as dependent
- [ ] OB3 car loan interest
- [ ] Variable pay (hourly)
- [ ] MFS living_together question
