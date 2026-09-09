"""
create_auth_users.py

Creates Firebase Auth test accounts for Demo 1.
Sets custom claims (role + facility_id) on each account.

Roles:
  facility_admin — manages one facility's inventory/transfers
  coordinator    — coordinates transfers between facilities
  donor          — donor mobile app user

Run once. If accounts already exist, script will skip them.
"""

import firebase_admin
from firebase_admin import credentials, auth
import time

cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)

# ── Test accounts ─────────────────────────────────────────────────
# Using Gmail +tag trick so all emails go to one inbox
# Replace "youremail" with your actual Gmail address

BASE_EMAIL = "vedu.pokale2004@gmail.com"  # ← change this to your Gmail

def make_email(tag):
    user, domain = BASE_EMAIL.split("@")
    return f"{user}+{tag}@{domain}"

ACCOUNTS = [
    # Facility Admins
    {
        "email"      : make_email("dhadmin"),
        "password"   : "HemoLynk@DH1",
        "display_name": "DH Admin - Ballari DH 1",
        "claims"     : {"role": "facility_admin", "facility_id": "FAC001", "district": "Ballari"}
    },
    {
        "email"      : make_email("bbadmin"),
        "password"   : "HemoLynk@BB1",
        "display_name": "BB Admin - Ballari Blood Bank 1",
        "claims"     : {"role": "facility_admin", "facility_id": "FAC004", "district": "Ballari"}
    },
    {
        "email"      : make_email("phcadmin"),
        "password"   : "HemoLynk@PHC1",
        "display_name": "PHC Admin - Ballari PHC 1",
        "claims"     : {"role": "facility_admin", "facility_id": "FAC007", "district": "Ballari"}
    },

    # Coordinators
    {
        "email"      : make_email("coord1"),
        "password"   : "HemoLynk@Coord1",
        "display_name": "Coordinator 1 - Ballari DH",
        "claims"     : {"role": "coordinator", "facility_id": "FAC001", "district": "Ballari"}
    },
    {
        "email"      : make_email("coord2"),
        "password"   : "HemoLynk@Coord2",
        "display_name": "Coordinator 2 - Ballari BB",
        "claims"     : {"role": "coordinator", "facility_id": "FAC004", "district": "Ballari"}
    },
    {
        "email"      : make_email("coord3"),
        "password"   : "HemoLynk@Coord3",
        "display_name": "Coordinator 3 - Ballari PHC",
        "claims"     : {"role": "coordinator", "facility_id": "FAC007", "district": "Ballari"}
    },

    # Donors
    {
        "email"      : make_email("donor1"),
        "password"   : "HemoLynk@Donor1",
        "display_name": "Test Donor 1 - O+",
        "claims"     : {"role": "donor", "donor_id": "DON0001", "district": "Ballari"}
    },
    {
        "email"      : make_email("donor2"),
        "password"   : "HemoLynk@Donor2",
        "display_name": "Test Donor 2 - A+",
        "claims"     : {"role": "donor", "donor_id": "DON0002", "district": "Ballari"}
    },
    {
        "email"      : make_email("donor3"),
        "password"   : "HemoLynk@Donor3",
        "display_name": "Test Donor 3 - B+",
        "claims"     : {"role": "donor", "donor_id": "DON0003", "district": "Ballari"}
    },
]


def create_accounts():
    print("Creating Firebase Auth test accounts...\n")

    for account in ACCOUNTS:
        email = account['email']
        try:
            # Check if user already exists
            existing = auth.get_user_by_email(email)
            print(f"  Already exists: {email} (uid: {existing.uid})")
            uid = existing.uid

        except auth.UserNotFoundError:
            # Create new user
            user = auth.create_user(
                email        = email,
                password     = account['password'],
                display_name = account['display_name'],
            )
            uid = user.uid
            print(f"  Created: {email} (uid: {uid})")

        # Set custom claims (role + facility/donor id)
        auth.set_custom_user_claims(uid, account['claims'])
        print(f"    Claims set: {account['claims']}")
        time.sleep(0.5)  # avoid rate limiting

    print(f"\n✅ All {len(ACCOUNTS)} accounts ready.")
    print("\nAccount summary:")
    print(f"{'Email':<45} {'Role':<20} {'Facility/Donor'}")
    print("-" * 80)
    for a in ACCOUNTS:
        role     = a['claims']['role']
        fac      = a['claims'].get('facility_id', a['claims'].get('donor_id', ''))
        print(f"{a['email']:<45} {role:<20} {fac}")


if __name__ == "__main__":
    create_accounts()