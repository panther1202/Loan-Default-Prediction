/**
 * The frozen model's preprocessing and scoring, reimplemented in TypeScript.
 *
 * docs/adr/0005-ml-model-hosting.md: the model is a plain logistic regression, so the whole
 * pipeline is arithmetic over `model_params.json` — no ONNX, no second host, no Python at
 * runtime. The step order below mirrors the training script exactly, because a serving
 * pipeline that derives before it clamps, or that orders the one-hot columns differently,
 * produces confident numbers that are quietly wrong. `evals/parity_cases.json` is what holds
 * this honest.
 */

import {
  CATEGORICAL_COLUMNS,
  COEFFICIENTS,
  FEATURE_ORDER,
  INTERCEPT,
  NUMERIC_FEATURES,
  OUTLIER_BOUNDS,
  PROTECTED_FEATURES,
  SCALER,
  must,
} from "./params.js";

/** The 9 raw numeric columns the training script clamps, including the assigned rate. */
export const RAW_NUMERIC_FIELDS = Object.keys(OUTLIER_BOUNDS);

/** The categorical columns an applicant supplies, from the encoder's own export. */
export const CATEGORICAL_FIELDS = Object.keys(CATEGORICAL_COLUMNS);

/**
 * What the applicant submits. `InterestRate` is deliberately absent: ADR-0007 assigns it
 * from the rate card, and it is the model's second-strongest feature — not something the
 * caller gets to choose.
 */
export const APPLICANT_NUMERIC_FIELDS = RAW_NUMERIC_FIELDS.filter(
  (field) => field !== "InterestRate",
);

export type ApplicantInput = Record<string, number | string>;
export type RawNumerics = Record<string, number>;
export type FeatureVector = Record<string, number>;

export class ValidationError extends Error {
  constructor(
    message: string,
    readonly field: string,
  ) {
    super(message);
    this.name = "ValidationError";
  }
}

export function validateApplicant(input: unknown): ApplicantInput {
  if (typeof input !== "object" || input === null) {
    throw new ValidationError("applicant must be an object", "");
  }
  const raw = input as Record<string, unknown>;

  if ("InterestRate" in raw) {
    throw new ValidationError(
      "InterestRate is assigned by the rate card, not submitted by the applicant",
      "InterestRate",
    );
  }

  const clean: ApplicantInput = {};

  for (const field of APPLICANT_NUMERIC_FIELDS) {
    const value = raw[field];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new ValidationError(`${field} must be a finite number`, field);
    }
    clean[field] = value;
  }

  if ((clean.LoanTerm as number) <= 0) {
    throw new ValidationError("LoanTerm must be a positive number of months", "LoanTerm");
  }

  for (const field of CATEGORICAL_FIELDS) {
    const value = raw[field];
    const column = must(CATEGORICAL_COLUMNS, field, "categorical column");
    if (typeof value !== "string" || !column.all_categories.includes(value)) {
      throw new ValidationError(
        `${field} must be one of: ${column.all_categories.join(", ")}`,
        field,
      );
    }
    clean[field] = value;
  }

  return clean;
}

/**
 * Clamp every raw numeric input to the IQR bounds the training script applied. No training
 * row fell outside these, so this changes nothing for a plausible applicant; it exists so an
 * out-of-range submission degrades predictably instead of extrapolating silently.
 */
export function clampRawNumerics(row: Record<string, unknown>): RawNumerics {
  const clamped: RawNumerics = {};
  for (const field of RAW_NUMERIC_FIELDS) {
    const bound = must(OUTLIER_BOUNDS, field, "outlier bound");
    const value = row[field];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new ValidationError(`${field} must be a finite number`, field);
    }
    clamped[field] = Math.min(Math.max(value, bound.lower), bound.upper);
  }
  return clamped;
}

/**
 * Derive EMI and payment-to-income from the *clamped* values, per
 * `model_params.json.derived_features`. These two are never themselves clamped — the
 * training script created them after the capping step.
 */
