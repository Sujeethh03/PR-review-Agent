import hmac
import hashlib
import json
import os
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from app.github_client import get_pr_diff

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")


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
        owner, repo_name = repo.split("/")
        installation_id = payload.get("installation", {}).get("id")

        print(f"PR action  : {action}")
        print(f"PR number  : #{number}")
        print(f"Title      : {title}")
        print(f"Author     : {author}")

        if action in ("opened", "synchronize") and installation_id:
            print(f"Fetching diff for PR #{number}...")
            diff = await get_pr_diff(installation_id, owner, repo_name, number)
            print(f"Diff fetched: {len(diff)} characters")
            # TODO: pass diff to ingestion agent

    else:
        print(f"Payload: {json.dumps(payload, indent=2)}")

    print("="*50 + "\n")

    return {"status": "ok", "event": event_type}


@app.get("/")
async def root():
    return {"status": "code review agent is running"}