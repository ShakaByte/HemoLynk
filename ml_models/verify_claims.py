import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)

emails = [
    "vedu.pokale2004+dhadmin@gmail.com",
    "vedu.pokale2004+bbadmin@gmail.com",
    "vedu.pokale2004+phcadmin@gmail.com",
    "vedu.pokale2004+coord1@gmail.com",
    "vedu.pokale2004+coord2@gmail.com",
    "vedu.pokale2004+coord3@gmail.com",
    "vedu.pokale2004+donor1@gmail.com",
    "vedu.pokale2004+donor2@gmail.com",
    "vedu.pokale2004+donor3@gmail.com",
]

for email in emails:
    user = auth.get_user_by_email(email)
    print(f"{email}\n  uid: {user.uid}\n  claims: {user.custom_claims}\n")