import json
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from platform_core.db import get_connection
from platform_core.decision_cards import resolve_approval, get_decision

app = FastAPI(title="AI Employee Platform API", version="1.0.0")

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DecisionActionRequest(BaseModel):
    edited_result: Optional[str] = None

class ProspectCreateRequest(BaseModel):
    domain: str  # REQUIRED
    company_name: Optional[str] = None
    contact_name: Optional[str] = "Decision Maker"
    contact_role: Optional[str] = "Executive"
    contact_email: Optional[str] = None
    tenant_id: str = "tenant-1"

class LeadIngestRequest(BaseModel):
    tenant_id: str = "tenant-1"
    domain: str
    decision_maker_name: Optional[str] = "Decision Maker"
    decision_maker_role: Optional[str] = "Executive"
    decision_maker_email: Optional[str] = "prospect@example.com"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AI Employee Platform API"}

@app.delete("/api/dev/reset")
def dev_reset(tenant_id: str = "tenant-1"):
    """
    DEV ONLY: Wipes all decision cards, audit logs, prospects and companies for a clean test.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM audit_logs WHERE tenant_id = %s", (tenant_id,))
        cursor.execute("DELETE FROM decision_cards WHERE tenant_id = %s", (tenant_id,))
        cursor.execute("DELETE FROM decision_makers WHERE tenant_id = %s", (tenant_id,))
        cursor.execute("DELETE FROM opportunities WHERE tenant_id = %s", (tenant_id,))
        cursor.execute("DELETE FROM prospects WHERE tenant_id = %s", (tenant_id,))
        cursor.execute("DELETE FROM companies WHERE tenant_id = %s", (tenant_id,))
        conn.commit()
        return {"status": "reset complete", "tenant_id": tenant_id}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()


def _run_pipeline_in_background(tenant_id: str, domain: str, name: str, role: str, email: str, prospect_id: int):
    import time
    import traceback
    from platform_core.security.tenant_isolation import set_current_tenant
    from platform_core.db import get_connection
    from business_agents.sales.nodes import ResearchAgent, ScoringAgent, DraftOutreachAgent, SendOutreachAgent
    
    set_current_tenant(tenant_id)
    state = {
        "tenant_id": tenant_id,
        "prospect_id": prospect_id,
        "prospects": [{"prospect_id": prospect_id, "domain": domain}],
        "current_prospect_index": 0,
        "decision_maker": {"name": name, "role": role, "email": email}
    }
    
    conn = None
    try:
        # Step 1: Research
        state.update(ResearchAgent(state))
        time.sleep(15) # Sleep delay for free tier API rate limits
        
        # Step 2: Score
        state.update(ScoringAgent(state))
        time.sleep(15)
        
        score = state.get("score", 0)
        
        # Step 3: Draft Outreach if Score >= 80
        if score >= 80:
            state.update(DraftOutreachAgent(state))
            final_status = 'DRAFTED'
        else:
            final_status = 'SKIPPED_LOW_SCORE'
            
        # Update DB status
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE prospects SET status = %s WHERE prospect_id = %s", (final_status, prospect_id))
        conn.commit()

    except Exception as e:
        print("\n--- BACKGROUND PIPELINE FAILED ---")
        traceback.print_exc()
        print("----------------------------------\n")
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE prospects SET status = 'FAILED' WHERE prospect_id = %s", (prospect_id,))
            conn.commit()
        except:
            pass
    finally:
        if conn:
            conn.close()

from fastapi import BackgroundTasks

@app.post("/api/leads/ingest")
def ingest_lead(lead: LeadIngestRequest, background_tasks: BackgroundTasks):
    """
    Webhook endpoint for n8n to drop new leads for AI processing.
    """
    background_tasks.add_task(
        _run_pipeline_in_background,
        lead.tenant_id,
        lead.domain,
        lead.decision_maker_name,
        lead.decision_maker_role,
        lead.decision_maker_email
    )
    return {
        "status": "accepted",
        "message": f"Lead '{lead.domain}' queued for AI Research & Scoring.",
        "tenant_id": lead.tenant_id
    }

@app.post("/api/prospects")
def create_prospect(prospect: ProspectCreateRequest, background_tasks: BackgroundTasks):
    """
    Creates a new prospect in the database and triggers AI processing.
    Only `domain` is required.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ensure tenant exists in tenants table to avoid ForeignKeyViolationError
        cursor.execute(
            "INSERT INTO tenants (tenant_id, name) VALUES (%s, %s) ON CONFLICT (tenant_id) DO NOTHING",
            (prospect.tenant_id, prospect.tenant_id)
        )

        # Smart defaults for optional fields
        company_name = prospect.company_name or prospect.domain.split('.')[0].capitalize()
        contact_email = prospect.contact_email or f"contact@{prospect.domain}"
        
        # 1. Insert Company
        cursor.execute(
            "INSERT INTO companies (tenant_id, name, domain) VALUES (%s, %s, %s) RETURNING company_id",
            (prospect.tenant_id, company_name, prospect.domain)
        )
        company_id = cursor.fetchone()[0]
        
        # 2. Insert Prospect
        cursor.execute(
            "INSERT INTO prospects (tenant_id, company_id, status) VALUES (%s, %s, 'PROCESSING') RETURNING prospect_id",
            (prospect.tenant_id, company_id)
        )
        prospect_id = cursor.fetchone()[0]
        
        # 3. Insert Decision Maker
        parts = (prospect.contact_name or "Decision Maker").split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        
        cursor.execute(
            """
            INSERT INTO decision_makers (tenant_id, prospect_id, first_name, last_name, title, email)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (prospect.tenant_id, prospect_id, first_name, last_name, prospect.contact_role, contact_email)
        )
        
        conn.commit()
        
        # 4. Trigger AI Pipeline in background
        background_tasks.add_task(
            _run_pipeline_in_background,
            prospect.tenant_id,
            prospect.domain,
            prospect.contact_name,
            prospect.contact_role,
            contact_email,
            prospect_id
        )
        
        return {
            "status": "success",
            "prospect_id": prospect_id,
            "company_name": company_name,
            "domain": prospect.domain,
            "message": "Prospect created and AI pipeline queued."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create prospect: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/api/prospects")
def list_prospects(tenant_id: str = "tenant-1", limit: int = 50):
    """
    Lists all prospects from PostgreSQL.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.prospect_id, c.name as company_name, c.domain, dm.first_name, dm.last_name, dm.title, dm.email, p.status, p.created_at
            FROM prospects p
            LEFT JOIN companies c ON p.company_id = c.company_id
            LEFT JOIN decision_makers dm ON p.prospect_id = dm.prospect_id
            WHERE p.tenant_id = %s
            ORDER BY p.prospect_id DESC LIMIT %s
            """,
            (tenant_id, limit)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            results.append({
                "prospect_id": r[0],
                "company_name": r[1],
                "domain": r[2],
                "contact_name": f"{r[3] or ''} {r[4] or ''}".strip() or "Decision Maker",
                "title": r[5],
                "email": r[6],
                "status": r[7],
                "created_at": str(r[8]) if r[8] else None
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.get("/api/stats")
def get_stats(tenant_id: str = "tenant-1"):
    """
    Returns aggregated system metrics for the dashboard overview.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total decisions
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s", (tenant_id,))
        total_decisions = cursor.fetchone()[0]
        
        # Pending approvals (including EDITED_PENDING)
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s AND approval_status IN ('PENDING_APPROVAL', 'EDITED_PENDING')", (tenant_id,))
        pending_approvals = cursor.fetchone()[0]
        
        # Approved / Sent
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s AND approval_status IN ('APPROVED', 'EDITED')", (tenant_id,))
        approved_count = cursor.fetchone()[0]

        # Total Cost
        cursor.execute("SELECT COALESCE(SUM(cost_usd), 0.0) FROM decision_cards WHERE tenant_id = %s", (tenant_id,))
        total_cost = float(cursor.fetchone()[0])
        
        return {
            "total_decisions": total_decisions,
            "pending_approvals": pending_approvals,
            "approved_count": approved_count,
            "total_cost_usd": round(total_cost, 4),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.get("/api/decisions")
def list_decisions(
    tenant_id: str = "tenant-1",
    status: Optional[str] = Query(None, description="Filter by approval_status"),
    limit: int = 50
):
    """
    Lists decision cards for the dashboard joined to their specific prospect and company.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT d.decision_id, d.agent_name, d.action, d.result, d.confidence, d.reason, d.sources, d.model, d.cost_usd, d.approval_status, d.timestamp,
                   dm.first_name, dm.last_name, dm.title, dm.email, c.domain, c.name as company_name
            FROM decision_cards d
            LEFT JOIN prospects p ON d.prospect_id = p.prospect_id
            LEFT JOIN companies c ON p.company_id = c.company_id
            LEFT JOIN LATERAL (
                SELECT dm.first_name, dm.last_name, dm.title, dm.email
                FROM decision_makers dm
                WHERE dm.prospect_id = p.prospect_id
                ORDER BY dm.decision_maker_id DESC LIMIT 1
            ) dm ON true
            WHERE d.tenant_id = %s AND (%s::text IS NULL OR d.approval_status = %s)
            ORDER BY d.decision_id DESC LIMIT %s
            """,
            (tenant_id, status, status, limit)
        )
            
        rows = cursor.fetchall()
        results = []
        for r in rows:
            results.append({
                "decision_id": r[0],
                "agent_name": r[1],
                "action": r[2],
                "result": r[3],
                "confidence": float(r[4]) if r[4] is not None else None,
                "reason": r[5] if isinstance(r[5], list) else (json.loads(r[5]) if r[5] else []),
                "sources": r[6] if isinstance(r[6], list) else (json.loads(r[6]) if r[6] else []),
                "model": r[7],
                "cost_usd": float(r[8]) if r[8] is not None else 0.0,
                "approval_status": r[9],
                "created_at": str(r[10]) if r[10] else None,
                "contact_name": f"{r[11] or ''} {r[12] or ''}".strip() or "Prospect",
                "contact_email": r[14] or "contact@domain.com",
                "domain": r[15] or "company.com",
                "company_name": r[16] or "Company"
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/decisions/{decision_id}/edit")
def edit_decision(decision_id: int, body: DecisionActionRequest):
    """
    Saves edits to a decision card without changing its approval status to APPROVED or dispatching.
    Keeps it in PENDING_APPROVAL status.
    """
    try:
        if body.edited_result:
            # We use a custom status or keep it PENDING_APPROVAL. 
            # We will use "EDITED_PENDING" so the UI knows it was edited but still waiting.
            resolve_approval(decision_id, "EDITED_PENDING", new_result=body.edited_result)
        return {"status": "success", "decision_id": decision_id, "approval_status": "EDITED_PENDING"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decisions/{decision_id}/approve")
def approve_decision(decision_id: int, body: Optional[DecisionActionRequest] = None):
    """
    Approves a decision card, saves any final edits, and triggers email dispatch via n8n.
    """
    try:
        new_result = body.edited_result if body else None
        status = "EDITED" if new_result else "APPROVED"
        resolve_approval(decision_id, status, new_result=new_result)
        
        # Fetch decision card details to send the email
        card = get_decision(decision_id)
        target_email = "prospect@example.com"
        
        if card:
            tenant_id = card.get("tenant_id", "tenant-1")
            prospect_id = card.get("prospect_id")
            
            # Retrieve recipient email from decision_makers in PostgreSQL for THIS specific prospect
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                if prospect_id:
                    cursor.execute(
                        """
                        SELECT dm.email 
                        FROM decision_makers dm
                        WHERE dm.prospect_id = %s
                        ORDER BY dm.decision_maker_id DESC LIMIT 1
                        """,
                        (prospect_id,)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT dm.email 
                        FROM decision_makers dm
                        ORDER BY dm.decision_maker_id DESC LIMIT 1
                        """
                    )
                row = cursor.fetchone()
                if row and row[0]:
                    target_email = row[0]
            except Exception as e:
                print(f"Warning: Failed to fetch recipient email: {e}")
            finally:
                if conn:
                    conn.close()

            from platform_core.sdk import sdk
            email_body = new_result if new_result else card.get("result", "")
            
            # Extract subject if present
            subject_line = "Partnership Opportunity - Custom AI Agents & Automation"
            lines = email_body.split("\n", 1)
            if lines and lines[0].startswith("Subject: "):
                subject_line = lines[0].replace("Subject: ", "").strip()
                email_body = lines[1].strip() if len(lines) > 1 else ""
                
            # Dispatch via n8n
            sdk.tools.call(
                "send_email",
                tenant_id=tenant_id,
                to_email=target_email,
                subject=subject_line,
                body=email_body
            )
            
        return {
            "status": "success", 
            "decision_id": decision_id, 
            "approval_status": status, 
            "email_dispatched": True,
            "recipient_email": target_email
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decisions/{decision_id}/reject")
def reject_decision(decision_id: int):
    """
    Rejects a decision card.
    """
    try:
        resolve_approval(decision_id, "REJECTED")
        return {"status": "success", "decision_id": decision_id, "approval_status": "REJECTED"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audit")
def get_audit_trail(tenant_id: str = "tenant-1", limit: int = 50):
    """
    Returns full audit logs (prompt, raw output, validation) for transparency.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT audit_id, decision_id, agent_name, prompt, raw_output, validation_result, timestamp
            FROM audit_logs
            WHERE tenant_id = %s
            ORDER BY audit_id DESC LIMIT %s
            """,
            (tenant_id, limit)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            results.append({
                "log_id": r[0],
                "decision_id": r[1],
                "agent_name": r[2],
                "prompt": r[3],
                "raw_output": r[4],
                "validation_result": r[5] if isinstance(r[5], dict) else (json.loads(r[5]) if r[5] else {}),
                "created_at": str(r[6]) if r[6] else None
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
