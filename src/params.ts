/**
 * Typed access to `model_params.json` — the exact export of the frozen sklearn model.
 *
 * Every data-derived constant in this project reads from here: coefficients, scaler
 * statistics, outlier bounds, category lists, feature count, credit-band breakpoints.
 * CLAUDE.md forbids hardcoding any of them, so that adding training data
 * (docs/adr/0009-training-data-source.md) is a re-run of `export_model_params.py` rather
 * than a rewrite. Policy numbers — the approval threshold, the APR per band — are not in
 * here; they live in `policy.ts` because they are decisions, not measurements.
 */

import raw from "../model_params.json";

export interface CategoricalColumn {
  all_categories: string[];
  dropped_category: string;
  encoded_columns: string[];
}

export interface OutlierBound {
  lower: number;
  upper: number;
}

const params = raw as unknown as {
  intercept: number;
  feature_order: string[];
  coefficients: Record<string, number>;
  numeric_features: string[];
  scaler: { mean: Record<string, number>; scale: Record<string, number> };
  categorical_columns: Record<string, CategoricalColumn>;
  outlier_bounds: { bounds: Record<string, OutlierBound> };
  credit_score_bands: { breakpoints: number[]; observed_range: [number, number] };
  compliance_flags: { protected_or_sensitive_input_features: string[] };
};

export const INTERCEPT = params.intercept;
export const FEATURE_ORDER = params.feature_order;
export const COEFFICIENTS = params.coefficients;
export const NUMERIC_FEATURES = params.numeric_features;
export const SCALER = params.scaler;
export const CATEGORICAL_COLUMNS = params.categorical_columns;
export const OUTLIER_BOUNDS = params.outlier_bounds.bounds;
export const CREDIT_BAND_BREAKPOINTS = params.credit_score_bands.breakpoints;
export const CREDIT_SCORE_OBSERVED_RANGE = params.credit_score_bands.observed_range;

/**
 * The features an explanation may never cite, per docs/adr/0005-ml-model-hosting.md:
 * `Age` (the model's largest-magnitude coefficient) and marital status are protected bases
 * under ECOA/Regulation B. Read from the export rather than retyped, so a re-export that
 * changes the feature set cannot leave a stale hardcoded list behind.
 */
export const PROTECTED_FEATURES = params.compliance_flags.protected_or_sensitive_input_features;

/** Look up a value that the export is required to contain, failing loudly if it does not. */
export function must<T>(record: Record<string, T>, key: string, what: string): T {
  const value = record[key];
  if (value === undefined) {
    throw new Error(`model_params.json is missing ${what} for "${key}"`);
  }
  return value;
}
