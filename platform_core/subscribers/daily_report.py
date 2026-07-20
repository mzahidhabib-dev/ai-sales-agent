import sys
import os
# Add the project root to sys.path so we can run this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from platform_core.sdk import sdk
from platform_core.logging_config import get_logger
from platform_core.db import get_connection

logger = get_logger(__name__)

def generate_daily_report(tenant_id: str):
    logger.info("Generating Daily Executive Report", extra={"tenant_id": tenant_id})
    
    # 1. Get Cost Metrics
    cost_metrics = sdk.cost.get_dashboard_metrics(tenant_id)
    
    # 2. Get Pipeline Metrics from Database
    conn = None
    prospects_found = 0
    meetings_booked = 0
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM events WHERE tenant_id = %s AND event_type = 'prospect.found'", (tenant_id,))
        prospects_found = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM events WHERE tenant_id = %s AND event_type = 'meeting.booked'", (tenant_id,))
        meetings_booked = cursor.fetchone()[0]
        
    except Exception as e:
        logger.error("Failed to fetch pipeline metrics", extra={"exc_type": type(e).__name__, "error": str(e)})
    finally:
        if conn:
            conn.close()

    # 3. Format the email
    report_body = (
        f"Daily Executive Report for {tenant_id}\n\n"
        f"Pipeline Activity:\n"
        f"- Prospects Found: {prospects_found}\n"
        f"- Meetings Booked: {meetings_booked}\n\n"
        f"Cost Analysis:\n"
        f"- Total Spend: ${cost_metrics.get('total_spend', 0):.4f}\n"
        f"- Cost per Lead: ${cost_metrics.get('cost_per_lead', 0):.4f}\n"
        f"- Cost per Meeting: ${cost_metrics.get('cost_per_meeting', 0):.4f}\n"
    )
    
    # 4. Send the email (using the Tool Gateway stub/MCP so we don't actually spam)
    logger.info("Dispatching daily report via Tool Gateway")
    sdk.tools.call("send_email", tenant_id=tenant_id, to_email="exec@company.com", subject="Daily AI Pipeline Report", body=report_body)
    
    return report_body

if __name__ == "__main__":
    tenant_id = "tenant-1"
    report = generate_daily_report(tenant_id)
    print("\n--- GENERATED REPORT ---")
    print(report)
