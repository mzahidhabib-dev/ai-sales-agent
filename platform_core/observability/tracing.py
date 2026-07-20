import os
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

def setup_tracing():
    """
    Step 10.1: Configures LangSmith tracing for LangGraph.
    LangGraph natively relies on environment variables, so we simply verify they exist.
    """
    logger.info("Setting up LangSmith tracing...")
    
    if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() != "true":
        logger.warning(
            "LangSmith tracing is disabled (LANGCHAIN_TRACING_V2 != true). "
            "Set this variable to enable end-to-end trace logging in LangSmith."
        )
    
    if not os.getenv("LANGCHAIN_API_KEY"):
        logger.warning(
            "LANGCHAIN_API_KEY is missing. "
            "LangGraph will not be able to export traces to LangSmith."
        )
        
    logger.info("Tracing configuration complete.")
