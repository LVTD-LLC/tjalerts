import datetime
import json
import logging
import re

import httpx
import openai
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Company, Email, Post, Technology, Title
from .utils import clean_job_json_object, fix_email, is_generic

logger = logging.getLogger(__file__)
openai.api_key = settings.OPENAI_KEY


def analyze_hn_page(who_is_hiring_post_id):
    r = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{who_is_hiring_post_id}.json").json()

    if "Who is hiring" not in r["title"]:
        return "Not a Who is hiring post"

    who_is_hiring_id = int(r["id"])
    who_is_hiring_title = str(re.search("\(([^)]+)", r["title"]).group(1))

    list_of_comment_ids = r["kids"]

    # if working in dev don't want to go through all the comments
    if settings.DEBUG:
        list_of_comment_ids = list_of_comment_ids[:150]

    for comment_id in list_of_comment_ids:
        if not Post.objects.filter(who_is_hiring_comment_id=comment_id).exists():
            logger.info(f"Analyzing comment {comment_id}")
            json_job = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json").json()

            try:
                if json_job["deleted"] is True:
                    continue
            except KeyError:
                pass

            who_is_hiring_comment_id = int(json_job["id"])
            hn_username = str(json_job["by"])
            unix_timestamp = int(json_job["time"])

            logger.info(f"JSON for comment {comment_id}: {json_job}")
            request = f""""Convert the text below into json object with the following valid keys (give me an empty string if there is no info, ignore the content in  brackets, it is only to explain what I need):
                - company_name - (string)
                - job_titles - (string of comma separated values)
                - locations - (string of comma separated values)
                - cities - (string of comma separated values)
                - countries - (string of comma separated values)
                - compensation_summary - (string, decribe the salary or other benefits)
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
                {json_job['text']}
                '''
            """  # noqa: E501

            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    temperature=0,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant.",
                        },
                        {"role": "user", "content": request},
                    ],
                )
                converted_comment_response = completion.choices[0].message
            except (openai.error.RateLimitError, openai.error.APIError) as e:
                logger.error(e)
                continue

            try:
                json_converted_comment_response = json.loads(converted_comment_response.content)
            except json.decoder.JSONDecodeError:
                continue

            cleaned_data = clean_job_json_object(json_job, json_converted_comment_response)

            technology_names = [name.strip() for name in cleaned_data["technologies_used"].split(",")]
            technologies = []
            for name in technology_names:
                if name != "":
                    obj, _ = Technology.objects.get_or_create(name=name)
                    technologies.append(obj)

            job_title_names = [name.strip() for name in cleaned_data["job_titles"].split(",")]
            job_titles = []
            for job_title in job_title_names:
                if job_title != "":
                    obj, _ = Title.objects.get_or_create(name=job_title)
                    job_titles.append(obj)

            company_obj, _ = Company.objects.get_or_create(name=cleaned_data["company_name"])
            company_obj.company_homepage_link = cleaned_data["company_homepage_link"]
            company_obj.emails += cleaned_data["emails"]
            company_obj.save()

            post = Post(
                who_is_hiring_id=who_is_hiring_id,
                who_is_hiring_title=who_is_hiring_title,
                who_is_hiring_comment_id=who_is_hiring_comment_id,
                submitted_datetime=datetime.datetime.fromtimestamp(unix_timestamp),
                company=company_obj,
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
                company_job_application_link=cleaned_data["company_job_application_link"],
                names_of_the_contact_person=cleaned_data["names_of_the_contact_person"],
                levels_of_experience=cleaned_data["levels_of_experience"],
                emails=cleaned_data["emails"],
            )
            post.save()

            post.technologies.add(*technologies)
            post.jobs.add(*job_titles)

            logger.info(f"{post} post was created.")
        else:
            logger.info(f"Job for {comment_id} already exists.")

    return "Task Completed"


def create_valid_emails():
    posts_with_emails = Post.objects.exclude(emails="")

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
                logger.info(f"Email for {post} already exists.")
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
            logger.info(f"Email for {post} was created.")
