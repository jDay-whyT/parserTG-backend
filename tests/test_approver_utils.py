import pytest
from services.approver.main import (
    _parse_callback_data,
    _build_callback_data,
    _build_red_text,
    _format_publish_text,
    _format_review_text,
)


class TestCallbackData:
    def test_build_and_parse_roundtrip(self):
        data = _build_callback_data("nbu_ua-123", "post_review")
        result = _parse_callback_data(data)
        assert result == ("nbu_ua-123", "post_review")

    def test_parse_invalid_returns_none(self):
        assert _parse_callback_data("bad_data") is None

    def test_parse_wrong_prefix_returns_none(self):
        assert _parse_callback_data("other:id:action") is None

    def test_parse_too_few_parts_returns_none(self):
        assert _parse_callback_data("draft:only_two") is None

    def test_all_ingest_actions(self):
        for action in ("tg_ingest", "social_ingest", "both_ingest", "skip_ingest"):
            data = _build_callback_data("test-123", action)
            assert _parse_callback_data(data) == ("test-123", action)

    def test_all_review_actions(self):
        for action in ("post_review", "red_review", "skip_review"):
            data = _build_callback_data("test-456", action)
            assert _parse_callback_data(data) == ("test-456", action)


class TestBuildRedText:
    def test_title_and_body(self):
        result = _build_red_text({"title": "Заголовок", "body": "Текст"}, "fallback")
        assert result == "Заголовок\n\nТекст"

    def test_title_only(self):
        result = _build_red_text({"title": "Тільки заголовок", "body": ""}, "fallback")
        assert result == "Тільки заголовок"

    def test_body_only(self):
        result = _build_red_text({"title": "", "body": "Тільки тіло"}, "fallback")
        assert result == "Тільки тіло"

    def test_empty_uses_fallback(self):
        result = _build_red_text({"title": "", "body": ""}, "fallback text")
        assert result == "fallback text"


class TestFormatPublishText:
    def test_uses_red_text_when_available(self):
        draft = {"red_text": "Готовий текст", "origin_text": "Сирець"}
        assert _format_publish_text(draft) == "Готовий текст"

    def test_falls_back_to_origin(self):
        draft = {"red_text": "", "origin_text": "Сирець"}
        assert _format_publish_text(draft) == "Сирець"

    def test_none_red_text_falls_back(self):
        draft = {"red_text": None, "origin_text": "Сирець"}
        assert _format_publish_text(draft) == "Сирець"


class TestFormatReviewText:
    def test_tg_target_shows_label(self):
        draft = {"id": "src-1", "post_targets": "tg", "red_text": "Текст поста"}
        result = _format_review_text(draft)
        assert "[TG]" in result
        assert "Текст поста" in result

    def test_social_target_shows_social_label(self):
        draft = {"id": "src-2", "post_targets": "social", "twitter_text": "Провокаційний твіт"}
        result = _format_review_text(draft)
        assert "[Social]" in result
        assert "Провокаційний твіт" in result

    def test_both_target_shows_both_texts(self):
        draft = {
            "id": "src-3",
            "post_targets": "both",
            "red_text": "TG текст",
            "twitter_text": "Social текст",
        }
        result = _format_review_text(draft)
        assert "[TG + Social]" in result
        assert "TG текст" in result
        assert "Social текст" in result

    def test_default_target_is_tg(self):
        draft = {"id": "src-4", "red_text": "Текст"}
        result = _format_review_text(draft)
        assert "[TG]" in result

    def test_html_escaped(self):
        draft = {"id": "src-5", "post_targets": "tg", "red_text": "<script>alert(1)</script>"}
        result = _format_review_text(draft)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
