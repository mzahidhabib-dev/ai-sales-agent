from platform_core.logging_config import get_logger
from platform_core.db import get_connection
import json

logger = get_logger(__name__)

def log_evaluation(tenant_id: str, agent_name: str, prompt_version: str, metrics: dict) -> None:
    """
    Logs continuous scoring hooks for an agent's execution to the database.
    Per Phase 9.1, this is logging only; auto-tuning is explicitly deferred.
    
    Args:
        tenant_id: The tenant identifier.
        agent_name: The name of the agent being evaluated.
        prompt_version: The version of the prompt used (e.g., 'v1.0').
        metrics: A dictionary of key-value pairs representing the evaluation scores.
    """
    logger.info("Logging evaluation metrics", extra={"tenant_id": tenant_id, "agent_name": agent_name, "metrics": metrics})
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO evaluations (tenant_id, agent_name, prompt_version, metrics)
            VALUES (%s, %s, %s, %s)
            """,
            (tenant_id, agent_name, prompt_version, json.dumps(metrics))
        )
        conn.commit()
    except Exception as e:
        # Rule 9: Professional error handling
        # We do NOT raise here because evaluation is a side-effect and 
        # should not fail the main pipeline if the analytics DB is down.
        logger.error(
            "Failed to save evaluation metrics",
            extra={
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Fail-open analytics logging: preventing pipeline crash due to metrics failure"
            }
        )
    finally:
        if conn:
            conn.close()
