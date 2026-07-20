import logging
from platform_core.sdk import sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase8")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Full Audit Trail API (Step 8.1) ---")
    try:
        # First, ensure we have at least one record to query by doing a quick run
        logger.info("Generating a test decision to ensure audit logs exist...")
        ai_res = sdk.ai.generate(prompt="What is your favorite color?")
        
        test_decision_id = sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="TestAuditAgent",
            action="test_audit",
            prompt="What is your favorite color?",
            raw_output=ai_res.get("raw"),
            result=ai_res.get("output")
        )
        logger.info(f"Created test decision ID: {test_decision_id}")
        
        # Now query the logs
        logs = sdk.audit.query_logs(tenant_id=tenant_id, limit=5)
        
        if not logs:
            logger.error("FAIL: query_logs returned an empty list")
        else:
            found = False
            for log in logs:
                if log["decision_id"] == test_decision_id:
                    found = True
                    if log["prompt"] == "What is your favorite color?":
                        logger.info("SUCCESS: Audit log retrieved successfully with joined prompt data!")
                    else:
                        logger.error(f"FAIL: Retrieved log had incorrect prompt: {log.get('prompt')}")
            
            if not found:
                logger.error("FAIL: The newly created decision ID was not found in the recent logs.")
                
    except Exception as e:
        logger.error(f"FAIL: Test 1 encountered an error: {e}")

    logger.info("--- Test 2: Replay Engine (Step 8.2) ---")
    try:
        # We will replay the test_decision_id we just created
        logger.info(f"Replaying decision ID: {test_decision_id}")
        new_decision_id = sdk.replay.replay_decision(test_decision_id)
        
        if not new_decision_id:
            logger.error("FAIL: Replay Engine returned null or 0")
        else:
            # Let's fetch the new decision card and verify the replay_id is set correctly
            from platform_core.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT replay_id FROM decision_cards WHERE decision_id = %s", (new_decision_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and str(row[0]) == str(test_decision_id):
                logger.info(f"SUCCESS: Replay Engine created decision {new_decision_id} successfully linked to {test_decision_id}!")
            else:
                logger.error(f"FAIL: Replay Engine created a decision but replay_id was missing or incorrect: {row}")
                
    except Exception as e:
        logger.error(f"FAIL: Test 2 encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
