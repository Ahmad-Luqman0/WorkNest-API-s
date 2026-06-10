import os
import hashlib
from urllib.parse import urlencode

MERCHANT_ID  = os.getenv("PAYFAST_MERCHANT_ID", "")
SECURED_KEY  = os.getenv("PAYFAST_SECURED_KEY", "")
SANDBOX      = os.getenv("PAYFAST_SANDBOX", "true").lower() == "true"
SANDBOX_URL  = os.getenv("PAYFAST_SANDBOX_URL", "https://sandbox.payfast.pk/v2/hosted_payment")
RETURN_URL   = os.getenv("PAYFAST_RETURN_URL", "")
NOTIFY_URL   = os.getenv("PAYFAST_NOTIFY_URL", "")


def _generate_signature(params: dict) -> str:
    """
    PayFast signature: alphabetically-sorted key=value pairs (excluding 'signature')
    concatenated with & then HMAC-SHA256 using the secured key.
    """
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if k != "signature" and v not in (None, "")
    )
    return hashlib.sha256(f"{sorted_params}{SECURED_KEY}".encode()).hexdigest()


def build_payfast_payload(
    booking_id: int,
    amount: float,
    description: str,
    customer_email: str,
    customer_name: str,
    order_id: str,
) -> dict:
    """
    Returns the full PayFast payment payload including the generated signature.
    Never exposes SECURED_KEY to the caller.
    """
    params = {
        "merchant_id":    MERCHANT_ID,
        "order_id":       order_id,
        "amount":         f"{amount:.2f}",
        "currency":       "PKR",
        "description":    description,
        "customer_email": customer_email,
        "customer_name":  customer_name,
        "return_url":     RETURN_URL,
        "notify_url":     NOTIFY_URL,
        "booking_id":     str(booking_id),
    }
    params["signature"] = _generate_signature(params)
    params["payment_url"] = SANDBOX_URL
    return params


def verify_notify_signature(notify_data: dict) -> bool:
    """
    Verifies an incoming PayFast IPN (notify) callback by recomputing the signature.
    Use this in the /payment/payfast/notify endpoint.
    """
    received_sig = notify_data.pop("signature", None)
    expected_sig = _generate_signature(notify_data)
    return received_sig == expected_sig
