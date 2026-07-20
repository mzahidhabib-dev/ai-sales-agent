from platform_core.logging_config import get_logger
from platform_core import decision_cards

logger = get_logger(__name__)

class APIStub:
    """
    Simulates the external HTTP API of the platform.
    In Phase 7, this will be replaced with a real FastAPI server.
    """
    def webhook_resolve_decision(self, payload: dict = None, payload_bytes: bytes = b"", signature_header: str = "", **kwargs) -> dict:
        """
        Simulates an HTTP POST route handling a webhook from a UI or Slack.
        """
        if payload is None:
            payload = kwargs.get("payload", {})
        if not payload_bytes:
            payload_bytes = kwargs.get("payload_bytes", b"")
        if not signature_header:
            signature_header = kwargs.get("signature_header", "")
        
        # Phase 5.6: Enforce signature verification
        from platform_core.security import verify_webhook_signature, get_secret
        # We assume n8n secret is configured in secrets manager
        secret = get_secret("WEBHOOK_SECRET", default="stub_secret_123")
        
        if not verify_webhook_signature(payload_bytes, signature_header, secret):
            return {"status": 401, "message": "Unauthorized: Invalid webhook signature"}
            
        decision_id = payload.get("decision_id")
        status = payload.get("status")
        new_result = payload.get("new_result")
        
        if not decision_id:
            return {"status": 400, "message": "Bad Request: decision_id is required"}
            
        if not status:
            return {"status": 400, "message": "Bad Request: status is required"}
            
        logger.info(
            "API Stub received webhook",
            extra={"decision_id": decision_id, "status": status, "is_edited": bool(new_result)}
        )
        
        try:
            decision_cards.resolve_approval(
                decision_id=int(decision_id),
                status=status,
                new_result=new_result
            )
            return {"status": 200, "message": "Decision successfully resolved."}
        except Exception as e:
            logger.error(
                "API Stub failed to process webhook", 
                extra={
                    "exc_type": type(e).__name__, 
                    "error": str(e),
                    "catch_reason": "Catching general exception in API route to return 500"
                }
            )
            return {"status": 500, "message": f"Internal Server Error: {str(e)}"}

api = APIStub()
