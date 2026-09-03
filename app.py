import warnings

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, \
    roc_curve
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import OneHotEncoder
# from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV  # To get probabilities

# Load the new dataset for default prediction
try:
    df_default = pd.read_csv('data/Loan_default.csv')
    print("Loan_default.csv loaded successfully.")
except FileNotFoundError:
    print("Error: 'Loan_default.csv' not found. Please ensure the dataset is in the correct directory.")
    exit()

print("\n--- Initial Data Inspection (Loan Default Data) ---")
print(df_default.head())

print("\n--- Loan Default DataFrame Info ---")
df_default.info()

print("\n--- Loan Default Descriptive Statistics ---")
print(df_default.describe())

print("\n--- Loan Default Missing Values Count ---")
print(df_default.isnull().sum())

# Separate numerical and categorical columns for imputation strategies
numerical_cols_default = df_default.select_dtypes(include=np.number).columns.tolist()
categorical_cols_default = df_default.select_dtypes(include='object').columns.tolist()

# The target variable 'Default' should not be in features for imputation
if 'Default' in numerical_cols_default:
    numerical_cols_default.remove('Default')
# 'LoanID' is just an identifier, not a feature for imputation
if 'LoanID' in categorical_cols_default:
    categorical_cols_default.remove('LoanID')


print(f"\nNumerical columns (Default Data): {numerical_cols_default}")
print(f"Categorical columns (Default Data): {categorical_cols_default}")

# Store imputation values from this dataset
imputation_values_default = {}

# Impute numerical missing values with the median
print("\n--- Imputing Loan Default Data ---")
for col in numerical_cols_default:
    if df_default[col].isnull().any():
        median_val = df_default[col].median()
        df_default[col].fillna(median_val, inplace=True)
        imputation_values_default[col] = median_val
        print(f"Filled missing values in '{col}' with median: {median_val}")

# Impute categorical missing values with the mode
for col in categorical_cols_default:
    if df_default[col].isnull().any():
        mode_val = df_default[col].mode()[0]
        df_default[col].fillna(mode_val, inplace=True)
        imputation_values_default[col] = mode_val
        print(f"Filled missing values in '{col}' with mode: {mode_val}")

print("\n--- Missing Values in Loan Default Data After Imputation ---")
print(df_default.isnull().sum())

# Identify numerical columns for outlier detection (excluding 'LoanID' and 'Default')
numeric_features_for_outliers_default = [col for col in numerical_cols_default if col not in ['LoanID', 'Default']]

print(f"\nChecking for outliers in (Loan Default Data): {numeric_features_for_outliers_default}")

# Store outlier bounds
outlier_bounds_default = {}

for col in numeric_features_for_outliers_default:
    Q1 = df_default[col].quantile(0.25)
    Q3 = df_default[col].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    outlier_bounds_default[col] = {'lower': lower_bound, 'upper': upper_bound}

    # Apply capping to data
    outliers_count = df_default[(df_default[col] < lower_bound) | (df_default[col] > upper_bound)].shape[0]
    if outliers_count > 0:
        df_default[col] = np.where(df_default[col] < lower_bound, lower_bound, df_default[col])
        df_default[col] = np.where(df_default[col] > upper_bound, upper_bound, df_default[col])
        print(f"Outliers in '{col}' capped at [{lower_bound:.2f}, {upper_bound:.2f}] (Count: {outliers_count})")
    else:
        print(f"Column '{col}' has no significant outliers (using IQR method).")

# Visualize distributions after outlier treatment
plt.figure(figsize=(18, 10))
for i, col in enumerate(numeric_features_for_outliers_default):
    plt.subplot(3, 4, i + 1)  # Adjust subplot grid based on number of columns
    sns.histplot(df_default[col], kde=True)
    plt.title(f'Distribution of {col} (Post-Outlier Treatment)')
plt.tight_layout()
plt.show()

# Calculate estimated monthly EMI (simplified, without accounting for compounding period accurately)
# A common formula for EMI: P * r * (1 + r)^n / ((1 + r)^n - 1)
# P = Principal Loan Amount
# r = Monthly Interest Rate (Annual Interest Rate / 12 / 100)
# n = Loan Term in Months
df_default['MonthlyInterestRate'] = df_default['InterestRate'] / 12 / 100
df_default['LoanTermMonths'] = df_default['LoanTerm']  # Assuming LoanTerm is already in months

# Handle cases where MonthlyInterestRate or LoanTermMonths might be 0 or cause division by zero
# If InterestRate is 0, EMI is just LoanAmount / LoanTerm
# Else, use the formula
df_default['EstimatedEMI'] = df_default.apply(
    lambda row: row['LoanAmount'] / row['LoanTermMonths'] if row['MonthlyInterestRate'] == 0 else
    row['LoanAmount'] * row['MonthlyInterestRate'] * (1 + row['MonthlyInterestRate'])**row['LoanTermMonths'] /
    ((1 + row['MonthlyInterestRate'])**row['LoanTermMonths'] - 1), axis=1
)

