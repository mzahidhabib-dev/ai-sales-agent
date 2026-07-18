"""
test_phase3.py

Manual end-to-end test of the full LangGraph sales pipeline.
Runs every node in sequence (mock AI, stub tools).

Run from the project root:
    .venv\\Scripts\\python.exe test_phase3.py

Requires env vars:
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB
    USE_MOCK_AI=true  (default — no Gemini key needed)
    REDIS_HOST=localhost  (default)
"""

from platform_core.logging_config import configure_logging, get_logger
configure_logging()
logger = get_logger("test_phase3")

from business_agents.sales.graph import sales_pipeline


def main():
    tenant_id = "tenant-1"
    config = {"configurable": {"thread_id": "test_thread_1"}}

    initial_state = {
        "tenant_id": tenant_id,
        "prospects": [],
        "current_prospect_index": 0,
    }

    logger.info("Starting full pipeline test", extra={"tenant_id": tenant_id})

    for s in sales_pipeline.stream(initial_state, config):
        node = list(s.keys())[0]
        logger.info("Node executed", extra={"node": node, "tenant_id": tenant_id})

    logger.info("Pipeline stream complete — checking final state")
    state = sales_pipeline.get_state(config)
    final = state.values
    logger.info("Final state", extra={
        "meeting_booked": final.get("meeting_booked"),
        "email_sent": final.get("email_sent"),
        "score": final.get("score"),
        "buying_signal": final.get("buying_signal"),
        "opportunity_id": final.get("opportunity_id"),
    })


if __name__ == "__main__":
    main()

