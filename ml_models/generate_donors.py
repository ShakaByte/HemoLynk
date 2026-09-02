"""
generate_donors.py

Generates a synthetic dataset of 500 blood donors across our
6 districts, using REAL village/taluk/pincode data for addresses,
plus age, gender, and detailed medical/eligibility fields
(including gender-specific screening questions).

Output: ../data/donors.csv
"""

import pandas as pd
import random
from faker import Faker
from datetime import date, timedelta

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
NUM_DONORS = 1000
TODAY = date(2026, 8, 1)

DISTRICT_NAME_FIX = {
    "Davanagere": "Davangere",
}

COOLDOWN_DAYS = {
    "Male": 90,
    "Female": 120,
    "Other": 90,
}


def load_real_addresses():
    df = pd.read_csv("../data/karnataka_blood_bank_geographic_directory.csv")
    df["District"] = df["District"].replace(DISTRICT_NAME_FIX)
    return df


def random_past_date(days_back_min, days_back_max):
    days_ago = random.randint(days_back_min, days_back_max)
    return TODAY - timedelta(days=days_ago)


def generate_age():
    bucket = random.random()
    if bucket < 0.45:
        return random.randint(18, 25)
    elif bucket < 0.85:
        return random.randint(26, 45)
    else:
        return random.randint(46, 65)


def generate_weight(gender):
    if gender == "Female":
        w = random.gauss(60, 7)
    else:
        w = random.gauss(68, 9)
    return max(38, round(w, 1))


def generate_hemoglobin(gender):
    if gender == "Female":
        hb = random.gauss(13.6, 1.0)
    else:
        hb = random.gauss(14.8, 1.2)
    return max(8.0, round(hb, 1))


def calculate_eligibility(age, weight_kg, hemoglobin, gender,
                           is_pregnant, is_breastfeeding, menstrual_issues,
                           last_donation_date, recent_illness, on_medication,
                           recent_travel, chronic_condition):
    if age < 18 or age > 65:
        return "Ineligible", "Age outside donation range (18-65)"

    if weight_kg < 50:
        return "Ineligible", "Weight below 50kg minimum"

    min_hb = 12.5 if gender == "Female" else 13.0
    if hemoglobin < min_hb:
        return "Ineligible", "Low hemoglobin (anemia risk)"

    if gender == "Female":
        if is_pregnant:
            return "Ineligible", "Pregnant"
        if is_breastfeeding:
            return "Ineligible", "Breastfeeding"
        if menstrual_issues:
            return "Ineligible", "Menstrual health issue"

    if chronic_condition:
        return "Ineligible", "Chronic condition"
    if recent_illness:
        return "Ineligible", "Recent illness"
    if on_medication:
        return "Ineligible", "On medication"
    if recent_travel:
        return "Ineligible", "Recent travel (deferral zone)"

    cooldown = COOLDOWN_DAYS[gender]
    days_since_donation = (TODAY - last_donation_date).days
    if days_since_donation < cooldown:
        return "Ineligible", f"Cooldown period ({cooldown - days_since_donation} days left)"

    return "Eligible", "All checks passed"


def generate_donors():
    addresses = load_real_addresses()
    rows = []

    for i in range(1, NUM_DONORS + 1):
        donor_id = f"DON{i:04d}"
        gender = random.choices(["Male", "Female", "Other"], weights=[0.55, 0.43, 0.02])[0]
        name = fake.name_male() if gender == "Male" else fake.name_female() if gender == "Female" else fake.name()

        age = generate_age()
        blood_group = random.choice(BLOOD_GROUPS)
        contact_number = "9" + "".join([str(random.randint(0, 9)) for _ in range(9)])

        weight_kg = generate_weight(gender)
        hemoglobin = generate_hemoglobin(gender)

        is_pregnant = (gender == "Female") and (random.random() < 0.05)
        is_breastfeeding = (gender == "Female") and (random.random() < 0.04)
        menstrual_issues = (gender == "Female") and (random.random() < 0.06)

        address_row = addresses.sample(n=1).iloc[0]
        district = address_row["District"]
        taluk = address_row["Taluk"]
        village = address_row["Village"]
        pincode = address_row["Pin_Code"]
        locality = address_row["Locality"]
        landmark = address_row["Landmark"]
        full_address = f"{locality}, near {landmark}, {village}, {taluk} Taluk, {district}, Karnataka - {pincode}"

        last_donation_date = random_past_date(5, 400)

        recent_illness = random.random() < 0.08
        on_medication = random.random() < 0.06
        recent_travel = random.random() < 0.05
        chronic_condition = random.random() < 0.04

        eligibility_status, reason = calculate_eligibility(
            age, weight_kg, hemoglobin, gender,
            is_pregnant, is_breastfeeding, menstrual_issues,
            last_donation_date, recent_illness, on_medication,
            recent_travel, chronic_condition
        )

        rows.append({
            "donor_id": donor_id,
            "name": name,
            "age": age,
            "gender": gender,
            "blood_group": blood_group,
            "district": district,
            "taluk": taluk,
            "village": village,
            "pincode": pincode,
            "full_address": full_address,
            "contact_number": contact_number,
            "weight_kg": weight_kg,
            "hemoglobin_level": hemoglobin,
            "is_pregnant": is_pregnant,
            "is_breastfeeding": is_breastfeeding,
            "menstrual_issues": menstrual_issues,
            "last_donation_date": last_donation_date,
            "recent_illness": recent_illness,
            "on_medication": on_medication,
            "recent_travel": recent_travel,
            "chronic_condition": chronic_condition,
            "eligibility_status": eligibility_status,
            "eligibility_reason": reason,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_donors()
    output_path = "../data/donors.csv"
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} donors -> {output_path}")
    print()
    print("Gender breakdown:")
    print(df["gender"].value_counts())
    print()
    print("Age range:", df["age"].min(), "-", df["age"].max())
    print()
    print("Eligibility breakdown:")
    print(df["eligibility_status"].value_counts())
    print()
    print("Ineligibility reasons:")
    print(df[df["eligibility_status"] == "Ineligible"]["eligibility_reason"].value_counts())