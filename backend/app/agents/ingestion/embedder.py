import os
import time
from app.models.chunks import Chunk

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def embed_chunks(
    chunks: list[Chunk],
    batch_size: int = 100,
    model: str = "text-embedding-3-small",
) -> list[tuple[Chunk, list[float]]]:
    if not chunks:
        return []

    client = _get_client()
    results: list[tuple[Chunk, list[float]]] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.text for c in batch]

        for attempt in range(2):
            try:
                response = client.embeddings.create(input=texts, model=model)
                vectors = [item.embedding for item in response.data]
                results.extend(zip(batch, vectors))
                break
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(1)

    return results
