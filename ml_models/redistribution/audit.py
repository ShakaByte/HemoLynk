"""
audit.py

Logs every system event related to transfers, donor searches,
and admin flags with timestamp, actor, and outcome.

In Phase 4 this will write directly to Firestore.
For now it writes to a local JSON file for verification.

Event types:
    TRANSFER_REQUESTED   — system identified shortage, found source
    TRANSFER_CONFIRMED   — source facility accepted (or auto-confirmed for CRITICAL)
    TRANSFER_REJECTED    — source facility rejected within time window
    TRANSFER_EXPIRED     — source facility did not respond in time
    TRANSFER_DISPATCHED  — van left source facility
    TRANSFER_DELIVERED   — van arrived at destination
    PARTIAL_FULFILLMENT  — need split across two sources
    VAN_REASSIGNED       — van reused at delivery point for next job
    DONOR_SEARCH_TRIGGERED — donor notification sent out
    DONOR_RESPONDED      — donor confirmed availability
    ADMIN_FLAGGED        — system could not resolve, admin notified
    COMPATIBILITY_USED   — exact match unavailable, compatible alt suggested
"""

import json
import uuid
from datetime import datetime


# In Phase 4: replace this with Firestore write
AUDIT_LOG_PATH = "audit_log.json"


def _load_log():
    try:
        with open(AUDIT_LOG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_log(log):
    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2, default=str)


def log_event(event_type, actor_facility_id, details: dict, priority="SHORTAGE"):
    """
    Logs a single audit event.

    Parameters:
        event_type        : one of the event type strings above
        actor_facility_id : facility that triggered or is involved in the event
        details           : dict of any relevant info (blood group, units, reason etc)
        priority          : CRITICAL or SHORTAGE
    """
    event = {
        "event_id"        : str(uuid.uuid4()),
        "timestamp"       : datetime.now().isoformat(),
        "event_type"      : event_type,
        "priority"        : priority,
        "actor_facility"  : actor_facility_id,
        "details"         : details,
    }

    log = _load_log()
    log.append(event)
    _save_log(log)

    return event


def log_transfer_requested(needy_facility, source_facility, blood_group,
                            component, units, distance_km, transfer_type,
                            priority, auto_confirmed=False):
    details = {
        "source_facility" : source_facility,
        "needy_facility"  : needy_facility,
        "blood_group"     : blood_group,
        "component"       : component,
        "units_requested" : units,
        "distance_km"     : distance_km,
        "transfer_type"   : transfer_type,  # DIRECT or RELAY
        "auto_confirmed"  : auto_confirmed,  # True for CRITICAL
    }
    event_type = "TRANSFER_CONFIRMED" if auto_confirmed else "TRANSFER_REQUESTED"
    return log_event(event_type, needy_facility, details, priority)


def log_transfer_confirmed(needy_facility, source_facility, blood_group,
                            component, units, priority):
    details = {
        "source_facility": source_facility,
        "blood_group"    : blood_group,
        "component"      : component,
        "units_confirmed": units,
    }
    return log_event("TRANSFER_CONFIRMED", needy_facility, details, priority)


def log_transfer_rejected(needy_facility, source_facility, blood_group,
                           component, reason, priority):
    details = {
        "source_facility": source_facility,
        "blood_group"    : blood_group,
        "component"      : component,
        "reason"         : reason,
    }
    return log_event("TRANSFER_REJECTED", needy_facility, details, priority)


def log_transfer_expired(needy_facility, source_facility, blood_group,
                          component, priority):
    details = {
        "source_facility": source_facility,
        "blood_group"    : blood_group,
        "component"      : component,
        "reason"         : "Source facility did not respond within time window",
    }
    return log_event("TRANSFER_EXPIRED", needy_facility, details, priority)


def log_dispatched(source_facility, needy_facility, blood_group,
                   component, units, prep_time_minutes, priority):
    details = {
        "to_facility"      : needy_facility,
        "blood_group"      : blood_group,
        "component"        : component,
        "units_dispatched" : units,
        "prep_time_minutes": prep_time_minutes,
    }
    return log_event("TRANSFER_DISPATCHED", source_facility, details, priority)


def log_delivered(source_facility, needy_facility, blood_group,
                  component, units, priority):
    details = {
        "from_facility"  : source_facility,
        "blood_group"    : blood_group,
        "component"      : component,
        "units_delivered": units,
    }
    return log_event("TRANSFER_DELIVERED", needy_facility, details, priority)


