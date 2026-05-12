import os
from openai import OpenAI
from .diff_utils import DiffHunk

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def get_context_for_hunk(
    hunk: DiffHunk,
    collection_name: str,
    n_results: int = 5,
) -> list[dict]:
    if not hunk.added_code.strip():
        return []

    import chromadb
    chroma = chromadb.PersistentClient(path="/tmp/chromadb")
    try:
        collection = chroma.get_collection(collection_name)
    except Exception:
        return []

    response = _get_client().embeddings.create(
        input=[hunk.added_code],
        model="text-embedding-3-small",
    )
    query_vector = response.data[0].embedding

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        include=["documents", "metadatas"],
    )

    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        # Skip chunks from the same file at overlapping lines to avoid self-match
        if (
            meta.get("file") == hunk.file
            and meta.get("start_line", 0) <= hunk.line_end
            and meta.get("end_line", 0) >= hunk.line_start
        ):
            continue
        chunks.append({
            "text": doc,
            "file": meta.get("file", ""),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "symbol_name": meta.get("symbol_name", ""),
        })

    return chunks
