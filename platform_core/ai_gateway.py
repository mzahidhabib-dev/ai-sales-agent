"""
platform_core/ai_gateway.py

Wraps multiple AI APIs behind a single generate() function.
Supports Gemini (primary), OpenAI, and Anthropic.
Implements Step 12.2 fallback logic.
"""

import json
import time
from platform_core.logging_config import get_logger
from platform_core.security.secrets import get_secret
from platform_core.observability.metrics import AI_GATEWAY_CALLS
from platform_core.security.guardrails import check_safety

logger = get_logger(__name__)

# Mock mode (Rule 16)
_USE_MOCK = get_secret("USE_MOCK_AI", "true").lower() == "true"
_MOCK_RESPONSE_TEXT = "This is a mock AI response for development and testing."
_MOCK_RESPONSE_JSON = {
    "score": 75.0,
    "reasons": ["Mock: Company shows strong buying signal indicators"],
    "buying_signal_detected": True,
    "greeting": "Hello! (mock)",
    "summary": "Mock research summary: The company is a strong ICP fit.",
}

# Simple in-process rate limiter for Gemini
_last_gemini_call_time = 0.0
GEMINI_RPM_LIMIT = 15
SECONDS_BETWEEN_GEMINI_CALLS = 60.0 / GEMINI_RPM_LIMIT


