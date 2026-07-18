import os
import time
import redis
import json
from platform_core.logging_config import configure_logging, get_logger
from business_agents.sales.graph import sales_pipeline

configure_logging()
logger = get_logger("worker")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

STREAM_NAME = "jobs:sales"
GROUP_NAME = "sales_worker_group"
CONSUMER_NAME = f"consumer_{os.getpid()}"

def process_job(job_id: str, job_data: dict):
    """Parses job data and executes LangGraph pipeline."""
    try:
        # Assuming the payload is stored under a key, often 'payload' or direct fields
        # If it's JSON encoded under a key, parse it:
        payload_str = job_data.get("payload")
        if payload_str:
            payload = json.loads(payload_str)
        else:
            payload = job_data

        tenant_id = payload.get("tenant_id", "tenant-1")
        logger.info("Executing sales pipeline", extra={"tenant_id": tenant_id, "job_id": job_id})
        
        # Initialize the LangGraph state
        initial_state = {
            "tenant_id": tenant_id,
            "prospects": [],
            "current_prospect_index": 0
        }
        
        config = {"configurable": {"thread_id": f"job_{job_id}"}}
        
        # Execute the pipeline
        for s in sales_pipeline.stream(initial_state, config):
            node = list(s.keys())[0]
            logger.info("Pipeline node executed", extra={"node": node, "job_id": job_id})
            
        logger.info("Pipeline execution finished", extra={"job_id": job_id})
        
    except Exception as e:

        logger.error(
            "Failed to process job",
            extra={
                "job_id": job_id,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching broad Exception from pipeline execution; re-raising so caller can decide not to ACK"
            }
        )
        # Step 4.3 / Rule 9: publish workflow.failed so the failure is visible in the events table
        try:
            tenant_id = job_data.get("tenant_id", "unknown")
            from platform_core import events as event_bus
            event_bus.publish(tenant_id, "workflow.failed", {
                "job_id": job_id,
                "error": str(e),
                "exc_type": type(e).__name__
            })
        except Exception as pub_err:
            logger.error(
                "Failed to publish workflow.failed event from worker",
                extra={"job_id": job_id, "pub_error": str(pub_err)}
            )
        raise e

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Ensure the stream and consumer group exist
    try:
        r.xgroup_create(STREAM_NAME, GROUP_NAME, mkstream=True)
        logger.info("Consumer group ready", extra={"stream": STREAM_NAME, "group": GROUP_NAME})
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP Consumer Group name already exists" in str(e):
            pass
        else:
            raise e

    logger.info("Worker started", extra={"consumer": CONSUMER_NAME, "stream": STREAM_NAME})

    while True:
        try:
            # Read from stream
            # Block for up to 5000ms
            messages = r.xreadgroup(GROUP_NAME, CONSUMER_NAME, {STREAM_NAME: ">"}, count=1, block=5000)

            if messages:
                for stream, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        logger.info("Job received", extra={"job_id": message_id})
                        
                        try:
                            process_job(message_id, message_data)
                            # Acknowledge the job if successful
                            r.xack(stream, GROUP_NAME, message_id)
                            logger.info("Job ACKed", extra={"job_id": message_id})
                        except Exception as e:
                            logger.error(
                                "Job processing failed, not acking",
                                extra={
                                    "job_id": message_id,
                                    "exc_type": type(e).__name__,
                                    "error": str(e)
                                }
                            )
            else:
                # No messages, looping
                pass
                
        except redis.ConnectionError as e:
            logger.error(
                "Lost connection to Redis",
                extra={"exc_type": type(e).__name__, "error": str(e), "catch_reason": "Redis connection drop; sleeping and retrying"}
            )
            time.sleep(2)
        except Exception as e:
            logger.error(
                "Unexpected error in message loop",
                extra={"exc_type": type(e).__name__, "error": str(e), "catch_reason": "Catching unexpected exceptions in polling loop to prevent worker death"}
            )
            time.sleep(1)

if __name__ == "__main__":
    main()