def log_partial_fulfillment(needy_facility, sources, blood_group,
                             component, total_needed, priority):
    details = {
        "blood_group"  : blood_group,
        "component"    : component,
        "total_needed" : total_needed,
        "sources"      : sources,  # list of {facility_id, units}
    }
    return log_event("PARTIAL_FULFILLMENT", needy_facility, details, priority)


def log_van_reassigned(facility_id, from_job, to_job):
    details = {
        "completed_delivery": from_job,
        "reassigned_to"     : to_job,
    }
    return log_event("VAN_REASSIGNED", facility_id, details)


def log_donor_search(needy_facility, blood_group, component,
                     donors_notified, priority):
    details = {
        "blood_group"     : blood_group,
        "component"       : component,
        "donors_notified" : donors_notified,
    }
    return log_event("DONOR_SEARCH_TRIGGERED", needy_facility, details, priority)


def log_compatibility_used(needy_facility, original_group, alternative_group,
                            component, priority):
    details = {
        "original_blood_group"    : original_group,
        "alternative_blood_group" : alternative_group,
        "component"               : component,
        "reason"                  : "Exact match unavailable, compatible alternative suggested",
    }
    return log_event("COMPATIBILITY_USED", needy_facility, details, priority)


def log_admin_flagged(needy_facility, blood_group, component, reason, priority):
    details = {
        "blood_group": blood_group,
        "component"  : component,
        "reason"     : reason,
    }
    return log_event("ADMIN_FLAGGED", needy_facility, details, priority)


def get_log():
    """Returns full audit log as a list."""
    return _load_log()


def get_facility_log(facility_id):
    """Returns all events involving a specific facility."""
    return [e for e in _load_log()
            if e['actor_facility'] == facility_id or
               e['details'].get('source_facility') == facility_id or
               e['details'].get('needy_facility') == facility_id]


def print_log_summary():
    log = _load_log()
    if not log:
        print("Audit log is empty.")
        return

    from collections import Counter
    event_counts = Counter(e['event_type'] for e in log)
    priority_counts = Counter(e['priority'] for e in log)

    print(f"Total events logged: {len(log)}")
    print("\nBy event type:")
    for event_type, count in event_counts.most_common():
        print(f"  {event_type}: {count}")
    print("\nBy priority:")
    for priority, count in priority_counts.most_common():
        print(f"  {priority}: {count}")
    print(f"\nFirst event: {log[0]['timestamp']}")
    print(f"Last event : {log[-1]['timestamp']}")


if __name__ == "__main__":
    import os

    # Clean slate for testing
    if os.path.exists(AUDIT_LOG_PATH):
        os.remove(AUDIT_LOG_PATH)

    # Simulate a full transfer lifecycle
    print("Logging simulated transfer lifecycle...\n")

    log_transfer_requested(
        needy_facility="FAC001", source_facility="FAC007",
        blood_group="O+", component="Whole Blood",
        units=3, distance_km=14.2, transfer_type="DIRECT",
        priority="SHORTAGE", auto_confirmed=False)

    log_transfer_confirmed(
        needy_facility="FAC001", source_facility="FAC007",
        blood_group="O+", component="Whole Blood",
        units=3, priority="SHORTAGE")

    log_dispatched(
        source_facility="FAC007", needy_facility="FAC001",
        blood_group="O+", component="Whole Blood",
        units=3, prep_time_minutes=30, priority="SHORTAGE")

    log_delivered(
        source_facility="FAC007", needy_facility="FAC001",
        blood_group="O+", component="Whole Blood",
        units=3, priority="SHORTAGE")

    log_compatibility_used(
        needy_facility="FAC002", original_group="A-",
        alternative_group="O-", component="Whole Blood",
        priority="SHORTAGE")

    log_admin_flagged(
        needy_facility="FAC003", blood_group="AB-",
        component="Platelets",
        reason="No surplus or compatible alternative found within range",
        priority="SHORTAGE")

    print_log_summary()

    print("\nFAC001 event log:")
    fac_log = get_facility_log("FAC001")
    for e in fac_log:
        print(f"  [{e['timestamp']}] {e['event_type']} | {e['details'].get('blood_group','')} {e['details'].get('component','')}")