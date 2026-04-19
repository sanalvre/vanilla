"""
Embedding generation service.

Generates float32 vector embeddings for text using the configured provider's
embedding model. Used for semantic search (sqlite-vec) and RAG context retrieval
in the agent pipeline.

Supported providers:
  OpenAI / OpenRouter — text-embedding-3-small (1536 dims), text-embedding-3-large (3072)
  Ollama              — nomic-embed-text (768 dims), mxbai-embed-large (1024)

Callers must handle None returns gracefully — embedding failures never block writes.
"""

import logging
from typing import Optional

import httpx

from config import VanillaConfig

logger = logging.getLogger("vanilla.embedding")

# Truncate input to ~8 000 tokens (≈ 32 000 chars) before embedding.
# OpenAI's embedding models accept up to 8 191 tokens; Ollama varies.
_MAX_EMBED_CHARS = 32_000


async def generate_embedding(
    text: str,
    config: VanillaConfig,
) -> Optional[list[float]]:
    """
    Generate a vector embedding for *text* using the configured embedding model.

    Returns a list of floats (length = config.llm.embedding_dims) on success,
    or None on any error so callers can degrade gracefully.
    """
    if not text or not text.strip():
        return None

    truncated = text[:_MAX_EMBED_CHARS]
    provider = config.llm.provider
    model = config.llm.embedding_model
    api_key = config.llm.api_key
    base_url = config.llm.base_url

    try:
        if provider == "ollama":
            return await _embed_ollama(truncated, model, base_url or "http://localhost:11434")
        else:
            # OpenAI, OpenRouter, Anthropic (via OpenAI-compatible endpoint)
            return await _embed_openai_compat(truncated, model, api_key, provider, base_url)
    except Exception as e:
        logger.warning("Embedding failed (provider=%s, model=%s): %s", provider, model, e)
        return None


async def _embed_openai_compat(
    text: str,
    model: str,
    api_key: str,
    provider: str,
    base_url: Optional[str],
) -> list[float]:
    """Call an OpenAI-compatible /v1/embeddings endpoint."""
    if provider == "openrouter":
        url = (base_url or "https://openrouter.ai/api/v1").rstrip("/") + "/embeddings"
    else:
        url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/embeddings"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"input": text, "model": model}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["data"][0]["embedding"]


async def _embed_ollama(
    text: str,
    model: str,
    base_url: str,
) -> list[float]:
    """Call Ollama's /api/embeddings endpoint."""
    url = base_url.rstrip("/") + "/api/embeddings"
    payload = {"model": model, "prompt": text}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return data["embedding"]
