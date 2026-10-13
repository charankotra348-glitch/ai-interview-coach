from app.config import settings
from app.db.session import SessionLocal
from app.llm.client import LLMClient
from app.llm.pricing import load_price_table
from app.llm.recorder import database_recorder


def _provider_and_model():
    if settings.llm_provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(settings.ollama_base_url), settings.ollama_model

    from app.llm.gemini_provider import GeminiProvider

    key = settings.gemini_api_key
    provider = GeminiProvider(key.get_secret_value() if key is not None else None)
    return provider, settings.gemini_model


def build_llm_client() -> LLMClient:
    provider, model = _provider_and_model()
    return LLMClient(
        provider,
        model=model,
        prices=load_price_table(),
        recorder=database_recorder(SessionLocal),
        timeout_s=settings.llm_timeout_s,
        max_attempts=settings.llm_max_attempts,
        budget_s=settings.llm_budget_s,
    )