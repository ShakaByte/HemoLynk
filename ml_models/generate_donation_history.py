"""
generate_donation_history.py

Generates historical donation records - one row per past donation
event. Links donors.csv and facilities.csv together (a "junction
table" in database terms). Each donor's most recent donation matches
their last_donation_date already recorded in donors.csv; earlier
donations (for repeat donors) are generated backward in time,
respecting their correct gender-based cooldown period.

Output: ../data/donation_history.csv
"""

import pandas as pd
import random
from datetime import timedelta

random.seed(42)

COOLDOWN_DAYS = {
    "Male": 90,
    "Female": 120,
    "Other": 90,
}

DONATION_TIERS = [
    ("First-time", 0.25, (1, 1)),
    ("Occasional", 0.40, (2, 4)),
    ("Regular", 0.25, (5, 9)),
    ("Frequent", 0.10, (10, 16)),
]

COMPONENT_WEIGHTS = {
    "Whole Blood": 78,
    "Plasma": 12,
    "Platelets": 10,
}

VOLUME_RANGE_ML = {
    "Whole Blood": (350, 450),
    "Plasma": (200, 250),
    "Platelets": (50, 60),
}


def pick_tier():
    tiers, weights = zip(*[(t, w) for t, w, _ in DONATION_TIERS])
    chosen_name = random.choices(tiers, weights=weights)[0]
    for name, _, (min_n, max_n) in DONATION_TIERS:
        if name == chosen_name:
            return chosen_name, random.randint(min_n, max_n)


def pick_component():
    comps = list(COMPONENT_WEIGHTS.keys())
    weights = list(COMPONENT_WEIGHTS.values())
    return random.choices(comps, weights=weights)[0]


def generate_donation_history(donors_df, facilities_df):
    rows = []
    donation_counter = 1

    facilities_by_district = {
        district: group["facility_id"].tolist()
        for district, group in facilities_df.groupby("district")
    }

    for _, donor in donors_df.iterrows():
        donor_id = donor["donor_id"]
        district = donor["district"]
        gender = donor["gender"]
        cooldown = COOLDOWN_DAYS[gender]

        most_recent_date = pd.to_datetime(donor["last_donation_date"]).date()

        tier_name, total_donations = pick_tier()

        local_facility_ids = facilities_by_district.get(district, facilities_df["facility_id"].tolist())

        donation_dates = [most_recent_date]
        current_date = most_recent_date
        for _ in range(total_donations - 1):
            gap = cooldown + random.randint(0, 90)
            current_date = current_date - timedelta(days=gap)
            donation_dates.append(current_date)

        for donation_date in donation_dates:
            facility_id = random.choice(local_facility_ids)
            component = pick_component()
            min_vol, max_vol = VOLUME_RANGE_ML[component]
            quantity_ml = random.randint(min_vol, max_vol)

            donation_id = f"DNT{donation_counter:05d}"
            rows.append({
                "donation_id": donation_id,
                "donor_id": donor_id,
                "facility_id": facility_id,
                "donation_date": donation_date,
                "component_donated": component,
                "quantity_ml": quantity_ml,
                "donor_tier": tier_name,
            })
            donation_counter += 1

    return pd.DataFrame(rows)


if __name__ == "__main__":
    donors_df = pd.read_csv("../data/donors.csv")
    facilities_df = pd.read_csv("../data/facilities.csv")

    df = generate_donation_history(donors_df, facilities_df)

    output_path = "../data/donation_history.csv"
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} donation records -> {output_path}")
    print()
    print("Donations per tier (unique donors):")
    print(df.drop_duplicates("donor_id")["donor_tier"].value_counts())
    print()
    print("Total donation events per tier:")
    print(df["donor_tier"].value_counts())
    print()
    print("Component breakdown:")
    print(df["component_donated"].value_counts())
    print()
    print("Donations per donor - distribution check:")
    print(df.groupby("donor_id").size().describe())