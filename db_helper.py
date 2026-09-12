"""
Database helper functions for the Smart Ration Dispenser.
This is what the backend server calls for entitlement validation and logging.
"""

import sqlite3
from datetime import datetime

DB_PATH = "tnpds_simulated.db"
COMMODITIES = ["rice", "wheat", "dal", "sugar"]


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_beneficiary(card_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_remaining(card_id, commodity):
    b = get_beneficiary(card_id)
    if b is None:
        return None
    commodity = commodity.lower()
    limit = b[f"{commodity}_limit_kg"]
    dispensed = b[f"{commodity}_dispensed_this_month"]
    return round(limit - dispensed, 3)


def get_all_remaining(card_id):
    b = get_beneficiary(card_id)
    if b is None:
        return None
    return {c: round(b[f"{c}_limit_kg"] - b[f"{c}_dispensed_this_month"], 3) for c in COMMODITIES}


def validate_request(card_id, commodity, requested_qty_kg):
    commodity = commodity.lower()
    if commodity not in COMMODITIES:
        return False, None, f"Unknown commodity '{commodity}'"

    remaining = get_remaining(card_id, commodity)
    if remaining is None:
        return False, None, "Card not recognized"

    if requested_qty_kg <= 0:
        return False, remaining, "Quantity must be greater than zero"

    if remaining <= 0:
        return False, remaining, f"No {commodity} entitlement remaining this month"

    if requested_qty_kg > remaining:
        return False, remaining, f"Exceeds entitlement — max {remaining}kg {commodity} remaining"

    return True, remaining, "OK"


def price_for(card_id, commodity, quantity_kg):
    b = get_beneficiary(card_id)
    commodity = commodity.lower()
    rate = b[f"{commodity}_price_per_kg"]
    return round(rate * quantity_kg, 2)


def record_transaction(card_id, commodity, target_weight_kg, actual_weight_kg, status="success"):
    commodity = commodity.lower()
    conn = _connect()

    price = 0.0
    if status == "success":
        b = get_beneficiary(card_id)
        rate = b[f"{commodity}_price_per_kg"]
        price = round(rate * actual_weight_kg, 2)
        conn.execute(f"""
            UPDATE cards SET {commodity}_dispensed_this_month = {commodity}_dispensed_this_month + ?
            WHERE card_id = ?
        """, (actual_weight_kg, card_id))

    conn.execute("""
        INSERT INTO transactions (card_id, commodity, quantity_kg, target_weight_kg, actual_weight_kg, price_charged, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (card_id, commodity, actual_weight_kg, target_weight_kg, actual_weight_kg, price, status,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()
    return price


def get_customer_history(card_id):
    conn = _connect()
    rows = conn.execute("""
        SELECT transaction_id, commodity, quantity_kg, price_charged, status, timestamp
        FROM transactions WHERE card_id = ? ORDER BY timestamp DESC
    """, (card_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_admin_full_log():
    conn = _connect()
    rows = conn.execute("""
        SELECT t.transaction_id, t.card_id, c.name, t.commodity, t.quantity_kg,
               t.price_charged, t.status, t.timestamp
        FROM transactions t JOIN cards c ON t.card_id = c.card_id
        ORDER BY t.timestamp DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
