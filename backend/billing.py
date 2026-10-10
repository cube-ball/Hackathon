"""Stripe (sandbox only): create a Checkout Session and verify webhooks.

Uses Stripe's REST API directly, so the Streamlit app needs no extra packages.
Access is granted ONLY by a signature-verified checkout.session.completed webhook,
never by the success redirect.
"""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, store

STRIPE_API = "https://api.stripe.com/v1/checkout/sessions"


class BillingError(Exception):
    pass


def create_checkout(user_id):
    """Return (session_id, checkout_url) for the Semester Pass."""
    key = config.stripe_secret_key()
    if not key:
        raise BillingError("STRIPE_SECRET_KEY is not set")
    if not key.startswith(("sk_test_", "rk_test_")):
        raise BillingError("Use a Stripe TEST key (sk_test_...). Live keys are refused.")
    form = {
        "mode": "payment",
        "success_url": config.APP_URL + "/?checkout=success",
        "cancel_url": config.APP_URL + "/?checkout=cancelled",
        "client_reference_id": user_id,
        "metadata[user_id]": user_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": config.CURRENCY,
        "line_items[0][price_data][unit_amount]": str(config.PRICE_CENTS),
        "line_items[0][price_data][product_data][name]": config.PRODUCT_NAME,
        "line_items[0][price_data][product_data][description]": "Unlimited AI plan updates for the semester",
    }
    request = urllib.request.Request(
        STRIPE_API, data=urllib.parse.urlencode(form).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            session = json.loads(response.read().decode())
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300]
        raise BillingError(f"Stripe returned {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise BillingError(f"Could not reach Stripe: {err}") from err
    return session["id"], session["url"]


def verify_webhook(payload, signature_header, secret, tolerance=300, now=None):
    """Check the Stripe-Signature header. Returns the parsed event or raises ValueError."""
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not set")
    if not signature_header:
        raise ValueError("Missing Stripe-Signature header")
    timestamp, signatures = None, []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp or not signatures:
        raise ValueError("Malformed Stripe-Signature header")
    if isinstance(payload, str):
        payload = payload.encode()
    signed = timestamp.encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise ValueError("Signature does not match")
    if abs((now or time.time()) - int(timestamp)) > tolerance:
        raise ValueError("Timestamp outside tolerance")
    return json.loads(payload.decode())


def handle_event(event):
    """Apply a verified event. Returns a short description for logging."""
    if event.get("type") != "checkout.session.completed":
        return "ignored " + str(event.get("type"))
    session = event.get("data", {}).get("object", {})
    user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
    if not user_id:
        return "no user on session"
    if session.get("payment_status") != "paid":
        return "session not paid yet"
    first = store.grant_pro(user_id, session.get("id"), session.get("amount_total"),
                            session.get("currency"), session.get("payment_status"))
    return f"pro granted to {user_id}" + ("" if first else " (duplicate event)")
