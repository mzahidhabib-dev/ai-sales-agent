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
        "prospects": [{"prospect_id": 1, "domain": "n8n.io"}],  # Change this to any website you want to test!
        "current_prospect_index": 0,
        "decision_maker": {"name": "John Doe", "role": "CEO", "email": "john@n8n.io"}
    }

    # 2. Run Research (MCP Web Scraper + Gemini Summarization)
    print("1. Researching...")
    state.update(ResearchAgent(state))
    print(f"Summary: {state['research_summary'][:200]}...\n")

    # 3. Run Scoring (Gemini evaluating against your Knowledge Layer Rubric)
    print("2. Scoring...")
    state.update(ScoringAgent(state))
    print(f"Score: {state['score']} | Buying Signal: {state['buying_signal']}\n")

    # 4. Run Email Drafting & Send via n8n
    # Note: It will ONLY send the email if the lead score is > 80!
    print("3. Drafting & Sending Email...")
    if state['score'] >= 80:
        state.update(DraftOutreachAgent(state))
        
        # Bypass the Human-in-the-Loop pause by auto-approving the draft in the DB
        decision_id = state["outreach_decision_id"]
        sdk.decisions.update_decision(decision_id, "APPROVED")
        print(f"Human-in-the-Loop: Auto-approved email draft (ID: {decision_id})")
        
        state.update(SendOutreachAgent(state))
        print("Email triggered! Check your n8n Executions tab or your Gmail Sent folder.")
    else:
        print("Lead score too low. Email bypassed.")

if __name__ == "__main__":
    run()
