import redis
import json
import sys

# test_producer.py uses configure_logging() so its output is consistent with the rest of the stack (Rule 10)
sys.path.insert(0, '.')
from platform_core.logging_config import configure_logging, get_logger
configure_logging()
logger = get_logger('test_producer')

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Using jobs:sales as defined in Phase 4
STREAM_NAME = "jobs:sales"

# Push a dummy job with tenant_id for the worker to pick up
job_payload = {
    "tenant_id": "tenant-1",
    "trigger_type": "manual_test"
}

# The XADD command expects a dictionary of fields, so we wrap the JSON
msg_id = r.xadd(STREAM_NAME, {"payload": json.dumps(job_payload)})
logger.info("Job pushed to stream", extra={"job_id": msg_id, "stream": STREAM_NAME, "tenant_id": "tenant-1"})

