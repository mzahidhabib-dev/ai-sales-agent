import logging
from platform_core.sdk import sdk
import time
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase10")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    logger.info("--- Test 1: Start Prometheus Metrics Server (Step 10.2) ---")
    try:
        # Start the server on port 8000
        sdk.observability.metrics.start_metrics_server(port=8000)
        logger.info("SUCCESS: Metrics server initialized.")
        
        # Simulate an AI Gateway call to bump ai_gateway_calls_total
        logger.info("Simulating AI Gateway call to trigger metrics...")
        sdk.ai.generate(prompt="Hello metrics", model_name="gemini-mock")
        
        # Simulate a node execution latency
        logger.info("Simulating a node execution to trigger latency metrics...")
        from business_agents.sales.nodes import time_node
        
        @time_node("DummyAgent")
        def DummyAgent(state):
            time.sleep(0.1) # Sleep to generate latency
            return {"status": "ok"}
            
        DummyAgent({"tenant_id": tenant_id})
        
        # Now fetch the metrics via HTTP
        logger.info("Fetching metrics from http://localhost:8000/...")
        response = requests.get("http://localhost:8000/")
        
        if response.status_code == 200:
            metrics_text = response.text
            if "ai_gateway_calls_total" in metrics_text and 'model_name="gemini-mock"' in metrics_text:
                logger.info("SUCCESS: ai_gateway_calls_total metric found and correct!")
            else:
                logger.error("FAIL: ai_gateway_calls_total metric missing or incorrect.")
                
            if "agent_execution_latency_seconds" in metrics_text and 'agent_name="DummyAgent"' in metrics_text:
                logger.info("SUCCESS: agent_execution_latency_seconds metric found and correct!")
            else:
                logger.error("FAIL: agent_execution_latency_seconds metric missing or incorrect.")
        else:
            logger.error(f"FAIL: Expected HTTP 200 from metrics endpoint, got {response.status_code}")
            
    except Exception as e:
        logger.error(f"FAIL: Test 1 encountered an error: {e}")

if __name__ == "__main__":
    run_tests()
