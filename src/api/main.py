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

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AI Employee Platform API"}

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
        
        # Pending approvals
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s AND approval_status = 'PENDING_APPROVAL'", (tenant_id,))
        pending_approvals = cursor.fetchone()[0]
        
        # Approved / Sent
        cursor.execute("SELECT COUNT(*) FROM decision_cards WHERE tenant_id = %s AND approval_status = 'APPROVED'", (tenant_id,))
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
    Lists decision cards for the dashboard.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute(
                """
                SELECT decision_id, agent_name, action, result, confidence, reason, sources, model, cost_usd, approval_status, timestamp
                FROM decision_cards
                WHERE tenant_id = %s AND approval_status = %s
                ORDER BY decision_id DESC LIMIT %s
                """,
                (tenant_id, status, limit)
            )
        else:
            cursor.execute(
                """
                SELECT decision_id, agent_name, action, result, confidence, reason, sources, model, cost_usd, approval_status, timestamp
                FROM decision_cards
                WHERE tenant_id = %s
                ORDER BY decision_id DESC LIMIT %s
                """,
                (tenant_id, limit)
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
                "created_at": str(r[10]) if r[10] else None
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/decisions/{decision_id}/approve")
def approve_decision(decision_id: int, body: Optional[DecisionActionRequest] = None):
    """
    Approves a decision card and resumes pipeline execution.
    """
    try:
        new_result = body.edited_result if body else None
        status = "EDITED" if new_result else "APPROVED"
        resolve_approval(decision_id, status, new_result=new_result)
        return {"status": "success", "decision_id": decision_id, "approval_status": status}
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
