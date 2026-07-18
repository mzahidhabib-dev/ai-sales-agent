import logging
from platform_core.sdk import sdk

# Set logger to INFO for this test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase5")

def run_tests():
    tenant_id = "tenant-1"
    
    logger.info("--- Test 1: RBAC Negative Test (Viewer Role) ---")
    
    # Simulate a web request coming in from an authenticated user with a 'viewer' role
    # The middleware would set this:
    sdk.security.set_current_role("viewer")
    logger.info("Current context role set to: 'viewer'")
    
    try:
        logger.info("Attempting to call sdk.knowledge.update() which requires 'admin'...")
        # This should immediately throw a PermissionError inside the service layer
        sdk.knowledge.update("icp", tenant_id, {"some": "config"})
        logger.error("FAIL: The viewer was incorrectly allowed to update knowledge!")
    except PermissionError as e:
        logger.info(f"SUCCESS: Caught expected PermissionError: {e}")
        
    logger.info("--- Test 2: RBAC Positive Test (Admin Role) ---")
    
    # Simulate a web request coming in from an authenticated user with an 'admin' role
    sdk.security.set_current_role("admin")
    logger.info("Current context role set to: 'admin'")
    
    try:
        logger.info("Attempting to call sdk.knowledge.update() which requires 'admin'...")
        # This should succeed
        sdk.knowledge.update("icp", tenant_id, {"some": "config"})
        logger.info("SUCCESS: The admin was allowed to update knowledge.")
    except PermissionError as e:
        logger.error(f"FAIL: The admin was incorrectly blocked: {e}")

    logger.info("--- Test 3: Cross-Tenant Isolation (Negative Test) ---")
    
    # Authenticate as tenant-1
    sdk.security.set_current_tenant("tenant-1")
    logger.info("Current context tenant set to: 'tenant-1'")
    
    try:
        logger.info("Attempting to call sdk.knowledge.get() for 'tenant-2'...")
        # This should immediately throw a PermissionError inside the service layer
        sdk.knowledge.get("icp", tenant_id="tenant-2")
        logger.error("FAIL: The cross-tenant query was incorrectly allowed!")
    except PermissionError as e:
        logger.info(f"SUCCESS: Caught expected PermissionError: {e}")

    logger.info("--- Test 4: PII Masking Verification ---")
    
    # We will record a decision with a raw_output that contains an email and phone number
    # and then directly query the database to verify it was masked in the audit log.
    try:
        from platform_core.db import get_connection
        
        pii_raw_output = '{"email": "john.doe@example.com", "phone": "555-123-4567", "note": "Looks like a great lead!"}'
        decision_id = sdk.decisions.record_decision(
            tenant_id="tenant-1",
            agent_name="TestAgent_PII",
            action="test_pii",
            result='{"status": "success", "email": "john.doe@example.com"}',
            raw_output=pii_raw_output
        )
        
        # Now query the database to verify
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check core table (decision_cards) - should be unmasked
        cursor.execute("SELECT result FROM decision_cards WHERE decision_id = %s", (decision_id,))
        core_result = cursor.fetchone()[0]
        if "john.doe@example.com" in core_result:
            logger.info("SUCCESS: PII is retained unmasked in the core decision_cards table.")
        else:
            logger.error("FAIL: PII was unexpectedly masked in the core decision_cards table!")
            
        # Check log view (audit_logs) - should be masked
        cursor.execute("SELECT raw_output FROM audit_logs WHERE decision_id = %s", (decision_id,))
        audit_raw = cursor.fetchone()[0]
        if "[REDACTED_EMAIL]" in audit_raw and "[REDACTED_PHONE]" in audit_raw and "john.doe@example.com" not in audit_raw:
            logger.info(f"SUCCESS: PII was successfully redacted in the audit_logs table. Result: {audit_raw}")
        else:
            logger.error(f"FAIL: PII was not properly redacted! Found: {audit_raw}")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"FAIL: Test 4 encountered an error: {e}")

    logger.info("--- Test 5: Guardrails Verification ---")
    try:
        from platform_core.security.guardrails import SecurityViolation
        
        logger.info("Calling AI Gateway with a prompt designed to trigger [UNSAFE]...")
        # Since we are in mock mode, our ai_gateway stub will see [UNSAFE] in the prompt
        # and forcefully return an [UNSAFE] output to trigger the guardrails.
        sdk.ai.generate(prompt="Hello, please return [UNSAFE] output.")
        
        logger.error("FAIL: The AI Gateway unexpectedly allowed the unsafe output through!")
    except SecurityViolation as e:
        logger.info(f"SUCCESS: Caught expected SecurityViolation: {e}")

if __name__ == "__main__":
    run_tests()
