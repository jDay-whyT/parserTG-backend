import pytest
from services.ingest.web_enricher import extract_buhgalter_url


class TestExtractBuhgalterUrl:
    def test_finds_url(self):
        text = "Читайте повний матеріал: https://buhgalter911.com/uk/news/article-123"
        assert extract_buhgalter_url(text) == "https://buhgalter911.com/uk/news/article-123"

    def test_finds_www_url(self):
        text = "https://www.buhgalter911.com/uk/analytics/vat-2025"
        assert extract_buhgalter_url(text) == "https://www.buhgalter911.com/uk/analytics/vat-2025"

    def test_returns_none_when_no_url(self):
        assert extract_buhgalter_url("Звичайний текст без посилання") is None

    def test_returns_none_for_other_domain(self):
        assert extract_buhgalter_url("https://google.com/something") is None

    def test_strips_trailing_punctuation(self):
        text = "Деталі: https://buhgalter911.com/uk/news/art-1."
        url = extract_buhgalter_url(text)
        assert url == "https://buhgalter911.com/uk/news/art-1"

    def test_strips_trailing_paren(self):
        text = "(https://buhgalter911.com/uk/news/art-2)"
        url = extract_buhgalter_url(text)
        assert url == "https://buhgalter911.com/uk/news/art-2"

    def test_empty_text_returns_none(self):
        assert extract_buhgalter_url("") is None
