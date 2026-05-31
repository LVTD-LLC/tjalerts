import json
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from html import unescape

import httpx
import openai
import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django_q.tasks import async_task
from openai import OpenAI

from hn_jobs.utils import get_tjalerts_logger
from users.models import CustomUser

from jobs.choices import PostSource
from jobs.filters import PostFilter
from jobs.models import Alert, AlertEmailSend, Company, Email, Post, Technology, Title
from jobs.utils import clean_job_json_object, fix_email, get_embedding, has_number, is_generic

logger = get_tjalerts_logger(__name__)

client = OpenAI()

MAX_COMPANY_EMAILS_LENGTH = 2000
REMOTE_OK_API_URL = "https://remoteok.com/api"
REMOTE_OK_USER_AGENT = "gettjalerts.com jobs importer (https://gettjalerts.com)"
MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2", "\u00d8", "\u00d9")


def build_job_extraction_request(text):
    return f""""Convert the text below into json object with the following valid keys (give me an empty string if there is no info, ignore the content in  brackets, it is only to explain what I need):
        - company_name - (string)
        - job_titles - (string of comma separated values)
        - locations - (string of comma separated values)
        - cities - (string of comma separated values)
        - countries - (string of comma separated values)
        - compensation_summary - (string, decribe the salary or other benefits)
        - min_salary - (integer, if not available return 0)
        - max_salary - (integer, if not available return 0)
        - currency: (string, e.g "USD", "EUR", etc. if not available return "")
        - is_remote - (boolean)
        - remote_timezones - (string of comma separated values)
        - is_onsite - (boolean)
        - capacity - (string of comma separated values, options are 'Part-time Contractor', 'Full-time Contractor', 'Part-time Employee' and 'Full-time Employee', can't be empty)
        - description
        - technologies_used - (string of comma separated values, list of technologies that I might need to know and will use at this jobs)
        - company_homepage_link - (url link)
        - emails - (string of comma separated values)
        - company_job_application_link - (url link)
        - names_of_the_contact_person - (string of comma separated values)
        - years_of_experience - (string of comma separated values, years of experience required to apply)
        - levels_of_experience - (choose from these options: Junior, Mid-level, Senior, Principal, C-Level. figure out from description, can't be empty)

        Don't add any text and only respond with a JSON Object.

        Text: '''
        {text}
        '''
    """  # noqa: E501


def extract_job_data_from_text(text):
    try:
        completion = client.chat.completions.create(
            model=settings.OPENAI_JOB_EXTRACTION_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {"role": "user", "content": build_job_extraction_request(text)},
            ],
        )
        converted_comment_response = completion.choices[0].message
    except (openai.RateLimitError, openai.APIError) as e:
        raise e

    try:
        return json.loads(converted_comment_response.content)
    except json.decoder.JSONDecodeError as e:
        raise e


