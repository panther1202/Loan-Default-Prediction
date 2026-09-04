/**
 * Stage 1a demo: one approval and one denial, end to end, with no LLM involved.
 *
 * docs/IMPLEMENTATION_PLAN.md asks for each stage to be independently runnable and demoed
 * before the next starts. Run: `npm run demo`.
 */

import { type Assessment, DISCLAIMER, assess } from "./policy.js";

const BASE = {
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

const money = (value: number) =>
  value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function report(title: string, result: Assessment) {
  console.log(`\n=== ${title} ===`);
  console.log(
    `requested ${money(result.applicant.LoanAmount as number)} over ${result.termMonths} months`,
  );
  console.log(
    `credit band ${result.band} -> ${result.assignedApr.toFixed(1)}% APR (assigned by the rate card)`,
  );
  console.log(
    `P(default) ${result.probability.toFixed(4)} -> ${result.decision.toUpperCase()}`,
  );

  console.log("\ntop contributions as scored (internal, includes protected features):");
  for (const c of result.contributions.slice(0, 5)) {
    console.log(`  ${c.feature.padEnd(28)} ${c.contribution >= 0 ? "+" : ""}${c.contribution.toFixed(3)}`);
  }

  console.log("\ncitable drivers (protected features filtered out — what an explanation may use):");
  for (const c of result.citableContributions.slice(0, 5)) {
    console.log(`  ${c.feature.padEnd(28)} ${c.contribution >= 0 ? "+" : ""}${c.contribution.toFixed(3)}`);
  }

  if (result.decision === "deny") {
    console.log("\ncomputed suggestions (exact model arithmetic, not LLM guesses):");
    if (result.suggestions.length === 0) {
      console.log("  none — no single allow-listed change clears the threshold");
    }
    for (const s of result.suggestions) {
      const asMoney = s.feature === "LoanAmount";
      const from = asMoney ? money(s.currentValue as number) : String(s.currentValue);
      const to = asMoney ? money(s.suggestedValue as number) : String(s.suggestedValue);
      console.log(
        `  ${s.feature.padEnd(14)} ${from} -> ${to}   P(default) ${s.projectedProbability.toFixed(4)}`,
      );
    }
  }
}

report("Approval", assess(BASE));
report("Denial", assess({ ...BASE, MonthsEmployed: 36, LoanAmount: 90000 }));
report("Denial with nothing to suggest", assess({
  ...BASE,
  Age: 22,
  Income: 20000,
  LoanAmount: 200000,
  CreditScore: 420,
  MonthsEmployed: 1,
  NumCreditLines: 4,
  DTIRatio: 0.85,
  EmploymentType: "Unemployed",
  Education: "High School",
}));

console.log(`\n${DISCLAIMER}`);
