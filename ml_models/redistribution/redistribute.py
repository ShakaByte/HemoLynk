"""
redistribute.py

Main orchestrator for the risk redistribution engine.
Ties together scoring → transfer planning → van reassignment → admin flags.

Run this file directly to see a full redistribution plan
across all facilities for all critical/shortage combos.
"""

import pandas as pd
from scoring import score_facilities
from relay import find_transfer, check_van_reassignment

# Simulated van availability per facility (in real app this comes from Firebase)
# For now: District Hospitals have 2 vans, Blood Banks 1, PHCs 1
def build_van_availability(facilities_df):
    vans = {}
    for _, row in facilities_df.iterrows():
        if row['type'] == 'District Hospital':
            vans[row['facility_id']] = 2
        else:
            vans[row['facility_id']] = 1
    return vans


def run_redistribution(inventory_df, facilities_df):
    """
    Full redistribution run:
    1. Score all facilities
    2. For each critical/shortage combo (priority order), find best transfer
    3. After each confirmed transfer, lock units + deduct van
    4. Check van reassignment opportunities
    5. Collect admin flags

    Returns:
        transfers     : list of confirmed transfer plans
        admin_flags   : list of unresolvable situations for admin
        reassignments : list of van reassignment opportunities
    """

    needs_df, surplus_df, surplus_units_df = score_facilities(inventory_df, facilities_df)
    vans_available = build_van_availability(facilities_df)

    transfers     = []
    admin_flags   = []
    reassignments = []

    # Track locked unit IDs (reserved once a transfer is planned)
    locked_units = set()

    # Track which surplus combos still have enough stock after assignments
    surplus_units_live = surplus_units_df.copy()

    print(f"Processing {len(needs_df)} shortage combos in priority order...\n")

    for _, needy_row in needs_df.iterrows():
        # Remove already-locked units from available surplus pool
        surplus_units_live = surplus_units_live[
            ~surplus_units_live['unit_id'].isin(locked_units)
        ]

        # Recompute surplus_df available counts after locks
        live_counts = (
            surplus_units_live
            .groupby(['facility_id','blood_group','component'])
            .size()
            .reset_index(name='available_units')
        )
        surplus_df_live = surplus_df.merge(
            live_counts, on=['facility_id','blood_group','component'], how='inner',
            suffixes=('_old','')
        )
        # Keep only still-surplus facilities
        from scoring import SURPLUS_STOCK
        surplus_df_live = surplus_df_live[
            surplus_df_live.apply(
                lambda r: r['available_units'] > SURPLUS_STOCK[r['type']], axis=1)
        ]

        plan = find_transfer(
            needy_row, facilities_df,
            surplus_df_live, surplus_units_live,
            vans_available
        )

        if plan['admin_flag']:
            admin_flags.append(plan)
            continue

        # Lock units assigned in this transfer
        if plan['type'] == 'DIRECT':
            for unit_id in plan['legs'][0].get('units', []):
                locked_units.add(unit_id)

        elif plan['type'] == 'RELAY':
            for unit_id in plan.get('units_dispatched_from_source', []):
                locked_units.add(unit_id)

        # Deduct vans used
        for fac_id, count in plan['vans_dispatched'].items():
            vans_available[fac_id] = max(0, vans_available.get(fac_id, 0) - count)

        transfers.append(plan)

        # Check van reassignment after each confirmed transfer
                # Check van reassignment after each confirmed transfer
        already_reassigned = {r['van_from'] for r in reassignments}
        for leg in plan['legs']:
            destination = leg['to']
            if destination in already_reassigned:
                continue
            reassignment = check_van_reassignment(
                destination, vans_available, transfers[:-1])  # exclude current transfer
            if reassignment:
                reassignments.append(reassignment)
                already_reassigned.add(destination)

    return transfers, admin_flags, reassignments


def print_summary(transfers, admin_flags, reassignments):
    print("=" * 60)
    print("REDISTRIBUTION SUMMARY")
    print("=" * 60)

    criticals = [t for t in transfers if t['priority'] == 'CRITICAL']
    shortages  = [t for t in transfers if t['priority'] == 'SHORTAGE']
    directs    = [t for t in transfers if t['type'] == 'DIRECT']
    relays     = [t for t in transfers if t['type'] == 'RELAY']

    print(f"\nTransfers planned  : {len(transfers)}")
    print(f"  CRITICAL resolved: {len(criticals)}")
    print(f"  SHORTAGE resolved: {len(shortages)}")
    print(f"  Direct transfers : {len(directs)}")
    print(f"  Relay transfers  : {len(relays)}")
    print(f"\nAdmin flags raised : {len(admin_flags)}")
    print(f"Van reassignments  : {len(reassignments)}")

    if transfers:
        print("\n--- SAMPLE TRANSFERS (first 5) ---")
        for t in transfers[:5]:
            print(f"\n[{t['type']}] {t['priority']} | "
                  f"{t['needy_facility']} needs {t['blood_group']} {t['component']}")
            for leg in t['legs']:
                print(f"  {leg['from']} → {leg['to']} | {leg['distance_km']} km")

    if admin_flags:
        print("\n--- ADMIN FLAGS (first 5) ---")
        for f in admin_flags[:5]:
            print(f"\n[{f['priority']}] {f['needy_facility']} | "
                  f"{f['blood_group']} {f['component']}")
            print(f"  Reason: {f['reason']}")

    if reassignments:
        print("\n--- VAN REASSIGNMENTS (first 5) ---")
        for r in reassignments[:5]:
            print(f"\nVan at {r['van_from']} reassigned → "
                  f"{r['assigned_to_leg']['to']} | "
                  f"{r['blood_group']} {r['component']} | "
                  f"Priority: {r['transfer_priority']}")


if __name__ == "__main__":
    inventory_df  = pd.read_csv("../../data/inventory.csv")
    facilities_df = pd.read_csv("../../data/facilities.csv")

    transfers, admin_flags, reassignments = run_redistribution(
        inventory_df, facilities_df)

    print_summary(transfers, admin_flags, reassignments)