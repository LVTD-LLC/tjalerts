import uuid

from autoslug import AutoSlugField
from django.db import models
from django.urls import reverse
from model_utils.models import TimeStampedModel
from pgvector.django import HnswIndex, VectorField

from jobs.choices import PostSource
from utils.models import BaseModel


class Post(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitted_datetime = models.DateTimeField()

    # HN Specific
    who_is_hiring_id = models.IntegerField(null=True, blank=True)
    who_is_hiring_title = models.CharField(max_length=25, blank=True)
    who_is_hiring_comment_id = models.IntegerField(unique=True, null=True, blank=True)
    hn_username = models.CharField(max_length=50, blank=True)

    source = models.CharField(
        max_length=200,
        choices=PostSource.choices,
        default=PostSource.HACKER_NEWS,
    )
    source_external_id = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)

    original_text = models.TextField(blank=True)
    titles = models.ManyToManyField("Title", related_name="post", blank=True, through="PostTitle")
    description = models.TextField(blank=True)
    job_details = models.JSONField(default=dict, blank=True)
    company_homepage_context = models.JSONField(default=dict, blank=True)
    company_homepage_reader_content = models.TextField(blank=True, default="")
    job_posting_context = models.JSONField(default=dict, blank=True)
    job_posting_reader_content = models.TextField(blank=True, default="")
    levels_of_experience = models.TextField(blank=True)
    technologies = models.ManyToManyField("Technology", related_name="post", blank=True, through="PostTechnology")
    capacity = models.TextField(blank=True)
    years_of_experience = models.TextField(blank=True)
    vector = VectorField(null=True, dimensions=1536)

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
        indexes = [
            HnswIndex(name="vector_index", fields=["vector"], m=16, ef_construction=64, opclasses=["vector_l2_ops"]),
            HnswIndex(
                name="vectors_index_2",
                fields=["vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            models.Index(fields=["who_is_hiring_comment_id"], name="index_who_is_hiring_comment_id"),
            models.Index(fields=["source", "source_external_id"], name="index_post_source_ext_id"),
            models.Index(fields=["submitted_datetime"], name="index_post_submitted_datetime"),
            models.Index(fields=["created"], name="index_post_created"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_external_id"],
                condition=~models.Q(source_external_id=""),
                name="unique_post_source_external_id",
            ),
        ]


class Technology(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    slug = AutoSlugField(populate_from="name", always_update=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["name"], name="index_t_technology_name"),
            models.Index(fields=["id"], name="index_t_technology_id"),
            models.Index(fields=["slug"], name="index_t_technology_slug"),
        ]


class Title(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    slug = AutoSlugField(populate_from="name", always_update=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["name"], name="index_title_title_name"),
            models.Index(fields=["id"], name="index_title_title_id"),
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
            models.Index(fields=["name"], name="index_company_name"),
            models.Index(fields=["company_homepage_link"], name="index_company_homepage_link"),
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

    class Meta:
        indexes = [
            models.Index(fields=["email"], name="index_email"),
            models.Index(fields=["email_is_valid", "email_is_generic", "is_approved"], name="index_email_flags"),
        ]


class PostTitle(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    title = models.ForeignKey(Title, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["post_id", "title_id"], name="index_post_id_title_id"),
            models.Index(fields=["title_id"], name="index_posttitle_title_id"),
        ]


class PostTechnology(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    technology = models.ForeignKey(Technology, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=["post_id", "technology_id"], name="index_post_id_technology_id"),
            models.Index(fields=["technology_id"], name="index_pt_technology_id"),
        ]


class Alert(BaseModel):
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, null=True, blank=True)

    email = models.EmailField()
    confirmed = models.BooleanField(default=False)
    unsubscribed = models.BooleanField(default=False)

    name = models.CharField(max_length=100, blank=True)
    filter = models.JSONField()


class AlertEmailSend(BaseModel):
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField()


class TechnologyMapping(BaseModel):
    parent = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name="parent")
    child = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name="child")

    class Meta:
        unique_together = ("parent", "child")
        indexes = [
            models.Index(fields=["child_id"], name="index_child_id"),
            models.Index(fields=["parent_id"], name="index_parent_id"),
            models.Index(fields=["child_id", "parent_id"], name="index_child_id_parent_id"),
        ]
