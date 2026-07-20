import logging
from platform_core.sdk import sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase12")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Fallback Logic (Step 12.2) ---")
    
    # Send a prompt with "FAIL_PRIMARY" which causes the mock gateway to simulate an outage
    prompt = "FAIL_PRIMARY please process this"
    
    logger.info("Sending a prompt to Gemini (Primary)...")
    res = sdk.ai.generate(prompt=prompt, provider="gemini", fallback_provider="openai")
    
    if res.get("valid"):
        logger.info("SUCCESS: The prompt successfully returned!")
        logger.info("Check the logs above. You should see a WARNING saying 'Simulating primary provider failure, falling back...'")
    else:
        logger.error("FAIL: The prompt did not return successfully.")

if __name__ == "__main__":
    run_tests()
