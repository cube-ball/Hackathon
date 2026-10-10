"""Small Flask server for the parts Streamlit can't do: receiving Stripe webhooks.

Run from the repo root:   python -m backend.app
Then, in another terminal: stripe listen --forward-to localhost:5050/api/stripe/webhook
(Port 5050 because macOS uses 5000 for AirPlay Receiver.)
"""
import os

from flask import Flask, jsonify, request

from . import billing, config, store

app = Flask(__name__)


def error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/account")
def account():
    user = store.get_user(request.headers.get("X-User-Id") or config.USER_ID)
    return jsonify({"tier": user["tier"], "updates_remaining": store.updates_remaining(user)})


@app.post("/api/checkout")
def checkout():
    user_id = request.headers.get("X-User-Id") or config.USER_ID
    try:
        session_id, url = billing.create_checkout(user_id)
    except billing.BillingError as err:
        return error("stripe_error", str(err), 500)
    return jsonify({"session_id": session_id, "checkout_url": url, "product": config.PRODUCT_NAME,
                    "amount": config.PRICE_CENTS, "currency": config.CURRENCY})


@app.post("/api/stripe/webhook")
def stripe_webhook():
    payload = request.get_data()                     # raw bytes: needed for the signature
    try:
        event = billing.verify_webhook(payload, request.headers.get("Stripe-Signature"),
                                       config.stripe_webhook_secret())
    except ValueError as err:
        return error("bad_signature", str(err), 400)
    result = billing.handle_event(event)
    app.logger.info("Stripe webhook: %s", result)
    return jsonify({"received": True})


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", "5050")), debug=False)
