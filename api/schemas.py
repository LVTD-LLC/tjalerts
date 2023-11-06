from typing import List

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
