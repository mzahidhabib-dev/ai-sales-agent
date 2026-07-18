import hmac
import hashlib
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifies that a webhook request actually came from our trusted sender (e.g. n8n).
    Uses HMAC SHA-256 against the raw payload bytes and a shared secret.
    """
    if not signature_header or not secret:
        logger.warning(
            "Webhook signature verification failed: Missing header or secret",
            extra={"catch_reason": "Rejecting unverified webhook early"}
        )
        return False
        
    try:
        # Expected signature from payload
        expected_mac = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        )
        expected_signature = expected_mac.hexdigest()
        
        # In many systems it's prepended with sha256=...
        # We handle both raw hex and prefixed hex
        if signature_header.startswith("sha256="):
            provided_signature = signature_header.split("=")[1]
        else:
            provided_signature = signature_header
            
        # hmac.compare_digest prevents timing attacks
        is_valid = hmac.compare_digest(expected_signature, provided_signature)
        if not is_valid:
            logger.warning(
                "Webhook signature mismatch",
                extra={"catch_reason": "Rejecting forged/altered webhook"}
            )
        return is_valid
    except Exception as e:
        logger.error(
            "Error computing HMAC for webhook",
            extra={
                "exc_type": type(e).__name__, 
                "error": str(e),
                "catch_reason": "Rejecting due to exception in signature calculation"
            }
        )
        return False
