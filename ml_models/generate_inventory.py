"""
generate_inventory.py

Generates a synthetic blood inventory dataset with realistic:
- Facility-type-based stock variety (DH stocks everything, PHC stocks basics)
- India-realistic blood group population distribution (O+/B+ common, AB- rare)
- Real component shelf-life and standard unit volumes
- Near-expiry flagging (per our SRS rule: <=20% shelf life remaining)

Output: ../data/inventory.csv
"""

import pandas as pd
import random
from datetime import date, timedelta

random.seed(42)

TODAY = date(2026, 8, 1)

ALL_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
COMMON_BLOOD_GROUPS = ["A+", "B+", "O+", "O-"]

BLOOD_GROUP_WEIGHTS = {
    "O+": 37, "B+": 30, "A+": 22, "AB+": 7,
    "O-": 2, "A-": 1.5, "B-": 1, "AB-": 0.5,
}

ALL_COMPONENTS = ["Whole Blood", "RBC", "Platelets", "Plasma"]

SHELF_LIFE_DAYS = {
    "Whole Blood": 35,
    "RBC": 35,
    "Platelets": 5,
    "Plasma": 365,
}

VOLUME_RANGE_ML = {
    "Whole Blood": (350, 450),
    "RBC": (250, 300),
    "Platelets": (50, 60),
    "Plasma": (200, 250),
}

BASE_UNIT_COUNT = {
    "District Hospital": 150,
    "Blood Bank": 80,
    "Primary Health Centre": 30,
}

NEAR_EXPIRY_THRESHOLD_PCT = 0.20


def get_stock_profile(facility_type):
    if facility_type == "District Hospital":
        return ALL_BLOOD_GROUPS, ALL_COMPONENTS
    elif facility_type == "Blood Bank":
        groups = [g for g in ALL_BLOOD_GROUPS if random.random() > 0.15]
        components = ["Whole Blood", "RBC", "Platelets"]
        return groups, components
    else:
        return COMMON_BLOOD_GROUPS, ["Whole Blood"]


def weighted_blood_group_choice(available_groups):
    weights = [BLOOD_GROUP_WEIGHTS[g] for g in available_groups]
    return random.choices(available_groups, weights=weights)[0]


def generate_status(expiry_date):
    if expiry_date < TODAY:
        return "Expired"
    return random.choices(["Available", "Reserved"], weights=[0.88, 0.12])[0]


def generate_inventory(facilities_df):
    rows = []
    unit_counter = 1

    for _, facility in facilities_df.iterrows():
        facility_id = facility["facility_id"]
        facility_type = facility["type"]

        blood_groups, components = get_stock_profile(facility_type)

        base_count = BASE_UNIT_COUNT[facility_type]
        jitter = random.uniform(-0.10, 0.10)
        num_units = max(1, round(base_count * (1 + jitter)))

        for _ in range(num_units):
            unit_id = f"UNIT{unit_counter:05d}"
            blood_group = weighted_blood_group_choice(blood_groups)
            component = random.choice(components)
            shelf_life = SHELF_LIFE_DAYS[component]
            days_ago = round(random.triangular(0, shelf_life * 1.3, shelf_life * 0.2))
            collection_date = TODAY - timedelta(days=days_ago)
            expiry_date = collection_date + timedelta(days=shelf_life)

            status = generate_status(expiry_date)

            days_remaining = (expiry_date - TODAY).days
            pct_shelf_life_remaining = days_remaining / shelf_life if shelf_life > 0 else 0
            is_near_expiry = (
                status == "Available"
                and 0 <= pct_shelf_life_remaining <= NEAR_EXPIRY_THRESHOLD_PCT
            )

            min_vol, max_vol = VOLUME_RANGE_ML[component]
            quantity_ml = random.randint(min_vol, max_vol)

            rows.append({
                "unit_id": unit_id,
                "facility_id": facility_id,
                "blood_group": blood_group,
                "component": component,
                "quantity_ml": quantity_ml,
                "collection_date": collection_date,
                "expiry_date": expiry_date,
                "days_remaining": days_remaining,
                "status": status,
                "is_near_expiry": is_near_expiry,
            })

            unit_counter += 1

    return pd.DataFrame(rows)


if __name__ == "__main__":
    facilities_df = pd.read_csv("../data/facilities.csv")
    df = generate_inventory(facilities_df)

    output_path = "../data/inventory.csv"
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} inventory units -> {output_path}")
    print()
    print("Units per facility type:")
    merged = df.merge(facilities_df[["facility_id", "type"]], on="facility_id")
    print(merged["type"].value_counts())
    print()
    print("Blood group distribution (should roughly follow real population weights):")
    print(df["blood_group"].value_counts())
    print()
    print("Status breakdown:")
    print(df["status"].value_counts())
    print()
    print("Near-expiry units flagged:", df["is_near_expiry"].sum())
    print()
    print("Component breakdown:")
    print(df["component"].value_counts())