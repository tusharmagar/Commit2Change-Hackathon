from __future__ import annotations

import sys

import base64
import hashlib
import json
import re
import secrets
import time
import urllib.parse
from pathlib import Path

import httpx

from pathlib import Path

# Ensure repo root is on sys.path when running as a script
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("utf-8")).digest())
    return verifier, challenge


def _extract_resource_metadata(header_value: str | None) -> str | None:
    if not header_value:
        return None
    match = re.search(r'resource_metadata="([^"]+)"', header_value)
    return match.group(1) if match else None


def _fetch_protected_resource_metadata(resource_url: str) -> httpx.Response:
    return httpx.get(resource_url, headers={"Accept": "application/json"}, timeout=20)


def discover_oauth(mcp_url: str) -> dict:
    url = mcp_url.rstrip("/")
    resource_url = url + "/.well-known/oauth-protected-resource"
    resp = _fetch_protected_resource_metadata(resource_url)

    if resp.status_code in (401, 403):
        resource_meta = _extract_resource_metadata(resp.headers.get("WWW-Authenticate"))
        if not resource_meta:
            # Try hitting the MCP URL to elicit WWW-Authenticate header
            auth_probe = httpx.get(url, timeout=10)
            resource_meta = _extract_resource_metadata(auth_probe.headers.get("WWW-Authenticate"))
        if not resource_meta:
            # Fallback to root well-known
            parsed = urllib.parse.urlparse(url)
            resource_meta = f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource"

        resp = _fetch_protected_resource_metadata(resource_meta)

    resp.raise_for_status()
    resource = resp.json()
    auth_servers = resource.get("authorization_servers") or resource.get("authorization_server")
    if isinstance(auth_servers, list):
        auth_server = auth_servers[0]
    else:
        auth_server = auth_servers
    if not auth_server:
        raise RuntimeError("No authorization server found in protected resource metadata.")

    auth_meta_url = auth_server.rstrip("/") + "/.well-known/oauth-authorization-server"
    auth_resp = httpx.get(auth_meta_url, headers={"Accept": "application/json"}, timeout=20)
    auth_resp.raise_for_status()
    return auth_resp.json()


def dynamic_register(registration_endpoint: str, redirect_uri: str) -> str:
    payload = {
        "client_name": "Tomatose WhatsApp Bot",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    resp = httpx.post(registration_endpoint, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()["client_id"]


def build_auth_url(
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "user",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return authorization_endpoint + "?" + urllib.parse.urlencode(params)


def exchange_code(
    token_endpoint: str,
    client_id: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    redirect_uri = settings.PUBLIC_BASE_URL.rstrip("/") + "/oauth/notion/callback"

    auth_meta = discover_oauth(settings.NOTION_MCP_URL)
    registration_endpoint = auth_meta.get("registration_endpoint")
    authorization_endpoint = auth_meta.get("authorization_endpoint")
    token_endpoint = auth_meta.get("token_endpoint")

    if not (registration_endpoint and authorization_endpoint and token_endpoint):
        raise RuntimeError("OAuth metadata missing required endpoints.")

    client_id = dynamic_register(registration_endpoint, redirect_uri)
    verifier, challenge = pkce_pair()
    state = _b64url(secrets.token_bytes(16))

    auth_url = build_auth_url(
        authorization_endpoint,
        client_id,
        redirect_uri,
        challenge,
        state,
    )

    print("Open this URL in your browser and complete auth:")
    print(auth_url)
    print("\nPaste the full redirect URL after login:")
    callback = input("> ").strip()
    parsed = urllib.parse.urlparse(callback)
    query = urllib.parse.parse_qs(parsed.query)

    if "error" in query:
        raise RuntimeError(f"OAuth error: {query['error']}")
    if "code" not in query:
        raise RuntimeError("No code found in redirect URL.")

    code = query["code"][0]
    returned_state = query.get("state", [None])[0]
    if returned_state and returned_state != state:
        raise RuntimeError("State mismatch. Aborting.")

    token = exchange_code(token_endpoint, client_id, code, redirect_uri, verifier)

    storage_path = Path(settings.NOTION_OAUTH_STORAGE)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": client_id,
        "token_endpoint": token_endpoint,
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
        "expires_at": time.time() + token.get("expires_in", 3600),
    }
    storage_path.write_text(json.dumps(payload, indent=2))
    print(f"Saved OAuth tokens to {storage_path}")


if __name__ == "__main__":
    main()
