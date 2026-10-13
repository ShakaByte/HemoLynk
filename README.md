# 🩸 HemoLynk

AI-driven blood bank inventory management system with a risk redistribution engine.

## 📌 Overview

HemoLynk is a cross-platform app that gives blood banks, hospitals, and donors a single real-time view of blood stock across a network of facilities. It predicts shortages, flags near-expiry units, and suggests where to redistribute them and by which route.

## ❗ Problem Statement

India collects ~14.6M blood units a year, enough to meet demand, yet faces wastage and shortage at the same time:
- No centralized real-time inventory. Facilities rely on phone calls and manual registers.
- Manual redistribution is too slow to save near-expiry units (about 44,000 units wasted in Karnataka in one reporting period).
- Rural "blood deserts" lack last-mile logistics.
- Hospitals, NGOs, blood banks, and donors work in silos.

## ✅ Solution

- **Unified dashboard:** real-time stock by facility, blood group, and expiry date
- **Shortage forecasting:** Random Forest model predicts stockouts from historical usage
- **Risk redistribution engine:** greedy scoring ranks high-risk facilities and suggests reallocation of near-expiry stock, with score rationale shown to admins
- **Route optimization:** Dijkstra's algorithm finds the fastest path between facilities
- **Donor vault:** registration and matching by blood group, location, and eligibility
- **Role-based access** for admins, donors, and employees

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Flutter |
| Backend | FastAPI, Python |
| Database / Auth | Firebase |
| ML | Scikit-Learn (Random Forest) |
| Algorithms | Greedy scoring, Dijkstra |

## 📊 Scope

- 54 facilities across 6 districts
- Synthetic dataset: 1000+ inventory records, 1000 donors
- Tested with 9 accounts (3 per role)
