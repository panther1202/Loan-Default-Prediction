"""Recompute the frozen model's preprocessing constants from data/Loan_default.csv
and add the IQR outlier bounds that app.py applies before scaling.

app.py trains and pickles the model but never exported its preprocessing constants
in a runtime-readable form. model_params.json is that export. It was missing the
outlier-capping step, which app.py applies to the raw numeric columns *before* the
scaler is fit -- so a serving pipeline that skips capping diverges from the trained
model on any extreme input.

This script replays app.py's preprocessing exactly, asserts the scaler statistics it
derives match the ones already in model_params.json (proof the replay is faithful),
then writes the bounds into that file.

Run: py -3.13 export_model_params.py
"""

import json

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

CSV = "data/Loan_default.csv"
PARAMS = "model_params.json"

# app.py's list, in its order
SCALED = [
    "Age", "Income", "LoanAmount", "CreditScore", "MonthsEmployed",
    "NumCreditLines", "InterestRate", "LoanTerm", "DTIRatio",
    "EstimatedEMI", "Payment_to_Income_Ratio",
]

df = pd.read_csv(CSV)

# --- impute (app.py lines 42-72) ---
numeric_cols = [c for c in df.select_dtypes(include=np.number).columns if c != "Default"]
categorical_cols = [c for c in df.select_dtypes(include="object").columns if c != "LoanID"]
imputation = {}
for col in numeric_cols:
    if df[col].isnull().any():
        imputation[col] = float(df[col].median())
        df[col] = df[col].fillna(imputation[col])
for col in categorical_cols:
    if df[col].isnull().any():
        imputation[col] = df[col].mode()[0]
        df[col] = df[col].fillna(imputation[col])

# --- IQR outlier capping (app.py lines 80-102) ---
# Computed on the full dataset, before the train/test split and before the derived
# features exist -- so EstimatedEMI and Payment_to_Income_Ratio are NOT capped.
bounds = {}
for col in [c for c in numeric_cols if c not in ("LoanID", "Default")]:
    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    bounds[col] = {"lower": float(lower), "upper": float(upper)}
    df[col] = df[col].clip(lower, upper)

# --- derived features (app.py lines 120-138) ---
r = df["InterestRate"] / 12 / 100
n = df["LoanTerm"]
df["EstimatedEMI"] = np.where(
    r == 0,
    df["LoanAmount"] / n,
    df["LoanAmount"] * r * (1 + r) ** n / ((1 + r) ** n - 1),
)
df["EstimatedEMI"] = df["EstimatedEMI"].replace([np.inf, -np.inf], np.nan)
df["EstimatedEMI"] = df["EstimatedEMI"].fillna(df["EstimatedEMI"].median())
df["Payment_to_Income_Ratio"] = df["EstimatedEMI"] / (df["Income"] + 1e-6)

# --- split, then fit scaler on train only (app.py lines 167-198) ---
X = df.drop(columns=["LoanID", "Default"] + categorical_cols)
X_train, _ = train_test_split(
    X, test_size=0.2, random_state=42, stratify=df["Default"]
)
scaler = StandardScaler().fit(X_train[SCALED])

# --- verify the replay against the existing export ---
with open(PARAMS) as f:
    params = json.load(f)

for i, col in enumerate(SCALED):
    for stat, got in (("mean", scaler.mean_[i]), ("scale", scaler.scale_[i])):
        want = params["scaler"][stat][col]
        assert np.isclose(got, want, rtol=1e-9), (
            f"scaler.{stat}.{col}: replay {got!r} != model_params.json {want!r} -- "
            "preprocessing replay is not faithful, do not write the export"
        )
print(f"scaler parity OK: {len(SCALED)} features x 2 stats match model_params.json")

# --- write ---
params["outlier_bounds"] = {
    "note": (
        "IQR bounds (Q1-1.5*IQR, Q3+1.5*IQR) computed on the full dataset after "
        "median/mode imputation. app.py caps every raw numeric input to these bounds "
        "BEFORE deriving EstimatedEMI/Payment_to_Income_Ratio and before the scaler "
        "was fit, so a serving pipeline must clamp raw inputs to these bounds first or "
        "it diverges from the trained model on extreme inputs. EstimatedEMI and "
        "Payment_to_Income_Ratio are derived after capping and are themselves NOT capped."
    ),
    "bounds": bounds,
}
params["imputation_values"] = imputation
params["prediction_formula"] = (
    "clamp each raw numeric feature to outlier_bounds.bounds[f]; then derive "
    "EstimatedEMI and Payment_to_Income_Ratio from the clamped values; then "
    "p_default = sigmoid(intercept + sum(coefficients[f] * standardized_or_encoded_value[f] "
    "for f in feature_order)); standardize numeric features as "
    "(clamped_or_derived - scaler.mean[f]) / scaler.scale[f]; categorical dummy value is "
    "1.0 if that category is present else 0.0, and the dropped_category for each column "
    "maps to all-zeros."
)

with open(PARAMS, "w") as f:
    json.dump(params, f, indent=2)
    f.write("\n")
print(f"wrote {PARAMS}: outlier_bounds ({len(bounds)} features), imputation_values ({len(imputation)})")
