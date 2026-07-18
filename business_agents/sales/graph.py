from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from business_agents.sales.state import PipelineState
from business_agents.sales.nodes import (
    ProspectAgent,
    DecisionMakerAgent,
    ResearchAgent,
    ScoringAgent,
    PersonalizationAgent,
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
    builder.add_node("PersonalizationAgent", PersonalizationAgent)
    builder.add_node("FollowUpAgent", FollowUpAgent)
    builder.add_node("MeetingAgent", MeetingAgent)
    builder.add_node("HumanHandoff", HumanHandoff)
    
    # 3. Add Edges (Linear pipeline for MVP)
    builder.add_edge(START, "ProspectAgent")
    
    # Simple conditional routing logic (or linear for now)
    # We will do a simple linear flow based on Step 3.1
    # ProspectAgent -> DecisionMakerAgent -> ResearchAgent -> ScoringAgent 
    # -> PersonalizationAgent -> FollowUpAgent -> MeetingAgent -> HumanHandoff
    builder.add_edge("ProspectAgent", "DecisionMakerAgent")
    builder.add_edge("DecisionMakerAgent", "ResearchAgent")
    builder.add_edge("ResearchAgent", "ScoringAgent")
    
    # For now, unconditionally move forward. In Phase 6 (Intelligent routing), we will add conditional edges based on score.
    builder.add_edge("ScoringAgent", "PersonalizationAgent")
    builder.add_edge("PersonalizationAgent", "FollowUpAgent")
    builder.add_edge("FollowUpAgent", "MeetingAgent")
    builder.add_edge("MeetingAgent", "HumanHandoff")
    builder.add_edge("HumanHandoff", END)
    
    # 4. Compile with Checkpointer
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    return graph

# Expose a default instance
sales_pipeline = create_sales_graph()
