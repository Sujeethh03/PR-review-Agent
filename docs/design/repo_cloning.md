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
        ├── 2. delete any existing clones matching /tmp/repos/{owner}-{repo}-*
        │         └── removes stale clones from previous commits on the same repo
        │
        ├── 3. get installation token from github_client.get_installation_token()
        │
        ├── 4. build authenticated clone URL
        │         https://x-access-token:{token}@github.com/{owner}/{repo}.git
        │
        ├── 5. git clone --depth 1 {url} into /tmp/repos/{owner}-{repo}-{head_sha}
        │         --depth 1 = shallow clone, only latest snapshot, much faster
        │
        └── 6. return local path
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
| Stale clone cleanup | Delete `{owner}-{repo}-*` before cloning | Prevents `/tmp/repos` accumulating a folder per commit indefinitely |
| Auth | HTTPS with installation token | Reuses token we already fetch, no extra config |
| Library | `gitpython` | Already in the design doc tech stack |

---

## What is NOT being done yet

- ~~Cleanup of `/tmp/repos/` — deferred, not needed for Phase 1~~ — **implemented**: stale clones for the same repo are deleted before each fresh clone
- Incremental updates (pull instead of clone) — deferred to Phase 2 optimisation
- Error handling for private repos the App isn't installed on — deferred

---

## Function signature

```python
async def clone_repo(installation_id: int, owner: str, repo: str, head_sha: str) -> str:
    # returns local path to cloned repo
```

---

## What happens after clone_repo() returns — Phase 2

The cloned folder at `/tmp/repos/{owner}-{repo}-{sha}` is just files on disk at this point. Nothing reads them yet. The ingestion agent (Phase 2, weeks 3–4) is what uses the returned path.

### Step 1 — Walk the folder

The agent scans the cloned repo and walks all files, skipping binaries and files over a configurable size threshold (e.g. minified JS, lock files).

```
/tmp/repos/acme-myrepo-a3f92c1/
    src/
        auth.py
        payments.ts
        utils.go
    models/
        user.java
        order.rs
    config/
        settings.yaml   ← line-based fallback
```

Binary files and files over a configurable size threshold (e.g. minified JS bundles, `package-lock.json`) are skipped.

### Step 2 — Parse into chunks

Files are not split by character count. tree-sitter is the primary parser for all languages it supports (Python, Java, TypeScript, Go, Rust, C, C++, Ruby, and 100+ more). For file types not supported by tree-sitter, a line-based window fallback is used.

| Approach | Result |
|---|---|
| Naive — split by character count | Chunks split mid-function. Meaningless in isolation. |
| tree-sitter (all supported languages) | Each chunk is a complete function, class, or method. |
| Line-based fallback (unsupported types) | Fixed-size line windows — used for config, YAML, etc. |

A chunk boundary never falls in the middle of a function for any tree-sitter-supported language. When an agent retrieves context about payment processing, it gets a whole function — not fragments of two different ones.

### Step 3 — Embed each chunk

Each chunk is converted into a vector — a list of numbers that captures its semantic meaning — using OpenAI `text-embedding-3-small`:

```
"def validate_user(email)..." → [0.23, -0.81, 0.45, 0.12, ...]
                                  (1536 numbers)
```

Two functions that do similar things produce similar vectors, even if the code looks completely different. This is what enables search by meaning rather than by keyword.

### Step 4 — Store in ChromaDB

ChromaDB stores three things per chunk:

| Field | Value |
|---|---|
| `vector` | `[0.23, -0.81, 0.45, ...]` — used for similarity search |
| `document` | `"def validate_user(..."` — the actual source code |
| `metadata` | `{file: "auth.py", line: 12, type: "function"}` |

Later, when an agent needs context, it queries ChromaDB with a natural language or code fragment. ChromaDB converts the query to a vector, finds the closest stored vectors, and returns the matching code chunks. This is RAG — Retrieval Augmented Generation.

**Why this matters for false positive reduction:**

Without ChromaDB:
```
Bug agent sees: amount has no upper limit check → flags as bug
```

With ChromaDB:
```
Bug agent sees: amount has no upper limit check
Bug agent queries ChromaDB: find validators for payment amount
ChromaDB returns: validate_payment_limit() in payments/validators.py
Bug agent concludes: validation already exists upstream → not a bug
```

This context retrieval is the mechanism the critic agent uses to drop false positives before any finding reaches a human.

### How it plugs into main.py (Phase 2)

```python
# Phase 1 (current)
diff      = await get_pr_diff(installation_id, owner, repo_name, number)
repo_path = await clone_repo(installation_id, owner, repo_name, head_sha)
# TODO: pass diff + repo_path to ingestion agent

# Phase 2 (after ingestion agent is built)
diff      = await get_pr_diff(installation_id, owner, repo_name, number)
repo_path = await clone_repo(installation_id, owner, repo_name, head_sha)
await ingest(repo_path, diff)   # walks, parses, embeds, stores in ChromaDB
```
