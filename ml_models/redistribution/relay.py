"""
relay.py

Handles transfer decision making:
  - Direct transfer: source → needy (within distance + surplus)
  - Relay transfer: source → intermediate → needy (one hop, simultaneous legs)
  - Partial fulfillment: split across two sources if one can't cover full need
  - Cold chain validation: checks van is equipped for component temperature needs
  - Prep time buffer: accounts for unit preparation before dispatch
  - Compatibility fallback: suggests compatible blood groups if exact match unavailable
  - Van reassignment: reuses van already at a node for next outbound job
  - Admin flag: raised when no viable path exists
"""

import math
import pandas as pd
from compatibility import get_compatible_groups, suggest_alternatives
from scoring import get_units_to_ship, SURPLUS_STOCK, MIN_STOCK

MAX_DIRECT_KM = 80
MAX_RELAY_KM  = 160
MAX_CANDIDATES = 5

# Components requiring cold chain equipped vehicles
COLD_CHAIN_REQUIRED = {
    "Whole Blood": True,
    "RBC"        : True,
    "Platelets"  : True,
    "Plasma"     : True,
}

# Temperature requirements by component (for admin info)
TEMP_REQUIREMENTS = {
    "Whole Blood": "2-6°C (refrigerated)",
    "RBC"        : "2-6°C (refrigerated)",
    "Platelets"  : "20-24°C (agitated)",
    "Plasma"     : "Frozen (-18°C or below)",
}

# Preparation time in minutes before van can leave
PREP_TIME_MINUTES = {
    "District Hospital"     : 30,
    "Blood Bank"            : 45,
    "Primary Health Centre" : 60,
}

