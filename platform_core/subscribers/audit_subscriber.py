import json
from platform_core.logging_config import get_logger
from platform_core.db import get_connection
from platform_core.security.pii_masking import mask_pii

logger = get_logger(__name__)

def handle_audit_event(event_data: dict):
    if event_data.get("event_type") != "decision.recorded":
        return

    tenant_id = event_data.get("tenant_id")
    payload = event_data.get("payload", {})

    logger.info("Audit subscriber received decision.recorded event", extra={"tenant_id": tenant_id})

    # Mask PII before storing in the audit log view (Step 5.4)
    prompt = payload.get("prompt")
    raw_output = payload.get("raw_output")
    validation_result = payload.get("validation_result")
    
    masked_prompt = mask_pii(prompt) if prompt else None
    masked_raw_output = mask_pii(raw_output) if raw_output else None
    masked_validation_result = mask_pii(json.dumps(validation_result)) if validation_result else None

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert into audit_logs (Step 2.7 decoupled)
        cursor.execute(
            """
            INSERT INTO audit_logs (
                decision_id, tenant_id, agent_name, prompt, model, 
                raw_output, validation_result
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.get("decision_id"), tenant_id, payload.get("agent_name"), 
                masked_prompt, payload.get("model"),
                masked_raw_output, masked_validation_result
            )
        )

        conn.commit()
    except Exception as e:
        logger.error(
            "Audit subscriber failed to write to DB",
            extra={
                "tenant_id": tenant_id,
                "exc_type": type(e).__name__,
                "error": str(e)
            }
        )
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    from platform_core.events import subscribe
    # For testing, we can just hardcode a tenant or pass it.
    # In a real deployed environment, the worker would probably subscribe to a wildcard channel or multiple.
    # For this POC, we'll just listen to "tenant-1".
    tenant_id = "tenant-1"
    logger.info("Starting Audit Subscriber Worker")
    subscribe(tenant_id, handle_audit_event)
