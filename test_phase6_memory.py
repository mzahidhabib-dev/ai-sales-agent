import logging
from platform_core.sdk import sdk

# Set logger to INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_memory")

def run_tests():
    tenant_id = "tenant-1"
    prospect_id = 999  # Mock prospect id
    
    # 0. Setup: Ensure a prospect exists to satisfy the foreign key constraint
    from platform_core.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insert dummy company
    cursor.execute(
        "INSERT INTO companies (company_id, tenant_id, name, domain) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (prospect_id, tenant_id, "Test Corp", "testcorp.com")
    )
    # Insert dummy prospect linking to that company
    cursor.execute(
        "INSERT INTO prospects (prospect_id, tenant_id, company_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (prospect_id, tenant_id, prospect_id)
    )
    conn.commit()
    conn.close()
    
    logger.info("--- Test 1: Direct SDK Memory Read/Write ---")
    
    # 1. Clear any existing memory (for a clean test)
    # The upsert doesn't let us delete directly via SDK, but we can overwrite.
    sdk.memory.update(tenant_id, prospect_id, {"test_key": "initial_value", "follow_up_count": 0})
    
    # 2. Read it back
    mem = sdk.memory.get(tenant_id, prospect_id)
    if mem.get("test_key") == "initial_value":
        logger.info("SUCCESS: Successfully read newly written memory.")
    else:
        logger.error(f"FAIL: Memory read back did not match. Got: {mem}")
        
    # 3. Update it
    sdk.memory.update(tenant_id, prospect_id, {"test_key": "updated_value", "new_key": 123})
    mem = sdk.memory.get(tenant_id, prospect_id)
    if mem.get("test_key") == "updated_value" and mem.get("new_key") == 123 and mem.get("follow_up_count") == 0:
        logger.info("SUCCESS: Successfully merged updated memory without losing old keys.")
    else:
        logger.error(f"FAIL: Memory merge failed. Got: {mem}")


    logger.info("--- Test 2: Memory in the LangGraph Pipeline ---")
    
    try:
        from business_agents.sales.graph import create_sales_graph
        graph = create_sales_graph()
        
        sdk.security.set_current_tenant("tenant-1")
        
        # State representing what previous nodes would have set, bypassing up to FollowUpAgent
        config = {"configurable": {"thread_id": "test_memory_1"}}
        
        initial_state = {
            "tenant_id": "tenant-1",
            "prospects": [{"prospect_id": prospect_id, "domain": "example.com"}],
            "current_prospect_index": 0,
        }
        
        # We will directly invoke FollowUpAgent to test its memory reading/writing
        from business_agents.sales.nodes import FollowUpAgent
        
        logger.info("Running FollowUpAgent (Run 1)...")
        res1 = FollowUpAgent(initial_state)
        mem1 = sdk.memory.get(tenant_id, prospect_id)
        count1 = mem1.get("follow_up_count")
        logger.info(f"Run 1 Follow Up Count: {count1}")
        
        logger.info("Running FollowUpAgent (Run 2)...")
        res2 = FollowUpAgent(initial_state)
        mem2 = sdk.memory.get(tenant_id, prospect_id)
        count2 = mem2.get("follow_up_count")
        logger.info(f"Run 2 Follow Up Count: {count2}")
        
        if count2 == count1 + 1:
            logger.info("SUCCESS: FollowUpAgent successfully remembered the previous interaction and incremented the counter!")
        else:
            logger.error("FAIL: FollowUpAgent did not increment the memory counter.")
            
    except Exception as e:
        logger.error(f"FAIL: Test 2 encountered an error: {e}")

if __name__ == "__main__":
    import os
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()
    except Exception as e:
        pass
    run_tests()
