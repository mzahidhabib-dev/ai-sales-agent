from platform_core.logging_config import get_logger
from prometheus_client import start_http_server, Counter, Histogram

logger = get_logger(__name__)

# Core Metrics
AI_GATEWAY_CALLS = Counter(
    "ai_gateway_calls_total", 
    "Total calls made to the AI Gateway", 
    ["model_name", "tenant_id"]
)

AGENT_EXECUTION_LATENCY = Histogram(
    "agent_execution_latency_seconds",
    "Time spent executing an agent node",
    ["agent_name", "tenant_id"]
)

WORKFLOW_ERRORS = Counter(
    "workflow_errors_total",
    "Total unrecoverable workflow errors",
    ["agent_name", "tenant_id"]
)

_is_running = False

def start_metrics_server(port: int = 8000):
    """
    Step 10.2: Exposes Prometheus metrics on the given port.
    """
    global _is_running
    if not _is_running:
        try:
            start_http_server(port)
            _is_running = True
            logger.info("Prometheus metrics server started", extra={"port": port})
        except Exception as e:
            logger.error(
                "Failed to start Prometheus metrics server",
                extra={
                    "port": port,
                    "exc_type": type(e).__name__,
                    "error": str(e),
                    "catch_reason": "Metrics server failure should not crash the main application"
                }
            )
