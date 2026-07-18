import json
from platform_core.db import get_connection
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

def get(tenant_id: str, prospect_id: int) -> dict:
    """
    Retrieves the memory context for a specific prospect.
    If no memory exists, returns an empty dict.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data FROM memory WHERE tenant_id = %s AND prospect_id = %s",
            (tenant_id, prospect_id)
        )
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return {}
    except Exception as e:
        logger.error(
            "Failed to retrieve memory",
            extra={"tenant_id": tenant_id, "prospect_id": prospect_id, "error": str(e)}
        )
        raise e
    finally:
        if conn:
            conn.close()

def update(tenant_id: str, prospect_id: int, new_data: dict) -> None:
    """
    Merges new context into the existing memory for a prospect.
    Creates a new row if one doesn't exist.
    """
    conn = None
    try:
        current_data = get(tenant_id, prospect_id)
        current_data.update(new_data)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Upsert the memory using the unique constraint on (tenant_id, prospect_id)
        cursor.execute("""
            INSERT INTO memory (tenant_id, prospect_id, data, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (tenant_id, prospect_id) 
            DO UPDATE SET data = EXCLUDED.data, updated_at = CURRENT_TIMESTAMP
        """, (tenant_id, prospect_id, json.dumps(current_data)))
        
        conn.commit()
        logger.info(
            "Memory updated",
            extra={"tenant_id": tenant_id, "prospect_id": prospect_id, "keys_updated": list(new_data.keys())}
        )
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(
            "Failed to update memory",
            extra={"tenant_id": tenant_id, "prospect_id": prospect_id, "error": str(e)}
        )
        raise e
    finally:
        if conn:
            conn.close()
