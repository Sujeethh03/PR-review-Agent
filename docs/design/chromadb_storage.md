# ChromaDB Storage — Design

## Where it lives on disk

```
/tmp/chromadb/
    chroma.sqlite3                        ← master index (metadata, collection names, IDs)
    <uuid>/                               ← one folder per collection (vector data)
        data_level0.bin                   ← raw embedding vectors (1536 floats per chunk)
        header.bin                        ← HNSW graph header
        length.bin                        ← number of vectors stored
        link_lists.bin                    ← HNSW graph connections (for fast search)
```

Set in `backend/app/agents/ingestion/store.py`:

```python
chromadb.PersistentClient(path="/tmp/chromadb")
```

> **Important:** `/tmp/` is wiped on reboot. On the next PR after a restart, ingestion
> will detect an empty collection and run a full re-ingest automatically. Moving this
> to a persistent path (e.g. `~/.pr-review-agent/chromadb`) is a Phase 4 task.

---

## Collection naming

One collection per repo, named `{owner}__{repo_name}` (double underscore — ChromaDB
collection names cannot contain `/`).

| Repo | Collection name |
|---|---|
| `Sujeethh03/test-repo` | `Sujeethh03__test-repo` |
| `acme/myrepo` | `acme__myrepo` |

Each collection maps to one UUID folder on disk. The UUID is assigned by ChromaDB
internally — it is not the same as the repo name or the commit SHA.

---

## What `chroma.sqlite3` stores

The SQLite file is the master index. It stores:

- Collection names and their internal UUIDs
- Every chunk's **metadata**: file path, line numbers, language, symbol name, chunk type, repo, commit SHA
- Every chunk's **ID** (SHA256 hash of `file:start_line:end_line`)

This is the source of truth. The UUID folders are looked up via this file.

---

## What each UUID folder stores

The four binary files implement an **HNSW index** (Hierarchical Navigable Small World)
— the data structure ChromaDB uses for fast nearest-neighbour vector search.

| File | Contents |
|---|---|
| `data_level0.bin` | The raw embedding vectors — 1536 floats per chunk, stored contiguously |
| `header.bin` | HNSW graph metadata (dimensions, distance metric, entry point) |
| `length.bin` | Total number of vectors currently stored |
| `link_lists.bin` | The graph edges — links between nodes used to navigate during search |

Without HNSW, searching for the nearest vector would require comparing the query
against every stored vector one by one. HNSW lets ChromaDB find the nearest neighbours
in milliseconds by traversing a graph instead.

---

## What each chunk contains

Every chunk stored in ChromaDB has three parts:

### 1. ID
SHA256 hash of `{file}:{start_line}:{end_line}`. Deterministic and stable — the same
chunk from the same file always gets the same ID, which is what makes `upsert` work
correctly (re-ingesting a file replaces its old chunks rather than duplicating them).

### 2. Document (source code text)
The raw source code for that chunk — the actual function, class, or line window as a string.

### 3. Metadata
| Field | Example | Purpose |
|---|---|---|
| `file` | `"src/auth.py"` | Relative path from repo root |
| `start_line` | `42` | 1-indexed |
| `end_line` | `67` | 1-indexed |
| `language` | `"python"` | Detected from file extension |
| `chunk_type` | `"function"` | How it was parsed |
| `symbol_name` | `"validate_user"` | Function/class name, empty string if not extractable |
| `repo` | `"acme/myrepo"` | Full repo identifier |
| `ingested_at_sha` | `"a3f92c1"` | Commit SHA at time of ingest |

### 4. Embedding (vector)
1536 floats produced by OpenAI `text-embedding-3-small`. Stored in `data_level0.bin`.
Not visible in metadata — used internally by ChromaDB for similarity search.

---

## How chunks are counted — chunking behaviour

### Tree-sitter languages (Python, Java, TypeScript, Go, etc.)

Tree-sitter extracts **both** the outer container and inner members as separate chunks.

Example — a Java file with one class and one method:

```java
class A {
    public static void main(String[] args) {
        System.out.println("hello");
    }
}
```

Produces **2 chunks**:
- `class A` (the whole class node)
- `main` (the method node inside it)

Example — a Python file:

```python
class PaymentProcessor:
    def __init__(self): ...
    def charge(self): ...
    def refund(self): ...
```

Produces **4 chunks**:
- `class PaymentProcessor` (whole class)
- `__init__`, `charge`, `refund` (each method separately)

This means a file with N classes and M total methods produces `N + M` chunks.

### Non-code files (plain text, YAML, SQL, etc.)

Falls back to **60-line windows with 15-line overlap**. Each window is one chunk.
A 3-line file produces 1 chunk. A 90-line file produces 3 chunks.

---

## Real example — PR #5 on `Sujeethh03/test-repo`

This PR triggered the first ingest of a small test repo. The repo had 4 files:

| File | Parser used | Chunks |
|---|---|---|
| `README` | Line window (no code structure) | 1 |
| `test.txt` | Line window | 1 |
| `myfile.txt` | Line window | 1 |
| `A.java` | tree-sitter → `class A` + `main` method | 2 |
| **Total** | | **5** |

Collection: `Sujeethh03__test-repo` | Mode: `full` (first PR on this repo)

---

## Full vs incremental ingest

| Condition | Mode | What happens |
|---|---|---|
| `collection.count() == 0` | Full | Walk entire repo, embed everything |
| `collection.count() > 0` | Incremental | Parse diff → re-embed changed files only, purge deleted files |

The mode is logged on every PR:
```
Ingestion: 5 chunks (full) → 'Sujeethh03__test-repo'
Ingestion: 3 chunks (incremental) → 'Sujeethh03__test-repo'
```
