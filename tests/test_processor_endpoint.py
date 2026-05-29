import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import services.processor.main as processor_module

_MOCK_WORKSPACE = MagicMock()
_MOCK_WORKSPACE.id = "test-workspace"
_MOCK_WORKSPACE.data = {
    "tg_group_chat_id": -100123,
    "ingest_thread_id": 1,
    "review_thread_id": 2,
    "publish_channel": "@testchannel",
}


@pytest.fixture
def client():
    processor_module._workspace_cache = None
    with (
        patch("services.processor.main.get_workspace", return_value=_MOCK_WORKSPACE),
        patch("services.processor.main.verify_pubsub_jwt"),
        patch("services.processor.main.get_source") as mock_source,
        patch("services.processor.main.get_draft", return_value=None),
        patch("services.processor.main.create_draft") as mock_create,
        patch("services.processor.main.update_draft"),
        patch("services.processor.main.requests"),
    ):
        mock_source.return_value = {"id": "nbu_ua", "tg_entity": "@nbu_ua", "enabled": True}
        mock_create.side_effect = lambda ws, draft_id, **kw: {"id": draft_id, **kw}
        with TestClient(processor_module.app) as c:
            yield c
    processor_module._workspace_cache = None


def _pubsub_body(payload: dict) -> dict:
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data, "messageId": "msg-1"}, "subscription": "sub-test"}


class TestHealthz:
    def test_ok(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestPubsubPush:
    def _valid_payload(self):
        return {
            "workspace_id": "test-workspace",
            "source_id": "nbu_ua",
            "origin_message_id": 12345,
            "origin_text": "Нові правила оподаткування ФОП з 2025 року — детальний аналіз",
            "origin_chat": "@nbu_ua",
            "origin_message_date": 1700000000,
            "trace_id": "trace-abc",
        }

    def test_valid_message_returns_ingested(self, client):
        r = client.post("/pubsub/push", json=_pubsub_body(self._valid_payload()))
        assert r.status_code == 200
        assert r.json()["status"] == "ingested"

    def test_invalid_json_returns_204(self, client):
        r = client.post("/pubsub/push", content=b"not json", headers={"content-type": "application/json"})
        assert r.status_code == 204

    def test_workspace_mismatch_returns_204(self, client):
        payload = self._valid_payload()
        payload["workspace_id"] = "other-workspace"
        r = client.post("/pubsub/push", json=_pubsub_body(payload))
        assert r.status_code == 204

    def test_missing_source_id_returns_204(self, client):
        payload = self._valid_payload()
        del payload["source_id"]
        r = client.post("/pubsub/push", json=_pubsub_body(payload))
        assert r.status_code == 204

    def test_short_text_returns_skipped(self, client):
        payload = self._valid_payload()
        payload["origin_text"] = "short"
        r = client.post("/pubsub/push", json=_pubsub_body(payload))
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

    def test_empty_body_returns_204(self, client):
        r = client.post("/pubsub/push", json={})
        assert r.status_code == 204
