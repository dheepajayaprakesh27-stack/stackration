"""
Simulated TNPDS Database for Smart Ration Dispenser
-----------------------------------------------------
Rules encoded here (as specified by the team):
- Rice entitlement varies by family size: 4kg per member (2 members = 8kg, 5 members = 20kg)
- Wheat, Dal, Sugar are FIXED at 1kg per card, regardless of family size
- Wheat is FREE (price = 0); Rice, Dal, Sugar are charged
- Person can dispense ANY amount up to (not exceeding) their remaining entitlement,
  including partial amounts like 0.8kg
- ~30 beneficiary records, matching one ration shop's typical size
"""

import sqlite3
import random

DB_PATH = "tnpds_simulated.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    family_members INTEGER NOT NULL,
    rice_limit_kg REAL NOT NULL,
    wheat_limit_kg REAL NOT NULL DEFAULT 1.0,
    dal_limit_kg REAL NOT NULL DEFAULT 1.0,
    sugar_limit_kg REAL NOT NULL DEFAULT 1.0,
    rice_price_per_kg REAL NOT NULL DEFAULT 3.0,
    wheat_price_per_kg REAL NOT NULL DEFAULT 0.0,
    dal_price_per_kg REAL NOT NULL DEFAULT 50.0,
    sugar_price_per_kg REAL NOT NULL DEFAULT 20.0,
    rice_dispensed_this_month REAL NOT NULL DEFAULT 0.0,
    wheat_dispensed_this_month REAL NOT NULL DEFAULT 0.0,
    dal_dispensed_this_month REAL NOT NULL DEFAULT 0.0,
    sugar_dispensed_this_month REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    commodity TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    target_weight_kg REAL,
    actual_weight_kg REAL,
    price_charged REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'success',
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (card_id) REFERENCES cards(card_id)
);
"""

FIRST_NAMES = ["Kumar", "Ramesh", "Lakshmi", "Priya", "Suresh", "Meena", "Anand",
               "Devi", "Ravi", "Kavitha", "Murugan", "Saraswathi", "Selvam", "Geetha",
               "Rajan", "Vani", "Karthik", "Shanthi", "Mohan", "Radha", "Prakash",
               "Vasanthi", "Elango", "Malar", "Senthil", "Padma", "Balan", "Uma",
               "Gopal", "Kalyani"]


def build_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    cur.execute("DELETE FROM cards")
    cur.execute("DELETE FROM transactions")

    random.seed(42)
    for i in range(1, 31):
        card_id = f"TNPDS{1000 + i}"
        name = FIRST_NAMES[i - 1]
        family_members = random.choice([2, 3, 4, 5])
        rice_limit = 4.0 * family_members
        cur.execute("""
            INSERT INTO cards (card_id, name, family_members, rice_limit_kg)
            VALUES (?, ?, ?, ?)
        """, (card_id, name, family_members, rice_limit))

    conn.commit()
    conn.close()
    print(f"Database created: {DB_PATH} with 30 beneficiary records.")


if __name__ == "__main__":
    build_database()
