"""
redistribute.py

Main orchestrator for the risk redistribution engine.
Ties together: scoring → compatibility → transfer planning
             → van reassignment → audit logging → admin flags.
"""

import pandas as pd
from scoring import score_facilities, SURPLUS_STOCK
from relay import find_transfer, check_van_reassignment
from audit import (log_transfer_requested, log_partial_fulfillment,
                   log_van_reassigned, log_admin_flagged,
                   log_compatibility_used, print_log_summary)
import os


def build_van_availability(facilities_df):
    """
    Returns two dicts:
      vans_available  : {facility_id: total_vans}
      vans_cold_chain : {facility_id: cold_chain_vans}

    District Hospitals: 2 vans total, 2 cold chain
    Blood Banks       : 1 van total,  1 cold chain
    PHCs              : 1 van total,  0 cold chain (realistic — PHCs rarely have cold chain vans)
    """
    vans_available  = {}
    vans_cold_chain = {}

    for _, row in facilities_df.iterrows():
        fid = row['facility_id']
        if row['type'] == 'District Hospital':
            vans_available[fid]  = 2
            vans_cold_chain[fid] = 2
        elif row['type'] == 'Blood Bank':
            vans_available[fid]  = 1
            vans_cold_chain[fid] = 1
        else:  # PHC
            vans_available[fid]  = 1
            vans_cold_chain[fid] = 0

    return vans_available, vans_cold_chain


def run_redistribution(inventory_df, facilities_df):
    needs_df, surplus_df, surplus_units_df = score_facilities(
        inventory_df, facilities_df)

    vans_available, vans_cold_chain = build_van_availability(facilities_df)

    transfers     = []
    admin_flags   = []
    reassignments = []
    locked_units  = set()

    print(f"Processing {len(needs_df)} shortage combos in priority order...\n")

    for _, needy_row in needs_df.iterrows():
        # Remove locked units from live pool
        surplus_units_live = surplus_units_df[
            ~surplus_units_df['unit_id'].isin(locked_units)].copy()

        # Recompute live surplus counts after locks
        live_counts = (
            surplus_units_live
            .groupby(['facility_id','blood_group','component'])
            .size()
            .reset_index(name='available_units')
        )
        surplus_df_live = surplus_df.merge(
            live_counts,
            on=['facility_id','blood_group','component'],
            how='inner',
            suffixes=('_old','')
        )
        surplus_df_live = surplus_df_live[
            surplus_df_live.apply(
                lambda r: r['available_units'] > SURPLUS_STOCK[r['type']],
                axis=1)
        ]

        plan = find_transfer(
            needy_row, facilities_df,
            surplus_df_live, surplus_units_live,
            vans_available, vans_cold_chain
        )

        if plan['admin_flag']:
            admin_flags.append(plan)
            log_admin_flagged(
                plan['needy_facility'], plan['blood_group'],
                plan['component'], plan['reason'], plan['priority'])
            continue

        # Lock units + deduct vans
        for leg in plan['legs']:
            for unit_id in leg.get('units', []):
                locked_units.add(unit_id)
        for unit_id in plan.get('units_dispatched_from_source', []):
            locked_units.add(unit_id)

        for fac_id, count in plan['vans_dispatched'].items():
            vans_available[fac_id]  = max(0, vans_available.get(fac_id, 0) - count)
            vans_cold_chain[fac_id] = max(0, vans_cold_chain.get(fac_id, 0) - count)

        transfers.append(plan)

        # Audit log
        if plan['type'] == 'PARTIAL':
            log_partial_fulfillment(
                plan['needy_facility'],
                [{"facility_id": l['from'], "units": len(l.get('units',[]))}
                 for l in plan['legs']],
                plan['blood_group'], plan['component'],
                plan['units_needed'], plan['priority'])
        else:
            source = plan['legs'][0]['from']
            log_transfer_requested(
                plan['needy_facility'], source,
                plan['blood_group'], plan['component'],
                plan['units_needed'],
                plan['legs'][0]['distance_km'],
                plan['type'], plan['priority'],
                auto_confirmed=plan['auto_confirmed'])

        if plan.get('compatibility_used'):
            log_compatibility_used(
                plan['needy_facility'],
                plan['original_group'],
                plan['alternative_group'],
                plan['component'],
                plan['priority'])

        # Van reassignment check
        already_reassigned = {r['van_from'] for r in reassignments}
        for leg in plan['legs']:
            destination = leg['to']
            if destination in already_reassigned:
                continue
            reassignment = check_van_reassignment(
                destination, vans_available, transfers[:-1])
            if reassignment:
                reassignments.append(reassignment)
                already_reassigned.add(destination)
                log_van_reassigned(
                    destination,
                    from_job={"blood_group": plan['blood_group'],
                               "component" : plan['component']},
                    to_job=reassignment['assigned_to_leg'])

    return transfers, admin_flags, reassignments


