"""Clients LLM : Anthropic (primaire) et Mistral (alternatif)."""

from __future__ import annotations

import json
import os
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return text


class LLMClient:
    """Interface du client LLM."""

    def call_structured(self, system_prompt: str, user_prompt: str, output_schema: type[T]) -> T:
        raise NotImplementedError

    def call_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        raise NotImplementedError


class AnthropicClient(LLMClient):
    """Client Anthropic Claude.

    Cle : https://console.anthropic.com — variable ANTHROPIC_API_KEY dans .env.
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, model: str | None = None):
        try:
            import anthropic as _anthropic
            self._anthropic = _anthropic
        except ImportError as e:
            raise ImportError("Le package 'anthropic' n'est pas installe.") from e

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY non defini. Remplis .env (cf .env.example)."
            )
        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _build_json_system(self, system_prompt: str, schema: type[BaseModel]) -> str:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        return (
            f"{system_prompt}\n\n"
            "REGLES DE FORMAT (strictes) :\n"
            "- Reponds UNIQUEMENT par un objet JSON valide, sans texte avant ou apres.\n"
            "- Pas de fences markdown (pas de ```json ni de ```).\n"
            "- Toutes les cles entre guillemets doubles.\n"
            "- Pas de commentaires, pas de virgules trainantes.\n\n"
            f"Schema JSON cible (Pydantic v2) :\n{schema_json}"
        )

    def call_structured(self, system_prompt: str, user_prompt: str, output_schema: type[T]) -> T:
        enriched = self._build_json_system(system_prompt, output_schema)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=enriched,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text
        cleaned = _strip_json_fences(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"JSON invalide dans la reponse Anthropic.\nErreur : {e}\n"
                f"Reponse brute (premiers 2000 chars) :\n{raw[:2000]}"
            ) from e
        try:
            return output_schema.model_validate(data)
        except ValidationError as e:
            raise RuntimeError(
                f"JSON valide mais ne respecte pas le schema {output_schema.__name__}.\n"
                f"Validation : {e}\nJSON recu :\n{json.dumps(data, indent=2)[:2000]}"
            ) from e

    def call_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text


class MistralClient(LLMClient):
    """Client Mistral (alternatif, meme API que I3)."""

    DEFAULT_MODEL = "mistral-medium-latest"

    def __init__(self, model: str | None = None):
        try:
            from mistralai.client import Mistral
        except ImportError as e:
            raise ImportError("Le package 'mistralai' n'est pas installe.") from e

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY non defini.")
        self._client = Mistral(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL
        self._min_interval_s = 1.2
        self._last_call_at: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        if elapsed < self._min_interval_s:
            time.sleep(self._min_interval_s - elapsed)
        self._last_call_at = time.monotonic()

    def _build_json_system(self, system_prompt: str, schema: type[BaseModel]) -> str:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        return (
            f"{system_prompt}\n\n"
            "REGLES DE FORMAT (strictes) :\n"
            "- Reponds UNIQUEMENT par un JSON valide, sans texte avant ou apres.\n"
            "- Pas de fences markdown.\n"
            f"Schema JSON cible :\n{schema_json}"
        )

    def call_structured(self, system_prompt: str, user_prompt: str, output_schema: type[T]) -> T:
        enriched = self._build_json_system(system_prompt, output_schema)
        self._throttle()
        response = self._client.chat.complete(
            model=self._model,
            messages=[
                {"role": "system", "content": enriched},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        cleaned = _strip_json_fences(raw)
        data = json.loads(cleaned)
        return output_schema.model_validate(data)

    def call_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        self._throttle()
        response = self._client.chat.complete(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
        )
        return response.choices[0].message.content
