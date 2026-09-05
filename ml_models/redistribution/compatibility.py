"""
compatibility.py

Defines blood group compatibility rules for transfusion.
Used by the redistribution engine when exact blood group
match is unavailable — suggests compatible alternatives
ranked by preference (closest match first).

Compatibility follows standard transfusion medicine rules:
- O- is universal donor (can give to anyone)
- AB+ is universal recipient (can receive from anyone)
- Negative groups can only receive from negative donors
- Positive groups can receive from both positive and negative donors
"""

# For each blood group that NEEDS blood, which groups can DONATE to them
# Listed in order of preference (best match first, universal donor last)
COMPATIBILITY = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],
}

# Components where compatibility rules apply
# Platelets follow ABO compatibility but less strictly in emergencies
# Plasma compatibility is REVERSE (AB plasma is universal donor for plasma)
PLASMA_COMPATIBILITY = {
    "A+":  ["A+", "A-", "AB+", "AB-"],
    "A-":  ["A+", "A-", "AB+", "AB-"],
    "B+":  ["B+", "B-", "AB+", "AB-"],
    "B-":  ["B+", "B-", "AB+", "AB-"],
    "AB+": ["AB+", "AB-"],
    "AB-": ["AB+", "AB-"],
    "O+":  ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"],
    "O-":  ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"],
}


def get_compatible_groups(blood_group, component):
    """
    Returns ordered list of compatible donor blood groups
    for a given recipient blood group and component.

    First entry is always the exact match (ideal).
    Remaining are alternatives in preference order.
    """
    if component == "Plasma":
        return PLASMA_COMPATIBILITY.get(blood_group, [blood_group])
    return COMPATIBILITY.get(blood_group, [blood_group])


def is_compatible(donor_group, recipient_group, component):
    """
    Returns True if donor_group can be transfused into recipient_group
    for the given component.
    """
    compatible = get_compatible_groups(recipient_group, component)
    return donor_group in compatible


def suggest_alternatives(blood_group, component, available_groups):
    """
    Given a blood group in shortage and a list of blood groups
    that ARE available somewhere, returns compatible alternatives
    ranked by preference — for auto-suggesting to admin.

    Parameters:
        blood_group     : the blood group that's in shortage e.g. "A-"
        component       : e.g. "Whole Blood"
        available_groups: list of blood groups that exist in surplus
                          at nearby facilities

    Returns: list of dicts ranked by preference
    """
    compatible_ordered = get_compatible_groups(blood_group, component)

    suggestions = []
    for group in compatible_ordered:
        if group == blood_group:
            continue  # skip exact match, that's already been tried
        if group in available_groups:
            suggestions.append({
                "alternative_group": group,
                "for_recipient"    : blood_group,
                "component"        : component,
                "preference_rank"  : compatible_ordered.index(group),
                "note"             : (
                    "Universal donor — use only if no closer match available"
                    if group == "O-" else
                    "Compatible alternative"
                )
            })

    return suggestions


if __name__ == "__main__":
    # Test 1: what can A- receive?
    print("=== Compatible groups for A- recipient ===")
    print(get_compatible_groups("A-", "Whole Blood"))

    # Test 2: what can AB+ receive?
    print("\n=== Compatible groups for AB+ recipient ===")
    print(get_compatible_groups("AB+", "Whole Blood"))

    # Test 3: plasma is reverse
    print("\n=== Compatible PLASMA groups for O+ recipient ===")
    print(get_compatible_groups("O+", "Plasma"))

    # Test 4: suggest alternatives when A- is in shortage
    print("\n=== Alternatives for A- shortage (Whole Blood) ===")
    available = ["O+", "O-", "B+", "AB+"]
    suggestions = suggest_alternatives("A-", "Whole Blood", available)
    for s in suggestions:
        print(f"  {s['alternative_group']} (rank {s['preference_rank']}): {s['note']}")

    # Test 5: no alternatives available
    print("\n=== Alternatives for O- shortage (Whole Blood) ===")
    available = ["A+", "B+", "AB+"]
    suggestions = suggest_alternatives("O-", "Whole Blood", available)
    print(f"  Suggestions: {suggestions if suggestions else 'None — admin must source externally'}")