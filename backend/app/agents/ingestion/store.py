import hashlib
import os
import chromadb
from app.models.chunks import Chunk

_chroma_client = None


def _get_client() -> chromadb.Client:
    global _chroma_client
    if _chroma_client is None:
        path = os.getenv("CHROMADB_PATH", "/tmp/chromadb")
        _chroma_client = chromadb.PersistentClient(path=path)
    return _chroma_client


def get_or_create_collection(owner: str, repo_name: str) -> chromadb.Collection:
    client = _get_client()
    collection_name = f"{owner}__{repo_name}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def collection_has_data(collection: chromadb.Collection) -> bool:
    return collection.count() > 0


def _chunk_id(chunk: Chunk) -> str:
    key = f"{chunk.file}:{chunk.start_line}:{chunk.end_line}"
    return hashlib.sha256(key.encode()).hexdigest()


def upsert_chunks(
    collection: chromadb.Collection,
    embedded_chunks: list[tuple[Chunk, list[float]]],
    head_sha: str,
    repo_full_name: str,
) -> int:
    if not embedded_chunks:
        return 0

    ids        = []
    documents  = []
    embeddings = []
    metadatas  = []

    for chunk, vector in embedded_chunks:
        ids.append(_chunk_id(chunk))
        documents.append(chunk.text)
        embeddings.append(vector)
        metadatas.append({
            "file":             chunk.file,
            "start_line":       chunk.start_line,
            "end_line":         chunk.end_line,
            "language":         chunk.language,
            "chunk_type":       chunk.chunk_type,
            "symbol_name":      chunk.symbol_name,
            "repo":             repo_full_name,
            "ingested_at_sha":  head_sha,
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(ids)


def delete_chunks_for_files(
    collection: chromadb.Collection,
    file_rel_paths: list[str],
) -> None:
    for file_path in file_rel_paths:
        collection.delete(where={"file": file_path})
