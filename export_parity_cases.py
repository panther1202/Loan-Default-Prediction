"""Score a fixed set of applicant rows with the actual pickled sklearn artifacts and write
them to evals/parity_cases.json as the ground truth for the TypeScript pipeline.

Stage 1a reimplements the frozen model's preprocessing and scoring in TypeScript from
model_params.json. A silent mismatch there -- one mis-ordered one-hot column, a derived
feature computed before the outlier clamp instead of after -- would make every downstream
explanation wrong in a way that inspection would not catch. The only honest check is to
compare against sklearn itself, so this script produces expectations from the .pkl files
rather than from anyone's arithmetic.

Read-only with respect to ADR-0008: it loads the frozen model, scaler and encoder and
writes only evals/parity_cases.json.

Run: py -3.13 export_parity_cases.py
"""

import json

import joblib
import numpy as np
import pandas as pd

MODEL = "logistic_regression_loan_default_model.pkl"
SCALER = "default_feature_scaler.pkl"
ENCODER = "default_one_hot_encoder.pkl"
FEATURE_NAMES = "default_model_feature_names.pkl"
PARAMS = "model_params.json"
OUT = "evals/parity_cases.json"

# The 9 raw numeric columns app.py clamps to IQR bounds, before the derived features exist.
RAW_NUMERIC = [
    "Age", "Income", "LoanAmount", "CreditScore", "MonthsEmployed",
    "NumCreditLines", "InterestRate", "LoanTerm", "DTIRatio",
]
CATEGORICAL = [
    "Education", "EmploymentType", "MaritalStatus",
    "HasMortgage", "HasDependents", "LoanPurpose", "HasCoSigner",
]

