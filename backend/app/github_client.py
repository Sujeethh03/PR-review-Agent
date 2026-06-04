import time
import jwt
import httpx
import os

GITHUB_API = "https://api.github.com"


def _generate_jwt() -> str:
    app_id = os.getenv("GITHUB_APP_ID")

    # Production: base64-encoded key in GITHUB_PRIVATE_KEY env var
    # Local: path to .pem file in GITHUB_PRIVATE_KEY_PATH env var
    raw = os.getenv("GITHUB_PRIVATE_KEY")
    if raw:
        import base64
        private_key = base64.b64decode(raw).decode("utf-8")
    else:
        key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
        with open(key_path, "r") as f:
            private_key = f.read()

    now = int(time.time())
    payload = {
        "iat": now - 60,   # issued at (60s in past to allow clock skew)
        "exp": now + 540,  # expires in 9 minutes (max is 10)
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    token = _generate_jwt()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        return response.json()["token"]


async def get_pr_diff(installation_id: int, owner: str, repo: str, pr_number: int) -> str:
    token = await get_installation_token(installation_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.diff",
            },
        )
        response.raise_for_status()
        return response.text
