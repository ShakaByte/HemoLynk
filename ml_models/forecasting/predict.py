"""
predict.py

Loads the trained forecasting model and predicts next-day usage
for a given facility + blood group. Flags shortage risk if
predicted usage > current stock for that blood group.
"""

import pandas as pd
import numpy as np
import pickle
from datetime import date, timedelta

# ── Load model ────────────────────────────────────────────────────
with open("../forecasting_model.pkl", "rb") as f:
    model = pickle.load(f)

FEATURES = ['rolling_avg_7d', 'rolling_avg_30d', 'month',
            'is_spike_day', 'facility_type_enc', 'blood_group_enc']

FACILITY_TYPE_ENC = {'District Hospital': 2, 'Blood Bank': 1, 'Primary Health Centre': 0}

BG_MAP = {bg: i for i, bg in enumerate(sorted(
    ["A+","A-","B+","B-","AB+","AB-","O+","O-"]))}

def predict_shortage(facility_id, facility_type, blood_group,
                     recent_usage_7d, recent_usage_30d,
                     current_stock_units, target_date=None):
    """
    Predicts next-day usage and flags if shortage risk exists.

    Parameters:
        facility_id       : e.g. "FAC001"
        facility_type     : "District Hospital" / "Blood Bank" / "Primary Health Centre"
        blood_group       : e.g. "O-"
        recent_usage_7d   : list of daily units used over last 7 days
        recent_usage_30d  : list of daily units used over last 30 days
        current_stock_units: how many units currently in stock
        target_date       : date to predict for (defaults to tomorrow)

    Returns: dict with prediction and shortage flag
    """
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    avg_7d  = np.mean(recent_usage_7d)  if recent_usage_7d  else 0.0
    avg_30d = np.mean(recent_usage_30d) if recent_usage_30d else 0.0

    month = target_date.month

    # Simple spike detection: if next day falls in known spike windows
    spike_months = [8, 9, 10, 12, 1]
    is_spike = 1 if month in spike_months else 0

    features = pd.DataFrame([{
        'rolling_avg_7d'    : avg_7d,
        'rolling_avg_30d'   : avg_30d,
        'month'             : month,
        'is_spike_day'      : is_spike,
        'facility_type_enc' : FACILITY_TYPE_ENC.get(facility_type, 1),
        'blood_group_enc'   : BG_MAP.get(blood_group, 0),
    }])

    predicted_units = max(0, round(model.predict(features[FEATURES])[0], 2))
    shortage_risk   = predicted_units > current_stock_units

    return {
        "facility_id"     : facility_id,
        "blood_group"     : blood_group,
        "target_date"     : str(target_date),
        "predicted_usage" : predicted_units,
        "current_stock"   : current_stock_units,
        "shortage_risk"   : shortage_risk,
        "message"         : (
            f"⚠️ SHORTAGE RISK: Predicted {predicted_units} units needed, only {current_stock_units} in stock."
            if shortage_risk else
            f"✅ Stock OK: Predicted {predicted_units} units needed, {current_stock_units} available."
        )
    }


# ── Quick test ────────────────────────────────────────────────────
if __name__ == "__main__":
    result = predict_shortage(
        facility_id       = "FAC001",
        facility_type     = "District Hospital",
        blood_group       = "O-",
        recent_usage_7d   = [2, 0, 3, 1, 0, 2, 1],
        recent_usage_30d  = [1]*30,
        current_stock_units = 1,
        target_date       = date(2026, 8, 2)
    )
    for k, v in result.items():
        print(f"{k}: {v}")