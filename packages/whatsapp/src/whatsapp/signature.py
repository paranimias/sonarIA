import hashlib
import hmac


def verify_signature(body: bytes, signature_header: str, app_secret: str) -> bool:
    """Verify X-Hub-Signature-256 header from Meta webhook."""
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
