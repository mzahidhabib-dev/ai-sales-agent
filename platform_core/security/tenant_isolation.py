import contextvars
import inspect
from functools import wraps
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

# Context variable to hold the current tenant's ID.
# When the Dashboard/API layer is built, a middleware will set this per-request.
# Default is None, meaning no tenant is authenticated.
_current_tenant_id = contextvars.ContextVar("current_tenant_id", default=None)

def set_current_tenant(tenant_id: str):
    """Sets the tenant_id for the current context (e.g., current API request)."""
    return _current_tenant_id.set(tenant_id)

def get_current_tenant() -> str:
    """Gets the tenant_id for the current context."""
    return _current_tenant_id.get()

def enforce_tenant(func):
    """
    Decorator to enforce tenant isolation on an SDK function.
    
    It intercepts the function call, inspects the arguments to find 'tenant_id',
    and compares it to the currently authenticated tenant_id in the context.
    If they do not match, it blocks the call.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        current_context_tenant = get_current_tenant()
        
        # If no tenant is set in context, it might be a system-level cron or unauthenticated request.
        # For strict isolation, we require a tenant context unless we explicitly allow global scope.
        if current_context_tenant is None:
            logger.error(
                "Tenant Isolation failed: No tenant context set",
                extra={
                    "function": func.__name__,
                    "catch_reason": "Fail-fast on unauthenticated SDK call"
                }
            )
            raise PermissionError("Unauthorized: No tenant context is active.")
            
        # Find the tenant_id passed to the function
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        requested_tenant = bound_args.arguments.get("tenant_id")
        
        if not requested_tenant:
            logger.error(
                "Tenant Isolation failed: Function missing tenant_id argument",
                extra={
                    "function": func.__name__,
                    "catch_reason": "SDK function decorated but lacks tenant_id parameter"
                }
            )
            raise ValueError(f"Function {func.__name__} does not have a tenant_id argument.")
            
        if current_context_tenant != requested_tenant:
            logger.error(
                "Tenant Isolation Authorization failed (CROSS-TENANT VIOLATION)",
                extra={
                    "function": func.__name__,
                    "authenticated_tenant": current_context_tenant,
                    "requested_tenant": requested_tenant,
                    "catch_reason": "Fail-fast on cross-tenant access attempt"
                }
            )
            raise PermissionError(
                f"Cross-Tenant Violation: Authenticated as '{current_context_tenant}' "
                f"but attempted to act on behalf of '{requested_tenant}'."
            )
            
        return func(*args, **kwargs)
    return wrapper
