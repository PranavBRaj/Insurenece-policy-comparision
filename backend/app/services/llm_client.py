from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from groq import Groq

from app.config import settings

_VALID_PROVIDERS = {"groq", "ollama"}


def resolve_llm_provider(provider: Optional[str] = None) -> str:
	selected = (provider or settings.LLM_PROVIDER or "groq").strip().lower()
	if selected not in _VALID_PROVIDERS:
		raise ValueError(
			f"Invalid llm provider '{selected}'. Use one of: {', '.join(sorted(_VALID_PROVIDERS))}"
		)
	return selected


def llm_chat_completion(
	messages: List[Dict[str, str]],
	*,
	provider: Optional[str] = None,
	temperature: float = 0.1,
	max_tokens: int = 2048,
	json_mode: bool = False,
) -> str:
	selected = resolve_llm_provider(provider)
	if selected == "groq":
		return _groq_chat_completion(
			messages,
			temperature=temperature,
			max_tokens=max_tokens,
			json_mode=json_mode,
		)
	return _ollama_chat_completion(
		messages,
		temperature=temperature,
		max_tokens=max_tokens,
		json_mode=json_mode,
	)


def _groq_chat_completion(
	messages: List[Dict[str, str]],
	*,
	temperature: float,
	max_tokens: int,
	json_mode: bool,
) -> str:
	if not settings.GROQ_API_KEY:
		raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")

	client = Groq(api_key=settings.GROQ_API_KEY)
	kwargs: Dict[str, Any] = {
		"model": settings.GROQ_MODEL,
		"messages": messages,
		"temperature": temperature,
		"max_tokens": max_tokens,
	}
	if json_mode:
		kwargs["response_format"] = {"type": "json_object"}

	response = client.chat.completions.create(**kwargs)
	return response.choices[0].message.content or ""


def _ollama_chat_completion(
	messages: List[Dict[str, str]],
	*,
	temperature: float,
	max_tokens: int,
	json_mode: bool,
) -> str:
	payload: Dict[str, Any] = {
		"model": settings.OLLAMA_MODEL,
		"messages": messages,
		"stream": False,
		"options": {
			"temperature": temperature,
			"num_predict": max_tokens,
		},
	}
	if json_mode:
		payload["format"] = "json"

	endpoint = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"

	try:
		with httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
			response = client.post(endpoint, json=payload)
			response.raise_for_status()
	except httpx.HTTPStatusError as exc:
		detail = exc.response.text
		raise ValueError(f"Ollama API error ({exc.response.status_code}): {detail}") from exc
	except httpx.HTTPError as exc:
		raise ValueError(f"Ollama API request failed: {exc}") from exc

	try:
		data = response.json()
	except json.JSONDecodeError as exc:
		raise ValueError(f"Ollama returned non-JSON response: {exc}") from exc

	content = (data.get("message") or {}).get("content")
	if not content:
		raise ValueError("Ollama response did not contain message.content")

	return content
