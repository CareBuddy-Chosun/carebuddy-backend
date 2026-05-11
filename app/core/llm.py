"""Provider-agnostic LLM and Embeddings factory.

Switch models by changing LLM_PROVIDER / LLM_MODEL in .env — no code changes needed.

Supported LLM providers:  openai, google, anthropic
Supported Embedding providers: openai, google
"""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from app.core.config import settings

# ── Default models per provider ──────────────────────────────────────────────

_DEFAULT_CHAT_MODELS = {
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash",
    "anthropic": "claude-sonnet-4-20250514",
}

_DEFAULT_EMBEDDING_MODELS = {
    "openai": "text-embedding-3-small",
    "google": "models/embedding-001",
}


# ── Chat LLM factory ────────────────────────────────────────────────────────

@lru_cache()
def get_chat_llm() -> BaseChatModel:
    """Return a LangChain ChatModel based on env settings."""
    provider = settings.LLM_PROVIDER.lower()
    model = settings.LLM_MODEL or _DEFAULT_CHAT_MODELS.get(provider)
    temperature = settings.LLM_TEMPERATURE
    max_tokens = settings.LLM_MAX_TOKENS

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


# ── Embeddings factory ───────────────────────────────────────────────────────

@lru_cache()
def get_embeddings() -> Embeddings:
    """Return a LangChain Embeddings model based on env settings."""
    provider = (settings.EMBEDDING_PROVIDER or settings.LLM_PROVIDER).lower()
    model = settings.EMBEDDING_MODEL or _DEFAULT_EMBEDDING_MODELS.get(provider)

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=model,
            api_key=settings.OPENAI_API_KEY,
        )

    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
        )

    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER: {provider}. "
        "Supported: openai, google"
    )
