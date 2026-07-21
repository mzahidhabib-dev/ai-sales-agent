import json
import logging
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from platform_core.sdk import sdk
from business_agents.sales.nodes import ResearchAgent, ScoringAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_regression")

def run_tests():
    tenant_id = "tenant-1"
    sdk.security.set_current_tenant(tenant_id)
    os.environ["USE_MCP"] = "true"
    
    # Load Golden Dataset
    dataset_path = os.path.join(os.path.dirname(__file__), "tests", "golden_dataset.json")
    if not os.path.exists(dataset_path):
        logger.error(f"FAIL: Golden dataset not found at {dataset_path}")
        return
        
    with open(dataset_path, "r") as f:
        dataset = json.load(f)
        
    logger.info(f"--- Golden Dataset Regression Test ({len(dataset)} cases) ---")
    
    # Create a generic ICP config for scoring
    # In a real run, this is loaded from the Knowledge Layer
    os.environ["MOCK_ICP"] = json.dumps({
        "ideal_customer_profile": "B2B SaaS companies, Developer Tools, Automation Platforms",
        "pain_points": ["complex workflows", "managing code", "developer efficiency"]
    })
    
    for idx, test_case in enumerate(dataset):
        domain = test_case["company_domain"]
        logger.info(f"\n--- Testing Case {idx+1}: {domain} ---")
        
        # 1. Setup mock state for ResearchAgent
        state = {
            "tenant_id": tenant_id,
            "prospects": [{"prospect_id": idx, "domain": domain}],
            "current_prospect_index": 0
        }
        
        try:
            # 2. Run ResearchAgent
            logger.info("Running ResearchAgent (fetches via Web Scraper + summarizes via AI)...")
            state.update(ResearchAgent(state))
            summary = state.get("research_summary", "")
            logger.info(f"Research Summary generated! Length: {len(summary)} chars.")
            
            # 3. Run ScoringAgent
            logger.info("Running ScoringAgent...")
            state.update(ScoringAgent(state))
            score = state.get("lead_score", 0)
            
            # Print the AI's reasoning directly from the database for debugging
            from platform_core.db import get_connection
            c = get_connection()
            cur = c.cursor()
            cur.execute("SELECT reason FROM decision_cards WHERE action='score_prospect' ORDER BY decision_id DESC LIMIT 1")
            reason = cur.fetchone()[0]
            logger.info(f"AI Reasoning: {reason}")
            c.close()
            
            # 4. Verify against Golden Dataset
            expected_min = test_case["expected_score_min"]
            logger.info(f"Actual Score: {score} | Expected Min: {expected_min}")
            
            if score >= expected_min:
                logger.info("SUCCESS: Lead score matches Golden Expectations!")
            else:
                logger.error(f"FAIL: Lead score {score} was lower than expected {expected_min}")
                
            # Verify keywords in research
            keywords = test_case["buying_signal_keywords"]
            if keywords:
                # We check if any of the keywords show up in the summary
                found = any(k.lower() in summary.lower() for k in keywords)
                if found:
                    logger.info("SUCCESS: Golden buying signal keywords successfully extracted from website!")
                else:
                    logger.warning(f"WARNING: None of the expected keywords {keywords} were prominent in the summary.")
            
        except Exception as e:
            logger.error(f"FAIL: Pipeline broke on {domain}. Error: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    run_tests()
