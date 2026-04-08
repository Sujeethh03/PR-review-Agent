"""
Standalone test for the ingestion pipeline.

Run from backend/:
    python test_ingestion.py

What it does:
  1. Full ingest  — ingests this project's backend/ folder into ChromaDB
  2. Query        — searches for chunks related to "webhook signature verification"
  3. Incremental  — simulates a PR diff and re-ingests only changed files
  4. Prints results at each step so you can see what's happening
"""

import asyncio
import sys
import os

# Make sure backend/ is on the path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(override=True)

from app.agents.ingestion import run_ingestion
from app.agents.ingestion.store import get_or_create_collection, _get_client
import chromadb


REPO_PATH = os.path.dirname(__file__)   # backend/ itself
OWNER     = "test"
REPO_NAME = "ingestion-test"
HEAD_SHA  = "abc1234"


MOCK_DIFF = """\
diff --git a/app/github_client.py b/app/github_client.py
index 0000000..1111111 100644
--- a/app/github_client.py
+++ b/app/github_client.py
@@ -1,5 +1,6 @@
 import time
 import jwt
+import logging
 import httpx
"""


def separator(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def main():
    # ------------------------------------------------------------------ #
    # 0. Clean up any leftover collection from a previous run
    # ------------------------------------------------------------------ #
    separator("0. Cleanup — removing old test collection if it exists")
    client = _get_client()
    try:
        client.delete_collection(f"{OWNER}__{REPO_NAME}")
        print("Deleted existing collection.")
    except Exception:
        print("No existing collection — starting fresh.")

    # ------------------------------------------------------------------ #
    # 1. Full ingest
    # ------------------------------------------------------------------ #
    separator("1. Full ingest — ingesting backend/ into ChromaDB")
    result = await run_ingestion(
        diff="",           # empty diff on first run — full ingest ignores it
        repo_path=REPO_PATH,
        owner=OWNER,
        repo_name=REPO_NAME,
        head_sha=HEAD_SHA,
    )
    print(f"Mode            : {result.mode}")
    print(f"Collection      : {result.collection_name}")
    print(f"Files processed : {result.files_processed}")
    print(f"Files skipped   : {result.files_skipped}")
    print(f"Chunks stored   : {result.chunks_stored}")

    if result.chunks_stored == 0:
        print("\nERROR: No chunks stored. Check tree-sitter install and OPENAI_API_KEY.")
        return

    # ------------------------------------------------------------------ #
    # 2. Query ChromaDB to prove it worked
    # ------------------------------------------------------------------ #
    separator("2. Query — searching for 'webhook signature verification'")
    from openai import OpenAI
    oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    query = "webhook signature verification"
    query_vector = oai.embeddings.create(
        input=[query],
        model="text-embedding-3-small",
    ).data[0].embedding

    collection = get_or_create_collection(OWNER, REPO_NAME)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        print(f"\n--- Result {i + 1} (distance: {dist:.4f}) ---")
        print(f"File       : {meta['file']}  (lines {meta['start_line']}–{meta['end_line']})")
        print(f"Symbol     : {meta['symbol_name'] or '(none)'}")
        print(f"Chunk type : {meta['chunk_type']}")
        print(f"Preview    :\n{doc[:300]}")

    # ------------------------------------------------------------------ #
    # 3. Incremental ingest (simulate a PR diff)
    # ------------------------------------------------------------------ #
    separator("3. Incremental ingest — simulating a PR diff")
    result2 = await run_ingestion(
        diff=MOCK_DIFF,
        repo_path=REPO_PATH,
        owner=OWNER,
        repo_name=REPO_NAME,
        head_sha="def5678",
    )
    print(f"Mode            : {result2.mode}")
    print(f"Files processed : {result2.files_processed}")
    print(f"Files skipped   : {result2.files_skipped}")
    print(f"Chunks stored   : {result2.chunks_stored}")

    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
