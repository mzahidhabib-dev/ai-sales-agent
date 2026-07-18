from platform_core.logging_config import get_logger
from platform_core.db import get_connection

logger = get_logger(__name__)

# --- STUBBED TOOLS FOR PHASE 1 ---

def find_prospect(tenant_id: str, icp_config: dict) -> list:
    """Stub: Returns a fake list of prospects based on ICP."""
    logger.info("Finding prospects", extra={"tenant_id": tenant_id, "icp_industry": icp_config.get("industry")})
    return [{"company_name": "TechCorp", "domain": "techcorp.com", "prospect_id": 1}]

def find_decision_maker(tenant_id: str, prospect_id: int) -> dict:
    """Stub: Returns a fake decision maker."""
    logger.info("Finding decision maker", extra={"tenant_id": tenant_id, "prospect_id": prospect_id})
    return {"first_name": "Alice", "last_name": "Smith", "title": "CTO", "email": "alice@techcorp.com", "decision_maker_id": 1}

def research_company(tenant_id: str, domain: str) -> str:
    """Stub: Returns fake research data."""
    logger.info("Researching company", extra={"tenant_id": tenant_id, "domain": domain})
    return f"{domain} is a growing B2B SaaS company that recently raised Series A."

def send_email(tenant_id: str, to_email: str, subject: str, body: str) -> bool:
    """Stub: Fakes sending an email."""
    # Rule 15: log to_email and subject only — never log email body (PII / content)
    logger.info("Sending email (stub)", extra={"tenant_id": tenant_id, "to_email": to_email, "subject": subject})
    return True

def check_calendar_availability(tenant_id: str) -> list:
    """Stub: Returns fake calendar slots."""
    logger.info("Checking calendar availability", extra={"tenant_id": tenant_id})
    return ["2026-07-20T10:00:00Z", "2026-07-21T14:00:00Z"]

# --- IMPLEMENTED TOOLS ---

def update_crm(tenant_id: str, prospect_id: int, stage_id: str, value: float = 0.0) -> int:
    """
    Writes directly to Postgres `opportunities` / `pipeline_stage` tables.
    Returns the opportunity_id.
    """
    logger.info("Updating CRM", extra={"tenant_id": tenant_id, "prospect_id": prospect_id, "stage_id": stage_id})
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if opportunity exists
        cursor.execute(
            "SELECT opportunity_id FROM opportunities WHERE tenant_id = %s AND prospect_id = %s",
            (tenant_id, prospect_id)
        )
        row = cursor.fetchone()
        
        if row:
            opp_id = row[0]
            cursor.execute(
                "UPDATE opportunities SET stage_id = %s, value = %s, updated_at = CURRENT_TIMESTAMP WHERE opportunity_id = %s",
                (stage_id, value, opp_id)
            )
        else:
            cursor.execute(
                "INSERT INTO opportunities (tenant_id, prospect_id, stage_id, value) VALUES (%s, %s, %s, %s) RETURNING opportunity_id",
                (tenant_id, prospect_id, stage_id, value)
            )
            opp_id = cursor.fetchone()[0]
            
        conn.commit()
        return opp_id
    except Exception as e:
        logger.error(
            "Failed to update CRM",
            extra={
                "tenant_id": tenant_id,
                "prospect_id": prospect_id,
                "stage_id": stage_id,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching pg8000 DB exception; rolling back and re-raising to caller"
            }
        )
        conn.rollback()
        raise e
    finally:
        conn.close()

def record_handoff(tenant_id: str, prospect_id: int, opportunity_id: int, summary: str) -> int:
    """Writes a handoff record to the Postgres `handoffs` table."""
    logger.info("Recording human handoff", extra={"tenant_id": tenant_id, "prospect_id": prospect_id})
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO handoffs (tenant_id, prospect_id, opportunity_id, summary) VALUES (%s, %s, %s, %s) RETURNING handoff_id",
            (tenant_id, prospect_id, opportunity_id, summary)
        )
        handoff_id = cursor.fetchone()[0]
        conn.commit()
        return handoff_id
    except Exception as e:
        logger.error(
            "Failed to record handoff",
            extra={
                "tenant_id": tenant_id,
                "prospect_id": prospect_id,
                "exc_type": type(e).__name__,
                "error": str(e),
                "catch_reason": "Catching pg8000 DB exception; rolling back and re-raising to caller"
            }
        )
        conn.rollback()
        raise e
    finally:
        conn.close()

def call(tool_name: str, **kwargs):
    """Dynamically dispatches to the tool by name."""
    tools = {
        "find_prospect": find_prospect,
        "find_decision_maker": find_decision_maker,
        "research_company": research_company,
        "send_email": send_email,
        "check_calendar_availability": check_calendar_availability,
        "update_crm": update_crm,
        "record_handoff": record_handoff
    }
    
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")
        
    return tools[tool_name](**kwargs)
