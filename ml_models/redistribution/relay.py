"""
relay.py

Handles transfer decision making:
  - Direct transfer: source facility → needy facility (if close enough + has surplus)
  - Relay transfer: source → intermediate → needy (if direct distance too large,
    one facility in between, both legs dispatched simultaneously)
  - Van reassignment: when a van completes delivery at a node, check if that
    node has a pending outbound job before sending van back empty
  - Admin flag: raised when no viable transfer path exists or no van available
"""

import math
import pandas as pd
from scoring import get_units_to_ship

# Max direct distance (km) allowed for a direct transfer
MAX_DIRECT_KM = 80

# Max total relay distance (km) for a two-leg relay
MAX_RELAY_KM = 160

# How many nearest facilities to consider as candidates
MAX_CANDIDATES = 5


def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two lat/lon points in km."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_nearest_facilities(needy_facility, facilities_df, exclude_ids=None, n=MAX_CANDIDATES):
    """Returns up to n nearest facilities sorted by distance, excluding given IDs."""
    exclude_ids = exclude_ids or []
    candidates = facilities_df[~facilities_df['facility_id'].isin(exclude_ids)].copy()

    candidates['distance_km'] = candidates.apply(
        lambda row: haversine_km(
            needy_facility['latitude'],
            needy_facility['longitude'],
            row['latitude'],
            row['longitude']
        ), axis=1
    )
    return candidates.sort_values('distance_km').head(n).reset_index(drop=True)


def find_transfer(needy_row, facilities_df, surplus_df, surplus_units_df, vans_available):
    """
    For one needy facility+blood_group+component combo, finds the best
    transfer plan: direct or relay.

    Parameters:
        needy_row       : one row from needs_df
        facilities_df   : full facilities dataframe
        surplus_df      : surplus facilities scored dataframe
        surplus_units_df: unit-level surplus stock (near-expiry first)
        vans_available  : dict {facility_id: int} — vans available at each facility

    Returns: dict describing the transfer plan, or admin flag dict if not solvable
    """
    facility_id  = needy_row['facility_id']
    blood_group  = needy_row['blood_group']
    component    = needy_row['component']
    stock_state  = needy_row['stock_state']
    units_needed = max(1, MIN_STOCK_TARGET[needy_row['type']] - needy_row['available_units'])

    needy_fac = facilities_df[facilities_df['facility_id'] == facility_id].iloc[0]

    # Surplus candidates matching exact blood group + component
    matching_surplus = surplus_df[
        (surplus_df['blood_group'] == blood_group) &
        (surplus_df['component']   == component)
    ]

    if matching_surplus.empty:
        return _flag_admin(facility_id, blood_group, component, stock_state,
                           reason="No surplus found for this blood group + component")

    # Get nearest facilities overall (for relay candidate lookup)
    nearest = get_nearest_facilities(needy_fac, facilities_df,
                                     exclude_ids=[facility_id])

    # ── Try direct transfer first ─────────────────────────────────
    for _, candidate in nearest.iterrows():
        cand_id = candidate['facility_id']
        dist_km = candidate['distance_km']

        if dist_km > MAX_DIRECT_KM:
            break  # sorted by distance, no point checking further for direct

        if cand_id not in matching_surplus['facility_id'].values:
            continue  # not a surplus facility for this blood group + component

        # Check relay point is not itself in shortage for this blood group
        if _is_in_need(cand_id, blood_group, component, surplus_df):
            continue

        # Check van available at source
        if vans_available.get(cand_id, 0) < 1:
            return _flag_admin(facility_id, blood_group, component, stock_state,
                               reason=f"No van available at surplus facility {cand_id}")

        units_to_ship = get_units_to_ship(
            surplus_units_df, cand_id, blood_group, component, units_needed)

        return {
            "type"          : "DIRECT",
            "priority"      : stock_state,
            "needy_facility": facility_id,
            "blood_group"   : blood_group,
            "component"     : component,
            "units_needed"  : units_needed,
            "legs"          : [
                {"from": cand_id, "to": facility_id,
                 "units": units_to_ship, "distance_km": round(dist_km, 2)}
            ],
            "vans_dispatched": {cand_id: 1},
            "admin_flag"    : False,
        }

    # ── Try relay transfer ────────────────────────────────────────
    for _, mid_candidate in nearest.iterrows():
        mid_id   = mid_candidate['facility_id']
        mid_dist = mid_candidate['distance_km']  # needy → mid distance

        if mid_dist > MAX_RELAY_KM:
            break

        # Mid facility must NOT be in shortage itself
        if _is_in_shortage(mid_id, blood_group, component, needy_row):
            continue

        # Find a surplus facility near the mid point
        mid_fac = facilities_df[facilities_df['facility_id'] == mid_id].iloc[0]
        nearest_to_mid = get_nearest_facilities(
            mid_fac, facilities_df,
            exclude_ids=[facility_id, mid_id]
        )

        for _, source_candidate in nearest_to_mid.iterrows():
            src_id   = source_candidate['facility_id']
            src_dist = source_candidate['distance_km']  # mid → source distance

            total_dist = mid_dist + src_dist
            if total_dist > MAX_RELAY_KM:
                break

            if src_id not in matching_surplus['facility_id'].values:
                continue

            # Both legs need a van
            vans_at_src = vans_available.get(src_id, 0)
            vans_at_mid = vans_available.get(mid_id, 0)

            if vans_at_src < 1 or vans_at_mid < 1:
                return _flag_admin(facility_id, blood_group, component, stock_state,
                                   reason=f"Relay possible ({src_id}→{mid_id}→{facility_id}) but van unavailable")

            units_to_ship = get_units_to_ship(
                surplus_units_df, src_id, blood_group, component, units_needed)

            return {
                "type"          : "RELAY",
                "priority"      : stock_state,
                "needy_facility": facility_id,
                "blood_group"   : blood_group,
                "component"     : component,
                "units_needed"  : units_needed,
                "legs"          : [
                    {"from": src_id,  "to": mid_id,     "distance_km": round(src_dist, 2)},
                    {"from": mid_id,  "to": facility_id, "distance_km": round(mid_dist, 2)},
                ],
                "units_dispatched_from_source": units_to_ship,
                "simultaneous"  : True,
                "vans_dispatched": {src_id: 1, mid_id: 1},
                "admin_flag"    : False,
            }

    return _flag_admin(facility_id, blood_group, component, stock_state,
                       reason="No viable direct or relay path found within distance limits")


