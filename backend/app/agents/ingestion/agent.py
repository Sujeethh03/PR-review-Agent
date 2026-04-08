import asyncio
import os
from app.models.chunks import IngestionResult
from app.models.ingestion_config import IngestionConfig
from .walker import walk_repo
from .parser import parse_file
from .embedder import embed_chunks
from .store import (
    get_or_create_collection,
    collection_has_data,
    upsert_chunks,
    delete_chunks_for_files,
)
from .diff_parser import parse_diff_file_paths


async def run_ingestion(
    diff: str,
    repo_path: str,
    owner: str,
    repo_name: str,
    head_sha: str,
    config: IngestionConfig | None = None,
) -> IngestionResult:
    if config is None:
        config = IngestionConfig()

    return await asyncio.to_thread(
        _run_ingestion_sync,
        diff, repo_path, owner, repo_name, head_sha, config,
    )


def _run_ingestion_sync(
    diff: str,
    repo_path: str,
    owner: str,
    repo_name: str,
    head_sha: str,
    config: IngestionConfig,
) -> IngestionResult:
    collection    = get_or_create_collection(owner, repo_name)
    repo_full     = f"{owner}/{repo_name}"
    collection_name = collection.name

    if collection_has_data(collection):
        mode = "incremental"
        modified_paths, deleted_paths = parse_diff_file_paths(diff)

        # Purge deleted files first
        if deleted_paths:
            delete_chunks_for_files(collection, deleted_paths)

        # Only walk files that were added or modified in the diff
        files_to_ingest = [
            os.path.join(repo_path, p)
            for p in modified_paths
            if os.path.isfile(os.path.join(repo_path, p))
        ]
    else:
        mode = "full"
        files_to_ingest = walk_repo(repo_path, config)

    files_processed = 0
    files_skipped   = 0
    total_stored    = 0

    for abs_path in files_to_ingest:
        chunks = parse_file(abs_path, repo_path, config)
        if not chunks:
            files_skipped += 1
            continue

        embedded = embed_chunks(chunks, config.embedding_batch_size)
        stored   = upsert_chunks(collection, embedded, head_sha, repo_full)

        total_stored    += stored
        files_processed += 1

    return IngestionResult(
        collection_name=collection_name,
        chunks_stored=total_stored,
        files_processed=files_processed,
        files_skipped=files_skipped,
        mode=mode,
    )
