from typing import Annotated

from django.db import close_old_connections
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from jobs.choices import PostSource
from jobs.services import (
    DEFAULT_JOB_PAGE_SIZE,
    MAX_JOB_PAGE,
    MAX_JOB_PAGE_SIZE,
    MAX_JOB_QUERY_LENGTH,
    MAX_TECHNOLOGY_FILTERS,
    MAX_TECHNOLOGY_NAME_LENGTH,
    JobDetail,
    JobNotFoundError,
    JobQueryError,
    JobSearchResult,
    JobSource,
    get_job as get_job_data,
    search_jobs as search_jobs_data,
)

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

TechnologyName = Annotated[
    str,
    Field(min_length=1, max_length=MAX_TECHNOLOGY_NAME_LENGTH),
]

mcp = FastMCP(
    name="Tech Job Alerts",
    instructions=(
        "Search and inspect the public Tech Job Alerts jobs database. "
        "This server is read-only. Keep searches bounded, use search_jobs to discover "
        "matching roles, then use get_job when you need one complete job record."
    ),
)


@mcp.tool(
    name="search_jobs",
    description=(
        "Search public developer jobs by text, technologies, source, remote status, "
        "and salary. Returns a bounded page ordered newest first."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
)
def search_jobs(
    query: Annotated[
        str | None,
        Field(
            default=None,
            max_length=MAX_JOB_QUERY_LENGTH,
            description="Text to match across job, company, role, technology, and location data.",
        ),
    ] = None,
    technologies: Annotated[
        list[TechnologyName] | None,
        Field(
            default=None,
            max_length=MAX_TECHNOLOGY_FILTERS,
            description="Technology names every returned job must include.",
        ),
    ] = None,
    source: Annotated[
        JobSource | None,
        Field(default=None, description=f"One of: {', '.join(PostSource.values)}."),
    ] = None,
    remote: Annotated[
        bool | None,
        Field(default=None, description="Set true for remote jobs or false for jobs not marked remote."),
    ] = None,
    minimum_salary: Annotated[
        int | None,
        Field(default=None, ge=0, description="Minimum acceptable upper salary bound."),
    ] = None,
    page: Annotated[
        int,
        Field(default=1, ge=1, le=MAX_JOB_PAGE, description="One-based result page."),
    ] = 1,
    page_size: Annotated[
        int,
        Field(
            default=DEFAULT_JOB_PAGE_SIZE,
            ge=1,
            le=MAX_JOB_PAGE_SIZE,
            description=f"Jobs per page, up to {MAX_JOB_PAGE_SIZE}.",
        ),
    ] = DEFAULT_JOB_PAGE_SIZE,
) -> JobSearchResult:
    close_old_connections()
    try:
        return search_jobs_data(
            query=query,
            technologies=technologies,
            source=source,
            remote=remote,
            minimum_salary=minimum_salary,
            page=page,
            page_size=page_size,
        )
    except JobQueryError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        close_old_connections()


@mcp.tool(
    name="get_job",
    description="Return one complete public job record by its Tech Job Alerts job ID.",
    annotations=READ_ONLY_ANNOTATIONS,
)
def get_job(
    job_id: Annotated[str, Field(description="Tech Job Alerts job UUID.")],
) -> JobDetail:
    close_old_connections()
    try:
        return get_job_data(job_id)
    except JobNotFoundError as exc:
        raise ToolError(str(exc)) from exc
    finally:
        close_old_connections()
