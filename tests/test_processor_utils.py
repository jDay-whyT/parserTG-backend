import pytest
from services.processor.main import _is_valid_text, _normalize_source, _build_draft_id


class TestIsValidText:
    def test_none_returns_false(self):
        assert _is_valid_text(None) is False

    def test_empty_returns_false(self):
        assert _is_valid_text("") is False

    def test_too_short_returns_false(self):
        assert _is_valid_text("short") is False

    def test_exactly_minimum_returns_true(self):
        assert _is_valid_text("a" * 20) is True

    def test_long_text_returns_true(self):
        assert _is_valid_text("Нові правила ФОП з 2025 року: що змінилось для ФОП 2-ї групи") is True

    def test_whitespace_only_returns_false(self):
        assert _is_valid_text("   ") is False


class TestNormalizeSource:
    def test_strips_at(self):
        assert _normalize_source("@nbu_ua") == "nbu_ua"

    def test_no_at(self):
        assert _normalize_source("nbu_ua") == "nbu_ua"

    def test_none_returns_none(self):
        assert _normalize_source(None) is None

    def test_empty_returns_none(self):
        assert _normalize_source("") is None

    def test_at_only_returns_none(self):
        assert _normalize_source("@") is None


class TestBuildDraftId:
    def test_format(self):
        assert _build_draft_id("nbu_ua", 12345) == "nbu_ua-12345"

    def test_different_sources(self):
        assert _build_draft_id("tax_gov_ua", 1) == "tax_gov_ua-1"
