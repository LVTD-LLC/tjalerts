from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from ninja import Schema
from pydantic import UUID4


class ReadCompany(Schema):
    id: UUID4
    name: str
    company_homepage_link: str


class ReadEmail(Schema):
    email: str
    name: str
    company__name: str
    company__compliment: str


class ReadEmails(Schema):
    count: int
    emails: List[ReadEmail]


# class ReadPost(Schema):
#     company__name: str
#     description: str
#     title_names: List[str]
#     technology_names: List[str]


# class ReadPosts(Schema):
#     count: int
#     posts: List[ReadPost]


class TechnologySchema(Schema):
    id: str
    name: str
    slug: str
    post_count: int


class TitleSchema(Schema):
    id: str
    name: str
    slug: str
    post_count: int


class CompanySchema(Schema):
    id: str
    name: str


class PostSchema(Schema):
    id: str
    description: str
    created_at: datetime
    company: CompanySchema


class SimilarPostsResponse(Schema):
    similar_posts: List[PostSchema]


class BlogPostCreateSchema(Schema):
    admin_key: str
    title: str
    slug: str
    content: str
    description: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = "DR"  # Corresponds to BlogPost.DRAFT


class JobEmailSchema(Schema):
    email: str
    name: str


class JobSchema(Schema):
    id: str
    company_name: str
    company_url: str
    description: str
    job_details: Dict[str, Any]
    compensation_summary: Optional[str]
    min_salary: Optional[int]
    max_salary: Optional[int]
    is_remote: bool
    locations: str
    technologies: List[str]
    title: List[str]
    source: str
    source_url: str
    source_external_id: str
    who_is_hiring_comment_id: Optional[int]
    submitted_datetime: datetime
    emails: List[JobEmailSchema]


class JobsResponse(Schema):
    count: int
    total: int
    page: int
    page_size: int
    total_pages: int
    jobs: List[JobSchema]
