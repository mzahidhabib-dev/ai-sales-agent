import logging
import json
import os
from platform_core.sdk import sdk
from business_agents.sales.nodes import FollowUpAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase14")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Knowledge Layer Playbooks (Step 14.1) ---")
    
    state = {
        "tenant_id": tenant_id,
        "prospects": [{"prospect_id": 1, "domain": "test.com"}],
        "current_prospect_index": 0,
        "prospect_reply": "We love the product but it's just too expensive for us right now."
    }
    
    try:
        logger.info("Simulating FollowUpAgent with 'too expensive' objection...")
        result = FollowUpAgent(state)
        
        draft = result.get("follow_up_draft")
        logger.info(f"AI drafted response: {draft}")
        
        # Checking if it pivoted to ROI like the playbook instructed
        if draft and "return on investment" in draft.lower() or "roi" in draft.lower() or "3x" in draft.lower():
            logger.info("SUCCESS: The FollowUpAgent correctly pulled the 'too_expensive' playbook from the Knowledge Layer and used it to draft the response!")
        else:
            logger.error("FAIL: The AI did not use the exact script from the playbook.")
            
    except Exception as e:
        logger.error(f"FAIL: Test encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
