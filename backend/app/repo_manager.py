import os
import shutil
import git
from app.github_client import get_installation_token

CLONE_BASE = "/tmp/repos"


async def clone_repo(installation_id: int, owner: str, repo: str, head_sha: str) -> str:
    clone_path = os.path.join(CLONE_BASE, f"{owner}-{repo}-{head_sha}")

    if os.path.exists(clone_path):
        return clone_path

    # Remove old clones of the same repo before cloning the new commit
    os.makedirs(CLONE_BASE, exist_ok=True)
    prefix = f"{owner}-{repo}-"
    for entry in os.listdir(CLONE_BASE):
        if entry.startswith(prefix):
            shutil.rmtree(os.path.join(CLONE_BASE, entry), ignore_errors=True)

    token = await get_installation_token(installation_id)
    clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"

    git.Repo.clone_from(clone_url, clone_path, depth=1)

    return clone_path