# Hand-authored rather than sampled from data/Loan_default.csv: the cases that matter for
# parity are the ones the training distribution does not contain -- values outside the IQR
# bounds, a zero interest rate, each categorical column at both its dropped reference
# category and a non-dropped one. `InterestRate` is carried explicitly here even though the
# rate card assigns it at request time, because this fixture tests the model pipeline, not
# ADR-0007's pricing policy; the card is unit-tested separately.
CASES = [
    {
        "name": "top-band, low risk, all dropped categories",
        "input": {
            "Age": 45, "Income": 120000, "LoanAmount": 20000, "CreditScore": 800,
            "MonthsEmployed": 90, "NumCreditLines": 2, "InterestRate": 7.0,
            "LoanTerm": 36, "DTIRatio": 0.2,
            "Education": "Bachelor's", "EmploymentType": "Full-time",
            "MaritalStatus": "Divorced", "HasMortgage": "No", "HasDependents": "No",
            "LoanPurpose": "Auto", "HasCoSigner": "No",
        },
    },
    {
        "name": "band 629-739, mid profile",
        "input": {
            "Age": 38, "Income": 65000, "LoanAmount": 45000, "CreditScore": 700,
            "MonthsEmployed": 40, "NumCreditLines": 3, "InterestRate": 8.0,
            "LoanTerm": 48, "DTIRatio": 0.45,
            "Education": "Master's", "EmploymentType": "Self-employed",
            "MaritalStatus": "Married", "HasMortgage": "Yes", "HasDependents": "Yes",
            "LoanPurpose": "Home", "HasCoSigner": "Yes",
        },
    },
    {
        "name": "band 519-628, PhD, business loan",
        "input": {
            "Age": 52, "Income": 90000, "LoanAmount": 150000, "CreditScore": 560,
            "MonthsEmployed": 110, "NumCreditLines": 1, "InterestRate": 9.0,
            "LoanTerm": 60, "DTIRatio": 0.6,
            "Education": "PhD", "EmploymentType": "Part-time",
            "MaritalStatus": "Single", "HasMortgage": "No", "HasDependents": "Yes",
            "LoanPurpose": "Business", "HasCoSigner": "No",
        },
    },
    {
        "name": "band 409-518, high school, unemployed",
        "input": {
            "Age": 24, "Income": 22000, "LoanAmount": 90000, "CreditScore": 450,
            "MonthsEmployed": 3, "NumCreditLines": 4, "InterestRate": 10.0,
            "LoanTerm": 24, "DTIRatio": 0.8,
            "Education": "High School", "EmploymentType": "Unemployed",
            "MaritalStatus": "Married", "HasMortgage": "Yes", "HasDependents": "No",
            "LoanPurpose": "Education", "HasCoSigner": "Yes",
        },
    },
    {
        "name": "bottom band, high risk",
        "input": {
            "Age": 19, "Income": 16000, "LoanAmount": 240000, "CreditScore": 310,
            "MonthsEmployed": 0, "NumCreditLines": 4, "InterestRate": 11.0,
            "LoanTerm": 12, "DTIRatio": 0.9,
            "Education": "High School", "EmploymentType": "Unemployed",
            "MaritalStatus": "Single", "HasMortgage": "No", "HasDependents": "Yes",
            "LoanPurpose": "Other", "HasCoSigner": "No",
        },
    },
    {
        "name": "zero interest rate -- exercises the EMI LoanAmount/LoanTerm branch",
        "input": {
            "Age": 40, "Income": 70000, "LoanAmount": 36000, "CreditScore": 650,
            "MonthsEmployed": 60, "NumCreditLines": 2, "InterestRate": 0.0,
            "LoanTerm": 36, "DTIRatio": 0.3,
            "Education": "Bachelor's", "EmploymentType": "Full-time",
            "MaritalStatus": "Divorced", "HasMortgage": "No", "HasDependents": "No",
            "LoanPurpose": "Auto", "HasCoSigner": "No",
        },
    },
    {
        "name": "out of range low -- Age 5, Income below the lower bound",
        "input": {
            "Age": 5, "Income": -5000, "LoanAmount": 1000, "CreditScore": 100,
            "MonthsEmployed": -10, "NumCreditLines": 0, "InterestRate": 1.0,
            "LoanTerm": 6, "DTIRatio": 0.0,
            "Education": "Bachelor's", "EmploymentType": "Full-time",
            "MaritalStatus": "Divorced", "HasMortgage": "No", "HasDependents": "No",
            "LoanPurpose": "Auto", "HasCoSigner": "No",
        },
    },
    {
        "name": "out of range high -- Age 200, Income and LoanAmount above the upper bound",
        "input": {
            "Age": 200, "Income": 5000000, "LoanAmount": 9000000, "CreditScore": 2000,
            "MonthsEmployed": 900, "NumCreditLines": 40, "InterestRate": 95.0,
            "LoanTerm": 480, "DTIRatio": 5.0,
            "Education": "PhD", "EmploymentType": "Self-employed",
            "MaritalStatus": "Married", "HasMortgage": "Yes", "HasDependents": "Yes",
            "LoanPurpose": "Business", "HasCoSigner": "Yes",
        },
    },
    {
        "name": "categorical sweep A -- Master's / Part-time / Married / Home",
        "input": {
            "Age": 33, "Income": 55000, "LoanAmount": 30000, "CreditScore": 620,
            "MonthsEmployed": 25, "NumCreditLines": 2, "InterestRate": 9.0,
            "LoanTerm": 36, "DTIRatio": 0.5,
            "Education": "Master's", "EmploymentType": "Part-time",
            "MaritalStatus": "Married", "HasMortgage": "Yes", "HasDependents": "No",
            "LoanPurpose": "Home", "HasCoSigner": "Yes",
        },
    },
    {
        "name": "categorical sweep B -- High School / Unemployed / Single / Education",
        "input": {
            "Age": 60, "Income": 45000, "LoanAmount": 12000, "CreditScore": 530,
            "MonthsEmployed": 100, "NumCreditLines": 1, "InterestRate": 9.0,
            "LoanTerm": 12, "DTIRatio": 0.35,
            "Education": "High School", "EmploymentType": "Unemployed",
            "MaritalStatus": "Single", "HasMortgage": "No", "HasDependents": "Yes",
            "LoanPurpose": "Education", "HasCoSigner": "No",
        },
    },
    {
        "name": "categorical sweep C -- PhD / Self-employed / Divorced / Other",
        "input": {
            "Age": 47, "Income": 135000, "LoanAmount": 75000, "CreditScore": 745,
            "MonthsEmployed": 80, "NumCreditLines": 3, "InterestRate": 7.0,
            "LoanTerm": 60, "DTIRatio": 0.25,
            "Education": "PhD", "EmploymentType": "Self-employed",
            "MaritalStatus": "Divorced", "HasMortgage": "Yes", "HasDependents": "Yes",
            "LoanPurpose": "Other", "HasCoSigner": "Yes",
        },
    },
    {
        "name": "borderline -- near the 0.37 approval threshold",
        "input": {
            "Age": 35, "Income": 80000, "LoanAmount": 60000, "CreditScore": 640,
            "MonthsEmployed": 30, "NumCreditLines": 2, "InterestRate": 8.0,
            "LoanTerm": 36, "DTIRatio": 0.55,
            "Education": "Bachelor's", "EmploymentType": "Full-time",
            "MaritalStatus": "Single", "HasMortgage": "No", "HasDependents": "No",
            "LoanPurpose": "Auto", "HasCoSigner": "No",
        },
    },
]


