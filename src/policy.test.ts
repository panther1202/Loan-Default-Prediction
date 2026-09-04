import { describe, expect, it } from "vitest";

import { CREDIT_BAND_BREAKPOINTS, CREDIT_SCORE_OBSERVED_RANGE } from "./params.js";
import { buildFeatureVector, score, validateApplicant } from "./pipeline.js";
import {
  APPROVAL_THRESHOLD,
  RATE_CARD_APR,
  SUGGESTION_ALLOW_LIST,
  TERM_OPTIONS,
  assess,
  assignedApr,
  creditBand,
  decide,
} from "./policy.js";

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

/** A denial close enough to the threshold that a single allow-listed lever can still fix it. */
const DENIED = { ...APPLICANT, MonthsEmployed: 36, LoanAmount: 90000 };

/** Denied with a co-signer already in place — the co-signer lever must not be offered again. */
const DENIED_WITH_COSIGNER = {
  ...APPLICANT,
  MonthsEmployed: 24,
  LoanAmount: 120000,
  HasCoSigner: "Yes",
};

/**
 * Far enough above the threshold that no single allow-listed change rescues it. ADR-0007
 * measured the best single lever at rescuing 23.1% of denials, so this is the common case,
 * not a contrived one.
 */
const HOPELESS = {
  ...APPLICANT,
  Age: 22,
  Income: 20000,
  LoanAmount: 200000,
  CreditScore: 420,
  MonthsEmployed: 1,
  NumCreditLines: 4,
  DTIRatio: 0.85,
  EmploymentType: "Unemployed",
  Education: "High School",
};

describe("rate card", () => {
  it("has one APR per band, spanning ADR-0007's 400bps spread", () => {
    expect(RATE_CARD_APR).toHaveLength(CREDIT_BAND_BREAKPOINTS.length + 1);
    expect(RATE_CARD_APR).toEqual([11.0, 10.0, 9.0, 8.0, 7.0]);
  });

  it("offers exactly the terms the dataset was trained over", () => {
    expect(TERM_OPTIONS).toEqual([12, 24, 36, 48, 60]);
  });

  it("treats each exported breakpoint as the floor of its band", () => {
    // Breakpoints come from model_params.json, so this keeps holding after a re-export with
    // different quintiles rather than pinning today's 409/519/629/740.
    CREDIT_BAND_BREAKPOINTS.forEach((breakpoint, index) => {
      expect(creditBand(breakpoint), `at ${breakpoint}`).toBe(index + 1);
      expect(creditBand(breakpoint - 1), `just below ${breakpoint}`).toBe(index);
    });
  });

  it("places the ends of the observed range in the bottom and top bands", () => {
    const [low, high] = CREDIT_SCORE_OBSERVED_RANGE;
    expect(creditBand(low)).toBe(0);
    expect(creditBand(high)).toBe(RATE_CARD_APR.length - 1);
    expect(assignedApr(low)).toBe(11.0);
    expect(assignedApr(high)).toBe(7.0);
  });

  it("never charges a better score a worse rate", () => {
    const rates = CREDIT_BAND_BREAKPOINTS.map((b) => assignedApr(b));
    expect(rates).toEqual([...rates].sort((a, b) => b - a));
  });

  it("does not vary the rate by requested term", () => {
    // ADR-0007 Evidence 2: the proposed longer-term surcharge was worth 6.5bps of P(default)
    // and taxed the direction that was already worse, so it was dropped.
    const short = assess({ ...APPLICANT, LoanTerm: 12 });
    const long = assess({ ...APPLICANT, LoanTerm: 60 });
    expect(short.assignedApr).toBe(long.assignedApr);
  });
});

describe("decide", () => {
  it("approves exactly at the threshold, not just below it", () => {
    expect(decide(APPROVAL_THRESHOLD)).toBe("approve");
  });

  it("denies just above the threshold", () => {
    expect(decide(APPROVAL_THRESHOLD + Number.EPSILON)).toBe("deny");
  });

  it("reads P(default) as risk, so a low score approves and a high one denies", () => {
    expect(decide(0.01)).toBe("approve");
    expect(decide(0.99)).toBe("deny");
  });
});

