import logging
from platform_core.sdk import sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase9")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Evaluation Logging API (Step 9.1) ---")
    
    try:
        # 1. Log some dummy metrics
        metrics = {
            "research_quality": 0.92,
            "hallucination_rate": 0.01,
            "prompt_adherence": 0.88,
            "meeting_booked": True
        }
        
        logger.info("Calling sdk.evaluation.log_evaluation()...")
        sdk.evaluation.log_evaluation(
            tenant_id=tenant_id,
            agent_name="ResearchAgent",
            prompt_version="v2.1",
            metrics=metrics
        )
        logger.info("Successfully called the API without crashing.")
        
        # 2. Verify it was stored by querying the DB
        from platform_core.db import get_connection
        import json
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT metrics FROM evaluations 
            WHERE tenant_id = %s AND agent_name = %s AND prompt_version = %s
            ORDER BY timestamp DESC LIMIT 1
            """,
            (tenant_id, "ResearchAgent", "v2.1")
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.error("FAIL: Could not find the evaluation record in the database.")
        else:
            db_metrics = row[0]
            if isinstance(db_metrics, str):
                db_metrics = json.loads(db_metrics)
                
            if db_metrics.get("research_quality") == 0.92:
                logger.info(f"SUCCESS: Successfully retrieved evaluation metrics from DB: {db_metrics}")
            else:
                logger.error(f"FAIL: Metrics retrieved did not match what was saved. Got: {db_metrics}")
                
    except Exception as e:
        logger.error(f"FAIL: Test 1 encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
