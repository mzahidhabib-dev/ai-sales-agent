"""
test_phase2.py

Manual test for platform_core SDK:
  - Knowledge Layer
  - AI Gateway (mock)
  - Tool Gateway (CRM write)
  - Decision Cards
  - Events

Run from the project root:
    .venv\\Scripts\\python.exe test_phase2.py

Requires env vars:
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB
    USE_MOCK_AI=true (default)
    REDIS_HOST=localhost (default)
"""

from platform_core.logging_config import configure_logging, get_logger
configure_logging()
logger = get_logger("test_phase2")

from platform_core.sdk import sdk


def main():
    tenant_id = "tenant-1"

    # ----------------------------------------------------------------
    # 1. Knowledge Layer
    # ----------------------------------------------------------------
    logger.info("--- Test 1: Knowledge Layer ---")
    icp = sdk.knowledge.get("icp", tenant_id)
    logger.info("ICP config loaded", extra={"tenant_id": tenant_id, "icp": icp})

    # ----------------------------------------------------------------
    # 2. AI Gateway (mock mode by default)
    # ----------------------------------------------------------------
    logger.info("--- Test 2: AI Gateway (mock mode) ---")
    res = sdk.ai.generate(
        "Say hello",
        schema={"type": "object", "properties": {"greeting": {"type": "string"}}, "required": ["greeting"]}
    )
    logger.info("AI response received",
                extra={"valid": res["valid"], "output_type": type(res["output"]).__name__, "error": res["error"]})

    # ----------------------------------------------------------------
    # 3. Tool Gateway — CRM Update (requires DB)
    # ----------------------------------------------------------------
    logger.info("--- Test 3: Tool Gateway — CRM Update ---")
    try:
        opp_id = sdk.tools.call("update_crm", tenant_id=tenant_id, prospect_id=1,
                                stage_id="contacted", value=100.0)
        logger.info("CRM updated", extra={"tenant_id": tenant_id, "opportunity_id": opp_id})
    except Exception as e:
        logger.warning("CRM update failed (expected if prospect FK missing)",
                       extra={"exc_type": type(e).__name__, "error": str(e)})

    # ----------------------------------------------------------------
    # 4. Decision Cards + Events (requires DB + Redis)
    # ----------------------------------------------------------------
    logger.info("--- Test 4: Decision Cards + Events ---")
    try:
        decision_id = sdk.decisions.record_decision(
            tenant_id=tenant_id,
            agent_name="TestAgent",
            action="test_action",
            prompt="Hello",
            raw_output="world",
            result="Test passed"
        )
        logger.info("Decision card recorded", extra={"tenant_id": tenant_id, "decision_id": decision_id})

        sdk.events.publish(tenant_id, "prospect.found", {"prospect_id": 1})
        logger.info("Event published", extra={"tenant_id": tenant_id, "event_type": "prospect.found"})
    except Exception as e:
        logger.error("Events/Decision test failed",
                     extra={"exc_type": type(e).__name__, "error": str(e)})


if __name__ == "__main__":
    main()