def print_summary(transfers, admin_flags, reassignments):
    print("=" * 60)
    print("REDISTRIBUTION SUMMARY")
    print("=" * 60)

    criticals = [t for t in transfers if t['priority'] == 'CRITICAL']
    shortages  = [t for t in transfers if t['priority'] == 'SHORTAGE']
    directs    = [t for t in transfers if t['type'] == 'DIRECT']
    relays     = [t for t in transfers if t['type'] == 'RELAY']
    partials   = [t for t in transfers if t['type'] == 'PARTIAL']
    compat     = [t for t in transfers if t.get('compatibility_used')]

    print(f"\nTransfers planned   : {len(transfers)}")
    print(f"  CRITICAL resolved : {len(criticals)}")
    print(f"  SHORTAGE resolved : {len(shortages)}")
    print(f"  Direct transfers  : {len(directs)}")
    print(f"  Relay transfers   : {len(relays)}")
    print(f"  Partial transfers : {len(partials)}")
    print(f"  Compatibility used: {len(compat)}")
    print(f"\nAdmin flags raised  : {len(admin_flags)}")
    print(f"Van reassignments   : {len(reassignments)}")

    if transfers:
        print("\n--- SAMPLE TRANSFERS (first 5) ---")
        for t in transfers[:5]:
            compat_note = (f" [COMPAT: {t.get('original_group')} → "
                           f"{t.get('alternative_group')}]"
                           if t.get('compatibility_used') else "")
            auto_note   = " [AUTO-CONFIRMED]" if t['auto_confirmed'] else ""
            print(f"\n[{t['type']}]{auto_note}{compat_note} {t['priority']} | "
                  f"{t['needy_facility']} needs "
                  f"{t['blood_group']} {t['component']}")
            for leg in t['legs']:
                print(f"  {leg['from']} → {leg['to']} | "
                      f"{leg['distance_km']} km | "
                      f"prep: {leg['prep_time_minutes']} min")

    if admin_flags:
        print("\n--- ADMIN FLAGS (first 5) ---")
        for f in admin_flags[:5]:
            print(f"\n[{f['priority']}] {f['needy_facility']} | "
                  f"{f['blood_group']} {f['component']}")
            print(f"  Reason: {f['reason']}")

    if reassignments:
        print("\n--- VAN REASSIGNMENTS ---")
        for r in reassignments:
            print(f"\nVan at {r['van_from']} reassigned → "
                  f"{r['assigned_to_leg']['to']} | "
                  f"{r['blood_group']} {r['component']} | "
                  f"Priority: {r['transfer_priority']}")

    print("\n--- AUDIT LOG SUMMARY ---")
    print_log_summary()


if __name__ == "__main__":
    # Clear old audit log for fresh run
    import os
    if os.path.exists("audit_log.json"):
        os.remove("audit_log.json")

    inventory_df  = pd.read_csv("../../data/inventory.csv")
    facilities_df = pd.read_csv("../../data/facilities.csv")

    transfers, admin_flags, reassignments = run_redistribution(
        inventory_df, facilities_df)

    print_summary(transfers, admin_flags, reassignments)