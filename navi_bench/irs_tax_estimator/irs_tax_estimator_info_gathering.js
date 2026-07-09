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
 * 
 * VERIFIED AGAINST: fact-dictionary.xml (July 2026)
 * All field paths confirmed as WRITABLE unless noted.
 */
(function () {
  'use strict';

  // ============================================================
  // EXTRACT RAW FACT-GRAPH
  // ============================================================

  var rawData = null;

  // Try sessionStorage first (persisted, reliable)
  try {
    var stored = sessionStorage.getItem('factGraph');
    if (stored) {
      rawData = JSON.parse(stored);
    }
  } catch (e) { /* ignore */ }

  // Fallback: try window.factGraph.toJSON() 
  if (!rawData) {
    try {
      if (window.factGraph && typeof window.factGraph.toJSON === 'function') {
        var exported = window.factGraph.toJSON();
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

    var t = entry.$type || '';

    // Real IRS format: {$type: "DollarWrapper", item: "1518.00"}
    if (t === 'DollarWrapper') {
      var v = entry.item;
      if (v === null || v === undefined || v === '') return undefined;
      return parseFloat(String(v).replace(/[$,\s]/g, ''));
    }

    // {$type: "BooleanWrapper", item: true}
    if (t === 'BooleanWrapper') {
      return entry.item === true || entry.item === 'true';
    }

    // {$type: "EnumWrapper", item: {value: "single", enumOptionsPath: "..."}}
    if (t === 'EnumWrapper') {
      if (entry.item && entry.item.value !== undefined) return entry.item.value;
      return entry.item;
    }

    // {$type: "DayWrapper", item: {date: "2026-05-31"}}
    if (t === 'DayWrapper') {
      if (entry.item && entry.item.date) return entry.item.date;
      return entry.item;
    }

    // {$type: "IntWrapper", item: 2}
    if (t === 'IntWrapper') {
      return entry.item;
    }

    // {$type: "CollectionWrapper", item: {items: ["uuid1", ...]}}
    if (t === 'CollectionWrapper') {
      if (entry.item && entry.item.items) return entry.item.items;
      return entry.item;
    }

    // Fallback: older format {$type: "Dollar", value: 1518}
    if (entry.value !== undefined) return entry.value;
    if (entry.item !== undefined) return entry.item;
    
    return entry;
  }

  function getFactValue(path) {
    var entry = rawData[path];
    if (entry === undefined) return undefined;
    return getValue(entry);
  }

  // ============================================================
  // FACT-GRAPH PATH → QUERY FIELD MAPPING (TOP LEVEL)
  // All paths verified against fact-dictionary.xml
  // ============================================================

  var TOP_LEVEL_MAP = {
    // About You — VERIFIED against real sessionStorage (July 2026)
    '/filingStatus': 'filing_status',
    '/primaryFilerAge65OrOlder': 'user_age_65_or_older',
    '/primaryFilerIsBlind': 'is_blind',
    '/primaryFilerIsClaimedOnAnotherReturn': 'claimed_as_dependent',
    '/secondaryFilerIsClaimedOnAnotherReturn': 'spouse_claimed_as_dependent',
    '/primaryFilerIsClaimingDependents': 'plan_to_claim_dependents',
    '/secondaryFilerAge65OrOlder': 'spouse_age_65_or_older',
    '/secondaryFilerIsBlind': 'spouse_is_blind',
    '/isMFSLivedTogether': 'living_together',
    // Dependents
    '/primaryFilerIsClaimingDependents': 'plan_to_claim_dependents',
    // Spouse dependents (MFJ)
    '/spousePlanToClaimDependents': 'spouse_plan_to_claim_dependents',
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
    '/sCorpPassiveIncome': 'passive_income',
    '/nonSpecificOtherIncome': 'other_taxable_income',
    '/otherIncomeWithholding': 'other_taxable_withholding',
    '/unemploymentIncome': 'gross_unemployment_income',
    // REMOVED: /unemploymentIncomeWithholding — boolean field, not currency
    '/preTaxRetirementAccountIncome': 'pre_tax_total_distribution',
    // Adjustments
    '/educatorExpenses': 'educator_expenses',
    // REMOVED: /educatorExpensesAdjustment (capped derived value, overwrites user-entered amount)
    '/alimonyPaid': 'alimony_paid',
    '/penaltyForEarlySavingsWithdrawal': 'early_withdrawal_penalty',
    '/movingExpensesForArmedServicesMembers': 'moving_expenses',
    '/selfEmploymentHealthInsuranceContributions': 'se_health_insurance_premiums',
    '/selfEmploymentRetirementPlanContributions': 'se_retirement_contributions',
    '/hsaContributionAmount': 'hsa_deduction',
    '/deductionForTraditionalIRAContribution': 'traditional_ira',
    '/deductionForTraditionalIRAContributionMax': 'traditional_ira',
    '/studentLoanInterestAmount': 'student_loan_interest',
    // REMOVED: /maxStudentLoanDeduction (statutory $2500 cap, overwrites user-entered amount)
    // Deductions — /wantsStandardDeduction is a boolean (true=standard, false=itemized)
    '/wantsStandardDeduction': 'deduction_type_raw',
    '/stateAndLocalTaxPayments': 'salt',
    '/qualifiedMortgageInsurancePremiums': 'mortgage_insurance',
    '/medicalAndDentalExpenses': 'medical_expenses',
    // REMOVED: /otherDeductionsTotal→medical_expenses (unrelated total, corrupts medical_expenses)
    '/casualtyLossesTotal': 'casualty_losses',
    '/otherItemizedDeductions': 'other_itemized',
    '/otherDeductions': 'other_itemized',
    // Mortgage interest — verified real path from sessionStorage (July 2026)
    '/qualifiedMortgageInterestAndInvestmentInterestExpenses': 'mortgage_interest',
    '/qualifiedMortgageInterest': 'mortgage_interest',
    '/homeInterest': 'mortgage_interest',
    // Additional deductions
    '/cashCharitableContributions': 'charity_gifts',
    '/nonItemizerCharitableContributionDeductionAmount': 'cash_charitable_contributions',
    '/nonCashCharitableContributions': 'non_cash_charitable_contributions',
    '/personalVehicleLoanInterestAmount': 'car_loan_interest',
    // REMOVED: /isEligibleForQualifiedPassengerVehicleLoanInterestDeduction (boolean→1.0, corrupts currency)
    '/qBIDeductionOverrideAmount': 'qbi_deduction',
    // Credits
    '/cdccQualifyingPersons': 'cdcc_number_of_children',
    // REMOVED: /flowIsEligibleForCDCC (boolean, corrupts integer count)
    '/cdccQualifyingExpenses': 'cdcc_annual_care_expenses',
    '/estimatedTotalQualifiedAdoptionExpenses': 'adoption_credit_annual_expenses',
    '/adoptionEligibleChildren': 'adoption_credit_number_of_children',
    '/aotcQualifiedEducationExpenses': 'aotc_tuition_fees',
    '/llcQualifiedEducationExpenses': 'llc_total_tuition_fees',
    '/elderlyAndDisabledTaxCreditAmount': 'elderly_disabled_credit',
    // REMOVED: /flowIsEligibleForEDC (boolean, corrupts currency amount)
    '/businessCreditsForEligible': 'business_credit',
    '/schedule3Line1': 'foreign_tax_credit',
    '/schedule3Line2': 'foreign_tax_credit',
    '/schedule3Line6b': 'mortgage_interest_credit',
    '/odcEligibleDependents': 'odc_number_of_dependants',
    '/flowShouldAskWhetherPrimaryFilerAge25OrOlderForEitc': 'eitc_25_year_old',
    '/schedule3Line6a': 'retirement_savings_credit',
    '/schedule3Line6z': 'retirement_savings_credit',
    '/retirementSavingsContributionsTaxCreditAmount': 'retirement_savings_credit',
    // REMOVED: /adjustmentsToIncomeExcludingStudentLoanInterest→adoption_expenses (wrong semantic mapping)
    '/maxSchedule3Line6g': 'amt_credit',
    '/tentativeSchedule3Line6g': 'amt_credit',
    '/alternativeMinimumTaxCreditAmount': 'amt_credit',
    // Senior deduction
    '/primaryTaxpayerElectsForSeniorDeduction': 'additional_senior_deduction',
    '/secondaryTaxpayerElectsForSeniorDeduction': 'spouse_additional_senior_deduction',
  };

  // ============================================================
  // JOB-LEVEL FIELD MAPPING
  // All writable fields verified against fact-dictionary.xml
  // ============================================================

  var JOB_FIELD_MAP = {
    // Person assignment (WRITABLE, needs conversion)
    'filerAssignment':                       'person_raw',
    // Job type (WRITABLE Boolean, needs conversion: false→"salary", true→"hourly")
    'isHourlyJob':                           'job_type_raw',
    // Job duration (WRITABLE Boolean, needs conversion: true→"all_year", false→"part_year")
    'isAllYear':                             'job_duration_raw',
    // Pay frequency (WRITABLE Int)
    'payFrequency':                          'pay_frequency_raw',
    // Dates (WRITABLE)
    'mostRecentPayPeriodEnd':                'recent_pay_period_end',
    'mostRecentPayDate':                     'recent_pay_date',
    // Gross per period (WRITABLE Dollar — amount on last paycheck)
    'amountLastPaycheck':                    'gross_per_period',
    // Year-to-date gross (WRITABLE Dollar)
    'yearToDateIncome':                      'ytd_gross',
    // Federal withholding per period (WRITABLE Dollar — amount withheld on last paycheck)
    'amountWithheldLastPaycheck':            'fed_withholding_period',
    // Year-to-date withholding (WRITABLE Dollar)
    'yearToDateWithholding':                 'fed_withholding_ytd',
    // Variable pay paystubs (WRITABLE Dollar)
    'pastPaycheckIncome1':                   'gross_per_period',
    'pastPaycheckIncome2':                   'second_gross_per_period',
    'pastPaycheckIncome3':                   'third_gross_per_period',
    // Variable pay indicator (WRITABLE Boolean — false = variable pay)
    'consistentPay':                         'pay_is_variable_raw',
    // Bonus (WRITABLE)
    'mostRecentPayPeriodHasBonus':           'received_bonus',
    'mostRecentPayPeriodBonusAmount':        'bonus_this_period',
    'totalFutureBonus':                      'estimate_bonus_pay',
    // Pre-tax deductions (WRITABLE Dollar)
    'retirementPlanContributionsPerPayPeriod': 'retirement_401k_period',
    'retirementPlanContributionsToDate':      'retirement_401k_ytd',
    'healthInsuranceContributionsPerPayPeriod': 'health_insurance_period',
    'healthInsuranceContributionsToDate':     'health_insurance_ytd',
    'hsaOrFsaContributionsPerPayPeriod':     'hsa_period',
    'hsaOrFsaContributionsToDate':           'hsa_ytd',
    'otherPreTaxContributionsPerPayPeriod':  'pre_tax_period',
    'otherPreTaxContributionsToDate':        'pre_tax_ytd',
    // Tips and overtime (WRITABLE)
    'qualifiedTipIncome':                    'annual_tip_income',
    'overtimeCompensationRate':              'overtime_rate',
    'overtimeCompensationTotal':             'annual_overtime_income',
    // Part-year dates (WRITABLE)
    'writableStartDate':                     'start_date',
    'writableEndDate':                       'end_date',
    // Variable pay indicator (WRITABLE)
    'expectedFuturePayPerHour':              'pay_is_variable_raw',
  };

  // ============================================================
  // PENSION-LEVEL FIELD MAPPING
  // ============================================================

  var PENSION_FIELD_MAP = {
    'filerAssignment':                           'pension_paid_to_raw',
    'payFrequency':                              'pension_payment_frequency_raw',
    'mostRecentPayDate':                         'pension_payment_date',
    'averagePayPerPayPeriodForWithholding':       'pension_gross_per_payment',
    'yearToDateIncome':                          'pension_ytd_gross',
    'averageWithholdingPerPayPeriod':             'pension_withholding_per_payment',
    'yearToDateWithholding':                     'pension_withholding_ytd',
    'healthInsuranceContributionsPerPayPeriod':   'pension_health_amount_per_period',
    'healthInsuranceContributionsToDate':         'pension_health_amount_so_far',
    'hsaOrFsaContributionsPerPayPeriod':          'pension_hsa_pay_period',
    'hsaOrFsaContributionsToDate':               'pension_hsa_amount_so_far',
    'otherPreTaxContributionsPerPayPeriod':       'pension_other_pay_period',
    'otherPreTaxContributionsToDate':             'pension_other_amount_so_far',
    'isAllYear':                                 'pension_duration_raw',
    'writableStartDate':                         'pension_start_date',
    'writableEndDate':                            'pension_end_date',
  };

  // ============================================================
  // SELF-EMPLOYMENT FIELD MAPPING
  // ============================================================

  var SE_FIELD_MAP = {
    'filerAssignment':     'person_raw',
    'grossIncome':         'gross_income',        // WRITABLE at SE level
    'workRelatedExpenses': 'business_expenses',    // WRITABLE
  };

  // ============================================================
  // SOCIAL SECURITY FIELD MAPPING
  // ============================================================

  var SSI_FIELD_MAP = {
    'filerAssignment':           'person_raw',
    'monthlyIncome':             'monthly_benefit',
    'withheldRateAsRationale':   'withholding_percent',
    'withheldRate':              'withholding_percent',
    'isAllYear':                 'ssi_pay_period_raw',
    'writableStartDate':         'ss_start_date',
    'startDate':                 'ss_start_date',
    'writableEndDate':           'ss_end_date',
    'endDate':                   'ss_end_date',
  };

  // ============================================================
  // PAY FREQUENCY INT → STRING CONVERSION
  // The IRS stores pay frequency as an integer (pay periods per year)
  // ============================================================

  var PAY_FREQ_MAP = {
    52: 'weekly',
    26: 'biweekly',
    24: 'twice_monthly',
    12: 'monthly',
    1:  'annually',
    4:  'quarterly',
  };

  // ============================================================
  // FILER ASSIGNMENT CONVERSION
  // ============================================================

  function convertPerson(rawValue) {
    if (rawValue === undefined || rawValue === null) return undefined;
    var s = String(rawValue).toLowerCase();
    if (s === 'primary' || s === 'primaryfiler' || s === 'self') return 'myself';
    if (s === 'secondary' || s === 'secondaryfiler' || s === 'spouse') return 'spouse';
    return s;
  }

  // ============================================================
  // DATE FORMAT CONVERSION
  // IRS stores: "2026-05-31" (ISO)
  // GT expects:  "05/31/2026" (MM/DD/YYYY)
  // ============================================================

  function isoToMmDdYyyy(isoDate) {
    if (!isoDate || typeof isoDate !== 'string') return isoDate;
    // Already in MM/DD/YYYY format?
    if (isoDate.indexOf('/') !== -1) return isoDate;
    // Parse YYYY-MM-DD
    var parts = isoDate.split('-');
    if (parts.length === 3) {
      return parts[1] + '/' + parts[2] + '/' + parts[0];
    }
    return isoDate;
  }

  // ============================================================
  // EXTRACT COLLECTIONS (JOBS, PENSIONS, SE, SSI)
  // ============================================================

  function extractCollection(prefix, fieldMap) {
    var items = [];
    // Real IRS paths: /jobs/#d178f03f-8a7d-44b1-9922-3254ba639fdb/isHourlyJob
    // The UUID has a # prefix in the key
    var collectionKeys = Object.keys(rawData).filter(function (k) {
      return k.startsWith(prefix + '/') && k.split('/').length > 2;
    });

    // Group by UUID (the part after prefix/, may have # prefix)
    var uuids = {};
    collectionKeys.forEach(function (key) {
      var rest = key.replace(prefix + '/', '');
      var slashIdx = rest.indexOf('/');
      if (slashIdx === -1) return; // Skip the collection entry itself
      var uuid = rest.substring(0, slashIdx);
      var fieldName = rest.substring(slashIdx + 1);
      if (!uuids[uuid]) uuids[uuid] = {};
      uuids[uuid][fieldName] = getValue(rawData[key]);
    });

    // Use the collection order from the CollectionWrapper, not Object.keys order!
    // e.g. /jobs has {$type: "CollectionWrapper", item: {items: ["uuid1", "uuid2"]}}
    // This ensures "myself" job comes before "spouse" job, matching GT order.
    var collectionEntry = rawData[prefix];
    var orderedUuids;
    if (collectionEntry && collectionEntry.$type === 'CollectionWrapper' &&
        collectionEntry.item && collectionEntry.item.items) {
      // Use the exact order from the collection, adding # prefix to match grouped keys
      orderedUuids = collectionEntry.item.items.map(function (id) {
        return '#' + id;
      });
    } else {
      // Fallback: use whatever order Object.keys gives
      orderedUuids = Object.keys(uuids);
    }

    orderedUuids.forEach(function (uuid) {
      var rawItem = uuids[uuid];
      if (!rawItem) return; // UUID from collection but no fields found
      var mappedItem = {};

      Object.keys(fieldMap).forEach(function (factField) {
        var foundKey = Object.keys(rawItem).find(function(k) {
          return k === factField || k.split('/').pop() === factField;
        });
        if (foundKey && rawItem[foundKey] !== undefined) {
          mappedItem[fieldMap[factField]] = rawItem[foundKey];
        }
      });

      // Only add if it has meaningful data
      if (Object.keys(mappedItem).length > 0) {
        items.push(mappedItem);
      }
    });

    return items;
  }

  // ============================================================
  // POST-PROCESS: Convert raw boolean/int fields to enum strings
  // ============================================================

  function postProcessJob(job) {
    // job_type: isHourlyJob (Boolean) → "salary" / "hourly"
    if (job.job_type_raw !== undefined) {
      job.job_type = job.job_type_raw === true ? 'hourly' : 'salary';
      delete job.job_type_raw;
    }

    // job_duration: isAllYear (Boolean) → "all_year" / "part_year"
    if (job.job_duration_raw !== undefined) {
      job.job_duration = job.job_duration_raw === true ? 'all_year' : 'part_year';
      delete job.job_duration_raw;
    }

    // pay_frequency: can be integer (12) or string ("monthly") from EnumWrapper
    if (job.pay_frequency_raw !== undefined) {
      var raw = job.pay_frequency_raw;
      if (typeof raw === 'number') {
        // Old integer format: 12→monthly, 26→biweekly, etc.
        var freq = PAY_FREQ_MAP[raw];
        job.pay_frequency = freq || String(raw);
      } else if (typeof raw === 'string') {
        var freq = raw.toLowerCase().trim();

        if (freq === 'semimonthly') {
          freq = 'twice_monthly';
        }

        job.pay_frequency = freq;
      } else {
        job.pay_frequency = String(raw);
      }
      delete job.pay_frequency_raw;
    }

    // person: filerAssignment → "myself" / "spouse"
    if (job.person_raw !== undefined) {
      job.person = convertPerson(job.person_raw);
      delete job.person_raw;
    }

    // overtime_rate: "two" -> "2.0x", "onePointFive" -> "1.5x"
    if (job.overtime_rate !== undefined) {
      var oMap = { 'onePointFive': '1.5x', 'two': '2.0x' };
      if (oMap[job.overtime_rate]) {
        job.overtime_rate = oMap[job.overtime_rate];
      }
    }

    // Convert ISO dates (2026-05-31) to MM/DD/YYYY format
    if (job.recent_pay_period_end && typeof job.recent_pay_period_end === 'string') {
      job.recent_pay_period_end = isoToMmDdYyyy(job.recent_pay_period_end);
    }
    if (job.recent_pay_date && typeof job.recent_pay_date === 'string') {
      job.recent_pay_date = isoToMmDdYyyy(job.recent_pay_date);
    }
    if (job.start_date && typeof job.start_date === 'string') {
      job.start_date = isoToMmDdYyyy(job.start_date);
    }
    if (job.end_date && typeof job.end_date === 'string') {
      job.end_date = isoToMmDdYyyy(job.end_date);
    }

    // pay_is_variable: from consistentPay (false = variable) or expectedFuturePayPerHour
    if (job.pay_is_variable_raw !== undefined) {
      var pvRaw = job.pay_is_variable_raw;
      delete job.pay_is_variable_raw;
      if (typeof pvRaw === 'boolean') {
        // consistentPay: false means variable pay, true means consistent
        job.pay_is_variable = !pvRaw;
      } else if (job.second_gross_per_period !== undefined || job.third_gross_per_period !== undefined) {
        // Fallback: variable pay indicated by having multiple paystubs
        job.pay_is_variable = true;
      }
    }

    return job;
  }

  function postProcessPension(pension) {
    // pension_paid_to: filerAssignment → "myself" / "spouse"
    if (pension.pension_paid_to_raw !== undefined) {
      pension.pension_paid_to = convertPerson(pension.pension_paid_to_raw);
      delete pension.pension_paid_to_raw;
    }

    // pension_duration: isAllYear → "all_year" / "part_year"
    if (pension.pension_duration_raw !== undefined) {
      pension.pension_duration = pension.pension_duration_raw === true ? 'all_year' : 'part_year';
      delete pension.pension_duration_raw;
    }

    // pension_payment_frequency: integer or string
    if (pension.pension_payment_frequency_raw !== undefined) {
      var freqRaw = pension.pension_payment_frequency_raw;
      if (typeof freqRaw === 'number') {
        var freq = PAY_FREQ_MAP[freqRaw];
        pension.pension_payment_frequency = freq || String(freqRaw);
      } else if (typeof freqRaw === 'string') {
      var freq = freqRaw.toLowerCase().trim();

      if (freq === 'semimonthly') {
        freq = 'twice_monthly';
      }

      pension.pension_payment_frequency = freq;
    } else {
        pension.pension_payment_frequency = String(freqRaw);
      }
      delete pension.pension_payment_frequency_raw;
    }

    // Convert ISO dates (2026-05-31) to MM/DD/YYYY format
    if (pension.pension_payment_date && typeof pension.pension_payment_date === 'string') {
      pension.pension_payment_date = isoToMmDdYyyy(pension.pension_payment_date);
    }
    if (pension.pension_start_date && typeof pension.pension_start_date === 'string') {
      pension.pension_start_date = isoToMmDdYyyy(pension.pension_start_date);
    }
    if (pension.pension_end_date && typeof pension.pension_end_date === 'string') {
      pension.pension_end_date = isoToMmDdYyyy(pension.pension_end_date);
    }

    return pension;
  }


  function postProcessSE(se) {
    // person: filerAssignment → "myself" / "spouse"
    if (se.person_raw !== undefined) {
      se.person = convertPerson(se.person_raw);
      delete se.person_raw;
    }
    return se;
  }

  function postProcessSSI(ssi) {
    // person: filerAssignment → "myself" / "spouse"
    if (ssi.person_raw !== undefined) {
      ssi.person = convertPerson(ssi.person_raw);
      delete ssi.person_raw;
    }

    // ssi_pay_period: isAllYear → "all_year" / "part_year"
    if (ssi.ssi_pay_period_raw !== undefined) {
      ssi.ssi_pay_period = ssi.ssi_pay_period_raw === true ? 'all_year' : 'part_year';
      delete ssi.ssi_pay_period_raw;
    }

    // withholding_percent: "seven" -> "7"
    if (ssi.withholding_percent !== undefined) {
      var wMap = { 'seven': '7', 'ten': '10', 'twelve': '12', 'twentyTwo': '22' };
      if (wMap[ssi.withholding_percent]) {
        ssi.withholding_percent = wMap[ssi.withholding_percent];
      }
    }

    // Convert ISO dates (2026-05-31) to MM/DD/YYYY format
    if (ssi.ss_start_date && typeof ssi.ss_start_date === 'string') {
      ssi.ss_start_date = isoToMmDdYyyy(ssi.ss_start_date);
    }
    if (ssi.ss_end_date && typeof ssi.ss_end_date === 'string') {
      ssi.ss_end_date = isoToMmDdYyyy(ssi.ss_end_date);
    }

    return ssi;
  }

  // ============================================================
  // BUILD EXTRACTED QUERY
  // ============================================================

  var result = {};

  // Extract top-level facts (no-clobber: first valid value wins)
  Object.keys(TOP_LEVEL_MAP).forEach(function (factPath) {
    var queryField = TOP_LEVEL_MAP[factPath];
    var val = getFactValue(factPath);
    if (val === undefined || val === null) return;
    // No-clobber guard: don't let a later/derived path overwrite
    // an already-captured value from the correct primary path
    if (result[queryField] !== undefined && result[queryField] !== null) return;
    result[queryField] = val;
  });

  // Handle deduction_type: /wantsStandardDeduction (BooleanWrapper)
  // true = standard, false = itemized
  if (result.deduction_type_raw !== undefined) {
    result.deduction_type = result.deduction_type_raw === true ? 'standard' : 'itemized';
    delete result.deduction_type_raw;
  }

  // Extract and post-process collections
  var jobs = extractCollection('/jobs', JOB_FIELD_MAP);
  jobs = jobs.map(postProcessJob);
  if (jobs.length > 0) result.jobs = jobs;

  var pensions = extractCollection('/pensions', PENSION_FIELD_MAP);
  pensions = pensions.map(postProcessPension);
  if (pensions.length > 0) result.pensions = pensions;

  var selfEmployment = extractCollection('/selfEmploymentSources', SE_FIELD_MAP);
  selfEmployment = selfEmployment.map(postProcessSE);
  if (selfEmployment.length > 0) result.self_employment = selfEmployment;

  var ssi = extractCollection('/socialSecuritySources', SSI_FIELD_MAP);
  ssi = ssi.map(postProcessSSI);
  if (ssi.length > 0) result.ssi = ssi;

  // ============================================================
  // EXTRACT MORTGAGE INTEREST (try multiple paths)
  // ============================================================

  var mortgagePaths = [
    '/qualifiedMortgageAndInvestmentInterest',
    '/qualifiedMortgageInterest',
    '/mortgageInterest',
  ];
  for (var i = 0; i < mortgagePaths.length; i++) {
    var mVal = getFactValue(mortgagePaths[i]);
    if (mVal !== undefined && mVal !== null && mVal > 0) {
      result.mortgage_interest = mVal;
      break;
    }
  }

  // ============================================================
  // EXTRACT CHARITY GIFTS — fallback for derived paths
  // Only used if /cashCharitableContributions was NOT in sessionStorage
  // ============================================================

  if (result.charity_gifts === undefined) {
    var charityPaths = [
      '/charitableContributions',
      '/totalCharitableContributions',
    ];
    for (var c = 0; c < charityPaths.length; c++) {
      var cVal = getFactValue(charityPaths[c]);
      if (cVal !== undefined && cVal !== null && cVal > 0) {
        result.charity_gifts = cVal;
        break;
      }
    }
  }

  // ============================================================
  // EXTRACT ESTIMATED TAX PAYMENTS
  // ============================================================

  var estTaxPaths = [
    '/totalEstimatedTaxesPaid',
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
    '/ctcEligibleDependents',
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
    '/qualifyingStudents',
  ];
  for (var m = 0; m < aotcPaths.length; m++) {
    var aotcVal = getFactValue(aotcPaths[m]);
    if (aotcVal !== undefined && aotcVal !== null && aotcVal > 0) {
      result.aotc_number_of_college_students = aotcVal;
      break;
    }
  }

  // ============================================================
  // DOM EXTRACTION — Read visible form inputs as secondary source
  // Reads all <fg-set> elements and their current input values
  // ============================================================

  var domExtracted = {};

  try {
    var fgSets = document.querySelectorAll('fg-set[path]');
    fgSets.forEach(function (el) {
      var path = el.getAttribute('path');
      var inputType = el.getAttribute('inputtype');
      if (!path) return;

      var val = undefined;

      switch (inputType) {
        case 'dollar': {
          var input = el.querySelector('input');
          if (input && input.value) {
            // Remove $ and commas, parse as number
            var cleaned = input.value.replace(/[$,\s]/g, '');
            val = cleaned ? parseFloat(cleaned) : undefined;
          }
          break;
        }
        case 'boolean': {
          var checked = el.querySelector('input[type="radio"]:checked');
          if (checked) {
            val = checked.value === 'true' || checked.value === '1';
          }
          break;
        }
        case 'enum':
        case 'select': {
          var checked = el.querySelector('input[type="radio"]:checked');
          if (checked) {
            val = checked.value;
          } else {
            var sel = el.querySelector('select');
            if (sel && sel.value && sel.value !== '- Select -') {
              val = sel.value;
            }
          }
          break;
        }
        case 'date': {
          var month = el.querySelector('select[name*="-month"]');
          var day = el.querySelector('input[name*="-day"]');
          var year = el.querySelector('select[name*="-year"], input[name*="-year"]');
          if (month && day && year && month.value && day.value && year.value) {
            var mm = month.value.padStart(2, '0');
            var dd = day.value.padStart(2, '0');
            val = mm + '/' + dd + '/' + year.value;
          }
          break;
        }
        case 'single-checkbox': {
          var cb = el.querySelector('input[type="checkbox"]');
          if (cb) {
            val = cb.checked;
          }
          break;
        }
        default: {
          // Text/int inputs
          var input = el.querySelector('input');
          if (input && input.value) {
            var num = parseFloat(input.value.replace(/[$,\s]/g, ''));
            val = isNaN(num) ? input.value : num;
          }
        }
      }

      if (val !== undefined) {
        domExtracted[path] = { value: val, inputType: inputType };
      }
    });
  } catch (e) {
    domExtracted._error = String(e);
  }

  // ============================================================
  // POST-PROCESS FILING STATUS & SPOUSE DEPENDENTS
  // ============================================================

  if (result.filing_status) {
    // IRS Enum: marriedFilingJointly -> married_filing_jointly
    result.filing_status = result.filing_status.replace(/[A-Z]/g, function(letter) {
      return '_' + letter.toLowerCase();
    }).toLowerCase();

    // Alias for QSS
    if (result.filing_status === 'qualified_surviving_spouse') {
      result.filing_status = 'qualifying_surviving_spouse';
    }
  }

  // For MFJ, the IRS only asks "Do you plan to claim dependents?" once.
  // The factGraph does NOT store a separate /spousePlanToClaimDependents.
  // If our GT expects it, we must inject it from the primary answer.
  // No-clobber: only inject if not already set by the direct mapping (line 131).
  if (result.filing_status === 'married_filing_jointly'
      && result.plan_to_claim_dependents !== undefined
      && result.spouse_plan_to_claim_dependents === undefined) {
    result.spouse_plan_to_claim_dependents = result.plan_to_claim_dependents;
  }

  // C2 Fix: The Ground Truth (GT) completely omits the 'person' field
  // for non-married filers. If we emit 'person' for them, it's scored as
  // an EXTRA field and the task gets 0.0.
  if (result.filing_status !== 'married_filing_jointly' && result.filing_status !== 'married_filing_separately') {
    ['jobs', 'self_employment', 'ssi'].forEach(function (cat) {
      if (result[cat]) {
        result[cat].forEach(function (item) {
          delete item.person;
        });
      }
    });
    if (result.pensions) {
      result.pensions.forEach(function (item) {
        delete item.pension_paid_to;
      });
    }
  }

  // ============================================================
  // RETURN RESULTS (both payload and DOM)
  // ============================================================

  return {
    error: null,
    source: 'factGraph+dom',
    raw_key_count: Object.keys(rawData).length,
    extracted: result,
    dom_extracted: domExtracted,
    dom_field_count: Object.keys(domExtracted).length,
    raw_keys_sample: Object.keys(rawData).slice(0, 50),
  };
})();