def split_comma_separated_values(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def coerce_salary(value):
    if value in ["", None]:
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def create_post_from_cleaned_data(
    cleaned_data,
    *,
    source,
    submitted_datetime,
    vector,
    source_external_id="",
    source_url="",
    source_payload=None,
    who_is_hiring_id=None,
    who_is_hiring_title="",
    who_is_hiring_comment_id=None,
    hn_username="",
):
    technology_names = split_comma_separated_values(cleaned_data["technologies_used"])
    technologies = []
    for name in technology_names:
        obj, _ = Technology.objects.get_or_create(name=name)
        technologies.append(obj)

    job_title_names = split_comma_separated_values(cleaned_data["job_titles"])
    job_titles = []
    for job_title in job_title_names:
        obj, _ = Title.objects.get_or_create(name=job_title)
        job_titles.append(obj)

    company_obj, _ = Company.objects.get_or_create(name=cleaned_data["company_name"])
    if cleaned_data["company_homepage_link"]:
        company_obj.company_homepage_link = cleaned_data["company_homepage_link"]
    company_obj.emails = merge_company_emails(company_obj.emails, cleaned_data["emails"])
    company_obj.save()

    post = Post(
        who_is_hiring_id=who_is_hiring_id,
        who_is_hiring_title=who_is_hiring_title,
        who_is_hiring_comment_id=who_is_hiring_comment_id,
        submitted_datetime=submitted_datetime,
        company=company_obj,
        source=source,
        source_external_id=str(source_external_id or ""),
        source_url=source_url,
        source_payload=source_payload or {},
        original_text=cleaned_data["original_text"],
        hn_username=hn_username,
        description=cleaned_data["description"],
        locations=cleaned_data["locations"],
        cities=cleaned_data["cities"],
        countries=cleaned_data["countries"],
        is_remote=cleaned_data["is_remote"],
        remote_timezones=cleaned_data["remote_timezones"],
        is_onsite=cleaned_data["is_onsite"],
        years_of_experience=cleaned_data["years_of_experience"],
        capacity=cleaned_data["capacity"],
        compensation_summary=cleaned_data["compensation_summary"],
        min_salary=coerce_salary(cleaned_data["min_salary"]),
        max_salary=coerce_salary(cleaned_data["max_salary"]),
        currency=cleaned_data["currency"],
        company_job_application_link=cleaned_data["company_job_application_link"],
        names_of_the_contact_person=cleaned_data["names_of_the_contact_person"],
        levels_of_experience=cleaned_data["levels_of_experience"],
        emails=cleaned_data["emails"],
        vector=vector,
    )
    post.save()

    post.technologies.add(*technologies)
    post.titles.add(*job_titles)

    return post


def merge_company_emails(existing_emails, new_emails):
    """Keep Company.emails as a bounded, comma-separated summary.

    Post.emails and the Email model are the source of truth for extracted
    contact info. Company.emails is only a denormalized convenience field, so
    it should never grow without bound or break unrelated company saves.
    """

    emails = []
    seen = set()

    for email_blob in (existing_emails, new_emails):
        for email in email_blob.split(","):
            email = email.strip()
            if email and email not in seen:
                emails.append(email)
                seen.add(email)

    return ", ".join(emails)[:MAX_COMPANY_EMAILS_LENGTH]


def get_hn_pages_to_analyze(who_is_hiring_post_id):
    data = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{who_is_hiring_post_id}.json").json()

    if "Who is hiring" not in data["title"]:
        return "Not a Who is hiring post"

    list_of_comment_ids = data["kids"]

    # if working in dev don't want to go through all the comments
    if settings.DEBUG:
        list_of_comment_ids = list_of_comment_ids[:150]

    count = 0
    for comment_id in list_of_comment_ids:
        if (
            not Post.objects.filter(who_is_hiring_comment_id=comment_id).exists()
            and comment_id != who_is_hiring_post_id
        ):
            async_task(
                analyze_hn_page,
                int(data["id"]),
                str(re.search(r"\(([^)]+)", data["title"]).group(1)),
                comment_id,
                hook="jobs.hooks.print_result",
                group="Analyze HN Page",
            )
            count += 1

    try:
        httpx.get(f"{settings.HEALTHCHECKS_HOST}/e79df9c2-8e2d-4e0a-8be8-1723682c375d", timeout=10)
    except httpx.RequestException as e:
        logger.error("Ping failed", error=e)

    return f"{count} have been sent to be analyzed."


def analyze_hn_page(who_is_hiring_id, who_is_hiring_title, comment_id):
    json_job = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json").json()

    try:
        if json_job["deleted"] is True:
            return "Comment was deleted"
    except KeyError:
        pass

    who_is_hiring_comment_id = int(json_job["id"])
    if (
        Post.objects.filter(source=PostSource.HACKER_NEWS, source_external_id=str(who_is_hiring_comment_id)).exists()
        or Post.objects.filter(who_is_hiring_comment_id=who_is_hiring_comment_id).exists()
    ):
        return "Comment already exists"

    hn_username = str(json_job["by"])
    unix_timestamp = int(json_job["time"])
    vector = get_embedding(json_job["text"])

    cleaned_data = clean_job_json_object(json_job, extract_job_data_from_text(json_job["text"]))
    create_post_from_cleaned_data(
        cleaned_data,
        source=PostSource.HACKER_NEWS,
        source_external_id=who_is_hiring_comment_id,
        source_url=f"https://news.ycombinator.com/item?id={who_is_hiring_comment_id}",
        source_payload=json_job,
        who_is_hiring_id=who_is_hiring_id,
        who_is_hiring_title=who_is_hiring_title,
        who_is_hiring_comment_id=who_is_hiring_comment_id,
        hn_username=hn_username,
        submitted_datetime=datetime.fromtimestamp(unix_timestamp, tz=dt_timezone.utc),
        vector=vector,
    )

    return "Comment is saved."


def clean_remote_ok_string(value):
    value = str(value or "")

    if any(marker in value for marker in MOJIBAKE_MARKERS):
        try:
            value = value.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return unescape(value).strip()


def clean_remote_ok_description(value):
    return re.sub(r"\s+", " ", strip_tags(clean_remote_ok_string(value))).strip()


def fetch_remote_ok_jobs():
    response = httpx.get(
        REMOTE_OK_API_URL,
        headers={"User-Agent": REMOTE_OK_USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    return [item for item in data if isinstance(item, dict) and item.get("id")]


def build_remote_ok_extraction_text(remote_ok_job):
    company = clean_remote_ok_string(remote_ok_job.get("company"))
    position = clean_remote_ok_string(remote_ok_job.get("position"))
    location = clean_remote_ok_string(remote_ok_job.get("location"))
    description = clean_remote_ok_description(remote_ok_job.get("description"))
    tags = ", ".join(clean_remote_ok_string(tag) for tag in remote_ok_job.get("tags", []) if tag)

    parts = [
        f"Company: {company}" if company else "",
        f"Job title: {position}" if position else "",
        "Source: Remote OK",
        "Work arrangement: Remote",
        f"Location: {location}" if location else "",
        f"Tags: {tags}" if tags else "",
        f"Salary min: {remote_ok_job.get('salary_min')}" if remote_ok_job.get("salary_min") else "",
        f"Salary max: {remote_ok_job.get('salary_max')}" if remote_ok_job.get("salary_max") else "",
        f"Description: {description}" if description else "",
    ]

    return "\n".join(part for part in parts if part)


def build_remote_ok_compensation_summary(remote_ok_job):
    salary_min = coerce_salary(remote_ok_job.get("salary_min"))
    salary_max = coerce_salary(remote_ok_job.get("salary_max"))

    if salary_min and salary_max and salary_min != salary_max:
        return f"{salary_min} - {salary_max}"
    if salary_min:
        return str(salary_min)
    if salary_max:
        return str(salary_max)
    return ""


def apply_remote_ok_structured_defaults(remote_ok_job, extracted_data):
    company = clean_remote_ok_string(remote_ok_job.get("company"))
    position = clean_remote_ok_string(remote_ok_job.get("position"))
    location = clean_remote_ok_string(remote_ok_job.get("location"))
    application_link = clean_remote_ok_string(remote_ok_job.get("apply_url")) or clean_remote_ok_string(
        remote_ok_job.get("url")
    )
    compensation_summary = build_remote_ok_compensation_summary(remote_ok_job)
    salary_min = coerce_salary(remote_ok_job.get("salary_min"))
    salary_max = coerce_salary(remote_ok_job.get("salary_max"))

    extracted_data["company_name"] = extracted_data.get("company_name") or company
    extracted_data["job_titles"] = extracted_data.get("job_titles") or position
    extracted_data["locations"] = extracted_data.get("locations") or location
    extracted_data["is_remote"] = True
    extracted_data["company_job_application_link"] = (
        extracted_data.get("company_job_application_link") or application_link
    )

    if compensation_summary:
        extracted_data["compensation_summary"] = compensation_summary
        extracted_data["min_salary"] = salary_min
        extracted_data["max_salary"] = salary_max

    return extracted_data


def create_remote_ok_post(remote_ok_job):
    remote_ok_id = str(remote_ok_job["id"])
    existing_post = Post.objects.filter(source=PostSource.REMOTE_OK, source_external_id=remote_ok_id).first()
    if existing_post:
        return existing_post

    extraction_text = build_remote_ok_extraction_text(remote_ok_job)
    source_url = clean_remote_ok_string(remote_ok_job.get("url"))
    submitted_timestamp = int(remote_ok_job["epoch"])

    extracted_data = extract_job_data_from_text(extraction_text)
    extracted_data = apply_remote_ok_structured_defaults(remote_ok_job, extracted_data)
    cleaned_data = clean_job_json_object({"text": extraction_text}, extracted_data)

    return create_post_from_cleaned_data(
        cleaned_data,
        source=PostSource.REMOTE_OK,
        source_external_id=remote_ok_id,
        source_url=source_url,
        source_payload=remote_ok_job,
        submitted_datetime=datetime.fromtimestamp(submitted_timestamp, tz=dt_timezone.utc),
        vector=get_embedding(extraction_text),
    )


def import_remote_ok_jobs(limit=None):
    jobs = fetch_remote_ok_jobs()

    if settings.DEBUG and limit is None:
        jobs = jobs[:10]
    elif limit:
        jobs = jobs[: int(limit)]

    imported_count = 0
    skipped_count = 0
    failed_count = 0

    for job in jobs:
        remote_ok_id = str(job.get("id", ""))
        if not remote_ok_id:
            skipped_count += 1
            continue

        if Post.objects.filter(source=PostSource.REMOTE_OK, source_external_id=remote_ok_id).exists():
            skipped_count += 1
            continue

        try:
            create_remote_ok_post(job)
            imported_count += 1
        except IntegrityError:
            skipped_count += 1
            logger.info("Remote OK job already imported by concurrent task", remote_ok_id=remote_ok_id)
        except (openai.RateLimitError, openai.APIError):
            raise
        except Exception as e:
            failed_count += 1
            logger.error("Remote OK job import failed", remote_ok_id=remote_ok_id, error=e)

    return f"Imported {imported_count} Remote OK jobs. Skipped {skipped_count}. Failed {failed_count}."


def create_valid_emails():
    posts_with_emails = Post.objects.exclude(emails="")

    count = 0
    for post in posts_with_emails:
        # Split the name and pair it with a name if one exists.
        email_list = post.emails.split(",")
        name_list = post.names_of_the_contact_person.split(",")

        if len(email_list) == len(name_list):
            email_name_pairs = zip(email_list, name_list)
        else:
            email_name_pairs = zip(email_list, [""] * len(email_list))

        # Check that email is valid, and if not, try to fix it.
        for email, name in email_name_pairs:
            try:
                validate_email(email)
                email_is_valid = True
            except ValidationError:
                email_is_valid = False
                email = fix_email(email)
                try:
                    validate_email(email)
                    email_is_valid = True
                except ValidationError:
                    email_is_valid = False

            company = post.company

            if Email.objects.filter(post=post).exists():
                continue

            is_approved = False
            if name != "" and name.lower() in email.split("@")[0].lower():
                is_approved = True

            Email.objects.create(
                email=email,
                email_is_valid=email_is_valid,
                email_is_generic=is_generic(email),
                name=name,
                company=company,
                post=post,
                is_approved=is_approved,
            )
            count += 1
            logger.info("Email for post was created.", post=post, email=email)

    return f"Created {count} emails."


def find_bad_submitted_dates():
    list_of_repeated_datetimes = list(
        Post.objects.values("submitted_datetime")
        .annotate(count=Count("submitted_datetime"))
        .filter(count__gt=1)
        .values_list("submitted_datetime", flat=True)
        .distinct()
    )

    posts = Post.objects.filter(source=PostSource.HACKER_NEWS, submitted_datetime__in=list_of_repeated_datetimes)

    count = 0
    for post in posts:
        async_task(
            fix_submitted_date,
            post,
            hook="jobs.hooks.print_result",
            group="Fix Bad Post Datetime",
        )
        count += 1

    return f"{count} post have been scheduled for correction."


def fix_submitted_date(post):
    if post.source != PostSource.HACKER_NEWS or not post.who_is_hiring_comment_id:
        return "Post is not a Hacker News post"

    json_job = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{post.who_is_hiring_comment_id}.json").json()

    try:
        if json_job["deleted"] is True:
            return "Comment was deleted"
    except KeyError:
        pass

    unix_timestamp = datetime.fromtimestamp(int(json_job["time"]), tz=dt_timezone.utc)

    if post.submitted_datetime != unix_timestamp:
        post.submitted_datetime = unix_timestamp
        post.save()
        return "Date has been Corrected"
    else:
        return "Date is Correct"


@transaction.atomic
def delete_duplicate_jobs_posts():
    duplicate_ids = (
        Post.objects.filter(source=PostSource.HACKER_NEWS, who_is_hiring_comment_id__isnull=False)
        .values("who_is_hiring_comment_id")
        .annotate(count=Count("who_is_hiring_comment_id"))
        .filter(count__gt=1)
    )
    duplicate_ids = [item["who_is_hiring_comment_id"] for item in duplicate_ids]
    Post.objects.filter(who_is_hiring_comment_id__in=duplicate_ids).delete()

    return f"{len(duplicate_ids)} comments have been deleted"


def create_update_min_and_max_salary_jobs():
    jobs = Post.objects.filter(min_salary=None)

    count = 0
    for job in jobs:

        if job.compensation_summary == "" or not has_number(job.compensation_summary):
            job.min_salary = 0
            job.max_salary = 0
            job.currency = ""
            job.save()
            continue

        async_task(
            update_min_and_max_salary,
            job,
            hook="jobs.hooks.print_result",
            group="Update Job Salary",
        )
        count += 1

    return f"{count} have been sent to be analyzed."


def update_min_and_max_salary(job):

    request = f"""Find the minimum and maximum salary for the job, based on the following information: '{job.compensation_summary}'.
If there is no minimum or maximum salary, return 0. Do not lie, or make up numbers.
If the summary states that sarlary is weekly or monthly, convert it to annualy please.
Return a valid JSON Object with the following format:
{{
  min_salary: (integer, if not available return 0),
  max_salary: (integer, if not available return 0),
  currency: (string, e.g "USD", "EUR", etc. if not available return "")
}}
Do not return anything else. Just the JSON Object."""  # noqa: E501

    completion = client.chat.completions.create(
        model=settings.OPENAI_SALARY_EXTRACTION_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {"role": "user", "content": request},
        ],
    )
    converted_comment_response = completion.choices[0].message

    json_converted_comment_response = json.loads(converted_comment_response.content)

    min_salary = json_converted_comment_response["min_salary"]
    max_salary = json_converted_comment_response["max_salary"]

    if min_salary == 0 and max_salary != 0:
        min_salary = max_salary
    elif max_salary == 0 and min_salary != 0:
        max_salary = min_salary

    job.min_salary = min_salary
    job.max_salary = max_salary

    job.currency = json_converted_comment_response["currency"]
    job.save(update_fields=["min_salary", "max_salary", "currency"])

    return f"Job {job.id} has been updated."


def create_backfill_vector_data_jobs(rebuild=False):
    if bool(rebuild):
        jobs = Post.objects.all()
    else:
        jobs = Post.objects.filter(vector=None)

    count = 0
    for job in jobs:
        async_task(
            backfill_vector_data,
            job,
            hook="jobs.hooks.print_result",
            group="Backfill Vector Data",
        )
        count += 1

    return f"{count} have been sent to be analyzed."


def backfill_vector_data(job):
    if job.source == PostSource.HACKER_NEWS and job.who_is_hiring_comment_id:
        json_job = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{job.who_is_hiring_comment_id}.json").json()

        try:
            if json_job["deleted"] is True:
                return "Comment was deleted"
        except KeyError:
            pass

        text = json_job["text"]
    else:
        text = job.original_text or job.description

    vector = get_embedding(text)

    job.vector = vector
    job.save(update_fields=["vector"])

    return f"Job {job.id} has been updated."


def send_confirmation_email(instance, confirmation_url):
    message = f"""
      Hey there,

      Thanks a ton for the alert subscription for {instance["technology_selected"]} jobs.

      To make sure you start receving weekly alerts,
      please confirm your subscription by clicking the link below:

      {confirmation_url}
    """
    send_mail(
        "Confirm Your Job Alert Subscription",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [instance["email"]],
        fail_silently=False,
    )


def find_users_to_alert():
    seven_days_ago = timezone.now() - timedelta(days=7)

    alert_emails = (
        Alert.objects.filter(confirmed=True, unsubscribed=False, email__isnull=False)
        .values_list("email", flat=True)
        .distinct()
    )

    recent_alert_emails = AlertEmailSend.objects.filter(created__gte=seven_days_ago).values_list("email", flat=True)
    emails_to_send_to = alert_emails.difference(recent_alert_emails)

    count = 0
    for email in emails_to_send_to:
        async_task(
            send_alerts,
            email,
            Alert.objects.filter(email=email, unsubscribed=False, confirmed=True),
            hook="jobs.hooks.print_result",
            group="Send Alert",
        )
        count += 1

    return f"{count} alerts have been sent."


def send_alerts(email, alerts):
    current_date = timezone.now()
    week_number = (current_date.day - 1) // 7 + 1
    formatted_date = current_date.strftime("%B %Y, Week {}".format(week_number))
    subject = f"Job Alerts for {formatted_date}"

    context = {
        "alerts": [],
        "new_jobs_count": 0,
        "site_url": Site.objects.get_current().domain,
        "formatted_date": formatted_date,
    }

    for idx, alert in enumerate(alerts):
        name = alert.name if alert.name else idx
        context["alerts"].append(name)
        context["new_jobs_count"] += (
            PostFilter(alert.filter).qs.filter(submitted_datetime__gte=timezone.now() - timedelta(days=7)).count()
        )

    if context["new_jobs_count"] == 0:
        return f"{email} has no new jobs"

    if CustomUser.objects.filter(email=email).exists():
        user_status = "free"
        alert_email_send = AlertEmailSend.objects.create(email=email, user=CustomUser.objects.get(email=email))
    else:
        user_status = "guest"
        alert_email_send = AlertEmailSend.objects.create(email=email)

    context["alert_email_send"] = alert_email_send
    context["user_status"] = user_status

    html_content = render_to_string("jobs/alert-email.html", context)
    text_content = strip_tags(html_content)

    letter = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    letter.attach_alternative(html_content, "text/html")
    letter.send()

    return f"{email} is sent"


def add_email_to_buttondown(email, tag):
    data = {
        "email": str(email),
        "metadata": {"source": tag},
        "tags": [tag],
        "referrer_url": "https://gettjalerts.com",
        "subscriber_type": "unactivated",
    }
    if tag == "user":
        data["subscriber_type"] = "regular"

    r = requests.post(
        "https://api.buttondown.email/v1/subscribers",
        headers={"Authorization": f"Token {settings.BUTTONDOWN_API_TOKEN}"},
        json=data,
    )

    return r.json()


def send_daily_new_contacts_email():
    from django.db.models import Case, When, Value, IntegerField

    now = timezone.now()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    new_emails = (
        Email.objects.filter(
            created__gte=yesterday_start,
            created__lte=yesterday_end,
            email_is_valid=True,
            post__submitted_datetime__gte=current_month_start,
        )
        .select_related("company", "post")
        .annotate(
            priority=Case(
                When(name__isnull=False, name__gt="", email_is_generic=False, then=Value(1)),
                When(name__isnull=False, name__gt="", email_is_generic=True, then=Value(2)),
                When(name__isnull=True, email_is_generic=False, then=Value(3)),
                When(name="", email_is_generic=False, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        )
        .order_by("priority", "-created")
    )

    superuser = CustomUser.objects.filter(is_superuser=True).first()
    if not superuser or not superuser.email:
        logger.warning("No superuser with email found")
        return "No superuser email found"

    subject = f"New Contacts Report - {yesterday_start.strftime('%B %d, %Y')}"

    if not new_emails.exists():
        email_body = f"No new contacts were added on {yesterday_start.strftime('%B %d, %Y')}.\n"
        logger.info("No new contacts to send")
    else:
        email_body = f"Here are the new contacts that were added on {yesterday_start.strftime('%B %d, %Y')}:\n\n"

        for email_obj in new_emails:
            name = email_obj.name if email_obj.name else "N/A"
            email_body += f"{name} | {email_obj.email} | {email_obj.company.name} | {email_obj.company.fixed_company_homepage_link} | https://gettjalerts.com{email_obj.post.get_absolute_url()}\n"

        email_body += f"\nTotal new contacts: {new_emails.count()}\n"

    send_mail(
        subject,
        email_body,
        settings.DEFAULT_FROM_EMAIL,
        [superuser.email],
        fail_silently=False,
    )

    logger.info("Daily new contacts email sent", count=new_emails.count(), recipient=superuser.email)
    return f"Sent email with {new_emails.count()} new contacts to {superuser.email}"
