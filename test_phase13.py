import logging
import os
from platform_core.sdk import sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase13")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: MCP Client Full Wiring (Step 13.1 & 13.2) ---")
    
    # Enable the MCP routing for the test
    os.environ["USE_MCP"] = "true"
    
    try:
        logger.info("Calling sdk.tools.call('research_company', ...)")
        # This will hit Tool Gateway -> mcp_client.py -> dummy_mcp_server.py
        result = sdk.tools.call("research_company", tenant_id=tenant_id, domain="example.com")
        
        logger.info(f"Result returned to agent: {result}")
        
        if "[MCP LinkedIn Scraper Server]" in result:
            logger.info("SUCCESS: The Tool Gateway successfully routed the call over the Model Context Protocol (MCP) to the external server!")
        else:
            logger.error("FAIL: Did not get the expected string back from the MCP server.")
            
    except Exception as e:
        logger.error(f"FAIL: Test encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
