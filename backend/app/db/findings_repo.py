from datetime import datetime
from sqlalchemy import select, func, Integer
from app.models.findings import Finding, finding_hash
from app.db.connection import get_session_factory
from app.db.models import PRReview, FindingRow, FindingStatus


async def save_review(
    owner: str,
    repo_name: str,
    pr_number: int,
    head_sha: str,
    installation_id: int,
    collection_name: str,
) -> int:
    async with get_session_factory()() as session:
        review = PRReview(
            owner=owner,
            repo_name=repo_name,
            pr_number=pr_number,
            head_sha=head_sha,
            installation_id=installation_id,
            collection_name=collection_name,
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)
        return review.id


async def save_findings(
    review_id: int,
    findings: list[Finding],
    routes: dict[str, str],
) -> None:
    async with get_session_factory()() as session:
        for f in findings:
            fhash = finding_hash(f)
            route = routes.get(fhash, "digest")
            status = (
                FindingStatus.auto_posted if route == "auto"
                else FindingStatus.digest if route == "digest"
                else FindingStatus.pending
            )

            row = FindingRow(
                finding_hash=fhash,
                pr_review_id=review_id,
                agent=f.agent,
                file=f.file,
                line_start=f.line_start,
                line_end=f.line_end,
                severity=f.severity,
                category=f.category,
                title=f.title,
                description=f.description,
                suggestion=f.suggestion,
                specialist_conf=f.confidence,
                route=route,
                status=status,
            )
            session.add(row)

        await session.commit()


async def get_findings_by_status(
    status: str | None = None,
) -> list[tuple[FindingRow, PRReview]]:
    _status_map = {
        "approved":    FindingStatus.approved,
        "dismissed":   FindingStatus.dismissed,
        "auto_posted": FindingStatus.auto_posted,
        "digest":      FindingStatus.digest,
    }
    async with get_session_factory()() as session:
        query = (
            select(FindingRow, PRReview)
            .join(PRReview, FindingRow.pr_review_id == PRReview.id)
            .order_by(FindingRow.specialist_conf.desc())
        )
        if status and status != "all":
            mapped = _status_map.get(status, FindingStatus.pending)
            query = query.where(FindingRow.status == mapped)
        elif status != "all":
            query = query.where(FindingRow.status == FindingStatus.pending)
        result = await session.execute(query)
        return list(result.all())


async def get_review_by_id(review_id: int) -> PRReview | None:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(PRReview).where(PRReview.id == review_id)
        )
        return result.scalar_one_or_none()


async def get_finding_by_id(finding_id: int) -> FindingRow | None:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(FindingRow).where(FindingRow.id == finding_id)
        )
        return result.scalar_one_or_none()


async def resolve_finding(
    finding_id: int,
    status: FindingStatus,
    resolved_by: str,
) -> FindingRow | None:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(FindingRow).where(FindingRow.id == finding_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = status
        row.resolved_at = datetime.utcnow()
        row.resolved_by = resolved_by
        await session.commit()
        await session.refresh(row)
        return row


async def get_review_summaries() -> list[dict]:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(
                PRReview.id,
                PRReview.owner,
                PRReview.repo_name,
                PRReview.pr_number,
                PRReview.head_sha,
                PRReview.created_at,
                func.count(FindingRow.id).label("total"),
                func.sum(
                    (FindingRow.status == FindingStatus.pending).cast(Integer)
                ).label("pending"),
                func.sum(
                    (FindingRow.status == FindingStatus.approved).cast(Integer)
                ).label("approved"),
                func.sum(
                    (FindingRow.status == FindingStatus.dismissed).cast(Integer)
                ).label("dismissed"),
            )
            .outerjoin(FindingRow, FindingRow.pr_review_id == PRReview.id)
            .group_by(PRReview.id)
            .order_by(PRReview.created_at.desc())
        )
        rows = result.all()
        return [
            {
                "id": r.id,
                "owner": r.owner,
                "repo_name": r.repo_name,
                "pr_number": r.pr_number,
                "head_sha": r.head_sha,
                "created_at": r.created_at.isoformat(),
                "total": r.total or 0,
                "pending": r.pending or 0,
                "approved": r.approved or 0,
                "dismissed": r.dismissed or 0,
            }
            for r in rows
        ]
