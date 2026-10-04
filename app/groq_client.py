from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings


def extract_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Model returned non-JSON output: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Model JSON was not an object.")
    return parsed


def groq_chat(prompt: str, system: str) -> str:
    if not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    last_error = ""
    for use_json_mode in (True, False):
        body: dict[str, Any] = {
            "model": settings.groq_model,
            "temperature": 0.2,
            "messages": messages,
        }
        if use_json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(settings.groq_api_url, headers=headers, json=body)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI service is unavailable.") from exc

        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Groq rate limit reached. Wait a minute and retry.")
        if response.status_code >= 400:
            last_error = response.text[:400]
            continue
        try:
            data = response.json()
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Groq returned an unexpected payload.") from exc

    raise HTTPException(status_code=502, detail=f"Groq error: {last_error or 'unknown'}")
