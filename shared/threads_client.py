from __future__ import annotations

import logging
import time

import requests

from shared.settings import settings

logger = logging.getLogger("threads_client")

THREADS_API = "https://graph.threads.net/v1.0"
_REFRESH_INTERVAL_SECONDS = 45 * 86400  # refresh every 45 days

_token: str | None = None
_token_refreshed_at: float | None = None


def _current_token() -> str | None:
    return _token or settings.threads_access_token


def _try_refresh() -> None:
    global _token, _token_refreshed_at
    now = time.monotonic()
    if _token_refreshed_at and (now - _token_refreshed_at) < _REFRESH_INTERVAL_SECONDS:
        return
    current = _current_token()
    if not current:
        return
    try:
        resp = requests.get(
            f"{THREADS_API}/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": current},
            timeout=10,
        )
        if resp.status_code == 200:
            new_token = resp.json().get("access_token")
            if new_token:
                _token = new_token
                _token_refreshed_at = now
                logger.info("threads_token_refreshed")
                _update_secret_manager(new_token)
        else:
            logger.warning("threads_token_refresh_failed", extra={"status": resp.status_code})
    except Exception as exc:  # noqa: BLE001
        logger.warning("threads_token_refresh_error", extra={"error": str(exc)})


def _update_secret_manager(new_token: str) -> None:
    try:
        import os
        from google.cloud import secretmanager
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
        if not project_id:
            logger.warning("threads_secret_update_skipped: no project id")
            return
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project_id}/secrets/THREADS_ACCESS_TOKEN"
        client.add_secret_version(request={"parent": parent, "payload": {"data": new_token.encode()}})
        logger.info("threads_token_secret_updated")
    except Exception as exc:  # noqa: BLE001
        logger.warning("threads_secret_update_failed", extra={"error": str(exc)})


def post_thread(text: str) -> str | None:
    if not settings.threads_user_id:
        logger.warning("threads_user_id_missing")
        return None
    _try_refresh()
    token = _current_token()
    if not token:
        logger.warning("threads_access_token_missing")
        return None
    user_id = settings.threads_user_id

    resp = requests.post(
        f"{THREADS_API}/{user_id}/threads",
        params={"media_type": "TEXT", "text": text, "access_token": token},
        timeout=30,
    )
    if resp.status_code != 200:
        logger.warning("threads_create_failed", extra={"status": resp.status_code, "body": resp.text[:200]})
        return None
    creation_id = resp.json().get("id")
    if not creation_id:
        logger.warning("threads_no_creation_id")
        return None

    resp = requests.post(
        f"{THREADS_API}/{user_id}/threads_publish",
        params={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    if resp.status_code != 200:
        logger.warning("threads_publish_failed", extra={"status": resp.status_code, "body": resp.text[:200]})
        return None
    thread_id = str(resp.json().get("id", ""))
    logger.info("threads_post_success", extra={"thread_id": thread_id})
    return thread_id or None
