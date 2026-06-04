import asyncio
import hmac
import hashlib
import json
import os
import shutil
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from app.github_client import get_pr_diff
from app.repo_manager import clone_repo
from app.agents.ingestion import run_ingestion
from app.agents.specialist import run_specialist_agents
from app.agents.pr_writer import run_pr_writer

load_dotenv(override=True)

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("GITHUB_WEBHOOK_SECRET is not set")

CONFIDENCE_THRESHOLD = 0.70


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    expected_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


async def _run_pipeline(
    owner: str,
    repo_name: str,
    pr_number: int,
    installation_id: int,
    head_sha: str,
) -> None:
    print(f"\n{'='*50}")
    print(f"Pipeline starting — PR #{pr_number} ({owner}/{repo_name} @ {head_sha[:7]})")
    repo_path = None
    try:
        diff = await get_pr_diff(installation_id, owner, repo_name, pr_number)
        print(f"Diff fetched: {len(diff)} characters")

        repo_path = await clone_repo(installation_id, owner, repo_name, head_sha)
        print(f"Repo cloned: {repo_path}")

        ingestion_result = await run_ingestion(
            diff=diff,
            repo_path=repo_path,
            owner=owner,
            repo_name=repo_name,
            head_sha=head_sha,
        )
        print(
            f"Ingestion: {ingestion_result.chunks_stored} chunks "
            f"({ingestion_result.mode}) → '{ingestion_result.collection_name}'"
        )

    finally:
        if repo_path:
            shutil.rmtree(repo_path, ignore_errors=True)
            print(f"Cleaned up {repo_path}")

    specialist_result = await run_specialist_agents(
        diff=diff,
        collection_name=ingestion_result.collection_name,
        owner=owner,
        repo_name=repo_name,
    )
    all_findings = specialist_result.all_findings()
    print(
        f"Findings: {len(all_findings)} total "
        f"({len(specialist_result.bug.findings)} bug, "
        f"{len(specialist_result.security.findings)} security, "
        f"{len(specialist_result.pattern.findings)} pattern)"
    )

    to_post = [f for f in all_findings if f.confidence >= CONFIDENCE_THRESHOLD]
    dropped = len(all_findings) - len(to_post)
    print(f"Posting {len(to_post)} finding(s), dropped {dropped} below {CONFIDENCE_THRESHOLD:.0%}")

    if to_post:
        await run_pr_writer(
            findings=to_post,
            installation_id=installation_id,
            owner=owner,
            repo_name=repo_name,
            pr_number=pr_number,
            head_sha=head_sha,
            diff=diff,
        )
        print(f"Posted to GitHub PR #{pr_number}")
        for f in to_post:
            print(f"  [{f.severity.upper()}] {f.file}:{f.line_start} — {f.title} (conf: {f.confidence:.2f})")

    print("=" * 50)


async def _safe_run_pipeline(*args, **kwargs) -> None:
    try:
        await _run_pipeline(*args, **kwargs)
    except Exception as e:
        print(f"Pipeline error: {e}")
        print("=" * 50)


@app.post("/webhook")
async def webhook(request: Request):
    payload_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_body, signature_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(payload_body)
    event_type = request.headers.get("X-GitHub-Event", "unknown")

    if event_type in (
        "security_advisory", "github_app_authorization",
        "check_suite", "check_run", "status",
        "pull_request_review", "pull_request_review_comment",
        "pull_request_review_thread",
    ):
        return {"status": "ok", "event": event_type}

    if event_type == "push":
        repo    = payload.get("repository", {}).get("full_name", "unknown")
        branch  = payload.get("ref", "").replace("refs/heads/", "")
        pusher  = payload.get("pusher", {}).get("name", "unknown")
        commits = payload.get("commits", [])
        print(f"\n{'='*50}")
        print(f"Push — {repo} / {branch} by {pusher} ({len(commits)} commit(s))")
        for commit in commits:
            print(f"  {commit.get('id', '')[:7]} {commit.get('message', '').splitlines()[0]}")
        print("=" * 50)

    elif event_type == "pull_request":
        action          = payload.get("action", "unknown")
        pr              = payload.get("pull_request", {})
        number          = pr.get("number")
        repo            = payload.get("repository", {}).get("full_name", "unknown")
        installation_id = payload.get("installation", {}).get("id")
        head_sha        = pr.get("head", {}).get("sha")

        if "/" not in repo:
            raise HTTPException(status_code=400, detail=f"Unexpected repo format: {repo}")
        owner, repo_name = repo.split("/", 1)

        print(f"\n{'='*50}")
        print(f"PR #{number} {action} — {pr.get('title', '')} by {pr.get('user', {}).get('login', '')}")
        print("=" * 50)

        if action in ("opened", "synchronize") and installation_id and head_sha:
            asyncio.create_task(
                _safe_run_pipeline(owner, repo_name, number, installation_id, head_sha)
            )

    else:
        print(f"Unhandled event: {event_type}")

    return {"status": "ok", "event": event_type}


@app.get("/")
async def root():
    return {"status": "code review agent is running"}
