"""Runtime translator that supports language switching without restart."""

from __future__ import annotations

import json
import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "ar")
RTL_LANGS = frozenset({"ar"})


class Translator:
    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        self._dictionaries: dict[str, dict[str, str]] = {}
        for code in SUPPORTED_LANGS:
            self._dictionaries[code] = self._load(code)
        self._lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
        self._observers: list[Any] = []

    # -- loaders -----------------------------------------------------------
    def _load(self, code: str) -> dict[str, str]:
        try:
            raw = (files("ordertracker.i18n") / f"{code}.json").read_text(encoding="utf-8")
        except FileNotFoundError:
            here = Path(__file__).resolve().parent / f"{code}.json"
            raw = here.read_text(encoding="utf-8")
        return json.loads(raw)

    # -- API ---------------------------------------------------------------
    @property
    def lang(self) -> str:
        return self._lang

    @property
    def is_rtl(self) -> bool:
        return self._lang in RTL_LANGS

    def set_language(self, code: str) -> None:
        if code not in SUPPORTED_LANGS:
            raise ValueError(f"Unsupported language: {code}")
        if code == self._lang:
            return
        self._lang = code
        for observer in list(self._observers):
            observer(code)

    def add_observer(self, callback) -> None:
        self._observers.append(callback)

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate ``key`` using the current language with optional ``str.format`` args."""
        primary = self._dictionaries[self._lang]
        fallback = self._dictionaries[DEFAULT_LANG]
        template = primary.get(key) or fallback.get(key) or key
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, IndexError):
                return template
        return template


_singleton: Translator | None = None


def get_translator(lang: str = DEFAULT_LANG) -> Translator:
    global _singleton
    if _singleton is None:
        _singleton = Translator(lang)
    return _singleton
