import { describe, expect, it } from "vitest";

import {
  CATEGORICAL_COLUMNS,
  COEFFICIENTS,
  CREDIT_BAND_BREAKPOINTS,
  FEATURE_ORDER,
  INTERCEPT,
  NUMERIC_FEATURES,
  OUTLIER_BOUNDS,
  PROTECTED_FEATURES,
  SCALER,
} from "./params.js";

// These guard a future re-export (docs/adr/0008-model-change-policy.md permits one after
// approval). Nothing downstream re-derives these numbers, so a truncated or reordered
// export would otherwise surface as subtly wrong probabilities rather than as a failure.
describe("model parameter export integrity", () => {
  it("exposes exactly the 26 features the model was trained on", () => {
    expect(FEATURE_ORDER).toHaveLength(26);
    expect(new Set(FEATURE_ORDER).size).toBe(26);
  });

  it("has a coefficient for every feature and no orphans", () => {
    expect(Object.keys(COEFFICIENTS).sort()).toEqual([...FEATURE_ORDER].sort());
    expect(Number.isFinite(INTERCEPT)).toBe(true);
  });

  it("has scaler statistics for all 11 numeric features, with non-zero scales", () => {
    expect(NUMERIC_FEATURES).toHaveLength(11);
    for (const feature of NUMERIC_FEATURES) {
      expect(SCALER.mean[feature]).toBeTypeOf("number");
      expect(SCALER.scale[feature]).toBeGreaterThan(0);
    }
  });

  it("declares every numeric feature in feature order, ahead of the dummies", () => {
    expect(FEATURE_ORDER.slice(0, NUMERIC_FEATURES.length)).toEqual(NUMERIC_FEATURES);
  });

  it("maps each categorical column onto encoded columns that exist in feature order", () => {
    for (const [column, spec] of Object.entries(CATEGORICAL_COLUMNS)) {
      expect(spec.all_categories).toContain(spec.dropped_category);
      expect(spec.encoded_columns).toHaveLength(spec.all_categories.length - 1);
      for (const encoded of spec.encoded_columns) {
        expect(FEATURE_ORDER, `${column} -> ${encoded}`).toContain(encoded);
      }
    }
  });

  it("carries outlier bounds for the raw numeric inputs, but not the derived ones", () => {
    expect(Object.keys(OUTLIER_BOUNDS)).toHaveLength(9);
    expect(OUTLIER_BOUNDS).not.toHaveProperty("EstimatedEMI");
    expect(OUTLIER_BOUNDS).not.toHaveProperty("Payment_to_Income_Ratio");
    for (const bound of Object.values(OUTLIER_BOUNDS)) {
      expect(bound.upper).toBeGreaterThan(bound.lower);
    }
  });

  it("carries four ascending credit-score band breakpoints", () => {
    expect(CREDIT_BAND_BREAKPOINTS).toHaveLength(4);
    expect([...CREDIT_BAND_BREAKPOINTS].sort((a, b) => a - b)).toEqual(CREDIT_BAND_BREAKPOINTS);
  });

  it("names the protected features that explanations may never cite", () => {
    expect(PROTECTED_FEATURES).toEqual(
      expect.arrayContaining(["Age", "MaritalStatus_Married", "MaritalStatus_Single"]),
    );
    for (const feature of PROTECTED_FEATURES) {
      expect(FEATURE_ORDER).toContain(feature);
    }
  });
});
