from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.findings_repo import (
    get_pending_findings,
    get_finding_by_id,
    resolve_finding,
    get_review_summaries,
)
from app.db.models import FindingRow, FindingStatus

router = APIRouter()


class ResolveRequest(BaseModel):
    resolved_by: str = "dashboard"


def _serialize(row: FindingRow) -> dict:
    return {
        "id":               row.id,
        "finding_hash":     row.finding_hash,
        "pr_review_id":     row.pr_review_id,
        "agent":            row.agent,
        "file":             row.file,
        "line_start":       row.line_start,
        "line_end":         row.line_end,
        "severity":         row.severity,
        "category":         row.category,
        "title":            row.title,
        "description":      row.description,
        "suggestion":       row.suggestion,
        "specialist_conf":  row.specialist_conf,
        "critic_conf":      row.critic_conf,
        "critic_reasoning": row.critic_reasoning,
        "route":            row.route,
        "status":           row.status.value,
        "created_at":       row.created_at.isoformat(),
        "resolved_at":      row.resolved_at.isoformat() if row.resolved_at else None,
        "resolved_by":      row.resolved_by,
    }


@router.get("/findings")
async def list_findings() -> list[dict]:
    rows = await get_pending_findings()
    return [_serialize(r) for r in rows]


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: int) -> dict:
    row = await get_finding_by_id(finding_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return _serialize(row)


@router.get("/reviews")
async def list_reviews() -> list[dict]:
    return await get_review_summaries()


@router.patch("/findings/{finding_id}/approve")
async def approve_finding(finding_id: int, body: ResolveRequest) -> dict:
    row = await resolve_finding(finding_id, FindingStatus.approved, body.resolved_by)
    if row is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return _serialize(row)


@router.patch("/findings/{finding_id}/dismiss")
async def dismiss_finding(finding_id: int, body: ResolveRequest) -> dict:
    row = await resolve_finding(finding_id, FindingStatus.dismissed, body.resolved_by)
    if row is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return _serialize(row)
