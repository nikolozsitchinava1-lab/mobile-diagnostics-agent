# 🚗 Mobile Auto Diagnostics AI Assistant

An AI-powered booking and triage assistant built with **LangGraph**, **Groq**, and **Streamlit** for a mobile automotive diagnostics and pre-purchase car inspection service in Tbilisi, Georgia.

## 🎯 What It Does
- **Lead Qualification:** Collects vehicle details (make/model/year or 17-character VIN), symptoms, service type (`obd2_scan` vs. `pre_purchase`), and Tbilisi district in Georgian or English.
- **VIN Decoding (External API #1):** Integrates with the **NHTSA vPIC API** to decode vehicle VINs and verify engine/fuel specifications.
- **Distance & Call-Out Quote Calculation (External API #2):** Uses the **OSRM Routing API** to calculate real driving distance and travel time from central Tbilisi (Saburtalo) and compute an estimated call-out fee in GEL.
- **Stateful Booking Management & Human-in-the-Loop Approval:** Supports creating, listing, and canceling appointments with persistent session memory (`InMemorySaver` + `thread_id`) and mandatory `interrupt()` confirmation before deleting any booking.

## 🛠️ Tools & External APIs
1. `decode_vehicle_vin(vin)` — Calls `vpic.nhtsa.dot.gov` to retrieve vehicle specifications.
2. `calculate_callout_quote(district, service_type)` — Calls `router.project-osrm.org` to calculate driving distance/time and estimate pricing.
3. `create_booking(...)` — Stores confirmed appointments in session-isolated memory.
4. `list_bookings(thread_id)` — Retrieves active appointments for the current user.
5. `cancel_booking(thread_id, booking_id)` — Pauses execution via LangGraph `interrupt()` and requires explicit user confirmation (`True`/`False`) before deletion.

## 🚀 How to Run Locally
1. Clone the repository and create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt