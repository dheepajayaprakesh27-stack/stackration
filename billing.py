"""
Billing + UPI QR generation.
Demo VPA — replace with your team's actual UPI ID before the live demo if you want real payment testing.
"""

import qrcode
import io
import base64

DEMO_VPA = "rationdispenser@upi"   # placeholder — swap for a real UPI ID if testing live payment
PAYEE_NAME = "Smart Ration Dispenser"


def build_bill(card_id, dispensed_items):
    """
    dispensed_items: list of dicts like {"commodity": "rice", "quantity_kg": 2.5, "price": 7.5}
    Returns a bill summary dict with itemized list + total.
    """
    total = round(sum(item["price"] for item in dispensed_items), 2)
    return {
        "card_id": card_id,
        "items": dispensed_items,
        "total_amount": total
    }


def generate_upi_qr_base64(amount, transaction_note="Ration Dispenser Purchase"):
    """
    Builds a UPI deep-link and renders it as a QR code, returned as a base64 PNG string
    so it can be sent straight to the browser UI over the websocket / embedded in <img src="data:image/png;base64,...">.
    Amount of 0 (all-wheat / free items) skips QR generation — caller should check for that.
    """
    if amount <= 0:
        return None

    upi_url = (
        f"upi://pay?pa={DEMO_VPA}&pn={PAYEE_NAME.replace(' ', '%20')}"
        f"&am={amount}&cu=INR&tn={transaction_note.replace(' ', '%20')}"
    )

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")