export function deriveFeatures(clamped: RawNumerics): RawNumerics {
  const principal = must(clamped, "LoanAmount", "clamped value");
  const term = must(clamped, "LoanTerm", "clamped value");
  const income = must(clamped, "Income", "clamped value");
  const monthlyRate = must(clamped, "InterestRate", "clamped value") / 12 / 100;

  const emi =
    monthlyRate === 0
      ? principal / term
      : (principal * monthlyRate * Math.pow(1 + monthlyRate, term)) /
        (Math.pow(1 + monthlyRate, term) - 1);

  return {
    EstimatedEMI: emi,
    Payment_to_Income_Ratio: emi / (income + 1e-6),
  };
}

/**
 * Clamp, derive, standardise and one-hot encode into the 26-feature vector the model scores,
 * in `feature_order` order.
 */
export function buildFeatureVector(
  applicant: ApplicantInput,
  assignedInterestRate: number,
): FeatureVector {
  const clamped = clampRawNumerics({ ...applicant, InterestRate: assignedInterestRate });
  const derived = deriveFeatures(clamped);
  const numeric: RawNumerics = { ...clamped, ...derived };

  const encoded: FeatureVector = {};
  for (const field of CATEGORICAL_FIELDS) {
    const column = must(CATEGORICAL_COLUMNS, field, "categorical column");
    const category = applicant[field];
    const active = `${field}_${String(category)}`;
    for (const name of column.encoded_columns) {
      encoded[name] = name === active ? 1 : 0;
    }
    if (category !== column.dropped_category && !column.encoded_columns.includes(active)) {
      throw new ValidationError(`${field} has no encoded column for "${String(category)}"`, field);
    }
  }

  const vector: FeatureVector = {};
  for (const feature of FEATURE_ORDER) {
    if (NUMERIC_FEATURES.includes(feature)) {
      const value = must(numeric, feature, "numeric value");
      vector[feature] =
        (value - must(SCALER.mean, feature, "scaler mean")) /
        must(SCALER.scale, feature, "scaler scale");
    } else {
      vector[feature] = must(encoded, feature, "encoded value");
    }
  }
  return vector;
}

/** Numerically stable logistic function; `sigmoid(0)` is exactly 0.5. */
export function sigmoid(x: number): number {
  if (x >= 0) return 1 / (1 + Math.exp(-x));
  const e = Math.exp(x);
  return e / (1 + e);
}

export interface Score {
  logit: number;
  probability: number;
}

/** `P(default)` — a risk score. ADR-0007 approves at or below its threshold, not above. */
export function score(vector: FeatureVector): Score {
  let logit = INTERCEPT;
  for (const feature of FEATURE_ORDER) {
    logit += must(COEFFICIENTS, feature, "coefficient") * must(vector, feature, "feature value");
  }
  return { logit, probability: sigmoid(logit) };
}

export interface Contribution {
  feature: string;
  /** The standardised or one-hot value the model actually scored. */
  value: number;
  /** `coefficient x value` — this feature's exact share of the logit. */
  contribution: number;
}

/** Per-feature attribution for this decision, strongest absolute contribution first. */
export function attribute(vector: FeatureVector): Contribution[] {
  return FEATURE_ORDER.map((feature) => {
    const value = must(vector, feature, "feature value");
    return {
      feature,
      value,
      contribution: must(COEFFICIENTS, feature, "coefficient") * value,
    };
  }).sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
}

/**
 * Strip the protected bases before anything LLM-facing sees the attribution.
 *
 * ADR-0005 is explicit that this must be a filter in code, never a prompt instruction: `Age`
 * is the model's strongest single predictor and is a top-3 contributor in 76% of denials, so
 * "please don't mention it" would be relied on constantly and fail silently when it slipped.
 */
export function withoutProtectedFeatures(contributions: Contribution[]): Contribution[] {
  return contributions.filter((c) => !PROTECTED_FEATURES.includes(c.feature));
}
