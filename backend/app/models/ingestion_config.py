from pydantic import BaseModel


class IngestionConfig(BaseModel):
    max_file_bytes: int = 512_000
    binary_probe_bytes: int = 8_192
    window_size_lines: int = 60
    window_overlap_lines: int = 15
    embedding_batch_size: int = 100
    skip_dirs: list[str] = [
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "env", "dist", "build", ".next", "vendor", "target"
    ]
