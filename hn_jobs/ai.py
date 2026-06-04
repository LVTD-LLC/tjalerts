from functools import lru_cache

from django.conf import settings
from pydantic import BaseModel, Field
from pydantic_ai import Agent, Embedder
from pydantic_ai.embeddings import EmbeddingSettings
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider


AIRequestError = AgentRunError


class AIResult(BaseModel):
    output: object
    usage: object | None = None

    model_config = {"arbitrary_types_allowed": True}


class JobExtractionResult(BaseModel):
    company_name: str = ""
    job_titles: str = ""
    locations: str = ""
    cities: str = ""
    countries: str = ""
    compensation_summary: str = ""
    min_salary: int = 0
    max_salary: int = 0
    currency: str = ""
    is_remote: bool = False
    remote_timezones: str = ""
    is_onsite: bool = False
    capacity: str = ""
    description: str = ""
    technologies_used: str = ""
    company_homepage_link: str = ""
    emails: str = ""
    company_job_application_link: str = ""
    names_of_the_contact_person: str = ""
    years_of_experience: str = ""
    levels_of_experience: str = ""


class SalaryExtractionResult(BaseModel):
    min_salary: int = Field(default=0, ge=0)
    max_salary: int = Field(default=0, ge=0)
    currency: str = ""


class PageContextResult(BaseModel):
    page_summary: str = ""
    company_name: str = ""
    product_or_service: str = ""
    industry: str = ""
    hiring_signal: str = ""
    job_titles: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_policy: str = ""
    compensation: str = ""
    benefits: list[str] = Field(default_factory=list)
    seniority: str = ""
    employment_type: str = ""
    application_instructions: str = ""
    notable_links: list[str] = Field(default_factory=list)
    confidence: str = ""


def run_structured_ai_task(model_name, system_prompt, user_prompt, output_type):
    agent = Agent(
        get_openrouter_model(
            normalize_openrouter_model_name(model_name),
            settings.OPENROUTER_API_KEY,
            settings.OPENROUTER_APP_URL,
            settings.OPENROUTER_APP_TITLE,
        ),
        instructions=system_prompt,
        output_type=output_type,
        retries=settings.AI_RESULT_RETRIES,
    )
    result = agent.run_sync(user_prompt)
    return AIResult(output=result.output, usage=result.usage)


def embed_query(text, model_name=None):
    model_name = model_name or settings.AI_EMBEDDING_MODEL
    embedder = get_openrouter_embedder(
        normalize_openrouter_model_name(model_name),
        settings.AI_EMBEDDING_DIMENSIONS,
        settings.OPENROUTER_API_KEY,
        settings.OPENROUTER_BASE_URL,
        settings.OPENROUTER_APP_URL,
        settings.OPENROUTER_APP_TITLE,
    )
    result = embedder.embed_query_sync(text)
    return AIResult(output=list(result.embeddings[0]), usage=result.usage)


def normalize_openrouter_model_name(model_name):
    if not model_name or "/" in model_name or model_name.startswith("~"):
        return model_name

    if model_name.startswith(("gpt-", "o1", "o3", "o4", "text-embedding", "chatgpt", "codex")):
        return f"openai/{model_name}"

    return model_name


@lru_cache(maxsize=32)
def get_openrouter_model(model_name, api_key, app_url, app_title):
    provider = OpenRouterProvider(
        api_key=api_key or None,
        app_url=app_url or None,
        app_title=app_title or None,
    )
    model_settings = OpenRouterModelSettings(openrouter_usage={"include": True})
    return OpenRouterModel(model_name, provider=provider, settings=model_settings)


@lru_cache(maxsize=8)
def get_openrouter_embedder(model_name, dimensions, api_key, base_url, app_url, app_title):
    provider = OpenAIProvider(
        base_url=base_url,
        api_key=api_key or None,
    )
    model = OpenAIEmbeddingModel(
        model_name,
        provider=provider,
        settings=EmbeddingSettings(
            dimensions=dimensions,
            extra_headers=openrouter_headers(app_url, app_title),
        ),
    )
    return Embedder(model)


def openrouter_headers(app_url, app_title):
    headers = {}
    if app_url:
        headers["HTTP-Referer"] = app_url
    if app_title:
        headers["X-Title"] = app_title
    return headers


def ai_usage_properties(usage):
    if not usage:
        return {}

    prompt_tokens = getattr(usage, "input_tokens", None)
    completion_tokens = getattr(usage, "output_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)

    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
