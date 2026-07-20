"""
platform_core/sdk.py

Platform SDK — the ONLY module that Business Agent Layer nodes may import.

Rules compliance:
  Rule 1  -- This file defines the interface contract so any developer can read
             what is available without opening the gateway implementations.
  Rule 17 -- Business Agent Layer MUST import only from this module, never
             from platform_core.db, platform_core.ai_gateway, redis, pg8000, etc.

Interface contract (methods available to agents):
  sdk.ai.generate(prompt: str, schema: dict = None, model_name: str = "gemini-1.5-flash", retries: int = 3) -> dict
      Returns: {"output": ..., "raw": str, "valid": bool, "error": str | None}
      Callers MUST check result["valid"] before using result["output"].

  sdk.knowledge.get(key: str, tenant_id: str) -> dict
      Returns config dict, or {} if key not found.
      Raises ValueError if the config file has invalid JSON.

  sdk.tools.call(tool_name: str, **kwargs) -> Any
      Dispatches to a named capability function.
      Valid tool_name values: find_prospect, find_decision_maker, research_company,
      send_email, check_calendar_availability, update_crm, record_handoff.
      Raises ValueError for unknown tool names.
      Raises exceptions from the underlying tool on failure — callers must handle.

  sdk.decisions.record_decision(tenant_id, agent_name, action, ...) -> int
      Inserts a Decision Card row and corresponding Audit row.
      Returns the decision_id.
      Raises on DB failure — callers must handle.

  sdk.events.publish(tenant_id: str, event_type: str, payload: dict) -> None
      Publishes to Redis Pub/Sub and writes to the events DB table.
      Logs errors on failure but does not raise, to avoid killing the pipeline
      on a non-critical event log failure.
"""

from platform_core import ai_gateway
from platform_core import knowledge
from platform_core import tool_gateway
from platform_core import decision_cards
from platform_core import events
from platform_core import security
from platform_core.api_stub import api
from platform_core import memory


class PlatformSDK:
    """
    The official SDK for Business Agents.
    Usage:
        from platform_core.sdk import sdk
        sdk.tools.call("find_prospect", tenant_id="tenant_1")
    """

    def __init__(self):
        self.ai = ai_gateway
        self.knowledge = knowledge
        self.tools = tool_gateway
        self.memory = memory
        
        # We manually attach the new approval methods to the decisions namespace
        # so agents can call sdk.decisions.request_approval(id)
        self.decisions = decision_cards
        from platform_core import confidence
        self.confidence = confidence
        
        from platform_core import audit
        self.audit = audit
        
        from platform_core import replay
        self.replay = replay
        
        from platform_core import evaluation
        self.evaluation = evaluation
        
        from platform_core import observability
        self.observability = observability
        
        self.events = events
        self.security = security
        self.api = api
        
    def get_logger(self, name: str):
        """
        Returns the configured platform logger.
        Business agents must use this instead of importing logging modules directly.
        """
        from platform_core.logging_config import get_logger
        return get_logger(name)


# Singleton instance for agents to import
sdk = PlatformSDK()
