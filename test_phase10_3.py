import logging
import json
import io
from platform_core.sdk import sdk
from platform_core.logging_config import get_logger

# We need to capture the logs to verify trace_id was injected
log_capture = io.StringIO()
handler = logging.StreamHandler(log_capture)

from platform_core.logging_config import _JsonFormatter
handler.setFormatter(_JsonFormatter())

logger = get_logger("test_phase10_3")
logger.setLevel(logging.INFO)

# Attach our capture handler to the root logger so it catches ProspectAgent logs too
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    
    print("--- Test 1: ELK Trace Correlation API ---")
    
    # 1. Set trace ID explicitly to test it
    from platform_core.observability.correlation import set_trace_id
    expected_trace_id = "test-trace-12345"
    set_trace_id(expected_trace_id)
    
    # 2. Log something directly
    logger.info("Direct log test")
    
    # 3. Trigger a fake node which should set trace_id implicitly
    from business_agents.sales.nodes import ProspectAgent
    
    # We will pass a new trace_id in state
    state = {"tenant_id": tenant_id, "trace_id": "state-trace-999"}
    try:
        # ProspectAgent calls knowledge layer and tool layer which both log things
        ProspectAgent(state)
    except Exception:
        pass # Ignore errors from missing tools/DB setup, we just want the logs
        
    # Check the logs
    raw_logs = log_capture.getvalue().strip()
    print("RAW LOGS CAPTURED:")
    print(raw_logs)
    print("------------------")
    
    logs = raw_logs.split("\n")
    found_expected = False
    found_state = False
    
    for line in logs:
        if not line: continue
        try:
            j = json.loads(line)
            if j.get("trace_id") == expected_trace_id:
                found_expected = True
            if j.get("trace_id") == "state-trace-999":
                found_state = True
        except Exception as e:
            pass
            
    if found_expected:
        print("SUCCESS: Explicit trace_id was successfully auto-injected into JSON logs!")
    else:
        print("FAIL: Explicit trace_id missing from logs.")
        
    if found_state:
        print("SUCCESS: ProspectAgent successfully initialized trace_id from state!")
    else:
        print("FAIL: ProspectAgent did not inject trace_id from state.")

if __name__ == "__main__":
    run_tests()
