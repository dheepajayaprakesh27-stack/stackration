"""
End-to-end test: runs the server in a background thread, then drives it with
two simulated socket clients (ESP32 + laptop UI) to verify the whole flow works,
all in a single process so it survives in this sandbox.
"""

import threading
import time
import socketio as socketio_client
import server as server_module

DEMO_CARD_ID = "TNPDS1001"

# ---------- Start the server in a background thread ----------
def run_server():
    server_module.socketio.run(server_module.app, host="127.0.0.1", port=5000,
                                debug=False, allow_unsafe_werkzeug=True, log_output=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)
print("=== Server started ===\n")

# ---------- Simulated ESP32 client ----------
esp32 = socketio_client.Client()
targets = {}

@esp32.on("esp32_start_dispense")
def on_start(data):
    targets[data["commodity"]] = data["quantity_kg"]
    print(f"[ESP32] Got dispense command: {data}")
    def place_bin():
        time.sleep(0.5)
        print(f"[ESP32] Container placed for {data['commodity']}")
        esp32.emit("esp32_bin_present", {"commodity": data["commodity"]})
    threading.Thread(target=place_bin, daemon=True).start()

@esp32.on("esp32_open_gate")
def on_open_gate(data):
    commodity = data["commodity"]
    def dispense():
        target = targets[commodity]
        actual = 0.0
        step = target / 6
        while actual < target:
            time.sleep(0.1)
            actual = min(target, round(actual + step, 3))
            esp32.emit("esp32_weight_update", {"commodity": commodity, "target_weight_kg": target, "actual_weight_kg": actual})
        final_weight = round(actual, 3)
        print(f"[ESP32] Gate closed for {commodity}, final={final_weight}kg")
        esp32.emit("esp32_dispense_done", {"commodity": commodity, "target_weight_kg": target, "final_weight_kg": final_weight, "status": "success"})
    threading.Thread(target=dispense, daemon=True).start()

esp32.connect("http://127.0.0.1:5000")
time.sleep(0.5)

# ---------- Simulated laptop UI client (connect BEFORE triggering the scan) ----------
ui = socketio_client.Client()
transaction_done = threading.Event()

@ui.on("entitlement_data")
def on_entitlement(data):
    print(f"\n[UI] Entitlement received: {data}\n")

    # Test 1: request an amount that EXCEEDS entitlement (should fail)
    print("[TEST] Requesting 999kg rice (should be rejected)...")
    ui.emit("ui_select_quantities", {"card_id": DEMO_CARD_ID, "selections": {"rice": 999, "wheat": 0, "dal": 0, "sugar": 0}})

@ui.on("selection_errors")
def on_errors(data):
    print(f"[UI] Selection errors (expected for the 999kg test): {data}\n")

    # Test 2: now request a VALID mixed selection including a partial amount (0.8kg dal)
    print("[TEST] Requesting valid mix: rice=2.5kg, wheat=1.0kg (free), dal=0.8kg, sugar=0...")
    ui.emit("ui_select_quantities", {"card_id": DEMO_CARD_ID, "selections": {"rice": 2.5, "wheat": 1.0, "dal": 0.8, "sugar": 0}})

@ui.on("bill_ready")
def on_bill(data):
    print(f"[UI] Bill ready: {data['items']}")
    print(f"[UI] Total: Rs.{data['total_amount']}  |  QR generated: {'YES' if data['qr_image_base64'] else 'NO'}\n")
    print("[TEST] Confirming payment, starting dispensing sequence...\n")
    ui.emit("ui_confirm_payment", {"items": data["items"]})

@ui.on("bin_prompt")
def on_bin_prompt(data):
    print(f"[UI] Prompt: place container for {data['commodity']}")

@ui.on("dispense_item_done")
def on_item_done(data):
    print(f"[UI] Item done: {data}\n")

@ui.on("transaction_complete")
def on_complete(data):
    print(f"[UI] === TRANSACTION COMPLETE === {data}")
    transaction_done.set()

@ui.on("machine_status")
def on_status(data):
    print(f"[UI] Machine status: {'AVAILABLE' if data['available'] else 'UNAVAILABLE'}")

ui.connect("http://127.0.0.1:5000")
time.sleep(0.5)

print(f"[ESP32] Simulating card scan: {DEMO_CARD_ID}")
esp32.emit("esp32_card_scanned", {"card_id": DEMO_CARD_ID})
esp32.emit("esp32_sensor_telemetry", {"battery_pct": 82, "solar_status": "CHARGING", "online": True})

transaction_done.wait(timeout=8)

time.sleep(1)
print("\n=== Checking database after transaction ===")
import db_helper
print("Remaining entitlement now:", db_helper.get_all_remaining(DEMO_CARD_ID))
print("\nCustomer history:")
for row in db_helper.get_customer_history(DEMO_CARD_ID):
    print(" ", row)

esp32.disconnect()
ui.disconnect()
print("\n=== TEST COMPLETE ===")
