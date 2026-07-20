import contextvars
import uuid

_current_trace_id = contextvars.ContextVar("current_trace_id", default=None)

def set_trace_id(trace_id: str = None) -> str:
    """
    Sets the trace_id for the current context. If none is provided, generates a new UUID.
    Returns the trace_id that was set.
    """
    if not trace_id:
        trace_id = str(uuid.uuid4())
    _current_trace_id.set(trace_id)
    return trace_id

def get_trace_id() -> str:
    """
    Returns the trace_id for the current context.
    Returns None if not set.
    """
    return _current_trace_id.get()
