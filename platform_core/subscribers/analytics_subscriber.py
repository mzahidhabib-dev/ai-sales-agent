import json
import os
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

# In a real system, this would write to Snowflake/BigQuery or similar analytics DB.
# We will write to a local JSONL file for the proof of concept.
ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "scratch", "analytics_dump.jsonl")

def handle_analytics_event(event_data: dict):
    tenant_id = event_data.get("tenant_id")
    event_type = event_data.get("event_type")
    payload = event_data.get("payload", {})

    logger.info("Analytics subscriber received event", extra={"tenant_id": tenant_id, "event_type": event_type})

    # Rule 15: Sanitize PII
    # We drop 'prompt', 'raw_output', and 'email_draft' which may contain PII.
    sanitized_payload = {k: v for k, v in payload.items() if k not in ["prompt", "raw_output", "email_draft", "validation_result"]}

    record = {
        "tenant_id": tenant_id,
        "event_type": event_type,
        "payload": sanitized_payload
    }

    try:
        # Ensure the scratch directory exists
        os.makedirs(os.path.dirname(ANALYTICS_FILE), exist_ok=True)
        with open(ANALYTICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(
            "Analytics subscriber failed to write event",
            extra={
                "tenant_id": tenant_id,
                "event_type": event_type,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )

if __name__ == "__main__":
    from platform_core.events import subscribe
    tenant_id = "tenant-1"
    logger.info("Starting Analytics Subscriber Worker")
    subscribe(tenant_id, handle_analytics_event)
