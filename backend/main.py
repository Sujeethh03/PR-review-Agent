import hmac
import hashlib
import json
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.github_client import get_pr_diff
from app.repo_manager import clone_repo
from app.agents.ingestion import run_ingestion
from app.agents.specialist import run_specialist_agents
from app.agents.router import route_finding
from app.agents.pr_writer import run_pr_writer
from app.db.findings_repo import save_review, save_findings
from app.models.findings import finding_hash
from app.api.findings import router as findings_router

load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "PATCH"],
    allow_headers=["*"],
)

app.include_router(findings_router)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("GITHUB_WEBHOOK_SECRET is not set")


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False

    expected_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


@app.post("/webhook")
async def webhook(request: Request):
    payload_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_body, signature_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(payload_body)
    event_type = request.headers.get("X-GitHub-Event", "unknown")

    print("\n" + "="*50)
    print(f"Event received: {event_type}")

    if event_type in ("security_advisory", "github_app_authorization",
                      "check_suite", "check_run", "status",
                      "pull_request_review", "pull_request_review_comment",
                      "pull_request_review_thread"):
        return {"status": "ok", "event": event_type}

    if event_type == "push":
        repo    = payload.get("repository", {}).get("full_name", "unknown")
        branch  = payload.get("ref", "").replace("refs/heads/", "")
        pusher  = payload.get("pusher", {}).get("name", "unknown")
        commits = payload.get("commits", [])

        print(f"Repository : {repo}")
        print(f"Branch     : {branch}")
        print(f"Pushed by  : {pusher}")
        print(f"Commits    : {len(commits)}")

        for commit in commits:
            print(f"  - {commit.get('message', '')} ({commit.get('id', '')[:7]})")
            print(f"    Files changed: {len(commit.get('modified', []))}")

    elif event_type == "pull_request":
        action = payload.get("action", "unknown")
        pr     = payload.get("pull_request", {})
        title  = pr.get("title", "unknown")
        author = pr.get("user", {}).get("login", "unknown")
        number = pr.get("number")
        repo   = payload.get("repository", {}).get("full_name", "unknown")
        if "/" not in repo:
            raise HTTPException(status_code=400, detail=f"Unexpected repo format: {repo}")
        owner, repo_name = repo.split("/", 1)
        installation_id = payload.get("installation", {}).get("id")
        head_sha        = pr.get("head", {}).get("sha")

        print(f"PR action  : {action}")
        print(f"PR number  : #{number}")
        print(f"Title      : {title}")
        print(f"Author     : {author}")

        if action in ("opened", "synchronize") and installation_id and head_sha:
            try:
                print(f"Fetching diff for PR #{number}...")
                diff = await get_pr_diff(installation_id, owner, repo_name, number)
                print(f"Diff fetched: {len(diff)} characters")

                print(f"Cloning repo at {head_sha[:7]}...")
                repo_path = await clone_repo(installation_id, owner, repo_name, head_sha)
                print(f"Repo ready: {repo_path}")

                print("Running ingestion...")
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

                print("Running specialist agents...")
                specialist_result = await run_specialist_agents(
                    diff=diff,
                    collection_name=ingestion_result.collection_name,
                    owner=owner,
                    repo_name=repo_name,
                )
                all_findings = specialist_result.all_findings()
                print(
                    f"Specialist findings: {len(all_findings)} total "
                    f"({len(specialist_result.bug.findings)} bug, "
                    f"{len(specialist_result.security.findings)} security, "
                    f"{len(specialist_result.pattern.findings)} pattern)"
                )

                routes = {finding_hash(f): route_finding(f) for f in all_findings}

                review_id = await save_review(
                    owner, repo_name, number, head_sha,
                    ingestion_result.collection_name,
                )
                await save_findings(review_id, all_findings, routes)

                for f in all_findings:
                    route = routes[finding_hash(f)]
                    print(f"  [{f.severity.upper()}] [{route.upper()}] {f.file}:{f.line_start} — {f.title} (conf: {f.confidence:.2f})")

                print(f"Saved to DB — review_id: {review_id}")

                auto_findings = [f for f in all_findings if routes[finding_hash(f)] == "auto"]
                if auto_findings:
                    print(f"Posting {len(auto_findings)} auto finding(s) to PR #{number}...")
                    await run_pr_writer(
                        findings=auto_findings,
                        installation_id=installation_id,
                        owner=owner,
                        repo_name=repo_name,
                        pr_number=number,
                        head_sha=head_sha,
                    )
                    print(f"Posted to GitHub PR #{number}")

            except Exception as e:
                print(f"Pipeline error: {e}")

    else:
        print(f"Unhandled event: {event_type}")

    print("="*50 + "\n")

    return {"status": "ok", "event": event_type}


@app.get("/")
async def root():
    return {"status": "code review agent is running"}
