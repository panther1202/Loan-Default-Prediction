import { describe, expect, it } from "vitest";

import {
  CATEGORICAL_COLUMNS,
  FEATURE_ORDER,
  INTERCEPT,
  NUMERIC_FEATURES,
  OUTLIER_BOUNDS,
  PROTECTED_FEATURES,
} from "./params.js";
import {
  ValidationError,
  attribute,
  buildFeatureVector,
  clampRawNumerics,
  deriveFeatures,
  score,
  sigmoid,
  validateApplicant,
  withoutProtectedFeatures,
} from "./pipeline.js";

const APPLICANT = {
  Age: 40,
  Income: 70000,
  LoanAmount: 36000,
  CreditScore: 650,
  MonthsEmployed: 60,
  NumCreditLines: 2,
  LoanTerm: 36,
  DTIRatio: 0.3,
  Education: "Bachelor's",
  EmploymentType: "Full-time",
  MaritalStatus: "Divorced",
  HasMortgage: "No",
  HasDependents: "No",
  LoanPurpose: "Auto",
  HasCoSigner: "No",
};

describe("validateApplicant", () => {
  it("accepts a well-formed applicant", () => {
    expect(validateApplicant(APPLICANT)).toEqual(APPLICANT);
  });

  it("rejects a categorical value the model was never trained on", () => {
    // Silently scoring this as the dropped reference category would produce a confident
    // number for an applicant the model never saw. docs/TEST_STRATEGY.md requires rejection.
    expect(() => validateApplicant({ ...APPLICANT, Education: "Bootcamp" })).toThrow(
      ValidationError,
    );
    expect(() => validateApplicant({ ...APPLICANT, Education: "Bootcamp" })).toThrow(
      /Education/,
    );
  });

  it("rejects a missing required field", () => {
    const { Income, ...missing } = APPLICANT;
    expect(() => validateApplicant(missing)).toThrow(/Income/);
  });

  it("rejects a non-finite numeric field", () => {
    expect(() => validateApplicant({ ...APPLICANT, LoanAmount: Number.NaN })).toThrow(
      /LoanAmount/,
    );
    expect(() => validateApplicant({ ...APPLICANT, LoanAmount: "20000" })).toThrow(
      /LoanAmount/,
    );
  });

  it("rejects a caller-supplied InterestRate", () => {
    // ADR-0007: the rate card assigns the rate. Accepting one from the applicant would let
    // the caller pick the value of the model's second-strongest feature.
    expect(() => validateApplicant({ ...APPLICANT, InterestRate: 3 })).toThrow(
      /InterestRate/,
    );
  });

  it("rejects a zero or negative loan term, which the EMI formula cannot divide by", () => {
    expect(() => validateApplicant({ ...APPLICANT, LoanTerm: 0 })).toThrow(/LoanTerm/);
  });
});

describe("clampRawNumerics", () => {
  it("clamps a value above the exported upper bound", () => {
    const clamped = clampRawNumerics({ ...APPLICANT, Age: 200, InterestRate: 8 });
    expect(clamped.Age).toBe(OUTLIER_BOUNDS.Age!.upper);
  });

  it("clamps a value below the exported lower bound", () => {
    // The bound itself is negative here — an IQR artifact of a uniform Income distribution
    // (docs/adr/0009-training-data-source.md). Rejecting an implausible income is input
    // validation's job, not the clamp's; the clamp only keeps the arithmetic in-domain.
    const belowBound = OUTLIER_BOUNDS.Income!.lower - 1000;
    const clamped = clampRawNumerics({ ...APPLICANT, Income: belowBound, InterestRate: 8 });
    expect(clamped.Income).toBe(OUTLIER_BOUNDS.Income!.lower);
  });

  it("leaves an in-range value untouched", () => {
    const clamped = clampRawNumerics({ ...APPLICANT, InterestRate: 8 });
    expect(clamped.Age).toBe(APPLICANT.Age);
    expect(clamped.Income).toBe(APPLICANT.Income);
  });
});

describe("deriveFeatures", () => {
  it("computes an EMI that amortises the loan at the given rate", () => {
    // Independent check rather than restating the formula: the present value of LoanTerm
    // payments of EMI, discounted at the monthly rate, must equal the principal.
    const derived = deriveFeatures(clampRawNumerics({ ...APPLICANT, InterestRate: 8 }));
    const r = 8 / 12 / 100;
    const presentValue = (derived.EstimatedEMI! * (1 - Math.pow(1 + r, -APPLICANT.LoanTerm))) / r;
    expect(presentValue).toBeCloseTo(APPLICANT.LoanAmount, 6);
  });

  it("falls back to principal over term when the rate is zero", () => {
    const derived = deriveFeatures(clampRawNumerics({ ...APPLICANT, InterestRate: 0 }));
    expect(derived.EstimatedEMI!).toBe(APPLICANT.LoanAmount / APPLICANT.LoanTerm);
  });

  it("derives the payment-to-income ratio from the clamped income, not the raw one", () => {
    // Ordering matters: the training script clamps before deriving. Deriving first would
    // leak an out-of-range income into a feature that is never itself clamped.
    const clamped = clampRawNumerics({ ...APPLICANT, Income: 5_000_000, InterestRate: 8 });
    const derived = deriveFeatures(clamped);
    expect(clamped.Income).toBe(OUTLIER_BOUNDS.Income!.upper);
    expect(derived.Payment_to_Income_Ratio).toBe(
      derived.EstimatedEMI! / (OUTLIER_BOUNDS.Income!.upper + 1e-6),
    );
  });
});

