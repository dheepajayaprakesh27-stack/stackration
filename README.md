# Smart Ration Dispenser — Software (Working Prototype)

## Files
- `create_tnpds_db.py` — builds the simulated TNPDS SQLite database (30 beneficiaries)
- `db_helper.py` — entitlement validation, pricing, transaction logging (customer + admin queries)
- `billing.py` — UPI QR code generation for the bill
- `server.py` — Flask-SocketIO backend (the hub: ESP32 <-> server <-> laptop UI)
- `templates/index.html` — laptop UI (replaces the touchscreen) — scan, entitlement, +/- selector, bill+QR, dispensing progress
- `simulate_esp32.py` — stands in for the real ESP32 hardware until it's built
- `test_full_flow.py` — automated end-to-end test (already verified working)

## How to run once you have real ESP32 hardware
1. `python create_tnpds_db.py`   (one-time, builds the database)
2. `python server.py`            (starts the backend on port 5000)
3. Flash the ESP32 with matching firmware that emits the same socket events
   (esp32_card_scanned, esp32_bin_present, esp32_weight_update, esp32_dispense_done,
   esp32_sensor_telemetry) — connects over WiFi to the server's IP.
4. Open `http://<laptop-ip>:5000` in a browser on the laptop — this is your UI.

## How to test right now, without hardware
1. `python create_tnpds_db.py`
2. `python server.py` (terminal 1)
3. `python simulate_esp32.py` (terminal 2 — pretends to be the ESP32)
4. Open `http://localhost:5000` in a browser (terminal 3 not needed, just a browser)
5. Click through: scan happens automatically from the simulator, select quantities,
   confirm, watch it "dispense" with simulated progress.

Demo card ID used by the simulator: TNPDS1001 (Kumar, 2-member family, 8kg rice limit)

## Still to build
- ThingSpeak integration (telemetry push — currently just logged to console, see TODO in server.py)
- Firebase sync for the admin/customer dashboard views
- Real ESP32 firmware (Arduino/C++) matching this socket protocol
- Admin dashboard UI (separate page, currently only customer-facing UI exists)
