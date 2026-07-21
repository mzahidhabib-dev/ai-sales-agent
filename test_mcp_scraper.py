import logging
import os
from platform_core.sdk import sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_mcp_scraper")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    # Force USE_MCP=true so it doesn't fall back to the stub
    os.environ["USE_MCP"] = "true"
    
    logger.info("--- Test 1: Real Web Scraper MCP Server ---")
    
    test_domains = ["n8n.io", "github.com", "example.com"]
    
    for domain in test_domains:
        try:
            logger.info(f"Calling sdk.tools.call('research_company', domain='{domain}')")
            
            # This uses the MCP protocol over stdio to call workers/web_research_mcp.py
            result = sdk.tools.call(
                "research_company", 
                tenant_id=tenant_id, 
                domain=domain
            )
            
            logger.info(f"SUCCESS: Extracted {len(result)} characters from {domain}.")
            logger.info(f"Preview of extracted text: {result[:200]}...\n")
            
        except Exception as e:
            logger.error(f"FAIL: Test encountered an error on {domain}: {e}\n")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    run_tests()
