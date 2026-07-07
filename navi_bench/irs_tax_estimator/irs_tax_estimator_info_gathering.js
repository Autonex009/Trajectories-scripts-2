/**
 * IRS Tax Withholding Estimator — Fact-Graph Extraction Script
 * 
 * Injected into the browser page via Playwright's page.evaluate().
 * Extracts the complete form state from sessionStorage and/or
 * the window.factGraph global object.
 * 
 * Returns a flat JSON object with all writable fact values that
 * the agent entered, organized by our query field names.
 * 
 * Data sources (both checked for reliability):
 *   1. sessionStorage.getItem('factGraph')
 *   2. window.factGraph (if available)
 */
(function () {
  'use strict';

  // ============================================================
  // EXTRACT RAW FACT-GRAPH
  // ============================================================

  let rawData = null;

  // Try sessionStorage first (persisted, reliable)
  try {
    const stored = sessionStorage.getItem('factGraph');
    if (stored) {
      rawData = JSON.parse(stored);
    }
  } catch (e) { /* ignore */ }

  // Fallback: try window.factGraph.toJSON() 
  if (!rawData) {
    try {
      if (window.factGraph && typeof window.factGraph.toJSON === 'function') {
        const exported = window.factGraph.toJSON();
        rawData = typeof exported === 'string' ? JSON.parse(exported) : exported;
      }
    } catch (e) { /* ignore */ }
  }

  if (!rawData) {
    return {
      error: 'NO_FACTGRAPH_DATA',
      source: 'none',
      extracted: null,
      raw_keys: [],
    };
  }

  // ============================================================
  // HELPER: GET VALUE FROM FACT-GRAPH ENTRY
  // ============================================================

  function getValue(entry) {
    if (entry === null || entry === undefined) return undefined;
    
    // Direct primitive
    if (typeof entry !== 'object') return entry;
    
    // fact-graph stores values as {$type: "...", value: ...}
    // or as plain values in different shapes
    if (entry.value !== undefined) return entry.value;
    if (entry.$type === 'Dollar') return entry.value || 0;
    if (entry.$type === 'Boolean') return entry.value || false;
    if (entry.$type === 'Enum') return entry.value || '';
    if (entry.$type === 'Int') return entry.value || 0;
    if (entry.$type === 'Date') return entry.value || '';
    if (entry.$type === 'String') return entry.value || '';
    
    return entry;
  }

  function getFactValue(path) {
    const entry = rawData[path];
    if (entry === undefined) return undefined;
    return getValue(entry);
  }

  // ============================================================
  // FACT-GRAPH PATH → QUERY FIELD MAPPING (TOP LEVEL)
  // ============================================================

  const TOP_LEVEL_MAP = {
    // About You
    '/filingStatus': 'filing_status',
    '/onlyPrimaryFilerAge65OrOlder': 'user_age_65_or_older',
    '/onlyPrimaryFilerIsBlind': 'is_blind',
    '/treatFilersAsDependents': 'claimed_as_dependent',
    '/onlyPrimaryFilerIsClaimedOnAnotherReturn': 'claimed_as_dependent',
    '/secondaryFilerAge65OrOlder': 'spouse_age_65_or_older',
    '/secondaryFilerIsBlind': 'spouse_is_blind',
    '/isMFSLivedTogether': 'living_together',
    // Dependents (from credits page)
    '/tentativelyEligibleForCtcOdc': 'plan_to_claim_dependents',
    // Other Income
    '/taxableInterestIncome': 'interest',
    '/ordinaryDividendsIncome': 'ordinary_dividends',
    '/qualifiedDividendsIncome': 'qualified_dividends',
    '/shortTermCapitalGainsIncome': 'short_term_capital_gain',
    '/shortTermCapitalLoss': 'short_term_capital_loss',
    '/longTermCapitalGainsIncome': 'long_term_capital_gain',
    '/longTermCapitalLoss': 'long_term_capital_loss',
    '/rentalIncome': 'rental_income',
    '/royaltyIncome': 'royalty_income',
    '/sCorpNonPassiveIncome': 'non_passive_income',
    '/nonRentalRoyaltyScheduleEIncome': 'passive_income',
    '/nonSpecificOtherIncome': 'other_taxable_income',
    '/otherIncomeWithholding': 'other_taxable_withholding',
    '/unemploymentIncome': 'gross_unemployment_income',
    '/unemploymentIncomeWithholding': 'withhold_federal_tax',
    '/preTaxRetirementAccountIncome': 'pre_tax_total_distribution',
    // Adjustments
    '/educatorExpensesAdjustment': 'educator_expenses',
    '/alimonyPaid': 'alimony_paid',
    '/penaltyForEarlySavingsWithdrawal': 'early_withdrawal_penalty',
    '/selfEmploymentHealthInsuranceContributions': 'se_health_insurance_premiums',
    '/selfEmploymentRetirementPlanContributions': 'se_retirement_contributions',
    '/hsaContributionAmount': 'hsa_deduction',
    '/deductionForTraditionalIRAContributionMax': 'traditional_ira',
    // Student loan handled separately (has max check)
    '/maxStudentLoanDeduction': 'student_loan_interest',
    // Deductions
    '/wantsItemizedDeduction': 'deduction_type_raw',
    '/stateAndLocalTaxPayments': 'salt',
    '/charitableContributions': 'charity_gifts',
    '/qualifiedMortgageInsurancePremiums': 'mortgage_insurance',
    '/otherDeductionsTotal': 'medical_expenses',
    // Additional deductions
    '/cashCharitableContributions': 'cash_charitable_contributions',
    '/isEligibleForQualifiedPassengerVehicleLoanInterestDeduction': 'car_loan_interest',
    '/wantsQBIDeductionOverride': 'qbi_deduction',
    // Credits
    '/flowIsEligibleForCDCC': 'cdcc_number_of_children',
    '/cdccQualifyingExpenses': 'cdcc_annual_care_expenses',
    '/adoptionEligibleChildren': 'adoption_credit_number_of_children',
    '/aotcQualifiedEducationExpenses': 'aotc_tuition_fees',
    '/llcQualifiedEducationExpenses': 'llc_total_tuition_fees',
    '/flowIsEligibleForEDC': 'elderly_disabled_credit',
    '/businessCreditsForEligible': 'business_credit',
    '/schedule3Line2': 'foreign_tax_credit',
    '/schedule3Line6b': 'mortgage_interest_credit',
    '/odcEligibleDependents': 'odc_number_of_dependants',
    '/flowShouldAskWhetherPrimaryFilerAge25OrOlderForEitc': 'eitc_25_year_old',
    // Retirement savings credit
    '/schedule3Line6z': 'retirement_savings_credit',
    // Adoption expenses (for credit calculation)
    '/adjustmentsToIncomeExcludingStudentLoanInterest': 'adoption_expenses',
    // AMT credit
    '/maxSchedule3Line6g': 'amt_credit',
    // Senior deduction
    '/couldEitherTaxpayerBeEligibleForSeniorDeduction': 'additional_senior_deduction',
    '/secondaryTaxpayerElectsForSeniorDeduction': 'spouse_additional_senior_deduction',
  };

  // Job-level field mapping: fact-graph path suffix → query field name
  const JOB_FIELD_MAP = {
    'filerAssignment': 'person',
    'isFilerAssignmentSelfOrIncomplete': 'person_is_self',
    'isHourlyJob': 'job_type',
    'payFrequency': 'pay_frequency',
    'mostRecentPayPeriodEnd': 'recent_pay_period_end',
    'unboundedDefaultMostRecentPayDate': 'recent_pay_date',
    'amountLastPaycheck': 'gross_per_period',
    'averagePayPerPayPeriod': 'avg_pay',
    'expectedFuturePayPerHour': 'pay_is_variable',
    'effectivePayPerPayPeriod': 'effective_pay',
    'grossIncome': 'ytd_gross',
    'averageWithholdingPerPayPeriod': 'fed_withholding_period',
    'yearToDateWithholding': 'fed_withholding_ytd',
    'mostRecentPayPeriodHasBonus': 'received_bonus',
    'mostRecentPayPeriodBonusAmount': 'bonus_this_period',
    'totalBonusReceived': 'total_bonus_received',
    'totalFutureBonus': 'estimate_bonus_pay',
    'retirementPlanContributionsPerPayPeriod': 'retirement_401k_period',
    'retirementPlanContributionsToDate': 'retirement_401k_ytd',
    'healthInsuranceContributionsPerPayPeriod': 'health_insurance_period',
    'healthInsuranceContributionsToDate': 'health_insurance_ytd',
    'hsaOrFsaContributionsPerPayPeriod': 'hsa_period',
    'hsaOrFsaContributionsToDate': 'hsa_ytd',
    'otherPreTaxContributionsPerPayPeriod': 'pre_tax_period',
    'otherPreTaxContributionsToDate': 'pre_tax_ytd',
    'qualifiedTipIncome': 'annual_tip_income',
    'overtimeCompensationRate': 'overtime_rate',
    'pastPaycheckIncome2': 'second_gross_per_period',
    'pastPaycheckIncome3': 'third_gross_per_period',
    'writableStartDate': 'start_date',
    'writableEndDate': 'end_date',
    'eligibleForNoTaxOnOvertime': 'overtime_eligible',
    'hoursPerPayPeriod': 'annual_overtime_income',
    'expectedFutureAnnualSalary': 'job_duration',
  };

  // Pension-level field mapping
  const PENSION_FIELD_MAP = {
    'filerAssignment': 'pension_paid_to',
    'isFilerAssignmentSelf': 'pension_is_self',
    'payFrequency': 'pension_payment_frequency',
    'mostRecentPayDate': 'pension_payment_date',
    'averagePayPerPayPeriodForWithholding': 'pension_gross_per_payment',
    'yearToDateIncome': 'pension_ytd_gross',
    'expectedWithholdingPerPayPeriodForFutureJob': 'pension_withholding_per_payment',
    'healthInsuranceContributions': 'pension_health_amount_per_period',
    'healthInsuranceContributionsToDate': 'pension_health_amount_so_far',
    'hsaOrFsaContributions': 'pension_hsa_pay_period',
    'hsaOrFsaContributionsToDate': 'pension_hsa_amount_so_far',
    'otherPreTaxContributions': 'pension_other_pay_period',
    'otherPreTaxContributionsToDate': 'pension_other_amount_so_far',
    'healthInsuranceContributionsPerPayPeriod': 'pension_health_per_period',
    'flowInitialQuestionsComplete': 'pension_duration',
    'endDate': 'pension_withholding_ytd',
  };

  // Self-employment field mapping
  const SE_FIELD_MAP = {
    'filerAssignment': 'person',
    'netIncome': 'gross_income',
    'workRelatedExpenses': 'business_expenses',
  };

  // Social Security field mapping
  const SSI_FIELD_MAP = {
    'filerAssignment': 'person',
    'monthlyIncome': 'monthly_benefit',
    'withheldRateAsRationale': 'withholding_percent',
    'isAllYear': 'ssi_pay_period',
    'endDate': 'ss_end_date',
  };

  // ============================================================
  // EXTRACT COLLECTIONS (JOBS, PENSIONS, SE, SSI)
  // ============================================================

  function extractCollection(prefix, fieldMap) {
    const items = [];
    const collectionKeys = Object.keys(rawData).filter(function (k) {
      return k.startsWith(prefix + '/') && k.split('/').length > 2;
    });

    // Group by UUID (the part after prefix/)
    const uuids = {};
    collectionKeys.forEach(function (key) {
      const parts = key.replace(prefix + '/', '').split('/');
      const uuid = parts[0];
      const fieldName = parts.slice(1).join('/');
      if (!uuids[uuid]) uuids[uuid] = {};
      uuids[uuid][fieldName] = getValue(rawData[key]);
    });

    Object.keys(uuids).forEach(function (uuid) {
      const rawItem = uuids[uuid];
      const mappedItem = {};

      Object.keys(fieldMap).forEach(function (factField) {
        if (rawItem[factField] !== undefined) {
          mappedItem[fieldMap[factField]] = rawItem[factField];
        }
      });

      // Only add if it has meaningful data
      if (Object.keys(mappedItem).length > 0) {
        mappedItem._uuid = uuid;
        items.push(mappedItem);
      }
    });

    return items;
  }

  // ============================================================
  // BUILD EXTRACTED QUERY
  // ============================================================

  const result = {};

  // Extract top-level facts
  Object.keys(TOP_LEVEL_MAP).forEach(function (factPath) {
    const queryField = TOP_LEVEL_MAP[factPath];
    const val = getFactValue(factPath);
    if (val !== undefined && val !== null) {
      result[queryField] = val;
    }
  });

  // Handle deduction_type: /wantsItemizedDeduction is an int (1 = itemized, 0 = standard)
  if (result.deduction_type_raw !== undefined) {
    result.deduction_type = result.deduction_type_raw === 1 ? 'itemized' : 'standard';
    delete result.deduction_type_raw;
  }

  // Extract collections
  const jobs = extractCollection('/jobs', JOB_FIELD_MAP);
  if (jobs.length > 0) result.jobs = jobs;

  const pensions = extractCollection('/pensions', PENSION_FIELD_MAP);
  if (pensions.length > 0) result.pensions = pensions;

  const selfEmployment = extractCollection('/selfEmploymentSources', SE_FIELD_MAP);
  if (selfEmployment.length > 0) result.self_employment = selfEmployment;

  const ssi = extractCollection('/socialSecuritySources', SSI_FIELD_MAP);
  if (ssi.length > 0) result.ssi = ssi;

  // ============================================================
  // ALSO EXTRACT MORTGAGE INTEREST FROM DOM (not in factGraph directly)
  // ============================================================
  // Mortgage interest may be stored differently — check common paths
  var mortgagePaths = [
    '/qualifiedMortgageAndInvestmentInterest',
    '/qualifiedMortgageInterest',
    '/mortgageInterest',
  ];
  for (var i = 0; i < mortgagePaths.length; i++) {
    var val = getFactValue(mortgagePaths[i]);
    if (val !== undefined && val !== null && val > 0) {
      result.mortgage_interest = val;
      break;
    }
  }

  // ============================================================
  // EXTRACT ESTIMATED TAX PAYMENTS
  // ============================================================
  var estTaxPaths = [
    '/estimatedTaxPayments',
    '/estimatedTaxPaid',
    '/totalEstimatedTaxPayments',
  ];
  for (var j = 0; j < estTaxPaths.length; j++) {
    var etVal = getFactValue(estTaxPaths[j]);
    if (etVal !== undefined && etVal !== null && etVal > 0) {
      result.estimated_tax_paid = etVal;
      break;
    }
  }

  // ============================================================
  // EXTRACT CTC NUMBER OF CHILDREN
  // ============================================================
  var ctcPaths = [
    '/ctcEligibleChildren',
    '/numberOfCtcEligibleChildren',
    '/numberOfQualifyingChildren',
  ];
  for (var k = 0; k < ctcPaths.length; k++) {
    var ctcVal = getFactValue(ctcPaths[k]);
    if (ctcVal !== undefined && ctcVal !== null && ctcVal > 0) {
      result.number_of_children = ctcVal;
      break;
    }
  }

  // ============================================================
  // EXTRACT AOTC NUMBER OF STUDENTS
  // ============================================================
  var aotcPaths = [
    '/aotcEligibleStudents',
    '/numberOfAotcEligibleStudents',
  ];
  for (var m = 0; m < aotcPaths.length; m++) {
    var aotcVal = getFactValue(aotcPaths[m]);
    if (aotcVal !== undefined && aotcVal !== null && aotcVal > 0) {
      result.aotc_number_of_college_students = aotcVal;
      break;
    }
  }

  // ============================================================
  // RETURN RESULTS
  // ============================================================

  return {
    error: null,
    source: 'factGraph',
    raw_key_count: Object.keys(rawData).length,
    extracted: result,
    // Also return the raw keys for debugging
    raw_keys_sample: Object.keys(rawData).slice(0, 50),
  };
})();
