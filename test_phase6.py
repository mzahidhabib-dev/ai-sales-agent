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

    logger.info("--- Test 2: Workflow Suspension API ---")
    try:
        from business_agents.sales.graph import create_sales_graph
        graph = create_sales_graph()
        
        # Set tenant context so the agents can access the Knowledge Layer
        sdk.security.set_current_tenant("tenant-1")
        
        # We start the graph and pass initial state
        # The agent should halt right before SendOutreachAgent
        config = {"configurable": {"thread_id": "test_hitl_1"}}
        
        # State representing what previous nodes would have set
        initial_state = {
            "tenant_id": "tenant-1",
            "prospects": [{"prospect_id": 1, "domain": "example.com"}],
            "current_prospect_index": 0,
            "decision_maker": {"first_name": "Bob", "email": "bob@example.com"},
            "research_summary": "Test Summary"
        }
        
        logger.info("Starting pipeline. Should halt at SendOutreachAgent.")
        for chunk in graph.stream(initial_state, config):
            for node, state in chunk.items():
                logger.info(f"Ran node: {node}")
                
        # The pipeline has halted.
        pipeline_state = graph.get_state(config)
        next_nodes = pipeline_state.next
        if "SendOutreachAgent" in next_nodes:
            logger.info("SUCCESS: Pipeline is suspended waiting for SendOutreachAgent!")
        else:
            logger.error(f"FAIL: Pipeline did not halt. Next nodes: {next_nodes}")
            
        current_state = pipeline_state.values
        decision_id = current_state.get("outreach_decision_id")
        
        if decision_id:
            logger.info(f"Decision ID captured: {decision_id}. Simulating human editing the email...")
            # Human edits the email
            edited_text = "Hello Bob, this is a human-edited email."
            sdk.decisions.resolve_approval(decision_id, "EDITED", edited_text)
            
            logger.info("Resuming pipeline...")
            # Resume graph with no new state, it picks up where it left off
            for chunk in graph.stream(None, config):
                for node, state in chunk.items():
                    logger.info(f"Ran node: {node}")
                    
            final_state = graph.get_state(config).values
            
            # Now we query the DB to verify our "send_email" mock fired the event, or just check the logs.
            # We don't have a direct way to intercept the email body in the test, but SendOutreachAgent
            # will have used our edited text. The log output will show the nodes completing.
            if final_state.get("email_sent"):
                logger.info("SUCCESS: Pipeline completed and email was sent after human approval!")
            else:
                logger.error("FAIL: Pipeline resumed but email_sent was not set.")
        else:
            logger.error("FAIL: outreach_decision_id was not set in state.")
            
    except Exception as e:
        logger.error(f"FAIL: Test 2 encountered an error: {e}")

    logger.info("--- Test 3: External Resolution Endpoint (Stub) ---")
    try:
        # Step 1: Create a test decision card
        decision_id = sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="TestAgent_API",
            action="draft_api_test",
            result='{"email_body": "This is from the API test."}'
        )
        sdk.decisions.request_approval(decision_id)
        
        # Step 2: Simulate a webhook from Slack
        payload = {
            "decision_id": decision_id,
            "status": "REJECTED"
        }
        
        import json
        import hmac
        import hashlib
        
        payload_bytes = json.dumps(payload).encode("utf-8")
        
        secret = "stub_secret_123"
        signature = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        
        logger.info(f"Simulating webhook payload: {payload}")
        response = sdk.api.webhook_resolve_decision(
            payload=payload, 
            payload_bytes=payload_bytes, 
            signature_header=signature
        )
        
        if response.get("status") == 200:
            logger.info("SUCCESS: Webhook endpoint returned 200 OK")
        else:
            logger.error(f"FAIL: Webhook endpoint returned error: {response}")
            
        # Verify in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT approval_status FROM decision_cards WHERE decision_id = %s", (decision_id,))
        status = cursor.fetchone()[0]
        if status == "REJECTED":
            logger.info("SUCCESS: The external webhook successfully updated the internal database state!")
        else:
            logger.error(f"FAIL: Expected REJECTED but got {status}")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"FAIL: Test 3 encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
