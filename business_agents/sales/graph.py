from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from business_agents.sales.state import PipelineState
from business_agents.sales.nodes import (
    ProspectAgent,
    DecisionMakerAgent,
    ResearchAgent,
    ScoringAgent,
    DraftOutreachAgent,
    SendOutreachAgent,
    FollowUpAgent,
    MeetingAgent,
    HumanHandoff
)

def create_sales_graph():
    # 1. Initialize StateGraph
    builder = StateGraph(PipelineState)
    
    # 2. Add Nodes
    builder.add_node("ProspectAgent", ProspectAgent)
    builder.add_node("DecisionMakerAgent", DecisionMakerAgent)
    builder.add_node("ResearchAgent", ResearchAgent)
    builder.add_node("ScoringAgent", ScoringAgent)
    builder.add_node("DraftOutreachAgent", DraftOutreachAgent)
    builder.add_node("SendOutreachAgent", SendOutreachAgent)
    builder.add_node("FollowUpAgent", FollowUpAgent)
    builder.add_node("MeetingAgent", MeetingAgent)
    builder.add_node("HumanHandoff", HumanHandoff)
    
    # 3. Add Edges (Linear pipeline for MVP)
    builder.add_edge(START, "ProspectAgent")
    
    builder.add_edge("ProspectAgent", "DecisionMakerAgent")
    builder.add_edge("DecisionMakerAgent", "ResearchAgent")
    builder.add_edge("ResearchAgent", "ScoringAgent")
    
    builder.add_edge("ScoringAgent", "DraftOutreachAgent")
    builder.add_edge("DraftOutreachAgent", "SendOutreachAgent")
    builder.add_edge("SendOutreachAgent", "FollowUpAgent")
    builder.add_edge("FollowUpAgent", "MeetingAgent")
    builder.add_edge("MeetingAgent", "HumanHandoff")
    builder.add_edge("HumanHandoff", END)
    
    # 4. Compile with Checkpointer and HITL interrupt (Step 6.2)
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory, interrupt_before=["SendOutreachAgent"])
    return graph

# Expose a default instance
sales_pipeline = create_sales_graph()