# Handle potential NaN/Inf from EMI calculation (e.g., if LoanTerm is very small or zero)
df_default['EstimatedEMI'].replace([np.inf, -np.inf], np.nan, inplace=True)
df_default['EstimatedEMI'].fillna(df_default['EstimatedEMI'].median(), inplace=True)  # Impute with median if any NaN/Inf result

# Create Payment-to-Income Ratio
# Add a small epsilon to Income to prevent division by zero for DTIRatio and Payment_to_Income_Ratio
df_default['Payment_to_Income_Ratio'] = df_default['EstimatedEMI'] / (df_default['Income'] + 1e-6)

print("\nCreated 'EstimatedEMI' and 'Payment_to_Income_Ratio' features.")
print("\n--- Loan Default DataFrame after Feature Engineering ---")
print(df_default.head())

# Identify categorical columns for encoding (excluding 'LoanID' and 'Default')
categorical_features_to_encode_default = [col for col in df_default.select_dtypes(include='object').columns if col not in ['LoanID', 'Default']]
print(f"\nCategorical features to encode: {categorical_features_to_encode_default}")

# Initialize OneHotEncoder
encoder_default = OneHotEncoder(handle_unknown='ignore', sparse_output=False, drop='first')

# Fit encoder on the data and transform
encoded_features_default = encoder_default.fit_transform(df_default[categorical_features_to_encode_default])
encoded_feature_names_default = encoder_default.get_feature_names_out(categorical_features_to_encode_default)
df_default_encoded_part = pd.DataFrame(encoded_features_default, columns=encoded_feature_names_default, index=df_default.index)

# Drop original categorical columns and concatenate encoded features
df_default_processed = df_default.drop(columns=categorical_features_to_encode_default)
df_default_processed = pd.concat([df_default_processed, df_default_encoded_part], axis=1)

print("\n--- Loan Default DataFrame after One-Hot Encoding ---")
print(df_default_processed.head())

print("\n--- Final Loan Default DataFrame Info before Modeling ---")
df_default_processed.info()

# Define features (X) and target (y)
X_default = df_default_processed.drop(['LoanID', 'Default', 'MonthlyInterestRate', 'LoanTermMonths'], axis=1)
y_default = df_default_processed['Default']

# Split the data into training and testing sets for default prediction
# Use stratify=y_default due to potential class imbalance
X_train_default, X_test_default, y_train_default, y_test_default = train_test_split(
    X_default, y_default, test_size=0.2, random_state=42, stratify=y_default
)

print(f"\nTraining set size (Default): {X_train_default.shape[0]} samples")
print(f"Testing set size (Default): {X_test_default.shape[0]} samples")
print(f"Target distribution in training set (Default):\n{y_train_default.value_counts(normalize=True)}")
print(f"Target distribution in testing set (Default):\n{y_test_default.value_counts(normalize=True)}")

# Identify numerical features to scale in the X_default dataframe
# These are the ones that were not one-hot encoded or identifiers/target.
numerical_features_to_scale_default = [
    'Age', 'Income', 'LoanAmount', 'CreditScore', 'MonthsEmployed',
    'NumCreditLines', 'InterestRate', 'LoanTerm', 'DTIRatio',
    'EstimatedEMI', 'Payment_to_Income_Ratio'
]

# Filter to ensure only columns present in X_train_default are considered
numerical_features_to_scale_default = [col for col in numerical_features_to_scale_default if col in X_train_default.columns]

scaler_default = StandardScaler()

# Fit the scaler on the training data and transform both training and testing data
X_train_default[numerical_features_to_scale_default] = scaler_default.fit_transform(X_train_default[numerical_features_to_scale_default])
X_test_default[numerical_features_to_scale_default] = scaler_default.transform(X_test_default[numerical_features_to_scale_default])

print("\n--- Features Scaled (X_train_default head) ---")
print(X_train_default.head())

warnings.filterwarnings('ignore')  # Suppress warnings

# Initialize models
models_default = {
    'Logistic Regression': LogisticRegression(random_state=42, solver='liblinear', class_weight='balanced'),  # Add class_weight for imbalance
    'K-Nearest Neighbour': KNeighborsClassifier(),
    # 'Support Vector Machine': SVC(probability=True, random_state=42, class_weight='balanced'),  # Add class_weight
    'Naive Bayes': GaussianNB(),
    'Decision Tree': DecisionTreeClassifier(random_state=42, class_weight='balanced'),  # Add class_weight
    'Random Forest': RandomForestClassifier(random_state=42, class_weight='balanced'),  # Add class_weight
    'Gradient Boosting': GradientBoostingClassifier(random_state=42),  # Gradient Boosting handles imbalance internally somewhat
    # 'Linear SVM': LinearSVC(random_state=42, class_weight='balanced', max_iter=10000, dual=False),  # dual=False recommended for n_samples > n_features
    'Linear SVM (Calibrated)': CalibratedClassifierCV(LinearSVC(random_state=42, class_weight='balanced', max_iter=10000, dual=False), method='isotonic', cv=5)
}

