from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from shared.gpt_profiles import get_prompt
from shared.settings import settings

logger = logging.getLogger("openai_client")
_editor: "OpenAIEditor | None" = None


def get_editor() -> "OpenAIEditor | None":
    global _editor
    if _editor is not None:
        return _editor
    try:
        _editor = OpenAIEditor()
    except Exception:
        logger.exception("Failed to initialize OpenAI client")
        return None
    return _editor


class OpenAIEditor:
    def __init__(self) -> None:
        if settings.openrouter_api_key:
            self.client = OpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
            )
            self._model = settings.openrouter_model
            logger.info("llm_backend", extra={"backend": "openrouter", "model": self._model})
        elif settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
            self._model = settings.openai_text_model
            logger.info("llm_backend", extra={"backend": "openai", "model": self._model})
        else:
            raise ValueError("OPENROUTER_API_KEY or OPENAI_API_KEY is required.")

    def summarize(self, text: str, *, system_prompt: str | None = None) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt or get_prompt(None)},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse OpenAI response JSON. Returning fallback. Content: %s",
                content[:500],
            )
            return {
                "title": "",
                "body": content,
                "image_prompt": None,
                "error": "invalid_json_from_llm",
            }
        parsed["_model"] = response.model
        parsed["_tokens"] = response.usage.total_tokens if response.usage else None
        return parsed

    def generate_tweet(self, text: str) -> str:
        twitter_prompt = get_prompt("social")
        response = self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": twitter_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            max_tokens=150,
        )
        result = (response.choices[0].message.content or "").strip()
        if len(result) > 280:
            result = result[:277] + "..."
        return result

    def generate_image(self, prompt: str) -> str:
        response = self.client.images.generate(
            model=settings.openai_image_model,
            prompt=prompt,
            size="1024x1024",
        )
        return response.data[0].url
