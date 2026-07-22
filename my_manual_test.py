import os
from dotenv import load_dotenv
load_dotenv(override=True)

from platform_core.sdk import sdk
from platform_core.security.tenant_isolation import set_current_tenant
from business_agents.sales.nodes import ResearchAgent, ScoringAgent, DraftOutreachAgent, SendOutreachAgent

def run():
    print("\n--- Starting Manual Test ---")
    
    # 1. Provide the target company
    set_current_tenant("tenant-1")
    state = {
        "tenant_id": "tenant-1",
        "prospects": [{"prospect_id": 1, "domain": "langchain.com"}],  # Change this to any website you want to test!
        "current_prospect_index": 0,
        "decision_maker": {"name": "John Doe", "role": "CEO", "email": "john@n8n.io"}
    }

    import time

    # 2. Run Research (MCP Web Scraper + Gemini Summarization)
    print("1. Researching...")
    state.update(ResearchAgent(state))
    print(f"Summary: {state['research_summary'][:200]}...\n")
    
    print("Sleeping 20 seconds to respect Free Tier API RPM limits...")
    time.sleep(20)

    # 3. Run Scoring (Gemini evaluating against your Knowledge Layer Rubric)
    print("2. Scoring...")
    state.update(ScoringAgent(state))
    print(f"Score: {state['score']} | Buying Signal: {state['buying_signal']}\n")

    print("Sleeping 20 seconds to respect Free Tier API RPM limits...")
    time.sleep(20)

    # 4. Run Email Drafting & Send via n8n
    # Note: It will ONLY send the email if the lead score is > 80!
    print("3. Drafting & Sending Email...")
    if state['score'] >= 80:
        state.update(DraftOutreachAgent(state))
        
        print("\n⏳ HUMAN IN THE LOOP REQUIRED!")
        print("A Decision Card has been created in the database with status PENDING_APPROVAL.")
        print("Please open the AI Employee UI (http://localhost:5173/) to Approve or Reject the drafted email!")
        print("Once approved via the UI, a webhook or resume trigger would typically execute SendOutreachAgent.")
    else:
        print("Lead score too low. Email bypassed.")

if __name__ == "__main__":
    run()
