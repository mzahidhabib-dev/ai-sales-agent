import logging
from platform_core.sdk import sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase11")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Cost Engine Aggregation (Step 11.1) ---")
    
    try:
        # Generate some dummy costs using the AI Gateway to ensure it passes cost_usd
        logger.info("Generating a dummy AI request to create a decision card with cost...")
        
        # We simulate what the ProspectAgent does
        ai_res = sdk.ai.generate(prompt="Cost test 1", model_name="gemini-mock")
        
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="CostTestAgent",
            action="find_prospect",
            prompt="Cost test 1",
            raw_output=ai_res.get("raw"),
            result="dummy",
            cost_usd=ai_res.get("cost_usd"),
            model="gemini-mock"
        )
        
        # Simulate a booked meeting
        ai_res2 = sdk.ai.generate(prompt="Cost test 2", model_name="gemini-pro-mock")
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="CostTestAgent",
            action="book_meeting",
            prompt="Cost test 2",
            raw_output=ai_res2.get("raw"),
            result="dummy",
            cost_usd=ai_res2.get("cost_usd"),
            model="gemini-pro-mock"
        )
        
        # Now fetch the dashboard metrics
        metrics = sdk.cost.get_dashboard_metrics(tenant_id)
        
        logger.info(f"Dashboard Metrics: {metrics}")
        
        if metrics["total_spend"] > 0.0:
            logger.info("SUCCESS: total_spend is calculated correctly!")
        else:
            logger.error("FAIL: total_spend is zero.")
            
        if metrics["cost_per_lead"] > 0.0:
            logger.info("SUCCESS: cost_per_lead is calculated correctly!")
        else:
            logger.error("FAIL: cost_per_lead is zero.")
            
        if metrics["cost_per_meeting"] > 0.0:
            logger.info("SUCCESS: cost_per_meeting is calculated correctly!")
        else:
            logger.error("FAIL: cost_per_meeting is zero.")
            
    except Exception as e:
        logger.error(f"FAIL: Test 1 encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
