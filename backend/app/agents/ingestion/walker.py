import os
from app.models.ingestion_config import IngestionConfig


def is_binary(file_path: str, probe_bytes: int = 8_192) -> bool:
    try:
        with open(file_path, "rb") as f:
            return b"\x00" in f.read(probe_bytes)
    except OSError:
        return True


def should_skip_dir(dir_name: str, skip_dirs: list[str]) -> bool:
    return dir_name in skip_dirs


SKIP_FILENAMES = {".env", ".env.local", ".env.production", ".env.development"}
SKIP_EXTENSIONS = {".pem", ".key", ".lock", ".pyc", ".map"}


def walk_repo(repo_path: str, config: IngestionConfig) -> list[str]:
    accepted = []

    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [
            d for d in dirnames
            if not should_skip_dir(d, config.skip_dirs)
        ]

        for filename in filenames:
            if filename in SKIP_FILENAMES:
                continue
            if os.path.splitext(filename)[1].lower() in SKIP_EXTENSIONS:
                continue

            abs_path = os.path.join(dirpath, filename)

            try:
                if os.path.getsize(abs_path) > config.max_file_bytes:
                    continue
            except OSError:
                continue

            if is_binary(abs_path, config.binary_probe_bytes):
                continue

            accepted.append(abs_path)

    return accepted
