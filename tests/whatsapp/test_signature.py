import hashlib
import hmac

from whatsapp.signature import verify_signature

SECRET = "test_secret"
BODY = b'{"test": "payload"}'


def _make_sig(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_valid_signature():
    sig = _make_sig(BODY, SECRET)
    assert verify_signature(BODY, sig, SECRET) is True


def test_invalid_signature_wrong_secret():
    sig = _make_sig(BODY, "wrong_secret")
    assert verify_signature(BODY, sig, SECRET) is False


def test_invalid_signature_tampered_body():
    sig = _make_sig(BODY, SECRET)
    assert verify_signature(b'{"test": "tampered"}', sig, SECRET) is False


def test_missing_sha256_prefix():
    assert verify_signature(BODY, "abc123", SECRET) is False


def test_empty_body():
    sig = _make_sig(b"", SECRET)
    assert verify_signature(b"", sig, SECRET) is True
