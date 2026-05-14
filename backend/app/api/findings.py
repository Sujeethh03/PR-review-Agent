from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.db.findings_repo import (
    get_findings_by_status,
    get_finding_by_id,
    get_review_by_id,
    resolve_finding,
    get_review_summaries,
    get_finding_counts,
)
from app.db.models import FindingRow, PRReview, FindingStatus
from app.models.findings import Finding
from app.agents.pr_writer import run_pr_writer

router = APIRouter()


class ResolveRequest(BaseModel):
    resolved_by: str = "dashboard"


def _serialize(row: FindingRow, review: PRReview | None = None) -> dict:
    d = {
        "id":              row.id,
        "finding_hash":    row.finding_hash,
        "pr_review_id":    row.pr_review_id,
        "agent":           row.agent,
        "file":            row.file,
        "line_start":      row.line_start,
        "line_end":        row.line_end,
        "severity":        row.severity,
        "category":        row.category,
        "title":           row.title,
        "description":     row.description,
        "suggestion":      row.suggestion,
        "specialist_conf": row.specialist_conf,
        "route":           row.route,
        "status":          row.status.value,
        "created_at":      row.created_at.isoformat(),
        "resolved_at":     row.resolved_at.isoformat() if row.resolved_at else None,
        "resolved_by":     row.resolved_by,
    }
    if review:
        d["owner"]      = review.owner
        d["repo_name"]  = review.repo_name
        d["pr_number"]  = review.pr_number
        d["head_sha"]   = review.head_sha
    return d


def _row_to_finding(row: FindingRow) -> Finding:
    return Finding(
        file=row.file,
        line_start=row.line_start,
        line_end=row.line_end,
        severity=row.severity,
        category=row.category,
        title=row.title,
        description=row.description,
        suggestion=row.suggestion,
        confidence=row.specialist_conf,
        agent=row.agent,
    )


@router.get("/findings")
async def list_findings(status: str | None = Query(default=None)) -> list[dict]:
    pairs = await get_findings_by_status(status)
    return [_serialize(row, review) for row, review in pairs]


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: int) -> dict:
    row = await get_finding_by_id(finding_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    review = await get_review_by_id(row.pr_review_id)
    return _serialize(row, review)


@router.get("/stats")
async def stats() -> dict:
    return await get_finding_counts()


@router.get("/reviews")
async def list_reviews() -> list[dict]:
    return await get_review_summaries()


@router.patch("/findings/{finding_id}/approve")
async def approve_finding(finding_id: int, body: ResolveRequest) -> dict:
    row = await resolve_finding(finding_id, FindingStatus.approved, body.resolved_by)
    if row is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    review = await get_review_by_id(row.pr_review_id)
    if review is not None and review.installation_id:
        try:
            await run_pr_writer(
                findings=[_row_to_finding(row)],
                installation_id=review.installation_id,
                owner=review.owner,
                repo_name=review.repo_name,
                pr_number=review.pr_number,
                head_sha=review.head_sha,
            )
        except Exception as e:
            print(f"Warning: failed to post approved finding to GitHub: {e}")

    return _serialize(row, review)


@router.patch("/findings/{finding_id}/dismiss")
async def dismiss_finding(finding_id: int, body: ResolveRequest) -> dict:
    row = await resolve_finding(finding_id, FindingStatus.dismissed, body.resolved_by)
    if row is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    review = await get_review_by_id(row.pr_review_id)
    return _serialize(row, review)
