from platform_core.logging_config import get_logger
from platform_core.db import get_connection

logger = get_logger(__name__)

def get_dashboard_metrics(tenant_id: str) -> dict:
    """
    Step 11.1: Aggregates cost_usd from Decision Cards.
    Returns:
        {
            "total_spend": 0.00,
            "cost_by_model": {"gemini-pro": 0.00},
            "cost_per_lead": 0.00,
            "cost_per_meeting": 0.00
        }
    """
    logger.info("Fetching cost dashboard metrics", extra={"tenant_id": tenant_id})
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Total Spend
        cursor.execute("SELECT SUM(cost_usd) FROM decision_cards WHERE tenant_id = %s", (tenant_id,))
        total_spend = cursor.fetchone()[0] or 0.0
        
        # 2. Cost by Model
        cursor.execute("SELECT model, SUM(cost_usd) FROM decision_cards WHERE tenant_id = %s AND model IS NOT NULL GROUP BY model", (tenant_id,))
        cost_by_model = {row[0]: float(row[1] or 0.0) for row in cursor.fetchall()}
        
        # 3. Cost Per Lead (Assume every 'find_prospect' creates 1 lead)
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s AND action = 'find_prospect'", (tenant_id,))
        total_leads = cursor.fetchone()[0] or 0
        cost_per_lead = float(total_spend) / total_leads if total_leads > 0 else 0.0
        
        # 4. Cost Per Meeting (Assume every 'book_meeting' is a success)
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s AND action = 'book_meeting'", (tenant_id,))
        total_meetings = cursor.fetchone()[0] or 0
        cost_per_meeting = float(total_spend) / total_meetings if total_meetings > 0 else 0.0
        
        return {
            "total_spend": round(float(total_spend), 4),
            "cost_by_model": cost_by_model,
            "cost_per_lead": round(cost_per_lead, 4),
            "cost_per_meeting": round(cost_per_meeting, 4)
        }
    except Exception as e:
        logger.error(
            "Failed to fetch cost metrics",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)}
        )
        raise
    finally:
        conn.close()