results_default = {}
roc_curves_default = {}
best_model_name_default = ''
best_roc_auc_default = -1

print("\n--- Model Training and Evaluation for Default Prediction ---")
for name, model in models_default.items():
    print(f"\nTraining {name}...")
    model.fit(X_train_default, y_train_default)
    y_pred_default = model.predict(X_test_default)
    y_proba_default = model.predict_proba(X_test_default)[:, 1]  # Probability of defaulting

    accuracy = accuracy_score(y_test_default, y_pred_default)
    precision = precision_score(y_test_default, y_pred_default, zero_division=0)
    recall = recall_score(y_test_default, y_pred_default, zero_division=0)
    f1 = f1_score(y_test_default, y_pred_default, zero_division=0)
    roc_auc = roc_auc_score(y_test_default, y_proba_default)
    cm = confusion_matrix(y_test_default, y_pred_default)

    results_default[name] = {
        'Accuracy': accuracy,
        'Precision': precision,
        'Recall': recall,
        'F1-Score': f1,
        'ROC-AUC': roc_auc,
        'Confusion Matrix': cm
    }

    fpr, tpr, _ = roc_curve(y_test_default, y_proba_default)
    roc_curves_default[name] = {'fpr': fpr, 'tpr': tpr}

    print(f"{name} Results (Test Set):")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  F1-Score: {f1:.4f}")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  Confusion Matrix:\n{cm}")

    if roc_auc > best_roc_auc_default:
        best_roc_auc_default = roc_auc
        best_model_name_default = name

# Summarize results in a DataFrame
results_df_default = pd.DataFrame.from_dict(results_default, orient='index')
print("\n--- Summary of Model Performance (Loan Default Prediction) ---")
print(results_df_default[['Accuracy', 'Precision', 'Recall', 'F1-Score', 'ROC-AUC']].sort_values(by='ROC-AUC', ascending=False))

# Plot ROC Curves
plt.figure(figsize=(10, 8))
for name, curve_data in roc_curves_default.items():
    plt.plot(curve_data['fpr'], curve_data['tpr'], label=f'{name} (AUC = {results_default[name]["ROC-AUC"]:.2f})')
plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curves for Different Models (Loan Default Prediction)')
plt.legend()
plt.grid(True)
plt.show()

print(f"\nBased on ROC-AUC, the best performing model for Default Prediction is: {best_model_name_default}")

# Determine the final best model (considering tuned ones)
final_best_model_default = None
final_best_roc_auc_default = -1
final_best_model_name_default = ""

# Iterate through all original models and the tuned one if it was added
all_evaluated_models_default = models_default.copy()
if 'Gradient Boosting (Tuned)' in results_default:
    all_evaluated_models_default['Gradient Boosting (Tuned)'] = best_gb_model_default

print("\n--- Final Model Selection based on Test Set Performance (Default Prediction) ---")
for name, model_obj in all_evaluated_models_default.items():
    # Ensure we use the actual fitted model object for prediction
    if name == 'Gradient Boosting (Tuned)':
        current_model = model_obj
    else:
        current_model = models_default[name]  # Use the original fitted model object

    y_proba_test = current_model.predict_proba(X_test_default)[:, 1]
    roc_auc_test = roc_auc_score(y_test_default, y_proba_test)

    print(f"Model: {name}, Test ROC-AUC: {roc_auc_test:.4f}")

    if roc_auc_test > final_best_roc_auc_default:
        final_best_roc_auc_default = roc_auc_test
        final_best_model_default = current_model
        final_best_model_name_default = name

print(f"\nFinal best model selected for Default Prediction deployment: {final_best_model_name_default} (ROC-AUC: {final_best_roc_auc_default:.4f})")

# Save the trained model, scaler, and encoder
if final_best_model_default:
    model_filename_default = f'{final_best_model_name_default.replace(" ", "_").lower()}_loan_default_model.pkl'
    joblib.dump(final_best_model_default, model_filename_default)
    print(f"\nBest default prediction model saved as {model_filename_default}")

    scaler_filename_default = 'default_feature_scaler.pkl'
    joblib.dump(scaler_default, scaler_filename_default)
    print(f"Scaler for default prediction saved as {scaler_filename_default}")

    encoder_filename_default = 'default_one_hot_encoder.pkl'
    joblib.dump(encoder_default, encoder_filename_default)
    print(f"OneHotEncoder for default prediction saved as {encoder_filename_default}")

    # Optionally, save the list of column names the model expects
    joblib.dump(X_default.columns.tolist(), 'default_model_feature_names.pkl')
    print("Feature names for default model saved.")

else:
    print("No best model found for default prediction.")