describe("assess", () => {
  it("scores the applicant at the rate the card assigned, not at any submitted rate", () => {
    const result = assess(APPLICANT);
    const expected = score(
      buildFeatureVector(validateApplicant(APPLICANT), assignedApr(APPLICANT.CreditScore)),
    );
    expect(result.assignedApr).toBe(assignedApr(APPLICANT.CreditScore));
    expect(result.probability).toBe(expected.probability);
  });

  it("echoes the applicant's requested term rather than choosing one", () => {
    expect(assess({ ...APPLICANT, LoanTerm: 48 }).termMonths).toBe(48);
  });

  it("never exposes a protected feature in the citable attribution", () => {
    const result = assess({ ...APPLICANT, Age: 19 });
    const citable = result.citableContributions.map((c) => c.feature);
    expect(citable).not.toContain("Age");
    expect(citable).not.toContain("MaritalStatus_Married");
    expect(citable).not.toContain("MaritalStatus_Single");
    expect(result.contributions.map((c) => c.feature)).toContain("Age");
  });

  it("suggests nothing on an approval", () => {
    const result = assess(APPLICANT);
    expect(result.decision).toBe("approve");
    expect(result.suggestions).toEqual([]);
  });
});

describe("denial suggestions", () => {
  const denial = assess(DENIED);

  it("reaches the denial path at all", () => {
    expect(denial.decision).toBe("deny");
  });

  it("only ever references allow-listed features", () => {
    // Hard gate in docs/TEST_STRATEGY.md: LoanTerm is deliberately absent, because on this
    // model extending it flips 0.9% of denials and only shortening helps.
    for (const suggestion of denial.suggestions) {
      expect(SUGGESTION_ALLOW_LIST).toContain(suggestion.feature);
    }
    expect(SUGGESTION_ALLOW_LIST).not.toContain("LoanTerm");
    expect(SUGGESTION_ALLOW_LIST).not.toContain("Age");
    expect(SUGGESTION_ALLOW_LIST).not.toContain("MaritalStatus");
    expect(SUGGESTION_ALLOW_LIST).not.toContain("EmploymentType");
    expect(SUGGESTION_ALLOW_LIST).not.toContain("Education");
  });

  it("returns suggestions that actually clear the threshold when applied", () => {
    expect(denial.suggestions.length).toBeGreaterThan(0);
    for (const suggestion of denial.suggestions) {
      const applied = assess({ ...DENIED, [suggestion.feature]: suggestion.suggestedValue });
      expect(applied.probability, suggestion.feature).toBeLessThanOrEqual(APPROVAL_THRESHOLD);
      expect(applied.decision, suggestion.feature).toBe("approve");
    }
  });

  it("moves each lever in the helpful direction only", () => {
    for (const suggestion of denial.suggestions) {
      if (suggestion.feature === "LoanAmount") {
        expect(suggestion.suggestedValue).toBeLessThan(DENIED.LoanAmount);
      }
      if (suggestion.feature === "CreditScore") {
        expect(suggestion.suggestedValue).toBeGreaterThan(DENIED.CreditScore);
      }
      if (suggestion.feature === "HasCoSigner") {
        expect(suggestion.suggestedValue).toBe("Yes");
      }
    }
  });

  it("offers no co-signer suggestion to an applicant who already has one", () => {
    const result = assess(DENIED_WITH_COSIGNER);
    expect(result.decision).toBe("deny");
    expect(result.suggestions.length).toBeGreaterThan(0);
    expect(result.suggestions.map((s) => s.feature)).not.toContain("HasCoSigner");
  });

  it("stays silent when no single allow-listed lever can rescue the applicant", () => {
    // A denial nothing can fix must return no suggestion rather than an invented number:
    // the applicant is told the truth or told nothing.
    const result = assess(HOPELESS);
    expect(result.decision).toBe("deny");
    expect(result.suggestions).toEqual([]);
  });
});
