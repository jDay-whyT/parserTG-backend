import os
import pytest
from unittest.mock import MagicMock

from services.ingest.main import (
    _normalize_source,
    _source_id_from_entity,
    _get_ingest_limit,
    _get_bootstrap_max_age_seconds,
    _message_has_content,
    _validate_telethon_string_session,
    _collect_payloads,
)


class TestNormalizeSource:
    def test_strips_at_sign(self):
        assert _normalize_source("@nbu_ua") == "nbu_ua"

    def test_no_at_sign(self):
        assert _normalize_source("nbu_ua") == "nbu_ua"

    def test_strips_whitespace(self):
        assert _normalize_source("  @nbu_ua  ") == "nbu_ua"


class TestSourceIdFromEntity:
    def test_valid_username(self):
        assert _source_id_from_entity("@nbu_ua") == "nbu_ua"

    def test_valid_no_at(self):
        assert _source_id_from_entity("tax_gov_ua") == "tax_gov_ua"

    def test_invalid_characters_raises(self):
        with pytest.raises(RuntimeError, match="letters, numbers"):
            _source_id_from_entity("@invalid-username!")


class TestGetIngestLimit:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("INGEST_LIMIT", raising=False)
        monkeypatch.delenv("INGEST_MAX_MESSAGES_PER_SOURCE", raising=False)
        assert _get_ingest_limit() == 50

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("INGEST_LIMIT", "100")
        assert _get_ingest_limit() == 100

    def test_fallback_to_old_var(self, monkeypatch):
        monkeypatch.delenv("INGEST_LIMIT", raising=False)
        monkeypatch.setenv("INGEST_MAX_MESSAGES_PER_SOURCE", "25")
        assert _get_ingest_limit() == 25

    def test_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("INGEST_LIMIT", "abc")
        with pytest.raises(RuntimeError, match="integer"):
            _get_ingest_limit()

    def test_zero_raises(self, monkeypatch):
        monkeypatch.setenv("INGEST_LIMIT", "0")
        with pytest.raises(RuntimeError, match="greater than zero"):
            _get_ingest_limit()


class TestGetBootstrapMaxAge:
    def test_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("BOOTSTRAP_MAX_AGE_DAYS", raising=False)
        assert _get_bootstrap_max_age_seconds() is None

    def test_converts_days_to_seconds(self, monkeypatch):
        monkeypatch.setenv("BOOTSTRAP_MAX_AGE_DAYS", "30")
        assert _get_bootstrap_max_age_seconds() == 30 * 86400

    def test_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("BOOTSTRAP_MAX_AGE_DAYS", "xyz")
        with pytest.raises(RuntimeError, match="integer"):
            _get_bootstrap_max_age_seconds()


class TestMessageHasContent:
    def test_none_returns_false(self):
        assert _message_has_content(None) is False

    def test_empty_text_no_media_returns_false(self):
        msg = MagicMock()
        msg.message = ""
        msg.media = None
        assert _message_has_content(msg) is False

    def test_text_returns_true(self):
        msg = MagicMock()
        msg.message = "Hello world"
        assert _message_has_content(msg) is True

    def test_media_only_returns_true(self):
        msg = MagicMock()
        msg.message = ""
        msg.media = MagicMock()
        assert _message_has_content(msg) is True


class TestValidateTelethonSession:
    def test_valid_session(self):
        session = "1BVtsOK..."
        result = _validate_telethon_string_session(session)
        assert result == session

    def test_empty_raises(self):
        with pytest.raises(RuntimeError, match="required"):
            _validate_telethon_string_session("")

    def test_none_raises(self):
        with pytest.raises(RuntimeError, match="required"):
            _validate_telethon_string_session(None)

    def test_wrong_prefix_raises(self):
        with pytest.raises(RuntimeError, match="invalid"):
            _validate_telethon_string_session("2BVtsOK...")


class TestCollectPayloads:
    def _make_message(self, msg_id, text, date_ts=1700000000):
        msg = MagicMock()
        msg.id = msg_id
        msg.message = text
        from datetime import datetime, timezone
        msg.date = datetime.fromtimestamp(date_ts, tz=timezone.utc)
        return msg

    def _make_entity(self):
        entity = MagicMock()
        entity.id = 999
        entity.title = "Test Channel"
        entity.username = "testchannel"
        return entity

    def test_filters_old_messages(self):
        entity = self._make_entity()
        messages = [self._make_message(10, "old"), self._make_message(11, "new")]
        payloads, max_id, max_date = _collect_payloads(
            "ws", "src", "@testchannel", entity, messages, last_message_id=10
        )
        assert len(payloads) == 1
        assert payloads[0]["origin_message_id"] == 11

    def test_empty_when_no_new_messages(self):
        entity = self._make_entity()
        messages = [self._make_message(5, "old")]
        payloads, max_id, _ = _collect_payloads(
            "ws", "src", "@testchannel", entity, messages, last_message_id=10
        )
        assert payloads == []
        assert max_id == 10

    def test_payloads_sorted_by_id(self):
        entity = self._make_entity()
        messages = [
            self._make_message(15, "third"),
            self._make_message(12, "first"),
            self._make_message(13, "second"),
        ]
        payloads, _, _ = _collect_payloads(
            "ws", "src", "@ch", entity, messages, last_message_id=10
        )
        ids = [p["origin_message_id"] for p in payloads]
        assert ids == sorted(ids)

    def test_payload_fields(self):
        entity = self._make_entity()
        messages = [self._make_message(20, "Hello")]
        payloads, _, _ = _collect_payloads(
            "ws", "src", "@testchannel", entity, messages, last_message_id=0
        )
        p = payloads[0]
        assert p["workspace_id"] == "ws"
        assert p["source_id"] == "src"
        assert p["origin_chat"] == "@testchannel"
        assert p["origin_text"] == "Hello"
        assert p["origin_message_id"] == 20
