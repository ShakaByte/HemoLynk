"""
generate_facilities.py

Generates a synthetic dataset of blood bank / hospital facilities
across Ballari and neighboring Karnataka districts.

Output: ../data/facilities.csv
"""

import pandas as pd
import random

random.seed(42)

DISTRICTS = {
    "Ballari": (15.1394, 76.9214),
    "Vijayanagara": (15.2380, 76.4600),
    "Koppal": (15.3547, 76.1548),
    "Raichur": (16.2076, 77.3463),
    "Davangere": (14.4644, 75.9218),
    "Chitradurga": (14.2251, 76.3980),
}

FACILITY_TYPES = ["District Hospital", "Blood Bank", "Primary Health Centre"]
FACILITIES_PER_TYPE = 3  # 3 of EACH type, per district -> 9 per district total

def generate_facilities():
    rows = []
    facility_counter = 1

    for district, (base_lat, base_lon) in DISTRICTS.items():
        for f_type in FACILITY_TYPES:
            for i in range(1, FACILITIES_PER_TYPE + 1):
                facility_id = f"FAC{facility_counter:03d}"
                name = f"{district} {f_type} {i}"

                lat = base_lat + random.uniform(-0.15, 0.15)
                lon = base_lon + random.uniform(-0.15, 0.15)

                is_rural = (f_type == "Primary Health Centre")

                rows.append({
                    "facility_id": facility_id,
                    "name": name,
                    "district": district,
                    "type": f_type,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "is_rural": is_rural,
                })

                facility_counter += 1

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_facilities()
    output_path = "../data/facilities.csv"
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} facilities -> {output_path}")
    print(df.head(10))