"""
platform_core/events.py

Event bus: publishes events to Redis Pub/Sub and writes to the Postgres events table.

Rules compliance:
  Rule 9  -- Both r.publish() and the DB write are wrapped in try/except.
             Redis publish failures are logged with exc_type and re-raised so
             callers know the event was NOT delivered.
             DB write failures are logged but NOT re-raised (event already on Redis).
  Rule 10 -- All log lines use structured JSON via get_logger().
"""

import json
import redis
import os
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Pub/Sub Redis Client
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

VALID_EVENTS = {
    "prospect.found",
    "decision_maker.found",
    "research.completed",
    "score.completed",
    "buying_signal.detected",
    "outreach.generated",
    "email.sent",
    "followup.triggered",
    "meeting.booked",
    "crm.updated",
    "approval.requested",
    "approval.granted",
    "approval.rejected",
    "workflow.failed"
}

def publish(tenant_id: str, event_type: str, payload: dict) -> None:
    """
    Publish an event to Redis Pub/Sub and write to the Postgres events table.

    Args:
        tenant_id:  Tenant identifier.
        event_type: One of the VALID_EVENTS strings.
        payload:    Arbitrary dict to attach to the event.

    Raises:
        Exception: If the Redis publish fails. The DB write failure is NOT
                   re-raised — the event is already on Redis at that point.
    """
    if event_type not in VALID_EVENTS:
        logger.warning(
            "Unknown event type published",
            extra={"tenant_id": tenant_id, "event_type": event_type}
        )

    event_data = {
        "tenant_id": tenant_id,
        "event_type": event_type,
        "payload": payload
    }

    # 1. Publish to Redis Pub/Sub
    #    Rule 9: wrapped in try/except — a Redis failure is logged and re-raised
    #    so the calling node knows the event was NOT delivered.
    channel = f"events:{tenant_id}"
    try:
        r.publish(channel, json.dumps(event_data))
        logger.info(
            "Event published to Redis",
            extra={"tenant_id": tenant_id, "event_type": event_type, "channel": channel}
        )
    except Exception as e:
        logger.error(
            "Failed to publish event to Redis",
            extra={
                "tenant_id": tenant_id,
                "event_type": event_type,
                "channel": channel,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching Redis publish error; re-raising so caller knows event was not delivered"
            }
        )
        raise

    # 2. Write to events table (best-effort: logged but not re-raised)
    _write_event_to_db(tenant_id, event_type, payload)


def _write_event_to_db(tenant_id: str, event_type: str, payload: dict):
    # This will use the Postgres connection to write. 
    # For now, we will stub the actual DB call until we wire up SQLAlchemy/pg8000.
    from platform_core.db import get_connection
    import json
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (tenant_id, event_type, payload) VALUES (%s, %s, %s)",
            (tenant_id, event_type, json.dumps(payload))
        )
        conn.commit()
    except Exception as e:
        logger.error(
            "Failed to write event to DB",
            extra={
                "tenant_id": tenant_id,
                "event_type": event_type,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching pg8000 DB exception on event log; event already published to Redis, so we log and continue"
            }
        )
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
