import json
from platform_core.logging_config import get_logger
from platform_core.db import get_connection

logger = get_logger(__name__)

def record_decision(
    tenant_id: str,
    agent_name: str,
    action: str,
    result: str = None,
    confidence: float = None,
    reason: list = None,
    sources: list = None,
    model: str = None,
    prompt_version: str = None,
    cost_usd: float = None,
    duration_seconds: float = None,
    approved: bool = None,
    approval_required: bool = None,
    replay_id: str = None,
    # Context needed for full audit log
    prompt: str = None,
    raw_output: str = None,
    validation_result: dict = None
) -> int:
    """
    Inserts a row into decision_cards and writes the corresponding full audit trail to audit_logs.
    Returns the generated decision_id.
    """
    logger.info("Recording decision", extra={"tenant_id": tenant_id, "agent_name": agent_name, "action": action})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert into decision_cards
        cursor.execute(
            """
            INSERT INTO decision_cards (
                tenant_id, agent_name, action, result, confidence, 
                reason, sources, model, prompt_version, cost_usd, 
                duration_seconds, approved, approval_required, replay_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING decision_id
            """,
            (
                tenant_id, agent_name, action, result, confidence,
                reason, sources, model, prompt_version, cost_usd,
                duration_seconds, approved, approval_required, replay_id
            )
        )
        decision_id = cursor.fetchone()[0]

        from platform_core.security.pii_masking import mask_pii

        # Mask PII before storing in the audit log view (Step 5.4)
        masked_prompt = mask_pii(prompt) if prompt else None
        masked_raw_output = mask_pii(raw_output) if raw_output else None
        masked_validation_result = mask_pii(json.dumps(validation_result)) if validation_result else None

        # Insert into audit_logs (Step 2.7)
        cursor.execute(
            """
            INSERT INTO audit_logs (
                decision_id, tenant_id, agent_name, prompt, model, 
                raw_output, validation_result
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                decision_id, tenant_id, agent_name, masked_prompt, model,
                masked_raw_output, masked_validation_result
            )
        )

        conn.commit()
        logger.info(
            "Decision card recorded",
            extra={"tenant_id": tenant_id, "agent": agent_name, "action": action, "decision_id": decision_id}
        )
        return decision_id
    except Exception as e:
        logger.error(
            "Failed to record decision card",
            extra={
                "tenant_id": tenant_id,
                "agent": agent_name,
                "action": action,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching pg8000 DB exception; rolling back and re-raising to caller"
            }
        )
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()
