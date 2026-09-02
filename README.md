HemoLynk- AI driven Blood Bank Management System with Risk Redistribution Engine

AI-Driven Blood Bank Inventory Management System with Risk Redistribution Engine

1. Problem Statement

India collects ~14.6M blood units annually — enough to meet national demand — yet suffers simultaneous wastage and shortage due to systemic fragmentation:

No centralized real-time inventory visibility; facilities rely on phone calls and manual registers.
Manual redistribution is too slow to intercept near-expiry units (44,000 units wasted in Karnataka alone in one reporting period).
Rural "blood deserts" lack logistics infrastructure for last-mile delivery.
Hospitals, NGOs, blood banks, and donors operate in silos, preventing coordinated response during surge events.

2. Target Users
User	Need
Blood bank / hospital admins	Real-time stock visibility, shortage alerts, redistribution requests
Facility coordinators (rural/Tier 2-3)	Fast access to surplus stock from other facilities
NGOs / govt blood transfusion councils	Oversight across a network of facilities
Donors	Easy registration, matching, and donation scheduling
Transport/logistics operators	Optimized delivery routes between facilities

3. Goals
Cut blood wastage from expiry through proactive detection and redistribution.
Speed up redistribution to underserved/rural facilities.
Improve donor screening and donor-recipient matching.
Provide a single real-time source of truth for blood stock across a network.

4. Core Features
Unified Inventory Dashboard – real-time stock by blood group/component across all registered facilities.
Predictive Shortage Forecasting (ML) – Scikit-Learn regression model flags "O- will run out in 2 days" type alerts using historical usage.
Risk Redistribution Engine – greedy scoring algorithm ranks high-risk hospitals and triggers reallocation of near-expiry stock.
Route Optimization – Dijkstra's algorithm + Google Maps Distance Matrix API to compute fastest transport routes for redistribution vans.
Donor Vault – donor profile registry with matching logic (blood group, location, eligibility, donation history) and FCM notifications.
Notifications – push alerts to facility managers/donors/admins for low stock, expiry risk, and redistribution requests.

5. MVP Scope In:
Facility onboarding + manual/CSV inventory entry
Real-time dashboard (stock by facility, blood group, expiry date)
Expiry forecasting (Linear Regression on historical + synthetic data)
Greedy-scoring redistribution engine (single-region scope)
Dijkstra-based route suggestion between 2 facilities (no live van tracking)
Donor registration + basic matching (blood group + location)
Push notifications (FCM) for shortage/expiry/redistribution events
Android app (Flutter) + admin web dashboard

6. Out-of-Scope (for MVP)
Laboratory Information System (LIS) integration
Live GPS van tracking (route suggestion only, not real-time fleet tracking)
Blockchain-based security/audit trail
Multilingual IVR/SMS donor outreach
iOS app (Android + web only)
Gamification for donor retention
Multi-region/national scale redistribution (single-region MVP)
Automated fraud/anomaly detection on requests

7. Acceptance Criteria (MVP)
Dashboard reflects inventory changes across facilities within 5 minutes of update.
Shortage prediction generates an alert at least 24 hours before a facility's projected stockout for a given blood type.
Redistribution engine returns a ranked list of eligible receiving facilities for any flagged near-expiry unit, with score rationale visible to admin.
Route suggestion returns a valid path with estimated distance/time for any two onboarded facilities within the region.
Donor can register, and system returns matching donors for a given blood group + location query.
All critical alerts (shortage, expiry, redistribution) trigger FCM push notifications to relevant users.
