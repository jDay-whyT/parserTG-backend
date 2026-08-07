from __future__ import annotations

from pathlib import Path

_PERSONA_DIR = Path(__file__).resolve().parent.parent / "persona"


def _read(filename: str) -> str:
    return (_PERSONA_DIR / filename).read_text(encoding="utf-8").strip()


def load_persona_prompt() -> str:
    return "\n\n".join(_read(name) for name in ("SOUL.md", "PROFILE.md", "AGENTS.md"))
