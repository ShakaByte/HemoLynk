"""
scoring.py

Scores each facility's blood group stock into one of 4 states:
  CRITICAL  — 0 units available (immediate action needed)
  SHORTAGE  — below minimum threshold (needs resupply)
  NORMAL    — healthy stock level
  SURPLUS   — above normal range (candidate to donate stock)

Also scores near-expiry units at surplus facilities to determine
which units should be shipped out first (highest urgency = expiring soonest).

Priority order for receiving:  CRITICAL > SHORTAGE
Priority order for sending:    near-expiry units first, then by expiry date ascending
"""

import pandas as pd

# Minimum stock thresholds (units) per facility type per blood group
# Below this = SHORTAGE. At 0 = CRITICAL.
MIN_STOCK = {
    "District Hospital"     : 5,
    "Blood Bank"            : 3,
    "Primary Health Centre" : 2,
}

# Surplus threshold — above this = candidate to send stock out
SURPLUS_STOCK = {
    "District Hospital"     : 15,
    "Blood Bank"            : 8,
    "Primary Health Centre" : 5,
}


def score_facilities(inventory_df, facilities_df):
    """
    Returns two DataFrames:
      needs_df   — facilities in CRITICAL or SHORTAGE, sorted by priority
      surplus_df — facilities with SURPLUS available stock, with units ranked for shipment
    """

    # Only count Available units
    available = inventory_df[inventory_df['status'] == 'Available'].copy()

    # Aggregate available units per facility + blood group + component
    stock = (
        available
        .groupby(['facility_id', 'blood_group', 'component'])
        .agg(
            available_units=('unit_id', 'count'),
            near_expiry_units=('is_near_expiry', 'sum')
        )
        .reset_index()
    )

    # Merge facility type
    stock = stock.merge(facilities_df[['facility_id', 'type', 'district']], on='facility_id')

    # Assign stock state per row
    def get_state(row):
        min_t     = MIN_STOCK[row['type']]
        surplus_t = SURPLUS_STOCK[row['type']]
        units     = row['available_units']
        if units == 0:
            return 'CRITICAL'
        elif units < min_t:
            return 'SHORTAGE'
        elif units > surplus_t:
            return 'SURPLUS'
        else:
            return 'NORMAL'

    stock['stock_state'] = stock.apply(get_state, axis=1)

    # Criticality score for sorting (lower number = higher priority)
    STATE_PRIORITY = {'CRITICAL': 0, 'SHORTAGE': 1, 'NORMAL': 2, 'SURPLUS': 3}
    stock['priority_score'] = stock['stock_state'].map(STATE_PRIORITY)

    # ── Needs DataFrame (CRITICAL + SHORTAGE only) ────────────────
    needs_df = (
        stock[stock['stock_state'].isin(['CRITICAL', 'SHORTAGE'])]
        .sort_values(['priority_score', 'available_units'])  # most critical first
        .reset_index(drop=True)
    )

    # ── Surplus DataFrame ─────────────────────────────────────────
    surplus_df = stock[stock['stock_state'] == 'SURPLUS'].copy()

    # For surplus facilities, attach unit-level detail so we know
    # which exact units to ship (near-expiry first, then soonest expiry)
    surplus_units = available[
        available['facility_id'].isin(surplus_df['facility_id'])
    ].copy()

    surplus_units['expiry_date'] = pd.to_datetime(surplus_units['expiry_date'])
    surplus_units = surplus_units.sort_values(
        ['facility_id', 'blood_group', 'component', 'is_near_expiry', 'expiry_date'],
        ascending=[True, True, True, False, True]  # near_expiry=True first, then soonest expiry
    )

    return needs_df, surplus_df, surplus_units


def get_units_to_ship(surplus_units_df, facility_id, blood_group, component, quantity_needed):
    """
    From a surplus facility's available units, picks the exact units
    to ship — near-expiry first, then soonest expiry date.
    Locks them by marking as Reserved in the returned list.

    Returns: list of unit_ids to ship (up to quantity_needed)
    """
    candidate_units = surplus_units_df[
        (surplus_units_df['facility_id'] == facility_id) &
        (surplus_units_df['blood_group'] == blood_group) &
        (surplus_units_df['component']   == component)
    ]

    units_to_ship = candidate_units.head(quantity_needed)['unit_id'].tolist()
    return units_to_ship


if __name__ == "__main__":
    inventory_df  = pd.read_csv("../../data/inventory.csv")
    facilities_df = pd.read_csv("../../data/facilities.csv")

    needs_df, surplus_df, surplus_units = score_facilities(inventory_df, facilities_df)

    print("=== CRITICAL / SHORTAGE FACILITIES ===")
    print(f"Total: {len(needs_df)} facility-bloodgroup-component combos\n")
    print(needs_df[['facility_id','district','type','blood_group','component',
                     'available_units','stock_state']].head(20).to_string(index=False))

    print("\n=== SURPLUS FACILITIES ===")
    print(f"Total: {len(surplus_df)} facility-bloodgroup-component combos\n")
    print(surplus_df[['facility_id','district','type','blood_group','component',
                       'available_units','near_expiry_units','stock_state']].head(20).to_string(index=False))

    print("\n=== UNITS QUEUED FOR SHIPMENT (near-expiry first) ===")
    print(surplus_units[['unit_id','facility_id','blood_group','component',
                          'days_remaining','is_near_expiry']].head(20).to_string(index=False))