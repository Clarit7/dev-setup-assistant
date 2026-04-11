"""
LLM 프로바이더별 사용 가능한 텍스트 생성 모델 목록 조회
"""
from __future__ import annotations

from typing import List


def fetch_models(
    provider: str,
    api_key: str = "",
    base_url: str = "",
) -> List[str]:
    """
    프로바이더 API에서 텍스트 생성 가능한 모델 목록을 반환합니다.
    실패 시 빈 리스트를 반환합니다.
    """
    try:
        if provider == "anthropic":
            return _fetch_anthropic(api_key)
        elif provider == "openai":
            return _fetch_openai(api_key)
        elif provider == "gemini":
            return _fetch_gemini(api_key)
        elif provider == "groq":
            return _fetch_groq(api_key)
        elif provider == "ollama":
            return _fetch_ollama(base_url or "http://localhost:11434")
        return []
    except Exception:
        return []


def _fetch_anthropic(api_key: str) -> List[str]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    page = client.models.list(limit=100)
    return [m.id for m in page.data]


def _fetch_openai(api_key: str) -> List[str]:
    import openai
    client = openai.OpenAI(api_key=api_key)
    models = client.models.list()
    keywords = ("gpt", "o1", "o3", "o4", "chatgpt")
    ids = [m.id for m in models.data if any(k in m.id for k in keywords)]
    return sorted(ids)


def _fetch_gemini(api_key: str) -> List[str]:
    from google import genai
    client = genai.Client(api_key=api_key)
    result = []
    for m in client.models.list():
        # supported_actions 또는 supported_generation_methods 확인
        supported = (
            getattr(m, "supported_actions", None)
            or getattr(m, "supported_generation_methods", None)
            or []
        )
        if any("generateContent" in s or "generate_content" in s for s in supported):
            name = m.name
            result.append(name.split("/")[-1] if "/" in name else name)
    return result


def _fetch_groq(api_key: str) -> List[str]:
    try:
        import groq
        client = groq.Groq(api_key=api_key)
        models = client.models.list()
        return sorted(
            m.id for m in models.data
            if getattr(m, "active", True)
        )
    except ImportError:
        import openai
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        models = client.models.list()
        return sorted(m.id for m in models.data)


def _fetch_ollama(base_url: str) -> List[str]:
    import requests
    resp = requests.get(f"{base_url}/api/tags", timeout=5)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]
