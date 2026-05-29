from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import services.approver.main as approver_module

_MOCK_WORKSPACE = MagicMock()
_MOCK_WORKSPACE.id = "test-workspace"
_MOCK_WORKSPACE.data = {
    "tg_group_chat_id": -100123,
    "ingest_thread_id": 1,
    "review_thread_id": 2,
    "publish_channel": "@testchannel",
    "gpt_profile": "default",
}

_MOCK_DRAFT = {
    "id": "nbu_ua-123",
    "source_id": "nbu_ua",
    "source_type": "telegram",
    "origin_chat": "@nbu_ua",
    "origin_text": "Повний текст новини про ФОП який довший за двадцять символів",
    "red_text": "Відредагований текст для TG каналу",
    "twitter_text": "Провокаційний твіт #ФОП",
    "post_targets": "tg",
    "status": "RED_READY",
}


@pytest.fixture
def client():
    approver_module._workspace_cache = None
    with (
        patch("services.approver.main.get_workspace", return_value=_MOCK_WORKSPACE),
        patch("services.approver.main.get_draft", return_value=dict(_MOCK_DRAFT)),
        patch("services.approver.main.update_draft"),
        patch("services.approver.main.save_post"),
        patch("services.approver.main.bot") as mock_bot,
        patch("services.approver.main.post_tweet", return_value="tweet-id-1"),
    ):
        mock_bot.send_message.return_value = {"result": {"message_id": 42}}
        mock_bot.answer_callback.return_value = {}
        mock_bot.safe_delete_message.return_value = {}
        with TestClient(approver_module.app) as c:
            yield c
    approver_module._workspace_cache = None


def _callback_update(draft_id: str, action: str, message_id: int = 10, chat_id: int = -100123):
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb-1",
            "data": f"draft:{draft_id}:{action}",
            "message": {
                "message_id": message_id,
                "chat": {"id": chat_id},
                "message_thread_id": 2,
            },
            "from": {"id": 777},
        },
    }


class TestHealthz:
    def test_ok(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestTelegramWebhook:
    def test_invalid_json_returns_ok(self, client):
        r = client.post(
            "/telegram/webhook",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "invalid_json"

    def test_skip_ingest_callback(self, client):
        update = _callback_update("nbu_ua-123", "skip_ingest")
        r = client.post("/telegram/webhook", json=update)
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

    def test_post_review_callback(self, client):
        update = _callback_update("nbu_ua-123", "post_review")
        r = client.post("/telegram/webhook", json=update)
        assert r.status_code == 200
        assert r.json()["status"] == "posted"

    def test_skip_review_callback(self, client):
        update = _callback_update("nbu_ua-123", "skip_review")
        r = client.post("/telegram/webhook", json=update)
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

    def test_unknown_callback_returns_ignored(self, client):
        update = _callback_update("nbu_ua-123", "unknown_action")
        r = client.post("/telegram/webhook", json=update)
        assert r.status_code == 200
        assert r.json()["status"] == "ignored"

    def test_invalid_secret_returns_unauthorized(self, client):
        r = client.post(
            "/telegram/webhook",
            json={"update_id": 1},
            headers={"x-telegram-bot-api-secret-token": "wrong-token"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "unauthorized"


class TestInternalNotify:
    def test_missing_draft_id_returns_400(self, client):
        r = client.post("/internal/notify", json={})
        assert r.status_code == 400

    def test_ingested_draft_sends_message(self, client):
        with patch("services.approver.main.get_draft") as mock_gd:
            mock_gd.return_value = {**_MOCK_DRAFT, "status": "INGESTED"}
            r = client.post("/internal/notify", json={"draft_id": "nbu_ua-123"})
        assert r.status_code == 200
        assert r.json()["status"] == "sent"

    def test_non_ingested_draft_returns_ignored(self, client):
        with patch("services.approver.main.get_draft") as mock_gd:
            mock_gd.return_value = {**_MOCK_DRAFT, "status": "POSTED"}
            r = client.post("/internal/notify", json={"draft_id": "nbu_ua-123"})
        assert r.status_code == 200
        assert r.json()["status"] == "ignored"
