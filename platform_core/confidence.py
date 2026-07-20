from platform_core.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_THRESHOLD = 0.8

def evaluate_confidence(confidence_score: float, action: str, tenant_id: str) -> bool:
    """
    Evaluates whether an action's confidence score requires human approval.
    
    Args:
        confidence_score: Float between 0.0 and 1.0 representing AI confidence.
        action: The action string (e.g., "send_email", "update_crm").
        tenant_id: The tenant identifier, used to fetch custom thresholds.
        
    Returns:
        bool: True if approval is required, False otherwise.
    """
    if confidence_score is None:
        return False
        
    threshold = DEFAULT_THRESHOLD
    try:
        from platform_core.sdk import sdk
        # Step 7.1: Attempt to read from Knowledge Layer per tenant
        # Assuming knowledge config might return a dict of action thresholds
        config = sdk.knowledge.get(key="confidence_thresholds", tenant_id=tenant_id)
        if config and isinstance(config, dict):
            threshold = config.get(action, DEFAULT_THRESHOLD)
    except Exception as e:
        logger.error(
            "Failed to load confidence thresholds from Knowledge Layer",
            extra={
                "tenant_id": tenant_id,
                "action": action,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Fail-closed safety: forcing human approval because config could not be read"
            }
        )
        return True  # Fail-closed: require approval on error
        
    requires_approval = confidence_score < threshold
    
    if requires_approval:
        logger.info(
            "Confidence Engine flagged action for approval",
            extra={
                "tenant_id": tenant_id,
                "action": action,
                "confidence_score": confidence_score,
                "threshold": threshold
            }
        )
        
    return requires_approval
