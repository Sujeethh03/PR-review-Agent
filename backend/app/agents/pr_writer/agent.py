import httpx
from app.models.findings import Finding
from app.github_client import get_installation_token, GITHUB_API
from .formatter import format_finding_comment, format_summary_comment


async def run_pr_writer(
    findings: list[Finding],
    installation_id: int,
    owner: str,
    repo_name: str,
    pr_number: int,
    head_sha: str,
) -> None:
    if not findings:
        return

    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    inline_comments = [
        {"path": f.file, "line": f.line_start, "body": format_finding_comment(f)}
        for f in findings
    ]

    posted = await _post_review(
        headers, owner, repo_name, pr_number, head_sha, inline_comments
    )

    # If inline comments were rejected (lines not in diff), fall back to a PR body comment
    if not posted:
        await _post_body_comment(
            headers, owner, repo_name, pr_number, findings
        )


async def _post_review(
    headers: dict,
    owner: str,
    repo_name: str,
    pr_number: int,
    head_sha: str,
    inline_comments: list[dict],
) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
            headers=headers,
            json={
                "commit_id": head_sha,
                "event": "COMMENT",
                "comments": inline_comments,
            },
        )
        if response.status_code in (200, 201):
            return True

        # 422 means one or more lines aren't in the diff — retry without inline comments
        if response.status_code == 422:
            return False

        response.raise_for_status()
        return True


async def _post_body_comment(
    headers: dict,
    owner: str,
    repo_name: str,
    pr_number: int,
    findings: list[Finding],
) -> None:
    body = format_summary_comment(findings)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo_name}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": body},
        )
        response.raise_for_status()
