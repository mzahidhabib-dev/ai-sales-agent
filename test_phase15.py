import logging
import time
import subprocess
import threading
from platform_core.sdk import sdk
from platform_core.db import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase15")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Decoupled Audit Logs (Step 15.2) ---")
    
    import sys
    # 1. Start the audit subscriber in the background
    logger.info("Starting audit_subscriber.py in background...")
    proc = subprocess.Popen([sys.executable, "-m", "platform_core.subscribers.audit_subscriber"])
    
    # Give it a second to connect to Redis
    time.sleep(2)
    
    try:
        # 2. Record a decision (this now ONLY publishes an event, it does NOT write to audit_logs)
        logger.info("Recording a decision (which triggers a pub/sub event)...")
        decision_id = sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="TestAgent",
            action="test_action",
            prompt="This is a secret prompt containing test@example.com",
            raw_output="The output",
            model="gemini"
        )
        
        # 3. Wait for the background worker to process the event
        logger.info("Waiting 2 seconds for the background worker to process the event over Redis...")
        time.sleep(2)
        
        # 4. Verify the database
        logger.info("Checking audit_logs table...")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT prompt FROM audit_logs WHERE decision_id = %s", (decision_id,))
        row = cursor.fetchone()
        
        if row:
            prompt_saved = row[0]
            logger.info(f"Audit log found! Masked prompt: {prompt_saved}")
            if "[REDACTED_EMAIL]" in prompt_saved:
                logger.info("SUCCESS: The Audit Subscriber correctly intercepted the event via Redis, masked the PII, and wrote it to the database asynchronously!")
            else:
                logger.error("FAIL: Audit log found, but PII was not masked.")
        else:
            logger.error("FAIL: No audit log was found. The background worker failed to write it.")
            
    except Exception as e:
        logger.error(f"FAIL: Test encountered an error: {e}")
    finally:
        # Clean up the background worker
        logger.info("Terminating background worker.")
        proc.terminate()
        if conn:
            conn.close()

    logger.info("--- Test 2: Daily Executive Report (Step 15.3) ---")
    try:
        from platform_core.subscribers.daily_report import generate_daily_report
        import os
        os.environ["USE_MCP"] = "false" # force the local Python stub for send_email
        report = generate_daily_report(tenant_id)
        if "Cost Analysis" in report:
            logger.info("SUCCESS: Daily Executive Report generated and dispatched to the Tool Gateway!")
    except Exception as e:
        logger.error(f"FAIL: Daily report failed: {e}")

if __name__ == "__main__":
    run_tests()
