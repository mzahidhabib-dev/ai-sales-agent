"""
business_agents/sales/nodes.py

Pipeline node functions for the LangGraph sales pipeline.

Rules compliance:
  Rule 7  -- Every node follows the same error-handling and logging pattern.
  Rule 9  -- Every external call is wrapped in try/except with structured logging.
             workflow.failed is published on any unrecoverable error.
  Rule 12 -- Every node documents: required state keys, what happens when AI
             output is invalid, what happens when a tool call fails.
  Rule 17 -- Only platform_core.sdk is imported (no direct Postgres/Redis/Gemini).
"""

from platform_core.sdk import sdk
from typing import Any

logger = sdk.get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require(state: dict, *keys: str) -> None:
    """
    Asserts that all required keys are present and non-None in state.

    Raises:
        ValueError: with a clear message listing which keys are missing.
                    Callers should let this propagate -- the Worker will
                    publish workflow.failed.
    """
    missing = [k for k in keys if k not in state or state[k] is None]
    if missing:
        raise ValueError(
            f"Pipeline state is missing required fields: {missing}. "
            "This indicates a previous node did not complete successfully."
        )


def _publish_failure(tenant_id: str, agent: str, error: str) -> None:
    """
    Publishes a workflow.failed event. Used in every except block so failures
    are always visible in the events table.

    Args:
        tenant_id: Tenant identifier.
        agent:     Name of the node that failed.
        error:     Human-readable error description.
    """
    try:
        sdk.events.publish(tenant_id, "workflow.failed", {"agent": agent, "error": error})
    except Exception as pub_err:
        # If even the event publish fails, log it but do not swallow the original error.
        logger.error(
            "Failed to publish workflow.failed event",
            extra={"tenant_id": tenant_id, "agent": agent, "pub_error": str(pub_err)},
        )


# ---------------------------------------------------------------------------
# Pipeline nodes
# ---------------------------------------------------------------------------

