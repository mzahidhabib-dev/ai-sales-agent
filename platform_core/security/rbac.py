import contextvars
from functools import wraps
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

# Context variable to hold the current user's role.
# When the Dashboard/API layer is built, a middleware will set this per-request.
# Default is 'viewer' (least privilege) if not explicitly set.
_current_role = contextvars.ContextVar("current_role", default="viewer")

# Role hierarchy: lower index = higher privilege
ROLE_HIERARCHY = {
    "owner": 0,
    "admin": 1,
    "viewer": 2,
}

def set_current_role(role: str):
    """Sets the role for the current context (e.g., current API request)."""
    if role not in ROLE_HIERARCHY:
        raise ValueError(f"Invalid role: {role}. Must be one of {list(ROLE_HIERARCHY.keys())}")
    return _current_role.set(role)

def get_current_role() -> str:
    """Gets the role for the current context."""
    return _current_role.get()

def require_role(minimum_role: str):
    """
    Decorator to enforce RBAC on a function.
    
    Args:
        minimum_role: The minimum role required to execute this function.
                      e.g., 'admin' allows 'admin' and 'owner', but rejects 'viewer'.
    """
    if minimum_role not in ROLE_HIERARCHY:
        raise ValueError(f"Invalid minimum_role: {minimum_role}")
        
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_role = get_current_role()
            
            # Check hierarchy: lower number means higher privilege
            if ROLE_HIERARCHY[current_role] > ROLE_HIERARCHY[minimum_role]:
                logger.error(
                    "RBAC Authorization failed",
                    extra={
                        "function": func.__name__,
                        "current_role": current_role,
                        "required_role": minimum_role,
                        "catch_reason": "Fail-fast on unauthorized access attempt"
                    }
                )
                raise PermissionError(
                    f"Unauthorized: '{current_role}' role cannot perform this action. "
                    f"Minimum required role is '{minimum_role}'."
                )
                
            return func(*args, **kwargs)
        return wrapper
    return decorator
