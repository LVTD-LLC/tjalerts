from datetime import datetime
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
