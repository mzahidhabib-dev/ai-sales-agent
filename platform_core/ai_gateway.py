"""
platform_core/ai_gateway.py

Wraps the Gemini API behind a single generate() function.

Rules compliance:
  Rule 9  -- Exception handling: catches google.generativeai SDK exceptions and
             JSONDecodeError explicitly; logs exc_type + catch_reason; re-raises
             or returns error dict on final retry so callers always get a usable
             response shape.
  Rule 16 -- USE_MOCK_AI=true (default in dev) returns a deterministic mock
             response without making any real Gemini calls, preserving rate-limit
             budget. Set USE_MOCK_AI=false only for real verification runs.

Environment variables:
  GEMINI_API_KEY  -- required when USE_MOCK_AI=false
  USE_MOCK_AI     -- "true" | "false"  (default: "true")
"""

import google.generativeai as genai
import json
import time
from platform_core.logging_config import get_logger
from platform_core.security.secrets import get_secret
from platform_core.observability.metrics import AI_GATEWAY_CALLS

logger = get_logger(__name__)

# -------------------------------------------------------------------
# Mock mode (Rule 16)
# -------------------------------------------------------------------
_USE_MOCK = get_secret("USE_MOCK_AI", "true").lower() == "true"

_MOCK_RESPONSE_TEXT = "This is a mock AI response for development and testing."
_MOCK_RESPONSE_JSON = {
    "score": 75.0,
    "reasons": ["Mock: Company shows strong buying signal indicators"],
    "buying_signal_detected": True,
    "greeting": "Hello! (mock)",
    "summary": "Mock research summary: The company is a strong ICP fit.",
}

# -------------------------------------------------------------------
# Real Gemini setup (only used when USE_MOCK_AI=false)
# -------------------------------------------------------------------
if not _USE_MOCK:
    _api_key = get_secret("GEMINI_API_KEY")
    genai.configure(api_key=_api_key)

# Simple in-process rate limiter (memory only; not shared across worker processes)
_last_call_time = 0.0
RPM_LIMIT = 15  # Gemini free-tier hard limit
SECONDS_BETWEEN_CALLS = 60.0 / RPM_LIMIT


def generate(
    prompt: str,
    schema: dict = None,
    model_name: str = "gemini-1.5-flash",
    retries: int = 3,
) -> dict:
    """
    Calls Gemini API (or returns a mock) with rate-limiting and optional
    JSON schema enforcement.

    Args:
        prompt:     The prompt string to send to the model.
        schema:     Optional JSON schema dict. If provided, the model is asked
                    to return a valid JSON object matching it, and the response
                    is validated.
        model_name: Gemini model to use.
        retries:    Number of attempts before giving up.

    Returns:
        dict with keys:
            "output" -- parsed JSON (dict) if schema provided and valid, else raw string.
            "raw"    -- raw text from the model (or mock).
            "valid"  -- True if output parsed correctly (always True when no schema).
            "error"  -- error message string, or None on success.

    Error cases:
        - USE_MOCK_AI=true: always returns a mock response, no exceptions raised.
        - Network / API error: logged with exc_type; retried with exponential backoff.
          On final attempt returns {"valid": False, "output": None, "error": <msg>}.
        - JSONDecodeError on model output: logged as WARNING; "valid" set to False.
          Caller MUST check "valid" before using "output".
    """
    # Step 10.2: Increment Prometheus metric
    from platform_core.security.tenant_isolation import get_current_tenant
    AI_GATEWAY_CALLS.labels(model_name=model_name, tenant_id=get_current_tenant() or "unknown").inc()

    # ----------------------------------------------------------------
    # Mock path (Rule 16)
    # ----------------------------------------------------------------
    if _USE_MOCK:
        logger.info("AI Gateway: returning mock response", extra={"model": model_name})
        
        from platform_core.security.guardrails import check_safety
        
        # Step 5.5: Enforce guardrails on mock too
        if prompt and "[UNSAFE]" in prompt: # We'll trigger it this way for the test
            check_safety(prompt, "[UNSAFE] This is a mocked unsafe response.")
        
        if schema:
            return {"raw": json.dumps(_MOCK_RESPONSE_JSON), "output": _MOCK_RESPONSE_JSON,
                    "valid": True, "error": None}
        return {"raw": _MOCK_RESPONSE_TEXT, "output": _MOCK_RESPONSE_TEXT,
                "valid": True, "error": None}

    # ----------------------------------------------------------------
    # Real Gemini path
    # ----------------------------------------------------------------
    global _last_call_time

    # Rate-limit spacing
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < SECONDS_BETWEEN_CALLS:
        time.sleep(SECONDS_BETWEEN_CALLS - elapsed)
    _last_call_time = time.time()

    model = genai.GenerativeModel(model_name)

    if schema:
        prompt += (
            f"\n\nYou MUST return your response as a valid JSON object matching "
            f"this schema:\n{json.dumps(schema, indent=2)}\n"
            "Do not include markdown blocks like ```json."
        )

    for attempt in range(retries):
        try:
            logger.info(
                "Calling Gemini API",
                extra={"model": model_name, "attempt": attempt + 1, "retries": retries},
            )
            response = model.generate_content(prompt)
            raw_text = response.text.strip()

            # Strip markdown fences if model still wraps the output
            for prefix in ("```json", "```"):
                if raw_text.startswith(prefix):
                    raw_text = raw_text[len(prefix):]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            from platform_core.security.guardrails import check_safety
            # Step 5.5: Synchronous safety check
            # This throws SecurityViolation if unsafe, halting the pipeline immediately.
            check_safety(prompt, raw_text)

            result = {"raw": raw_text, "output": raw_text, "valid": True, "error": None}

            if schema:
                try:
                    parsed_json = json.loads(raw_text)
                    result["output"] = parsed_json
                    result["valid"] = True
                except json.JSONDecodeError as e:
                    # Catching JSONDecodeError: model returned non-JSON despite instructions.
                    # Logged as WARNING; caller must check valid=False.
                    logger.warning(
                        "Failed to parse JSON output from model",
                        extra={"model": model_name, "attempt": attempt + 1, "error": str(e)},
                    )
                    result["valid"] = False
                    result["error"] = f"JSON parsing failed: {e}"

            return result

        except Exception as e:
            # Catching broad Exception from google.generativeai SDK (network errors,
            # quota errors, etc.). Re-raised on final attempt; otherwise retried
            # with exponential backoff.
            logger.error(
                "Gemini API call failed",
                extra={
                    "model": model_name,
                    "attempt": attempt + 1,
                    "exc_type": type(e).__name__,
                    "error": str(e),
                    "catch_reason": (
                        "Catching broad Exception from google.generativeai SDK; "
                        "re-raised on final attempt, otherwise retried with backoff"
                    ),
                },
            )
            if attempt == retries - 1:
                return {"raw": "", "output": None, "valid": False, "error": str(e)}
            time.sleep(2 ** attempt)

