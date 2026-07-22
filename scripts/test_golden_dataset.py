import time
from platform_core.security.tenant_isolation import set_current_tenant
from business_agents.sales.nodes import ResearchAgent, ScoringAgent

GOLDEN_DATASET = [
    {
        "domain": "langchain.com",
        "expected_score_min": 70.0,
        "expected_buying_signal": True,
        "description": "Ideal Customer Fit: AI framework company"
    },
    {
        "domain": "n8n.io",
        "expected_score_min": 0.0,
        "expected_buying_signal": False,
        "description": "Protected site / low data scraped"
    }
]

def run_golden_dataset_test():
    print("=== 🧪 Running Golden Dataset Validation Test ===")
    set_current_tenant("tenant-1")
    
    passed_tests = 0
    total_tests = len(GOLDEN_DATASET)
    
    for idx, sample in enumerate(GOLDEN_DATASET):
        print(f"\n[{idx+1}/{total_tests}] Testing Domain: {sample['domain']} ({sample['description']})")
        state = {
            "tenant_id": "tenant-1",
            "prospects": [{"prospect_id": idx + 1, "domain": sample["domain"]}],
            "current_prospect_index": 0,
            "decision_maker": {"name": "Test Contact", "role": "CEO", "email": "test@example.com"}
        }
        
        try:
            # 1. Research
            state.update(ResearchAgent(state))
            print("  Research complete. Sleeping 15s...")
            time.sleep(15)
            
            # 2. Score
            state.update(ScoringAgent(state))
            actual_score = state.get("score", 0.0)
            actual_buying_signal = state.get("buying_signal", False)
            
            print(f"  Result: Actual Score={actual_score} (Expected Min={sample['expected_score_min']})")
            print(f"          Actual Buying Signal={actual_buying_signal} (Expected={sample['expected_buying_signal']})")
            
            if actual_score >= sample["expected_score_min"]:
                print("  ✅ PASSED BENCHMARK")
                passed_tests += 1
            else:
                print("  ❌ FAILED BENCHMARK")
                
            time.sleep(15)
        except Exception as e:
            print(f"  ❌ ERROR: {e}")

    print(f"\n==========================================")
    print(f"Golden Dataset Test Summary: {passed_tests}/{total_tests} Benchmarks Passed.")
    print(f"==========================================")

if __name__ == "__main__":
    run_golden_dataset_test()
