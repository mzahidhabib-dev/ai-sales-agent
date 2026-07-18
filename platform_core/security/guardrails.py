from platform_core.logging_config import get_logger

logger = get_logger(__name__)

class SecurityViolation(Exception):
    """Raised when an AI output fails safety guardrails."""
    pass

# Stub list of forbidden terms for Phase 2.
# In Phase 3, this will be replaced by an LLM-as-a-Judge or safety classifier.
FORBIDDEN_TERMS = [
    "[UNSAFE]",
    "IGNORE ALL PREVIOUS INSTRUCTIONS",
    "DROP TABLE"
]

def check_safety(prompt: str, output: str) -> None:
    """
    Synchronously inspects AI output before it is passed back to the agent.
    
    Args:
        prompt: The original prompt sent to the AI.
        output: The raw text returned by the AI.
        
    Raises:
        SecurityViolation: If the output contains forbidden terms.
    """
    if not output:
        return
        
    upper_output = output.upper()
    for term in FORBIDDEN_TERMS:
        if term in upper_output:
            logger.critical(
                "Guardrails triggered: Unsafe output detected",
                extra={
                    "forbidden_term": term,
                    "prompt_snippet": prompt[:100] + "..." if prompt else "",
                    "catch_reason": "Fail-fast on safety violation, halting pipeline immediately"
                }
            )
            raise SecurityViolation(f"AI output flagged as unsafe. Reason: Matched forbidden term '{term}'")