MIN_STOCK_TARGET = {
    "District Hospital"     : 10,
    "Blood Bank"            : 6,
    "Primary Health Centre" : 3,
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_nearest_facilities(needy_facility, facilities_df,
                           exclude_ids=None, n=MAX_CANDIDATES):
    exclude_ids = exclude_ids or []
    candidates  = facilities_df[
        ~facilities_df['facility_id'].isin(exclude_ids)].copy()
    candidates['distance_km'] = candidates.apply(
        lambda row: haversine_km(
            needy_facility['latitude'],  needy_facility['longitude'],
            row['latitude'],             row['longitude']), axis=1)
    return candidates.sort_values('distance_km').head(n).reset_index(drop=True)


def _van_is_cold_chain(facility_id, vans_cold_chain):
    """Check if at least one cold-chain van is available at facility."""
    return vans_cold_chain.get(facility_id, 0) > 0


def _check_van(facility_id, component, vans_available, vans_cold_chain):
    """
    Returns (ok, reason):
      ok     : True if a suitable van is available
      reason : explanation if not ok
    """
    if vans_available.get(facility_id, 0) < 1:
        return False, f"No van available at {facility_id}"
    if COLD_CHAIN_REQUIRED.get(component, False):
        if not _van_is_cold_chain(facility_id, vans_cold_chain):
            return False, (f"No cold-chain van at {facility_id} "
                           f"— {component} requires {TEMP_REQUIREMENTS[component]}")
    return True, "ok"


def _get_prep_time(facility_id, facilities_df):
    fac = facilities_df[facilities_df['facility_id'] == facility_id]
    if fac.empty:
        return 45
    return PREP_TIME_MINUTES[fac.iloc[0]['type']]


def _try_source(cand_id, cand_dist, needy_row, facilities_df,
                surplus_df, surplus_units_df,
                vans_available, vans_cold_chain):
    """
    Attempts to use cand_id as a direct source.
    Returns (units_available, units_to_ship, prep_time) or None if not viable.
    """
    blood_group  = needy_row['blood_group']
    component    = needy_row['component']
    units_needed = max(1, MIN_STOCK_TARGET[needy_row['type']]
                       - needy_row['available_units'])

    match = surplus_df[
        (surplus_df['facility_id'] == cand_id) &
        (surplus_df['blood_group'] == blood_group) &
        (surplus_df['component']   == component)
    ]
    if match.empty:
        return None

    # Check van
    van_ok, van_reason = _check_van(
        cand_id, component, vans_available, vans_cold_chain)
    if not van_ok:
        return None

    available_units = int(match.iloc[0]['available_units'])
    can_send        = min(available_units - SURPLUS_STOCK[match.iloc[0]['type']],
                          units_needed)
    if can_send < 1:
        return None

    units_to_ship = get_units_to_ship(
        surplus_units_df, cand_id, blood_group, component, can_send)
    prep_time = _get_prep_time(cand_id, facilities_df)

    return {
        "source_id"   : cand_id,
        "units"       : units_to_ship,
        "can_send"    : can_send,
        "needed"      : units_needed,
        "distance_km" : round(cand_dist, 2),
        "prep_time"   : prep_time,
    }


def find_transfer(needy_row, facilities_df, surplus_df,
                  surplus_units_df, vans_available, vans_cold_chain):
    """
    For one needy facility+blood_group+component, finds the best transfer plan.
    Tries in order:
      1. Direct exact match
      2. Direct partial (two sources)
      3. Relay exact match
      4. Compatibility fallback (exact → compatible group, same flow)
      5. Admin flag
    """
    facility_id  = needy_row['facility_id']
    blood_group  = needy_row['blood_group']
    component    = needy_row['component']
    stock_state  = needy_row['stock_state']
    units_needed = max(1, MIN_STOCK_TARGET[needy_row['type']]
                       - needy_row['available_units'])
    is_critical  = stock_state == 'CRITICAL'

    needy_fac = facilities_df[
        facilities_df['facility_id'] == facility_id].iloc[0]
    nearest   = get_nearest_facilities(
        needy_fac, facilities_df, exclude_ids=[facility_id])

    # ── 1. Direct exact match ─────────────────────────────────────
    for _, candidate in nearest.iterrows():
        if candidate['distance_km'] > MAX_DIRECT_KM:
            break
        result = _try_source(
            candidate['facility_id'], candidate['distance_km'],
            needy_row, facilities_df, surplus_df,
            surplus_units_df, vans_available, vans_cold_chain)
        if result is None:
            continue

        return _build_direct(result, needy_row, is_critical)

    # ── 2. Partial fulfillment (two sources) ──────────────────────
    partial = _try_partial(
        needy_row, nearest, facilities_df, surplus_df,
        surplus_units_df, vans_available, vans_cold_chain,
        units_needed, is_critical)
    if partial:
        return partial

    # ── 3. Relay exact match ──────────────────────────────────────
    relay = _try_relay(
        needy_row, needy_fac, nearest, facilities_df,
        surplus_df, surplus_units_df,
        vans_available, vans_cold_chain, is_critical)
    if relay:
        return relay

    # ── 4. Compatibility fallback ─────────────────────────────────
    available_groups = surplus_df['blood_group'].unique().tolist()
    alternatives     = suggest_alternatives(
        blood_group, component, available_groups)

    if alternatives:
        best_alt = alternatives[0]['alternative_group']
        # Rebuild a fake needy_row with the alternative group
        alt_needy = needy_row.copy()
        alt_needy['blood_group'] = best_alt

        for _, candidate in nearest.iterrows():
            if candidate['distance_km'] > MAX_DIRECT_KM:
                break
            result = _try_source(
                candidate['facility_id'], candidate['distance_km'],
                alt_needy, facilities_df, surplus_df,
                surplus_units_df, vans_available, vans_cold_chain)
            if result is None:
                continue

            plan = _build_direct(result, needy_row, is_critical)
            plan['compatibility_used'] = True
            plan['original_group']     = blood_group
            plan['alternative_group']  = best_alt
            plan['admin_suggestion']   = (
                f"Exact match {blood_group} unavailable. "
                f"Compatible alternative {best_alt} suggested — "
                f"awaiting admin confirmation.")
            return plan

    # ── 5. Admin flag ─────────────────────────────────────────────
    return _flag_admin(facility_id, blood_group, component,
                       stock_state, "No viable transfer found — "
                       "no surplus, no compatible alternative within range")


def _build_direct(result, needy_row, is_critical):
    return {
        "type"              : "DIRECT",
        "priority"          : needy_row['stock_state'],
        "needy_facility"    : needy_row['facility_id'],
        "blood_group"       : needy_row['blood_group'],
        "component"         : needy_row['component'],
        "units_needed"      : result['needed'],
        "auto_confirmed"    : is_critical,
        "compatibility_used": False,
        "legs"              : [{
            "from"       : result['source_id'],
            "to"         : needy_row['facility_id'],
            "units"      : result['units'],
            "distance_km": result['distance_km'],
            "prep_time_minutes": result['prep_time'],
        }],
        "vans_dispatched"   : {result['source_id']: 1},
        "admin_flag"        : False,
    }


def _try_partial(needy_row, nearest, facilities_df, surplus_df,
                 surplus_units_df, vans_available, vans_cold_chain,
                 units_needed, is_critical):
    """Try to fulfill need across two sources."""
    sources_found = []
    units_covered = 0

    for _, candidate in nearest.iterrows():
        if candidate['distance_km'] > MAX_DIRECT_KM:
            break
        if units_covered >= units_needed:
            break

        remaining_needy         = needy_row.copy()
        remaining_needy['available_units'] = (
            needy_row['available_units'] + units_covered)

        result = _try_source(
            candidate['facility_id'], candidate['distance_km'],
            remaining_needy, facilities_df, surplus_df,
            surplus_units_df, vans_available, vans_cold_chain)
        if result is None:
            continue

        sources_found.append(result)
        units_covered += result['can_send']

    if len(sources_found) >= 2:
        return {
            "type"           : "PARTIAL",
            "priority"       : needy_row['stock_state'],
            "needy_facility" : needy_row['facility_id'],
            "blood_group"    : needy_row['blood_group'],
            "component"      : needy_row['component'],
            "units_needed"   : units_needed,
            "units_covered"  : units_covered,
            "auto_confirmed" : is_critical,
            "compatibility_used": False,
            "legs"           : [{
                "from"             : s['source_id'],
                "to"               : needy_row['facility_id'],
                "units"            : s['units'],
                "distance_km"      : s['distance_km'],
                "prep_time_minutes": s['prep_time'],
            } for s in sources_found],
            "vans_dispatched": {s['source_id']: 1 for s in sources_found},
            "admin_flag"     : False,
        }
    return None


def _try_relay(needy_row, needy_fac, nearest, facilities_df,
               surplus_df, surplus_units_df,
               vans_available, vans_cold_chain, is_critical):
    """Try one-hop relay transfer."""
    for _, mid_candidate in nearest.iterrows():
        mid_id   = mid_candidate['facility_id']
        mid_dist = mid_candidate['distance_km']

        if mid_dist > MAX_RELAY_KM:
            break

        # Mid facility must not itself be in shortage for this combo
        mid_in_surplus = not surplus_df[
            (surplus_df['facility_id'] == mid_id) &
            (surplus_df['blood_group'] == needy_row['blood_group']) &
            (surplus_df['component']   == needy_row['component'])
        ].empty

        if not mid_in_surplus:
            continue

        mid_fac       = facilities_df[
            facilities_df['facility_id'] == mid_id].iloc[0]
        nearest_to_mid = get_nearest_facilities(
            mid_fac, facilities_df,
            exclude_ids=[needy_row['facility_id'], mid_id])

        for _, src_candidate in nearest_to_mid.iterrows():
            src_id    = src_candidate['facility_id']
            src_dist  = src_candidate['distance_km']
            total_dist = mid_dist + src_dist

            if total_dist > MAX_RELAY_KM:
                break

            result = _try_source(
                src_id, src_dist, needy_row, facilities_df,
                surplus_df, surplus_units_df,
                vans_available, vans_cold_chain)
            if result is None:
                continue

            # Check van at mid too
            van_ok, van_reason = _check_van(
                mid_id, needy_row['component'],
                vans_available, vans_cold_chain)
            if not van_ok:
                continue

            prep_src = _get_prep_time(src_id, facilities_df)
            prep_mid = _get_prep_time(mid_id, facilities_df)

            return {
                "type"           : "RELAY",
                "priority"       : needy_row['stock_state'],
                "needy_facility" : needy_row['facility_id'],
                "blood_group"    : needy_row['blood_group'],
                "component"      : needy_row['component'],
                "units_needed"   : result['needed'],
                "auto_confirmed" : is_critical,
                "compatibility_used": False,
                "simultaneous"   : True,
                "legs"           : [
                    {"from": src_id, "to": mid_id,
                     "distance_km": round(src_dist, 2),
                     "prep_time_minutes": prep_src},
                    {"from": mid_id, "to": needy_row['facility_id'],
                     "distance_km": round(mid_dist, 2),
                     "prep_time_minutes": prep_mid},
                ],
                "units_dispatched_from_source": result['units'],
                "vans_dispatched": {src_id: 1, mid_id: 1},
                "admin_flag"     : False,
            }
    return None


def check_van_reassignment(arrived_at_facility, vans_available, pending_transfers):
    for transfer in pending_transfers:
        for leg in transfer['legs']:
            if leg['from'] == arrived_at_facility:
                return {
                    "reassigned"       : True,
                    "van_from"         : arrived_at_facility,
                    "assigned_to_leg"  : leg,
                    "transfer_priority": transfer['priority'],
                    "blood_group"      : transfer['blood_group'],
                    "component"        : transfer['component'],
                }
    return None


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