def _strip_markdown(text: str) -> str:
    for prefix in ("```json", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _generate_gemini(prompt: str, schema: dict, model_name: str, retries: int) -> dict:
    import google.generativeai as genai
    
    _api_key = get_secret("GEMINI_API_KEY")
    genai.configure(api_key=_api_key)
    
    global _last_gemini_call_time
    now = time.time()
    elapsed = now - _last_gemini_call_time
    if elapsed < SECONDS_BETWEEN_GEMINI_CALLS:
        time.sleep(SECONDS_BETWEEN_GEMINI_CALLS - elapsed)
    _last_gemini_call_time = time.time()

    model = genai.GenerativeModel(model_name)

    if schema:
        prompt += (
            f"\n\nYou MUST return your response as a valid JSON object matching "
            f"this schema:\n{json.dumps(schema, indent=2)}\n"
            "Do not include markdown blocks like ```json."
        )

    for attempt in range(retries):
        try:
            logger.info("Calling Gemini API", extra={"model": model_name, "attempt": attempt + 1})
            response = model.generate_content(prompt)
            raw_text = _strip_markdown(response.text.strip())

            check_safety(prompt, raw_text)

            result = {"raw": raw_text, "output": raw_text, "valid": True, "error": None, "cost_usd": 0.01}

            if schema:
                try:
                    result["output"] = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSON output from Gemini", extra={"error": str(e)})
                    result["valid"] = False
                    result["error"] = f"JSON parsing failed: {e}"

            return result

        except Exception as e:
            logger.error(
                "Gemini API call failed",
                extra={
                    "model": model_name, "attempt": attempt + 1, "exc_type": type(e).__name__, "error": str(e),
                    "catch_reason": "Catching broad Exception from google.generativeai SDK; re-raised on final attempt."
                },
            )
            if attempt == retries - 1:
                raise RuntimeError(f"Gemini failed: {e}")
            time.sleep(2 ** attempt)


def _generate_openai(prompt: str, schema: dict, model_name: str, retries: int) -> dict:
    import openai
    
    _api_key = get_secret("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=_api_key)
    
    # We map 'gemini-1.5-flash' equivalent to 'gpt-4o-mini' for OpenAI
    if "gemini" in model_name:
        model_name = "gpt-4o-mini"
        
    if schema:
        prompt += (
            f"\n\nYou MUST return your response as a valid JSON object matching "
            f"this schema:\n{json.dumps(schema, indent=2)}\n"
            "Do not include markdown blocks like ```json."
        )

    for attempt in range(retries):
        try:
            logger.info("Calling OpenAI API", extra={"model": model_name, "attempt": attempt + 1})
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_text = _strip_markdown(response.choices[0].message.content.strip())
            check_safety(prompt, raw_text)

            result = {"raw": raw_text, "output": raw_text, "valid": True, "error": None, "cost_usd": 0.02}

            if schema:
                try:
                    result["output"] = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSON output from OpenAI", extra={"error": str(e)})
                    result["valid"] = False
                    result["error"] = f"JSON parsing failed: {e}"

            return result

        except Exception as e:
            logger.error("OpenAI API call failed", extra={"model": model_name, "attempt": attempt + 1, "exc_type": type(e).__name__, "error": str(e)})
            if attempt == retries - 1:
                raise RuntimeError(f"OpenAI failed: {e}")
            time.sleep(2 ** attempt)

def _generate_anthropic(prompt: str, schema: dict, model_name: str, retries: int) -> dict:
    import anthropic
    
    _api_key = get_secret("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=_api_key)
    
    if "gemini" in model_name:
        model_name = "claude-3-haiku-20240307"
        
    if schema:
        prompt += (
            f"\n\nYou MUST return your response as a valid JSON object matching "
            f"this schema:\n{json.dumps(schema, indent=2)}\n"
            "Do not include markdown blocks like ```json."
        )

    for attempt in range(retries):
        try:
            logger.info("Calling Anthropic API", extra={"model": model_name, "attempt": attempt + 1})
            response = client.messages.create(
                model=model_name,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_text = _strip_markdown(response.content[0].text.strip())
            check_safety(prompt, raw_text)

            result = {"raw": raw_text, "output": raw_text, "valid": True, "error": None, "cost_usd": 0.015}

            if schema:
                try:
                    result["output"] = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSON output from Anthropic", extra={"error": str(e)})
                    result["valid"] = False
                    result["error"] = f"JSON parsing failed: {e}"

            return result

        except Exception as e:
            logger.error("Anthropic API call failed", extra={"model": model_name, "attempt": attempt + 1, "exc_type": type(e).__name__, "error": str(e)})
            if attempt == retries - 1:
                raise RuntimeError(f"Anthropic failed: {e}")
            time.sleep(2 ** attempt)

def generate(
    prompt: str,
    schema: dict = None,
    model_name: str = "gemini-3.5-flash",
    retries: int = 3,
    provider: str = "gemini",
    fallback_provider: str = "openai"
) -> dict:
    """
    Step 12.1 and 12.2: Multi-provider AI Gateway with Fallback.
    """
    from platform_core.security.tenant_isolation import get_current_tenant
    tenant_id = get_current_tenant() or "unknown"
    AI_GATEWAY_CALLS.labels(model_name=model_name, tenant_id=tenant_id).inc()

    if _USE_MOCK:
        logger.info("AI Gateway: returning mock response", extra={"model": model_name, "provider": provider})
        if prompt and "[UNSAFE]" in prompt:
            check_safety(prompt, "[UNSAFE] This is a mocked unsafe response.")
        
        if "FAIL_PRIMARY" in prompt and provider == "gemini":
            logger.warning("Mock: Simulating primary provider failure, falling back...")
            provider = fallback_provider
            
        if schema:
            if "email_draft" in schema.get("properties", {}):
                # Phase 14 mock support
                return {"raw": '{"objection_category": "too_expensive", "email_draft": "Our customers typically see a 3x return on investment within 6 months, which offsets the cost."}', "output": {"objection_category": "too_expensive", "email_draft": "Our customers typically see a 3x return on investment within 6 months, which offsets the cost."}, "valid": True, "error": None, "cost_usd": 0.005}
                
            return {"raw": json.dumps(_MOCK_RESPONSE_JSON), "output": _MOCK_RESPONSE_JSON,
                    "valid": True, "error": None, "cost_usd": 0.005}
        return {"raw": _MOCK_RESPONSE_TEXT, "output": _MOCK_RESPONSE_TEXT,
                "valid": True, "error": None, "cost_usd": 0.005}

    providers = {
        "gemini": _generate_gemini,
        "openai": _generate_openai,
        "anthropic": _generate_anthropic
    }

    primary_func = providers.get(provider)
    if not primary_func:
        return {"valid": False, "output": None, "error": f"Unknown provider: {provider}"}

    try:
        return primary_func(prompt, schema, model_name, retries)
    except Exception as primary_e:
        if not fallback_provider or fallback_provider not in providers:
            logger.error("Primary provider failed and no valid fallback provider is configured", extra={"error": str(primary_e)})
            return {"raw": "", "output": None, "valid": False, "error": str(primary_e)}
            
        logger.warning(
            "Primary provider failed, initiating FALLBACK to secondary provider",
            extra={"primary": provider, "fallback": fallback_provider, "error": str(primary_e)}
        )
        fallback_func = providers[fallback_provider]
        try:
            return fallback_func(prompt, schema, model_name, retries=1) # Don't retry fallback multiple times
        except Exception as fallback_e:
            logger.error("Fallback provider also failed!", extra={"error": str(fallback_e)})
            return {"raw": "", "output": None, "valid": False, "error": f"Primary error: {primary_e}. Fallback error: {fallback_e}"}
