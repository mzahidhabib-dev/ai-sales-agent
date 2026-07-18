import logging
from platform_core.sdk import sdk
from platform_core.db import get_connection

# Set logger to INFO for this test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase6")

def run_tests():
    tenant_id = "tenant-1"
    
    logger.info("--- Test 1: HITL State Transitions ---")
    
    try:
        # Step 1: Create a test decision card
        decision_id = sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="TestAgent_HITL",
            action="draft_email",
            result='{"email_body": "Hello, please buy our software."}'
        )
        logger.info(f"Created Decision Card ID: {decision_id}")
        
        # Step 2: Request Approval
        sdk.decisions.request_approval(decision_id)
        
        # Verify status is PENDING_APPROVAL
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT approval_status FROM decision_cards WHERE decision_id = %s", (decision_id,))
        status = cursor.fetchone()[0]
        if status == "PENDING_APPROVAL":
            logger.info("SUCCESS: Status transitioned to PENDING_APPROVAL")
        else:
            logger.error(f"FAIL: Expected PENDING_APPROVAL but got {status}")
            
        # Step 3: Resolve Approval (Simulate a human hitting 'Approve')
        sdk.decisions.resolve_approval(decision_id, "APPROVED")
        
        # Verify status is APPROVED
        cursor.execute("SELECT approval_status FROM decision_cards WHERE decision_id = %s", (decision_id,))
        status = cursor.fetchone()[0]
        if status == "APPROVED":
            logger.info("SUCCESS: Status transitioned to APPROVED")
        else:
            logger.error(f"FAIL: Expected APPROVED but got {status}")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"FAIL: Test 1 encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
