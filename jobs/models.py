import uuid

from autoslug import AutoSlugField
from django.db import models
from django.urls import reverse
from model_utils.models import TimeStampedModel
from pgvector.django import VectorField

from utils.models import BaseModel


class Post(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    who_is_hiring_id = models.IntegerField()
    who_is_hiring_title = models.CharField(max_length=25)
    who_is_hiring_comment_id = models.IntegerField(unique=True)
    hn_username = models.CharField(max_length=50, blank=True)
    submitted_datetime = models.DateTimeField()

    jobs = models.ManyToManyField("Title", related_name="post", blank=True, through="PostTitle")
    description = models.TextField(blank=True)
    levels_of_experience = models.TextField(blank=True)
    technologies = models.ManyToManyField("Technology", related_name="post", blank=True, through="PostTechnology")
    capacity = models.TextField(blank=True)
    years_of_experience = models.TextField(blank=True)
    vector = VectorField(null=True)

    compensation_summary = models.TextField(blank=True, null=True)
    min_salary = models.IntegerField(null=True, default=None)
    max_salary = models.IntegerField(null=True, default=None)
    currency = models.CharField(blank=True)

    # GEO
    locations = models.TextField(blank=True)
    cities = models.TextField(blank=True)
    countries = models.CharField(max_length=100, blank=True)
    is_remote = models.BooleanField(default=False)
    is_onsite = models.BooleanField(default=False)
    remote_timezones = models.TextField(blank=True)

    # Secret
    company = models.ForeignKey("Company", on_delete=models.CASCADE)
    company_job_application_link = models.URLField(max_length=350, blank=True)
    names_of_the_contact_person = models.TextField(blank=True)
    emails = models.TextField(blank=True)

    # To Remove
    technologies_used = models.ManyToManyField("Technology", related_name="job", blank=True)
    job_titles = models.ManyToManyField("Title", related_name="job", blank=True)

    def get_absolute_url(self):
        return reverse("post", kwargs={"pk": self.id})

    def split_application_links(self):
        links = self.company_job_application_link.split(",")
        return [link.strip() for link in links]

    class Meta:
        ordering = ("-submitted_datetime",)


class Technology(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    slug = AutoSlugField(populate_from="name", always_update=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "name",
                ]
            ),
        ]


class Title(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    slug = AutoSlugField(populate_from="name", always_update=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "name",
                ]
            ),
        ]


class Company(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    company_homepage_link = models.URLField(blank=True)
    slug = AutoSlugField(populate_from="name", always_update=True)
    emails = models.TextField(blank=True)
    compliment = models.TextField(blank=True)

    @property
    def fixed_company_homepage_link(self):
        if not self.company_homepage_link.startswith("http"):
            self.company_homepage_link = "https://" + self.company_homepage_link

        return self.company_homepage_link

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "name",
                ]
            ),
        ]


class Email(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True)
    email_is_valid = models.BooleanField(default=False)
    email_is_generic = models.BooleanField(default=True)
    name = models.CharField(max_length=256)
    company = models.ForeignKey("Company", related_name="email", on_delete=models.CASCADE)
    post = models.ForeignKey("Post", related_name="email", on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)


class PostTitle(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    title = models.ForeignKey(Title, on_delete=models.CASCADE)


class PostTechnology(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    technology = models.ForeignKey(Technology, on_delete=models.CASCADE)


class Alert(BaseModel):
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, null=True, blank=True)

    email = models.EmailField()
    confirmed = models.BooleanField(default=False)
    unsubscribed = models.BooleanField(default=False)

    name = models.CharField(max_length=100, blank=True)
    filter = models.JSONField()
