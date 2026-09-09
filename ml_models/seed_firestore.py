"""
seed_firestore.py

Reads all 5 CSVs and seeds them into Firestore collections.
Run once to populate the database for the demo.

Collections created:
  - facilities
  - donors
  - inventory
  - usage_history
  - donation_history
"""

import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import math
import time

# ── Initialize Firebase ───────────────────────────────────────────
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


def clean_row(row):
    """
    Converts a pandas row to a clean dict Firestore can store.
    Handles NaN, numpy types, booleans cleanly.
    """
    cleaned = {}
    for key, value in row.items():
        if isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
        elif hasattr(value, 'item'):
            # numpy type → python native
            cleaned[key] = value.item()
        elif isinstance(value, bool):
            cleaned[key] = bool(value)
        else:
            cleaned[key] = str(value) if not isinstance(
                value, (int, float, bool)) else value
    return cleaned


def seed_collection(collection_name, df, id_column, batch_size=400):
    """
    Seeds a dataframe into a Firestore collection.
    Uses batch writes (max 500 per batch — we use 400 to be safe).
    Document ID = value of id_column for each row.
    """
    print(f"Seeding {collection_name} ({len(df)} records)...")
    col_ref = db.collection(collection_name)

    batch       = db.batch()
    batch_count = 0
    total       = 0

    for _, row in df.iterrows():
        doc_id  = str(row[id_column])
        doc_ref = col_ref.document(doc_id)
        batch.set(doc_ref, clean_row(row))
        batch_count += 1
        total       += 1

        if batch_count == batch_size:
            batch.commit()
            print(f"  Committed {total}/{len(df)}")
            batch       = db.batch()
            batch_count = 0
            time.sleep(5)

    if batch_count > 0:
        batch.commit()
        print(f"  Committed {total}/{len(df)}")

    print(f"  ✅ {collection_name} done.\n")


if __name__ == "__main__":
    donation_history = pd.read_csv("../data/donation_history.csv")
    seed_collection("donation_history", donation_history, "donation_id")
    print("Done.")