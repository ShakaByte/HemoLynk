"""
forecasting_model.py

Trains a Random Forest model to predict next-day blood unit usage
per facility per blood group. Uses usage_history.csv as input.

Output: forecasting_model.pkl (saved trained model)
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import pickle

# ── 1. Load data ──────────────────────────────────────────────────
usage = pd.read_csv("../../data/usage_history.csv")
facilities = pd.read_csv("../../data/facilities.csv")
usage['date'] = pd.to_datetime(usage['date'])

# ── 2. Build full grid (zeros for missing days) ───────────────────
all_dates = pd.date_range(start='2025-08-02', end='2026-08-01')
idx = pd.MultiIndex.from_product(
    [facilities['facility_id'].tolist(), usage['blood_group'].unique().tolist(), all_dates],
    names=['facility_id', 'blood_group', 'date'])
full_grid = pd.DataFrame(index=idx).reset_index()

usage_agg = usage.groupby(['facility_id','blood_group','date'])['units_used'].sum().reset_index()
full_grid = full_grid.merge(usage_agg, on=['facility_id','blood_group','date'], how='left')
full_grid['units_used'] = full_grid['units_used'].fillna(0)
full_grid = full_grid.sort_values(['facility_id','blood_group','date']).reset_index(drop=True)

# ── 3. Feature engineering ────────────────────────────────────────
full_grid['rolling_avg_7d'] = (
    full_grid.groupby(['facility_id','blood_group'])['units_used']
    .transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean())
)
full_grid['rolling_avg_30d'] = (
    full_grid.groupby(['facility_id','blood_group'])['units_used']
    .transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())
)
full_grid['target'] = (
    full_grid.groupby(['facility_id','blood_group'])['units_used']
    .transform(lambda x: x.shift(-1))
)
full_grid['month'] = full_grid['date'].dt.month
full_grid['is_spike_day'] = full_grid['date'].isin(
    usage[usage['is_spike_day']]['date']).astype(int)

full_grid = full_grid.merge(facilities[['facility_id','type']], on='facility_id')
full_grid['facility_type_enc'] = full_grid['type'].map(
    {'District Hospital': 2, 'Blood Bank': 1, 'Primary Health Centre': 0})
bg_map = {bg: i for i, bg in enumerate(sorted(full_grid['blood_group'].unique()))}
full_grid['blood_group_enc'] = full_grid['blood_group'].map(bg_map)

full_grid = full_grid.dropna(subset=['target','rolling_avg_7d','rolling_avg_30d'])

# ── 4. Train/test split (last 30 days = test, rest = train) ───────
FEATURES = ['rolling_avg_7d','rolling_avg_30d','month','is_spike_day',
            'facility_type_enc','blood_group_enc']
TARGET = 'target'

cutoff = pd.Timestamp('2026-07-02')
train = full_grid[full_grid['date'] <= cutoff]
test  = full_grid[full_grid['date'] >  cutoff]

X_train, y_train = train[FEATURES], train[TARGET]
X_test,  y_test  = test[FEATURES],  test[TARGET]

print(f"Train size: {len(X_train)} | Test size: {len(X_test)}")

# ── 5. Train model ────────────────────────────────────────────────
model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

# ── 6. Evaluate ───────────────────────────────────────────────────
preds = model.predict(X_test)
mae  = mean_absolute_error(y_test, preds)
rmse = mean_squared_error(y_test, preds) ** 0.5

print(f"\nMAE  : {mae:.4f}")
print(f"RMSE : {rmse:.4f}")
print(f"Baseline MAE (always predict mean): {mean_absolute_error(y_test, [y_train.mean()]*len(y_test)):.4f}")

print("\nFeature importances:")
for feat, imp in sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1]):
    print(f"  {feat}: {imp:.4f}")

# ── 7. Save model ─────────────────────────────────────────────────
with open("../forecasting_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("\nModel saved -> ml_models/forecasting_model.pkl")