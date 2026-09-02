"""
generate_usage_history.py

Generates 12 months of synthetic blood USAGE (transfusion) history -
one row per actual usage event (facility + blood group + day).

This is the dataset our AI forecasting model will learn from: it
needs to see realistic day-to-day consumption patterns, including
seasonal spikes, to be able to predict future shortages.

Output: ../data/usage_history.csv
"""

import pandas as pd
import random
from datetime import date, timedelta

random.seed(42)

START_DATE = date(2025, 8, 2)
END_DATE = date(2026, 8, 1)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1

BLOOD_GROUP_WEIGHTS = {
    "O+": 37, "B+": 30, "A+": 22, "AB+": 7,
    "O-": 2, "A-": 1.5, "B-": 1, "AB-": 0.5,
}
ALL_BLOOD_GROUPS = list(BLOOD_GROUP_WEIGHTS.keys())
COMMON_BLOOD_GROUPS = ["A+", "B+", "O+", "O-"]

DAILY_USAGE_PROBABILITY = {
    "District Hospital": 0.22,
    "Blood Bank": 0.10,
    "Primary Health Centre": 0.035,
}

BASE_UNITS_RANGE = {
    "District Hospital": (1, 4),
    "Blood Bank": (1, 3),
    "Primary Health Centre": (1, 2),
}

SEASONAL_SPIKE_WINDOWS = [
    (7, 15, 8, 5, 1.4, "Monsoon peak flood-risk weeks"),
    (9, 16, 10, 10, 1.6, "Festival travel peak (Dasara)"),
    (12, 30, 1, 2, 1.8, "New Year travel period"),
]


def get_seasonal_multiplier(d):
    for sm, sd, em, ed, mult, reason in SEASONAL_SPIKE_WINDOWS:
        start = date(d.year, sm, sd)
        if em < sm:
            end = date(d.year + 1, em, ed)
        else:
            end = date(d.year, em, ed)

        if start <= d <= end:
            return mult, reason

        if em < sm:
            prev_start = date(d.year - 1, sm, sd)
            prev_end = date(d.year, em, ed)
            if prev_start <= d <= prev_end:
                return mult, reason

    return 1.0, None


def get_facility_stock_groups(facility_type):
    if facility_type == "District Hospital":
        return ALL_BLOOD_GROUPS
    elif facility_type == "Blood Bank":
        return [g for g in ALL_BLOOD_GROUPS if random.random() > 0.15]
    else:
        return COMMON_BLOOD_GROUPS


def generate_usage_history(facilities_df):
    rows = []
    usage_counter = 1

    for _, facility in facilities_df.iterrows():
        facility_id = facility["facility_id"]
        facility_type = facility["type"]
        district = facility["district"]

        stocked_groups = get_facility_stock_groups(facility_type)
        base_prob = DAILY_USAGE_PROBABILITY[facility_type]
        min_units, max_units = BASE_UNITS_RANGE[facility_type]

        num_random_spikes = round(TOTAL_DAYS * 0.015)
        random_spike_days = set(
            random.randint(0, TOTAL_DAYS - 1) for _ in range(num_random_spikes)
        )

        for day_offset in range(TOTAL_DAYS):
            current_date = START_DATE + timedelta(days=day_offset)

            seasonal_mult, seasonal_reason = get_seasonal_multiplier(current_date)
            is_random_spike = day_offset in random_spike_days

            multiplier = seasonal_mult
            spike_reason = seasonal_reason
            if is_random_spike:
                multiplier = max(multiplier, 2.0)
                spike_reason = spike_reason or "Local incident spike"

            is_spike_day = multiplier > 1.0

            for blood_group in stocked_groups:
                group_weight_factor = BLOOD_GROUP_WEIGHTS[blood_group] / 37
                event_probability = min(1.0, base_prob * (0.3 + 0.7 * group_weight_factor) * multiplier)

                if random.random() < event_probability:
                    units_used = random.randint(min_units, max_units)
                    if is_spike_day:
                        units_used = round(units_used * random.uniform(1.3, 1.8))

                    usage_id = f"USG{usage_counter:06d}"
                    rows.append({
                        "usage_id": usage_id,
                        "facility_id": facility_id,
                        "district": district,
                        "date": current_date,
                        "blood_group": blood_group,
                        "units_used": units_used,
                        "is_spike_day": is_spike_day,
                        "spike_reason": spike_reason if is_spike_day else "",
                    })
                    usage_counter += 1

    return pd.DataFrame(rows)


if __name__ == "__main__":
    facilities_df = pd.read_csv("../data/facilities.csv")
    df = generate_usage_history(facilities_df)

    output_path = "../data/usage_history.csv"
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} usage records -> {output_path}")
    print()
    print("Date range:", df["date"].min(), "to", df["date"].max())
    print()
    print("Records per facility type:")
    merged = df.merge(facilities_df[["facility_id", "type"]], on="facility_id")
    print(merged["type"].value_counts())
    print()
    print("Spike day records:", df["is_spike_day"].sum(), f"({df['is_spike_day'].mean()*100:.1f}%)")
    print()
    print("Spike reasons breakdown:")
    print(df[df["is_spike_day"]]["spike_reason"].value_counts())
    print()
    print("Blood group usage distribution:")
    print(df["blood_group"].value_counts())
    print()
    print("Total units used overall:", df["units_used"].sum())