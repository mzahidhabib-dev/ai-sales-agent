from platform_core.logging_config import get_logger
from platform_core import decision_cards

logger = get_logger(__name__)

class APIStub:
    """
    Simulates the external HTTP API of the platform.
    In Phase 7, this will be replaced with a real FastAPI server.
    """
    def webhook_resolve_decision(self, payload: dict) -> dict:
        """
        Simulates an HTTP POST route handling a webhook from a UI or Slack.
        Expected payload format:
        {
            "decision_id": int,
            "status": "APPROVED" | "REJECTED" | "EDITED",
            "new_result": "Optional edited text"
        }
        """
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
            logger.error("API Stub failed to process webhook", extra={"error": str(e)})
            return {"status": 500, "message": f"Internal Server Error: {str(e)}"}

api = APIStub()
