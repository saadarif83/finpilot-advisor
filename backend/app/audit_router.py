from fastapi import APIRouter, Depends, HTTPException
from app.identity import current_employee
from app import audit
from app.proposals import store

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(employee: dict = Depends(current_employee)):
    return {"records": audit.list_records(employee)}


@router.get("/{rid}")
def get_audit(rid: str, employee: dict = Depends(current_employee)):
    rec = audit.get(rid)
    if not rec:
        raise HTTPException(404, "Not found")
    if employee["role"] not in ("compliance", "supervisor") and rec["employee"]["username"] != employee["username"]:
        raise HTTPException(403, "You can only view your own audit records")
    return rec | {"proposal_details": [store.get(p) for p in rec["proposals"] if store.get(p)]}
