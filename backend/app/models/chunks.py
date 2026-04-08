from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel

ChunkType = Literal["function", "class", "method", "window"]


@dataclass
class Chunk:
    text: str
    file: str           # relative path from repo root
    start_line: int     # 1-indexed
    end_line: int
    language: str
    chunk_type: ChunkType
    symbol_name: str    # empty string if not extractable


class IngestionResult(BaseModel):
    collection_name: str
    chunks_stored: int
    files_processed: int
    files_skipped: int
    mode: Literal["full", "incremental"]
