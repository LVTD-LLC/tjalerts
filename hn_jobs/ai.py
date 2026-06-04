from functools import lru_cache

from django.conf import settings
from django.test.signals import setting_changed
from pydantic import BaseModel, Field
from pydantic_ai import Agent, Embedder
from pydantic_ai.embeddings import EmbeddingSettings
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.exceptions import AgentRunError, UserError
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider


AIRequestError = (AgentRunError, UserError)
AI_CACHE_SETTINGS = {
    "AI_EMBEDDING_DIMENSIONS",
    "AI_RESULT_RETRIES",
    "OPENROUTER_API_KEY",
    "OPENROUTER_APP_TITLE",
    "OPENROUTER_APP_URL",
    "OPENROUTER_BASE_URL",
}


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
    job_details: "JobDetailsResult" = Field(default_factory=lambda: JobDetailsResult())


class JobDetailsResult(BaseModel):
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    nice_to_have_technologies: list[str] = Field(default_factory=list)
    timezone_requirements: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    duplicate_signals: list[str] = Field(default_factory=list)
    remote_policy: str = ""
    remote_scope: str = ""
    travel_requirements: str = ""
    relocation_support: str = ""
    visa_sponsorship: str = ""
    work_authorization: str = ""
    security_clearance: str = ""
    employment_type: str = ""
    salary_period: str = ""
    salary_location_basis: str = ""
    compensation_notes: str = ""
    equity: str = ""
    bonus: str = ""
    application_instructions: str = ""
    application_email_subject: str = ""
    portfolio_required: str = ""
    github_required: str = ""
    cover_letter_required: str = ""
    application_deadline: str = ""
    direct_apply: str = ""
    industry: str = ""
    product_or_service: str = ""
    company_hq: str = ""
    company_size: str = ""
    company_stage: str = ""
    company_funding: str = ""
    open_source: str = ""
    company_mission: str = ""
    job_status: str = ""
    canonical_job_url: str = ""
    extraction_confidence: str = ""


JobExtractionResult.model_rebuild()


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
    required_technologies: list[str] = Field(default_factory=list)
    nice_to_have_technologies: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_policy: str = ""
    remote_scope: str = ""
    timezone_requirements: list[str] = Field(default_factory=list)
    travel_requirements: str = ""
    relocation_support: str = ""
    visa_sponsorship: str = ""
    work_authorization: str = ""
    security_clearance: str = ""
    compensation: str = ""
    salary_period: str = ""
    salary_location_basis: str = ""
    equity: str = ""
    bonus: str = ""
    benefits: list[str] = Field(default_factory=list)
    seniority: str = ""
    employment_type: str = ""
    application_instructions: str = ""
    application_email_subject: str = ""
    portfolio_required: str = ""
    github_required: str = ""
    cover_letter_required: str = ""
    application_deadline: str = ""
    direct_apply: str = ""
    company_hq: str = ""
    company_size: str = ""
    company_stage: str = ""
    company_funding: str = ""
    open_source: str = ""
    company_mission: str = ""
    job_status: str = ""
    canonical_job_url: str = ""
    duplicate_signals: list[str] = Field(default_factory=list)
    notable_links: list[str] = Field(default_factory=list)
    confidence: str = ""


def run_structured_ai_task(model_name, system_prompt, user_prompt, output_type):
    agent = get_structured_agent(
        normalize_openrouter_model_name(model_name),
        system_prompt,
        output_type,
        settings.AI_RESULT_RETRIES,
        settings.OPENROUTER_API_KEY,
        settings.OPENROUTER_APP_URL,
        settings.OPENROUTER_APP_TITLE,
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
    """Add an OpenRouter provider prefix when a bare OpenAI model name is configured."""
    if not model_name or "/" in model_name or model_name.startswith("~"):
        return model_name

    if model_name.startswith(("gpt-", "o1", "o3", "o4", "text-embedding", "chatgpt", "codex")):
        return f"openai/{model_name}"

    raise UserError(
        f"Model name {model_name!r} has no provider prefix. "
        "Only bare OpenAI model names are auto-prefixed; use provider/name for other OpenRouter models."
    )


@lru_cache(maxsize=64)
def get_structured_agent(model_name, system_prompt, output_type, retries, api_key, app_url, app_title):
    return Agent(
        get_openrouter_model(model_name, api_key, app_url, app_title),
        instructions=system_prompt,
        output_type=output_type,
        retries=retries,
    )


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


def clear_ai_caches(*, setting=None, **kwargs):
    if setting in AI_CACHE_SETTINGS:
        get_structured_agent.cache_clear()
        get_openrouter_model.cache_clear()
        get_openrouter_embedder.cache_clear()


setting_changed.connect(clear_ai_caches)
