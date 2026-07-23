from typing import TypedDict, Optional, List, Dict, Any

class PipelineState(TypedDict):
    """
    The state dictionary that flows through the LangGraph pipeline.
    """
    tenant_id: str
    
    # Set by ProspectAgent
    prospects: List[Dict[str, Any]]
    current_prospect_index: int
    
    # Set by DecisionMakerAgent
    decision_maker: Optional[Dict[str, Any]]
    
    # Set by ResearchAgent
    research_summary: Optional[str]
    
    # Set by OpportunityAgent
    opportunity_detection: Optional[str]
    
    # Set by ScoringAgent
    score: Optional[float]
    buying_signal: Optional[bool]
    
    # Set by DraftOutreachAgent
    outreach_message: Optional[str]
    outreach_decision_id: Optional[int]
    
    # Set by SendOutreachAgent
    email_sent: Optional[bool]
    
    # Set by FollowUpAgent
    follow_up_triggered: Optional[bool]
    
    # Set by MeetingAgent
    meeting_booked: Optional[bool]
    opportunity_id: Optional[int]
    
    # Errors
    error: Optional[str]
