# Repo Cloning — Design

## Where it lives

```
backend/app/
    github_client.py    ← already exists (JWT auth, get_pr_diff)
    repo_manager.py     ← new file, handles cloning
```

`main.py` calls `repo_manager.py`, which calls `github_client.py` for the token.

---

## What `repo_manager.py` does

```
clone_repo(installation_id, owner, repo, head_sha)
        │
        ├── 1. check if /tmp/repos/{owner}-{repo}-{head_sha} already exists
        │         └── if yes → return path immediately (idempotent, safe to retry)
        │
        ├── 2. get installation token from github_client.get_installation_token()
        │
        ├── 3. build authenticated clone URL
        │         https://x-access-token:{token}@github.com/{owner}/{repo}.git
        │
        ├── 4. git clone --depth 1 {url} into /tmp/repos/{owner}-{repo}-{head_sha}
        │         --depth 1 = shallow clone, only latest snapshot, much faster
        │
        └── 5. return local path
```

---

## Where it plugs into `main.py`

```python
# current
diff = await get_pr_diff(...)
# TODO: pass diff to ingestion agent

# after this change
diff      = await get_pr_diff(...)
repo_path = await clone_repo(installation_id, owner, repo_name, head_sha)
# TODO: pass diff + repo_path to ingestion agent
```

`head_sha` comes from `payload["pull_request"]["head"]["sha"]` — already in the webhook payload, no extra API call needed.

---

## Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Clone destination | `/tmp/repos/{owner}-{repo}-{sha}` | Unique per SHA, safe across concurrent PRs |
| Shallow clone | `--depth 1` | We only need current file contents for chunking, not git history |
| Idempotency | Skip if path exists | Same SHA can arrive twice (re-opened PR), no need to re-clone |
| Auth | HTTPS with installation token | Reuses token we already fetch, no extra config |
| Library | `gitpython` | Already in the design doc tech stack |

---

## What is NOT being done yet

- Cleanup of `/tmp/repos/` — deferred, not needed for Phase 1
- Incremental updates (pull instead of clone) — deferred to Phase 2 optimisation
- Error handling for private repos the App isn't installed on — deferred

---

## Function signature

```python
async def clone_repo(installation_id: int, owner: str, repo: str, head_sha: str) -> str:
    # returns local path to cloned repo
```
