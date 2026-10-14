from app.config import settings
from app.db.session import SessionLocal
from app.llm.client import LLMClient
from app.llm.pricing import load_price_table
from app.llm.recorder import database_recorder


def _provider_and_model(provider: str, model: str | None):
    if provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(settings.ollama_base_url), model or settings.ollama_model

    if provider != "gemini":
        raise ValueError(f"unknown LLM provider: {provider}")

    from app.llm.gemini_provider import GeminiProvider

    key = settings.gemini_api_key
    client = GeminiProvider(key.get_secret_value() if key is not None else None)
    return client, model or settings.gemini_model


def build_llm_client(
    *, provider: str | None = None, model: str | None = None, record: bool = True
) -> LLMClient:
    """The app's model client. The evaluation harness overrides provider and model, and
    turns off recording so eval calls never land in the llm_calls table."""
    llm, model_name = _provider_and_model(provider or settings.llm_provider, model)
    return LLMClient(
        llm,
        model=model_name,
        prices=load_price_table(),
        recorder=database_recorder(SessionLocal) if record else None,
        timeout_s=settings.llm_timeout_s,
        max_attempts=settings.llm_max_attempts,
        budget_s=settings.llm_budget_s,
    )
