import { describe, expect, it } from "vitest";

import fixture from "../evals/parity_cases.json";
import { attribute, buildFeatureVector, score, validateApplicant } from "./pipeline.js";

/**
 * The check this whole stage exists to pass: does the TypeScript reimplementation produce
 * the same numbers as the sklearn artifacts it was derived from?
 *
 * Ground truth comes from `export_parity_cases.py`, which scores each case with the actual
 * pickled model, scaler and encoder. A mis-ordered one-hot column or a derived feature
 * computed before the clamp would sail past every other test in this repo and show up only
 * here — docs/IMPLEMENTATION_PLAN.md calls it out as the gate before Stage 2 for exactly
 * that reason.
 */
const TOLERANCE = 1e-12;

interface ParityCase {
  name: string;
  input: Record<string, number | string>;
  expected_probability: number;
  expected_features: Record<string, number>;
  expected_contributions: Record<string, number>;
}

const cases = fixture.cases as ParityCase[];

function relativeError(actual: number, expected: number): number {
  return Math.abs(actual - expected) / Math.max(Math.abs(expected), 1e-9);
}

describe("parity with the frozen sklearn model", () => {
  it("has a fixture covering the cases the training distribution does not", () => {
    expect(cases.length).toBeGreaterThanOrEqual(10);
    expect(fixture.feature_order).toHaveLength(26);
  });

  it.each(cases.map((c) => [c.name, c] as const))(
    "matches predict_proba for: %s",
    (_name, testCase) => {
      // The fixture carries InterestRate explicitly because it tests the model pipeline, not
      // ADR-0007's pricing; at request time the rate card supplies this argument instead.
      const { InterestRate, ...applicant } = testCase.input;
      const vector = buildFeatureVector(validateApplicant(applicant), InterestRate as number);

      for (const [feature, expected] of Object.entries(testCase.expected_features)) {
        expect(relativeError(vector[feature]!, expected), feature).toBeLessThan(TOLERANCE);
      }

      const result = score(vector);
      expect(relativeError(result.probability, testCase.expected_probability)).toBeLessThan(
        TOLERANCE,
      );

      // The attribution the explanation layer will cite, checked against sklearn's own
      // coef_ x X rather than against this repo's arithmetic.
      const contributions = Object.fromEntries(
        attribute(vector).map((c) => [c.feature, c.contribution]),
      );
      for (const [feature, expected] of Object.entries(testCase.expected_contributions)) {
        expect(relativeError(contributions[feature]!, expected), feature).toBeLessThan(TOLERANCE);
      }
    },
  );

  it("does not match when the pipeline is fed a different rate", () => {
    // Negative control. Without it, a comparison that silently always passed — an empty
    // fixture, a broken relative-error helper — would look identical to real parity.
    const [testCase] = cases;
    const { InterestRate, ...applicant } = testCase!.input;
    const wrong = score(
      buildFeatureVector(validateApplicant(applicant), (InterestRate as number) + 1),
    );
    expect(
      relativeError(wrong.probability, testCase!.expected_probability),
    ).toBeGreaterThan(TOLERANCE);
  });
});