def check_van_reassignment(arrived_at_facility, vans_available, pending_transfers):
    """
    After a van completes delivery at a facility, check if that facility
    has a pending outbound transfer job. If yes, reassign the van instead
    of sending it back empty.

    Parameters:
        arrived_at_facility : facility_id where van just finished delivery
        vans_available      : dict {facility_id: int}
        pending_transfers   : list of transfer plan dicts (from find_transfer)

    Returns: reassignment dict or None
    """
    for transfer in pending_transfers:
        for leg in transfer['legs']:
            if leg['from'] == arrived_at_facility:
                return {
                    "reassigned"        : True,
                    "van_from"          : arrived_at_facility,
                    "assigned_to_leg"   : leg,
                    "transfer_priority" : transfer['priority'],
                    "blood_group"       : transfer['blood_group'],
                    "component"         : transfer['component'],
                }
    return None


# ── Helpers ───────────────────────────────────────────────────────

MIN_STOCK_TARGET = {
    "District Hospital"     : 10,
    "Blood Bank"            : 6,
    "Primary Health Centre" : 3,
}

def _is_in_need(facility_id, blood_group, component, surplus_df):
    """Returns True if facility is NOT in surplus for this combo."""
    match = surplus_df[
        (surplus_df['facility_id'] == facility_id) &
        (surplus_df['blood_group'] == blood_group) &
        (surplus_df['component']   == component)
    ]
    return match.empty

def _is_in_shortage(facility_id, blood_group, component, needy_row):
    """Returns True if facility_id matches the needy facility (can't relay through itself)."""
    return facility_id == needy_row['facility_id']

def _flag_admin(facility_id, blood_group, component, stock_state, reason):
    return {
        "type"          : "ADMIN_FLAG",
        "priority"      : stock_state,
        "needy_facility": facility_id,
        "blood_group"   : blood_group,
        "component"     : component,
        "admin_flag"    : True,
        "reason"        : reason,
    }