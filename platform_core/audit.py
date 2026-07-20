from platform_core.logging_config import get_logger
from platform_core.database import get_connection
import json

logger = get_logger(__name__)

def query_logs(tenant_id: str, agent_name: str = None, limit: int = 50) -> list:
    """
    Retrieves the full audit trail for a given tenant, joining decision_cards 
    and audit_logs to provide a complete view (prompt, model, output, decision).
    
    Args:
        tenant_id: The tenant identifier.
        agent_name: Optional filter for a specific agent.
        limit: Maximum number of rows to return.
        
    Returns:
        List of dictionaries representing the audit trail.
    """
    logger.info("Querying audit logs", extra={"tenant_id": tenant_id, "agent_name": agent_name, "limit": limit})
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                d.decision_id, d.agent_name, d.action, d.result, d.confidence, 
                d.approved, d.timestamp as decision_time,
                a.prompt, a.model, a.raw_output, a.validation_result
            FROM decision_cards d
            LEFT JOIN audit_logs a ON d.decision_id = a.decision_id
            WHERE d.tenant_id = %s
        """
        params = [tenant_id]
        
        if agent_name:
            query += " AND d.agent_name = %s"
            params.append(agent_name)
            
        query += " ORDER BY d.timestamp DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Convert datetime to ISO string for JSON serialization if needed
            if "decision_time" in row_dict and row_dict["decision_time"]:
                row_dict["decision_time"] = row_dict["decision_time"].isoformat()
            results.append(row_dict)
            
        return results
        
    except Exception as e:
        logger.error(
            "Failed to query audit logs",
            extra={
                "tenant_id": tenant_id,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching DB exception; bubbling up empty list to prevent pipeline crash but logging heavily"
            }
        )
        # Rule 9: Professional error handling. Return empty list so caller doesn't crash, 
        # but the error is heavily logged above. Alternatively, we could raise.
        # Since this is a read API, raising is usually safer so the UI knows it failed.
        raise
    finally:
        if conn:
            conn.close()
