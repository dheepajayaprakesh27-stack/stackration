"""
Smart Ration Dispenser — Backend Server
-----------------------------------------
Connects: ESP32 (WiFi/WebSocket) <-> this server <-> Laptop UI (browser, WebSocket)

Run this first, then in separate terminals run:
  python simulate_esp32.py     (pretends to be the ESP32, since real hardware isn't here yet)
  open http://localhost:5000   (the laptop UI)
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import db_helper
import billing

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hackathon-demo-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---- Simple in-memory session state (single-machine demo: one active transaction at a time) ----
state = {
    "current_card_id": None,
    "dispense_queue": [],      # list of {"commodity": "rice", "quantity_kg": 2.5}
    "current_item_index": 0,
    "bin_confirmed": False,
}


@app.route("/")
def index():
    return render_template("index.html")


# ============ ESP32 -> SERVER ============

@socketio.on("esp32_card_scanned")
def handle_card_scan(data):
    card_id = data["card_id"]
    beneficiary = db_helper.get_beneficiary(card_id)
    if beneficiary is None:
        emit("invalid_card", {"card_id": card_id}, broadcast=True)
        return

    state["current_card_id"] = card_id
    remaining = db_helper.get_all_remaining(card_id)
    prices = {c: beneficiary[f"{c}_price_per_kg"] for c in db_helper.COMMODITIES}

    emit("entitlement_data", {
        "card_id": card_id,
        "name": beneficiary["name"],
        "family_members": beneficiary["family_members"],
        "remaining": remaining,
        "prices": prices,
    }, broadcast=True)
    print(f"[Auth] Card {card_id} ({beneficiary['name']}) authenticated. Remaining: {remaining}")


@socketio.on("esp32_bin_present")
def handle_bin_present(data):
    state["bin_confirmed"] = True
    emit("esp32_open_gate", {"commodity": data["commodity"]}, broadcast=True)
    print(f"[Bin] Container detected for {data['commodity']} — opening gate")


@socketio.on("esp32_weight_update")
def handle_weight_update(data):
    emit("dispense_progress", data, broadcast=True)


@socketio.on("esp32_dispense_done")
def handle_dispense_done(data):
    card_id = state["current_card_id"]
    commodity = data["commodity"]
    target = data["target_weight_kg"]
    actual = data["final_weight_kg"]
    status = data.get("status", "success")

    price_charged = db_helper.record_transaction(card_id, commodity, target, actual, status)
    print(f"[Dispense] {commodity}: target={target}kg actual={actual}kg status={status} charged=Rs.{price_charged}")

    emit("dispense_item_done", {**data, "price_charged": price_charged}, broadcast=True)

    state["current_item_index"] += 1
    _start_next_item()


@socketio.on("esp32_sensor_telemetry")
def handle_telemetry(data):
    battery = data.get("battery_pct", 0)
    solar_status = data.get("solar_status", "UNKNOWN")
    online = data.get("online", True)
    available = bool(online and battery > 15)

    emit("machine_status", {"available": available, "raw": data}, broadcast=True)
    # TODO once ThingSpeak channel/API key exist: push battery/solar/stock% via a simple HTTP GET here
    print(f"[Telemetry] battery={battery}% solar={solar_status} -> {'AVAILABLE' if available else 'UNAVAILABLE'}")


# ============ LAPTOP UI -> SERVER ============

@socketio.on("ui_select_quantities")
def handle_selection(data):
    card_id = data["card_id"]
    selections = data["selections"]  # {"rice": 2.5, "wheat": 1.0, "dal": 0.8, "sugar": 0}

    errors = {}
    valid_items = []
    for commodity, qty in selections.items():
        if qty <= 0:
            continue
        allowed, remaining, msg = db_helper.validate_request(card_id, commodity, qty)
        if not allowed:
            errors[commodity] = msg
        else:
            price = db_helper.price_for(card_id, commodity, qty)
            valid_items.append({"commodity": commodity, "quantity_kg": qty, "price": price})

    if errors:
        emit("selection_errors", {"errors": errors})
        return

    if not valid_items:
        emit("selection_errors", {"errors": {"general": "Select at least one item"}})
        return

    bill = billing.build_bill(card_id, valid_items)
    qr_b64 = billing.generate_upi_qr_base64(bill["total_amount"])
    emit("bill_ready", {**bill, "qr_image_base64": qr_b64})


@socketio.on("ui_confirm_payment")
def handle_confirm(data):
    items = data["items"]  # list of {"commodity", "quantity_kg"}
    state["dispense_queue"] = items
    state["current_item_index"] = 0
    _start_next_item()


def _start_next_item():
    idx = state["current_item_index"]
    queue = state["dispense_queue"]

    if idx >= len(queue):
        emit("transaction_complete", {"card_id": state["current_card_id"]}, broadcast=True)
        return

    item = queue[idx]
    state["bin_confirmed"] = False
    emit("bin_prompt", {"commodity": item["commodity"]}, broadcast=True)
    emit("esp32_start_dispense", item, broadcast=True)
    _start_bin_timeout(item["commodity"])


def _start_bin_timeout(commodity, timeout_sec=90):
    def waiter():
        socketio.sleep(timeout_sec)
        if not state["bin_confirmed"]:
            emit("bin_timeout", {"commodity": commodity}, broadcast=True)
            print(f"[Bin] Timeout waiting for container ({commodity}) — re-prompting")
            _start_bin_timeout(commodity, timeout_sec)   # restart the wait
    socketio.start_background_task(waiter)


if __name__ == "__main__":
    print("Smart Ration Dispenser backend running on http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
