from django.conf import settings
from django.db import models
from django.urls import reverse
from model_utils.models import TimeStampedModel


class BlogPost(TimeStampedModel):
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post")
    slug = models.SlugField(max_length=250)
    content = models.TextField()

    icon = models.ImageField(upload_to="images/", blank=True)

    DRAFT = "DR"
    PUBLISHED = "PB"
    PUBLISH_STATUS = [
        (DRAFT, "DRAFT"),
        (PUBLISHED, "PUBLISHED"),
    ]
    status = models.CharField(
        max_length=3,
        choices=PUBLISH_STATUS,
        default=DRAFT,
    )

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog-post", kwargs={"slug": self.slug})
