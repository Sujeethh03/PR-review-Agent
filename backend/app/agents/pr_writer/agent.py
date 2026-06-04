import asyncio
import httpx

from app.models.findings import Finding
from app.github_client import get_installation_token, GITHUB_API
from .formatter import format_finding_comment, format_summary_comment
from .suggester import generate_suggestion


async def _delete_bot_comments(
    headers: dict,
    owner: str,
    repo_name: str,
    pr_number: int,
) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls/{pr_number}/comments",
            headers=headers,
            params={"per_page": 100},
        )
        if response.status_code != 200:
            return
        tasks = [
            client.delete(
                f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls/comments/{c['id']}",
                headers=headers,
            )
            for c in response.json()
            if c.get("user", {}).get("type") == "Bot"
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def run_pr_writer(
    findings: list[Finding],
    installation_id: int,
    owner: str,
    repo_name: str,
    pr_number: int,
    head_sha: str,
    diff: str = "",
) -> None:
    if not findings:
        return

    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    await _delete_bot_comments(headers, owner, repo_name, pr_number)

    # Generate suggestions concurrently — fall back to None on any error
    suggestions: list[str | None] = list(
        await asyncio.gather(
            *[generate_suggestion(f, diff) for f in findings],
            return_exceptions=True,
        )
    )
    suggestions = [s if isinstance(s, str) else None for s in suggestions]

    inline_comments = []
    for f, suggestion in zip(findings, suggestions):
        comment: dict = {
            "path": f.file,
            "line": f.line_end,
            "side": "RIGHT",
            "body": format_finding_comment(f, suggestion),
        }
        if f.line_start != f.line_end:
            comment["start_line"] = f.line_start
            comment["start_side"] = "RIGHT"
        inline_comments.append(comment)

    posted = await _post_review(headers, owner, repo_name, pr_number, head_sha, inline_comments)

    if not posted:
        await _post_body_comment(headers, owner, repo_name, pr_number, findings)


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