def build_row(raw, bounds):
    """Replay app.py's preprocessing for one applicant: clamp, then derive, then encode."""
    row = dict(raw)
    for col in RAW_NUMERIC:
        b = bounds[col]
        row[col] = float(min(max(row[col], b["lower"]), b["upper"]))

    r = row["InterestRate"] / 12 / 100
    n = row["LoanTerm"]
    if r == 0:
        emi = row["LoanAmount"] / n
    else:
        emi = row["LoanAmount"] * r * (1 + r) ** n / ((1 + r) ** n - 1)
    row["EstimatedEMI"] = emi
    row["Payment_to_Income_Ratio"] = emi / (row["Income"] + 1e-6)
    return row


def main():
    model = joblib.load(MODEL)
    scaler = joblib.load(SCALER)
    encoder = joblib.load(ENCODER)
    feature_names = joblib.load(FEATURE_NAMES)

    with open(PARAMS) as f:
        bounds = json.load(f)["outlier_bounds"]["bounds"]

    scaled_cols = list(scaler.feature_names_in_)
    encoder_cols = list(encoder.feature_names_in_)
    coefs = model.coef_[0]

    out = []
    for case in CASES:
        row = build_row(case["input"], bounds)

        encoded = encoder.transform(pd.DataFrame([{c: row[c] for c in encoder_cols}]))
        encoded_names = list(encoder.get_feature_names_out(encoder_cols))

        frame = pd.DataFrame([{c: row[c] for c in scaled_cols}])
        frame[scaled_cols] = scaler.transform(frame[scaled_cols])
        for name, value in zip(encoded_names, encoded[0]):
            frame[name] = value
        frame = frame[feature_names]

        probability = float(model.predict_proba(frame)[0, 1])
        values = frame.iloc[0].to_numpy(dtype=float)
        contributions = {
            name: float(coefs[i] * values[i]) for i, name in enumerate(feature_names)
        }

        # Independent check that this frame really is what the model scored: the manual
        # logit must reproduce sklearn's probability. Catches a column-order slip in this
        # script itself, which would otherwise be baked into the fixture as truth.
        logit = float(model.intercept_[0] + sum(contributions.values()))
        assert np.isclose(1 / (1 + np.exp(-logit)), probability, rtol=1e-12), (
            f"{case['name']}: manual logit disagrees with predict_proba"
        )

        out.append({
            "name": case["name"],
            "input": case["input"],
            "expected_probability": probability,
            "expected_features": {
                name: float(values[i]) for i, name in enumerate(feature_names)
            },
            "expected_contributions": contributions,
        })

    with open(OUT, "w") as f:
        json.dump({
            "note": (
                "Ground truth for the TypeScript Stage 1a pipeline, produced by "
                "export_parity_cases.py from the frozen .pkl artifacts. `input` is the raw "
                "applicant payload; `expected_features` is the 26-value model input after "
                "clamping, derivation, scaling and one-hot encoding; `expected_contributions` "
                "is coefficient x value per feature. Regenerate whenever the model changes, "
                "per docs/adr/0008-model-change-policy.md."
            ),
            "sklearn_model": MODEL,
            "feature_order": list(feature_names),
            "cases": out,
        }, f, indent=2)
        f.write("\n")
    print(f"wrote {OUT}: {len(out)} cases, {len(feature_names)} features each")


if __name__ == "__main__":
    main()
