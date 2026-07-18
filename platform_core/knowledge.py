"""
platform_core/knowledge.py

Loads tenant/default configuration from flat JSON files.

Rules compliance:
  Rule 9  -- JSONDecodeError is caught and re-raised as ValueError with clear
             context (file path, key) so the caller knows exactly which config
             is broken.
  Rule 12 -- Missing config is a WARNING (not a silent empty return) so callers
             can decide whether to abort.
"""

import os
import json
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge_data")

from platform_core.security.tenant_isolation import enforce_tenant

@enforce_tenant
def get(key: str, tenant_id: str) -> dict:
    """
    Loads a configuration value from flat JSON files.

    Lookup order:
        1. <KNOWLEDGE_DIR>/<key>_<tenant_id>.json  (tenant-specific)
        2. <KNOWLEDGE_DIR>/<key>_default.json      (global default)

    Args:
        key:       Config key name (e.g. "icp", "scoring_rubric").
        tenant_id: Tenant identifier.

    Returns:
        dict: Parsed JSON config, or {} if no file is found.

    Raises:
        ValueError: If the config file exists but contains invalid JSON.
            Callers must handle this -- a broken config must not allow
            the pipeline to continue silently with empty data.
    """
    tenant_file = os.path.join(KNOWLEDGE_DIR, f"{key}_{tenant_id}.json")
    default_file = os.path.join(KNOWLEDGE_DIR, f"{key}_default.json")

    file_to_load = tenant_file if os.path.exists(tenant_file) else default_file

    if not os.path.exists(file_to_load):
        logger.warning(
            "Knowledge config not found",
            extra={"tenant_id": tenant_id, "key": key,
                   "searched_paths": [tenant_file, default_file]}
        )
        return {}

    try:
        with open(file_to_load, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        # Raise with full context so the caller can log tenant/agent details
        raise ValueError(
            f"Knowledge config file contains invalid JSON. "
            f"key={key!r}, tenant_id={tenant_id!r}, file={file_to_load!r}. "
            f"JSON error: {e}"
        ) from e


from platform_core.security.rbac import require_role

@require_role("admin")
def update(key: str, tenant_id: str, new_config: dict) -> None:
    """
    Updates the configuration for a given tenant.
    
    This is currently a stub for the Step 5.2 negative test to prove
    that a 'viewer' role is blocked from calling this function.
    
    Args:
        key:       Config key name.
        tenant_id: Tenant identifier.
        new_config: The new dictionary to save.
    """
    logger.info(
        "Knowledge config updated",
        extra={"tenant_id": tenant_id, "key": key}
    )
    # The actual file writing logic is not built yet, as this is just
    # a stub to demonstrate RBAC enforcement on the service layer.

