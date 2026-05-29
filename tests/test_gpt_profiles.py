import json
import pytest
from shared.gpt_profiles import _load_profiles_from_env, load_profiles, get_prompt
from shared.prompts import EDITORIAL_PROMPT_UK, SOCIAL_PROMPT_UK


class TestLoadProfilesFromEnv:
    def test_none_returns_empty(self):
        assert _load_profiles_from_env(None) == {}

    def test_empty_string_returns_empty(self):
        assert _load_profiles_from_env("") == {}

    def test_valid_json(self):
        raw = json.dumps({"fop": "Ти редактор ФОП"})
        result = _load_profiles_from_env(raw)
        assert result == {"fop": "Ти редактор ФОП"}

    def test_invalid_json_returns_empty(self):
        assert _load_profiles_from_env("{not valid json") == {}

    def test_non_dict_returns_empty(self):
        assert _load_profiles_from_env('["list", "not", "dict"]') == {}

    def test_ignores_non_string_values(self):
        raw = json.dumps({"valid": "prompt", "invalid": 123})
        result = _load_profiles_from_env(raw)
        assert "valid" in result
        assert "invalid" not in result


class TestLoadProfiles:
    def test_default_profile_exists(self, monkeypatch):
        monkeypatch.setattr("shared.gpt_profiles.settings.gpt_instructions_json", None)
        profiles = load_profiles()
        assert "default" in profiles
        assert profiles["default"] == EDITORIAL_PROMPT_UK

    def test_social_profile_exists(self, monkeypatch):
        monkeypatch.setattr("shared.gpt_profiles.settings.gpt_instructions_json", None)
        profiles = load_profiles()
        assert "social" in profiles
        assert profiles["social"] == SOCIAL_PROMPT_UK

    def test_env_overrides_default(self, monkeypatch):
        custom = json.dumps({"default": "Custom prompt"})
        monkeypatch.setattr("shared.gpt_profiles.settings.gpt_instructions_json", custom)
        profiles = load_profiles()
        assert profiles["default"] == "Custom prompt"


class TestGetPrompt:
    def test_none_returns_default(self, monkeypatch):
        monkeypatch.setattr("shared.gpt_profiles.settings.gpt_instructions_json", None)
        assert get_prompt(None) == EDITORIAL_PROMPT_UK

    def test_missing_profile_returns_default(self, monkeypatch):
        monkeypatch.setattr("shared.gpt_profiles.settings.gpt_instructions_json", None)
        assert get_prompt("nonexistent") == EDITORIAL_PROMPT_UK

    def test_social_returns_social_prompt(self, monkeypatch):
        monkeypatch.setattr("shared.gpt_profiles.settings.gpt_instructions_json", None)
        assert get_prompt("social") == SOCIAL_PROMPT_UK
