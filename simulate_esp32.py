"""
Simulated ESP32 — stands in for the real hardware until it's built.
Mimics: card scan, bin-presence detection, weight-feedback dispensing loop, telemetry.

Run this in a separate terminal AFTER server.py is running:
    python simulate_esp32.py
"""

import socketio
import time
import threading
import random
import sys

sio = socketio.Client()

DEMO_CARD_ID = "TNPDS1001"


@sio.event
def connect():
    print("[ESP32-sim] Connected to server")
    time.sleep(1)
    print(f"[ESP32-sim] Simulating RFID scan of card {DEMO_CARD_ID}")
    sio.emit("esp32_card_scanned", {"card_id": DEMO_CARD_ID})

    # background telemetry loop
    threading.Thread(target=telemetry_loop, daemon=True).start()


def telemetry_loop():
    battery = 82
    while True:
        time.sleep(10)
        battery = max(10, battery - random.randint(0, 1))  # slowly drains
        sio.emit("esp32_sensor_telemetry", {
            "battery_pct": battery,
            "solar_status": "CHARGING",
            "online": True,
            "hopper_levels": {"rice": 68, "wheat": 42, "dal": 18, "sugar": 73},
        })


@sio.on("esp32_start_dispense")
def on_start_dispense(data):
    commodity = data["commodity"]
    target_kg = data["quantity_kg"]
    print(f"[ESP32-sim] Received dispense command: {commodity} -> {target_kg}kg")
    threading.Thread(target=simulate_bin_and_dispense, args=(commodity, target_kg), daemon=True).start()


def simulate_bin_and_dispense(commodity, target_kg):
    # Simulate the person placing a container after a short delay (well within the 90s timeout)
    time.sleep(3)
    print(f"[ESP32-sim] Bin detected for {commodity}")
    sio.emit("esp32_bin_present", {"commodity": commodity})


@sio.on("esp32_open_gate")
def on_open_gate(data):
    commodity = data["commodity"]
    threading.Thread(target=run_dispensing, args=(commodity,), daemon=True).start()


# keep track of the target weight per commodity for the currently running job
_targets = {}


@sio.on("esp32_start_dispense")
def stash_target(data):
    _targets[data["commodity"]] = data["quantity_kg"]


def run_dispensing(commodity):
    target_kg = _targets.get(commodity, 1.0)
    actual = 0.0
    step = target_kg / 12  # ~12 updates to reach target, mimics gradual auger/gate flow
    print(f"[ESP32-sim] Gate open for {commodity}, dispensing toward {target_kg}kg")

    while actual < target_kg:
        time.sleep(0.3)
        actual = min(target_kg, round(actual + step, 3))
        sio.emit("esp32_weight_update", {
            "commodity": commodity,
            "target_weight_kg": target_kg,
            "actual_weight_kg": actual,
        })

    # small realistic overshoot/undershoot within +/-50g tolerance
    final_weight = round(actual + random.uniform(-0.02, 0.02), 3)
    time.sleep(0.3)
    print(f"[ESP32-sim] Gate closed for {commodity}. Final weight: {final_weight}kg")
    sio.emit("esp32_dispense_done", {
        "commodity": commodity,
        "target_weight_kg": target_kg,
        "final_weight_kg": final_weight,
        "status": "success",
    })


if __name__ == "__main__":
    print("Connecting simulated ESP32 to backend...")
    sio.connect("http://localhost:5000")
    sio.wait()