def ProspectAgent(state: dict) -> dict:
    """
    Finds prospects using ICP config from the Knowledge Layer.

    Required state keys: tenant_id
    Sets state keys:     prospects, current_prospect_index

    Error cases:
        - ICP config not found: Knowledge Layer returns {}; prospect tool will
          still run with empty config and return stub data.
        - tool call fails: workflow.failed event published; exception re-raised.
        - record_decision fails: workflow.failed published; exception re-raised.
    """
    tenant_id = state.get("tenant_id")
    if not tenant_id:
        raise ValueError("ProspectAgent: 'tenant_id' is required in pipeline state.")

    agent = "ProspectAgent"
    try:
        icp = sdk.knowledge.get("icp", tenant_id)
    except ValueError as e:
        _publish_failure(tenant_id, agent, f"Failed to load ICP config: {e}")
        raise

    try:
        prospects = sdk.tools.call("find_prospect", tenant_id=tenant_id, icp_config=icp)
    except Exception as e:
        logger.error(
            "ProspectAgent: find_prospect tool failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"find_prospect failed: {e}")
        raise

    try:
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="find_prospect",
            result=f"Found {len(prospects)} prospects",
        )
    except Exception as e:
        logger.error(
            "ProspectAgent: record_decision failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"record_decision failed: {e}")
        raise

    for p in prospects:
        sdk.events.publish(tenant_id, "prospect.found", p)

    return {"prospects": prospects, "current_prospect_index": 0}


def DecisionMakerAgent(state: dict) -> dict:
    """
    Finds the decision maker for the current prospect.

    Required state keys: tenant_id, prospects, current_prospect_index
    Sets state keys:     decision_maker

    Error cases:
        - prospects list is empty or index out of range: raises ValueError.
        - tool call fails: workflow.failed published; exception re-raised.
    """
    _require(state, "tenant_id", "prospects")
    tenant_id = state["tenant_id"]
    agent = "DecisionMakerAgent"
    idx = state.get("current_prospect_index", 0)
    prospects = state["prospects"]

    if not prospects or idx >= len(prospects):
        err = f"No prospect at index {idx} (total: {len(prospects)})"
        _publish_failure(tenant_id, agent, err)
        raise ValueError(f"DecisionMakerAgent: {err}")

    current_prospect = prospects[idx]
    prospect_id = current_prospect.get("prospect_id")

    try:
        dm = sdk.tools.call("find_decision_maker", tenant_id=tenant_id, prospect_id=prospect_id)
    except Exception as e:
        logger.error(
            "DecisionMakerAgent: find_decision_maker tool failed",
            extra={"tenant_id": tenant_id, "prospect_id": prospect_id,
                   "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"find_decision_maker failed: {e}")
        raise

    try:
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="find_decision_maker",
            result=f"Found DM {dm.get('first_name')} {dm.get('last_name')}",
        )
    except Exception as e:
        logger.error(
            "DecisionMakerAgent: record_decision failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"record_decision failed: {e}")
        raise

    sdk.events.publish(tenant_id, "decision_maker.found", dm)
    return {"decision_maker": dm}


def ResearchAgent(state: dict) -> dict:
    """
    Researches the prospect company and summarizes via AI Gateway.

    Required state keys: tenant_id, prospects, current_prospect_index
    Sets state keys:     research_summary

    Error cases:
        - research_company tool fails: workflow.failed published; exception re-raised.
        - AI Gateway returns valid=False: workflow.failed published; exception raised.
          Caller (Worker) will not ACK the job.
        - record_decision fails: workflow.failed published; exception re-raised.
    """
    _require(state, "tenant_id", "prospects")
    tenant_id = state["tenant_id"]
    agent = "ResearchAgent"
    idx = state.get("current_prospect_index", 0)
    domain = state["prospects"][idx].get("domain")

    try:
        raw_research = sdk.tools.call("research_company", tenant_id=tenant_id, domain=domain)
    except Exception as e:
        logger.error(
            "ResearchAgent: research_company tool failed",
            extra={"tenant_id": tenant_id, "domain": domain,
                   "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"research_company failed: {e}")
        raise
        
    prospect_id = state["prospects"][idx].get("prospect_id")
    try:
        mem = sdk.memory.get(tenant_id, prospect_id)
        memory_context = f"\nPast interaction memory: {mem}" if mem else ""
    except Exception as e:
        logger.warning(f"ResearchAgent: failed to read memory: {e}")
        memory_context = ""

    safe_research = sdk.security.sanitize_input(raw_research)
    prompt = f"Summarize this research concisely: {safe_research}{memory_context}"
    ai_res = sdk.ai.generate(prompt)

    # Rule 9/12: Must check valid before using output
    if not ai_res.get("valid"):
        err = f"AI summary failed: {ai_res.get('error')}"
        logger.error("ResearchAgent: AI Gateway returned invalid response",
                     extra={"tenant_id": tenant_id, "ai_error": ai_res.get("error")})
        _publish_failure(tenant_id, agent, err)
        raise RuntimeError(f"ResearchAgent: {err}")

    summary = ai_res["output"]

    try:
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="summarize_research",
            prompt=prompt,
            raw_output=ai_res.get("raw"),
            result=str(summary)[:500],  # truncate for the DB column
        )
    except Exception as e:
        logger.error(
            "ResearchAgent: record_decision failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"record_decision failed: {e}")
        raise

    sdk.events.publish(tenant_id, "research.completed", {"summary": str(summary)})
    return {"research_summary": str(summary)}


def ScoringAgent(state: dict) -> dict:
    """
    Scores the prospect using the scoring rubric and AI Gateway.

    Required state keys: tenant_id, research_summary
    Sets state keys:     score, buying_signal

    Error cases:
        - Scoring rubric not found: Knowledge Layer returns {}; AI will score
          with empty rubric and likely produce low-confidence result.
        - AI Gateway returns valid=False: workflow.failed published; exception raised.
        - record_decision fails: workflow.failed published; exception re-raised.
    """
    _require(state, "tenant_id", "research_summary")
    tenant_id = state["tenant_id"]
    agent = "ScoringAgent"
    summary = state["research_summary"]

    try:
        rubric = sdk.knowledge.get("scoring_rubric", tenant_id)
    except ValueError as e:
        _publish_failure(tenant_id, agent, f"Failed to load scoring rubric: {e}")
        raise

    prompt = f"Score this prospect based on the rubric. Rubric: {rubric}. Research: {summary}"
    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "reasons": {"type": "array", "items": {"type": "string"}},
            "buying_signal_detected": {"type": "boolean"},
        },
        "required": ["score", "reasons", "buying_signal_detected"],
    }

    ai_res = sdk.ai.generate(prompt, schema=schema)

    # Rule 9/12: Must check valid before using output
    if not ai_res.get("valid") or not isinstance(ai_res.get("output"), dict):
        err = f"Scoring AI output invalid: {ai_res.get('error')}"
        logger.error("ScoringAgent: AI Gateway returned invalid response",
                     extra={"tenant_id": tenant_id, "ai_error": ai_res.get("error")})
        _publish_failure(tenant_id, agent, err)
        raise RuntimeError(f"ScoringAgent: {err}")

    score = float(ai_res["output"].get("score", 0.0))
    reasons = ai_res["output"].get("reasons", [])
    buying_signal = bool(ai_res["output"].get("buying_signal_detected", False))

    try:
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="score_prospect",
            prompt=prompt,
            raw_output=ai_res.get("raw"),
            result=f"Score: {score}",
            confidence=score / 100.0,
            reason=reasons,
        )
    except Exception as e:
        logger.error(
            "ScoringAgent: record_decision failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"record_decision failed: {e}")
        raise

    sdk.events.publish(tenant_id, "score.completed", {"score": score})
    if buying_signal:
        sdk.events.publish(tenant_id, "buying_signal.detected", {"score": score})

    return {"score": score, "buying_signal": buying_signal}


def DraftOutreachAgent(state: dict) -> dict:
    """
    Generates a personalized outreach email, records it, and requests approval.
    (Pauses here for Human-in-the-Loop)
    
    Required state keys: tenant_id, decision_maker, research_summary
    Sets state keys:     outreach_message, outreach_decision_id
    """
    _require(state, "tenant_id", "decision_maker", "research_summary")
    tenant_id = state["tenant_id"]
    agent = "DraftOutreachAgent"
    dm = state["decision_maker"]
    summary = state["research_summary"]

    prompt = f"Write a cold email to {dm.get('first_name')}. Context: {summary}"
    ai_res = sdk.ai.generate(prompt)

    if not ai_res.get("valid"):
        err = f"Email generation AI output invalid: {ai_res.get('error')}"
        logger.error(f"{agent}: AI Gateway returned invalid response",
                     extra={"tenant_id": tenant_id, "ai_error": ai_res.get("error")})
        _publish_failure(tenant_id, agent, err)
        raise RuntimeError(f"{agent}: {err}")

    message = ai_res["output"]

    try:
        decision_id = sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="draft_outreach",
            prompt=prompt,
            raw_output=ai_res.get("raw"),
            result=str(message),
        )
        sdk.decisions.request_approval(decision_id)
    except Exception as e:
        logger.error(
            f"{agent}: record_decision or request_approval failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"approval request failed: {e}")
        raise

    sdk.events.publish(tenant_id, "outreach.drafted", {"message_preview": str(message)[:100], "decision_id": decision_id})
    return {"outreach_message": str(message), "outreach_decision_id": decision_id}


def SendOutreachAgent(state: dict) -> dict:
    """
    Wakes up after Human-in-the-Loop interaction.
    Reads the decision status. Sends the email (original or edited), or aborts if rejected.
    
    Required state keys: tenant_id, decision_maker, outreach_decision_id
    Sets state keys:     email_sent
    """
    _require(state, "tenant_id", "decision_maker", "outreach_decision_id")
    tenant_id = state["tenant_id"]
    agent = "SendOutreachAgent"
    dm = state["decision_maker"]
    decision_id = state["outreach_decision_id"]

    try:
        decision = sdk.decisions.get_decision(decision_id)
    except Exception as e:
        _publish_failure(tenant_id, agent, f"Failed to load decision: {e}")
        raise

    status = decision.get("approval_status")
    
    if status == "PENDING_APPROVAL":
        err = "Agent woke up but approval is still pending!"
        _publish_failure(tenant_id, agent, err)
        raise RuntimeError(f"{agent}: {err}")
        
    if status == "REJECTED":
        logger.info("Human rejected the email draft. Aborting send.", extra={"decision_id": decision_id})
        sdk.events.publish(tenant_id, "email.rejected", {"decision_id": decision_id})
        return {"email_sent": False}
        
    # If edited, use the human's result, otherwise use the original state message
    final_message = decision["result"] if status == "EDITED" else state.get("outreach_message", "")

    email = dm.get("email", "")
    if not email:
        err = "Decision maker has no email address"
        _publish_failure(tenant_id, agent, err)
        raise ValueError(f"{agent}: {err}")

    try:
        sdk.tools.call(
            "send_email",
            tenant_id=tenant_id,
            to_email=email,
            subject="Hello",
            body=final_message,
        )
    except Exception as e:
        logger.error(
            f"{agent}: send_email tool failed",
            extra={"tenant_id": tenant_id, "to_email": email, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"send_email failed: {e}")
        raise

    sdk.events.publish(tenant_id, "email.sent", {"to_email": email})
    return {"email_sent": True}


def FollowUpAgent(state: dict) -> dict:
    """
    Triggers a follow-up if no reply has been received.

    Required state keys: tenant_id
    Sets state keys:     follow_up_triggered

    Note: Full cadence/memory logic is deferred to Phase 6 (Memory Layer).
          In Phase Group 1 the follow-up always triggers.

    Error cases:
        - record_decision fails: workflow.failed published; exception re-raised.
    """
    _require(state, "tenant_id", "prospects")
    tenant_id = state["tenant_id"]
    agent = "FollowUpAgent"
    idx = state.get("current_prospect_index", 0)
    prospect_id = state["prospects"][idx].get("prospect_id")

    try:
        mem = sdk.memory.get(tenant_id, prospect_id)
        follow_up_count = mem.get("follow_up_count", 0)
        
        # We record that we are doing a follow up
        new_count = follow_up_count + 1
        sdk.memory.update(tenant_id, prospect_id, {"follow_up_count": new_count, "last_follow_up": "today"})
        
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="trigger_follow_up",
            result=f"Follow up triggered. This is follow up #{new_count}.",
        )
    except Exception as e:
        logger.error(
            "FollowUpAgent: record_decision or memory update failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"follow up failed: {e}")
        raise

    sdk.events.publish(tenant_id, "followup.triggered", {"follow_up_count": new_count})
    return {"follow_up_triggered": True}


def MeetingAgent(state: dict) -> dict:
    """
    Checks calendar availability and books a meeting by updating the CRM.

    Required state keys: tenant_id, prospects, current_prospect_index
    Sets state keys:     meeting_booked, opportunity_id

    Error cases:
        - check_calendar_availability fails: workflow.failed published; exception re-raised.
        - update_crm fails: workflow.failed published; exception re-raised.
        - record_decision fails: workflow.failed published; exception re-raised.
    """
    _require(state, "tenant_id", "prospects")
    tenant_id = state["tenant_id"]
    agent = "MeetingAgent"
    idx = state.get("current_prospect_index", 0)
    prospect_id = state["prospects"][idx].get("prospect_id")

    try:
        slots = sdk.tools.call("check_calendar_availability", tenant_id=tenant_id)
    except Exception as e:
        logger.error(
            "MeetingAgent: check_calendar_availability failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"check_calendar_availability failed: {e}")
        raise

    try:
        opp_id = sdk.tools.call(
            "update_crm",
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            stage_id="meeting_booked",
        )
    except Exception as e:
        logger.error(
            "MeetingAgent: update_crm failed",
            extra={"tenant_id": tenant_id, "prospect_id": prospect_id,
                   "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"update_crm failed: {e}")
        raise

    try:
        sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name=agent,
            action="book_meeting",
            result=f"Meeting booked. Opportunity ID: {opp_id}",
        )
    except Exception as e:
        logger.error(
            "MeetingAgent: record_decision failed",
            extra={"tenant_id": tenant_id, "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"record_decision failed: {e}")
        raise

    sdk.events.publish(tenant_id, "meeting.booked", {"available_slots": slots})
    sdk.events.publish(tenant_id, "crm.updated", {"opportunity_id": opp_id})
    return {"meeting_booked": True, "opportunity_id": opp_id}


def HumanHandoff(state: dict) -> dict:
    """
    Records the human handoff and ends the pipeline.

    Required state keys: tenant_id, prospects, current_prospect_index, opportunity_id
    Sets state keys:     (none — terminal node)

    Error cases:
        - record_handoff fails: workflow.failed published; exception re-raised.
          The job will not be ACKed and will be retried by the Worker.
    """
    _require(state, "tenant_id", "prospects", "opportunity_id")
    tenant_id = state["tenant_id"]
    agent = "HumanHandoff"
    idx = state.get("current_prospect_index", 0)
    prospect_id = state["prospects"][idx].get("prospect_id")
    opp_id = state["opportunity_id"]
    summary = state.get("research_summary", "")

    try:
        sdk.tools.call(
            "record_handoff",
            tenant_id=tenant_id,
            prospect_id=prospect_id,
            opportunity_id=opp_id,
            summary=summary,
        )
    except Exception as e:
        logger.error(
            "HumanHandoff: record_handoff failed",
            extra={"tenant_id": tenant_id, "prospect_id": prospect_id,
                   "exc_type": type(e).__name__, "error": str(e)},
        )
        _publish_failure(tenant_id, agent, f"record_handoff failed: {e}")
        raise

    logger.info(
        "Pipeline complete — prospect handed off to human",
        extra={"tenant_id": tenant_id, "prospect_id": prospect_id, "opportunity_id": opp_id},
    )
    return {"error": None}