describe("buildFeatureVector", () => {
  it("produces exactly the 26 features the model expects", () => {
    const vector = buildFeatureVector(validateApplicant(APPLICANT), 8);
    expect(Object.keys(vector).sort()).toEqual([...FEATURE_ORDER].sort());
  });

  it("encodes a dropped reference category as all zeros for that column", () => {
    const vector = buildFeatureVector(validateApplicant(APPLICANT), 8);
    for (const encoded of CATEGORICAL_COLUMNS.Education!.encoded_columns) {
      expect(vector[encoded], encoded).toBe(0);
    }
  });

  it("encodes a non-dropped category as exactly one 1.0 in that column", () => {
    const vector = buildFeatureVector(
      validateApplicant({ ...APPLICANT, Education: "PhD" }),
      8,
    );
    const set = CATEGORICAL_COLUMNS.Education!.encoded_columns.filter(
      (name) => vector[name] === 1,
    );
    expect(set).toEqual(["Education_PhD"]);
  });

  it("standardises the numeric features to roughly unit scale", () => {
    const vector = buildFeatureVector(validateApplicant(APPLICANT), 8);
    for (const feature of NUMERIC_FEATURES) {
      expect(Math.abs(vector[feature]!), feature).toBeLessThan(10);
    }
  });

  it("uses the assigned interest rate rather than any applicant-supplied value", () => {
    const low = buildFeatureVector(validateApplicant(APPLICANT), 7);
    const high = buildFeatureVector(validateApplicant(APPLICANT), 11);
    expect(low.InterestRate).not.toBe(high.InterestRate);
    expect(low.EstimatedEMI).not.toBe(high.EstimatedEMI);
  });
});

describe("attribute", () => {
  const vector = buildFeatureVector(validateApplicant(APPLICANT), 8);

  it("reconstructs the logit from the intercept plus every contribution", () => {
    // For a linear model this is not an approximation of SHAP — it is the same arithmetic
    // that produced the decision (docs/adr/0005-ml-model-hosting.md).
    const total = attribute(vector).reduce((sum, c) => sum + c.contribution, INTERCEPT);
    expect(total).toBeCloseTo(score(vector).logit, 12);
  });

  it("ranks features by absolute contribution, strongest first", () => {
    const magnitudes = attribute(vector).map((c) => Math.abs(c.contribution));
    expect(magnitudes).toEqual([...magnitudes].sort((a, b) => b - a));
  });

  it("covers all 26 features", () => {
    expect(attribute(vector)).toHaveLength(FEATURE_ORDER.length);
  });
});

describe("withoutProtectedFeatures", () => {
  it("removes Age and marital status even when Age ranks first", () => {
    // ADR-0007 measured Age as a top-3 attribution in 76% of denials, so this filter fires
    // on most cases rather than occasionally. A young applicant makes that concrete.
    const young = buildFeatureVector(validateApplicant({ ...APPLICANT, Age: 19 }), 11);
    const ranked = attribute(young);
    expect(ranked[0]!.feature).toBe("Age");

    const filtered = withoutProtectedFeatures(ranked);
    for (const feature of PROTECTED_FEATURES) {
      expect(filtered.map((c) => c.feature)).not.toContain(feature);
    }
    expect(filtered).toHaveLength(ranked.length - PROTECTED_FEATURES.length);
  });

  it("leaves the surviving order intact and still has material to cite", () => {
    const filtered = withoutProtectedFeatures(
      attribute(buildFeatureVector(validateApplicant(APPLICANT), 8)),
    );
    const magnitudes = filtered.map((c) => Math.abs(c.contribution));
    expect(magnitudes).toEqual([...magnitudes].sort((a, b) => b - a));
    expect(filtered.length).toBeGreaterThan(3);
  });
});

describe("score", () => {
  it("maps a zero logit to even odds", () => {
    expect(sigmoid(0)).toBe(0.5);
  });

  it("returns a probability that is the sigmoid of its own logit", () => {
    const result = score(buildFeatureVector(validateApplicant(APPLICANT), 8));
    expect(result.probability).toBe(sigmoid(result.logit));
    expect(result.probability).toBeGreaterThan(0);
    expect(result.probability).toBeLessThan(1);
  });
});
