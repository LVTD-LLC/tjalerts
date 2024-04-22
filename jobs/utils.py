import re
from datetime import datetime

from openai import OpenAI

from hn_jobs.utils import get_tjalerts_logger

client = OpenAI()

from .constants import GENERIC_KEYWORDS
from .models import Technology

logger = get_tjalerts_logger(__name__)

list_of_expected_keys = [
    "company_name",
    "job_titles",
    "locations",
    "cities",
    "countries",
    "compensation_summary",
    "is_remote",
    "remote_timezones",
    "is_onsite",
    "capacity",
    "description",
    "technologies_used",
    "company_homepage_link",
    "emails",
    "company_job_application_link",
    "names_of_the_contact_person",
    "years_of_experience",
    "levels_of_experience",
]


def clean_job_json_object(original_comment: dict, nlp_data: dict) -> dict:
    nlp_data = make_sure_all_keys_exists(nlp_data, list_of_expected_keys)

    for key, value in nlp_data.items():
        nlp_data[key] = if_value_is_unknown_return_empty_string(value)

    nlp_data["years_of_experience"] = check_years_of_experience_value(
        nlp_data["years_of_experience"], original_comment["text"]
    )

    nlp_data["original_text"] = original_comment["text"]

    check_boolean_value(nlp_data["is_remote"])
    check_boolean_value(nlp_data["is_onsite"])

    if not has_number(nlp_data["compensation_summary"]):
        nlp_data["min_salary"] = 0
        nlp_data["max_salary"] = 0

    return nlp_data


def check_years_of_experience_value(years: int, text: str):
    """Python function to check that the estimated years of experience appears in the text."""
    if str(years) in text and isinstance(years, int):
        return years
    else:
        return ""


def if_value_is_unknown_return_empty_string(value: str) -> str:
    if value in ["Unknown", "unknown", "empty", "not specified", "N/A", "null", "None", None]:
        return ""
    else:
        return value


def sort_dates(dates):
    """
    Sorts a list of dates in ascending order.
    """
    date_format = "%B %Y"
    sorted_dates = sorted(dates, key=lambda x: datetime.strptime(x, date_format))
    return sorted_dates


def check_boolean_value(boolean_value: any) -> bool:
    if isinstance(boolean_value, bool) or boolean_value in [
        "True",
        "true",
        "Yes",
        "yes",
    ]:
        return boolean_value
    else:
        return False


def make_sure_all_keys_exists(data: dict, keys: list) -> dict:
    for key in keys:
        try:
            data[key]
        except KeyError:
            data[key] = ""

    return data


def fix_email(email):
    """
    Fixes common misspellings of email addresses and returns the corrected email.
    """
    email = email.lower()
    email = (
        re.sub(r"\s+at\s+", "@", email)
        .replace(" [at] ", "@")
        .replace("[at]", "@")
        .replace(" at ", "@")
        .replace("(at)", "@")
        .replace("(a)", "@")
        .replace("[@]", "@")
        .replace("{@}", "@")
        .replace("-at-", "@")
        .replace("<at>", "@")
        .replace(" at:", "@")
        .replace("'at'", "@")
        .replace("_at_", "@")
        .replace(" dot ", ".")
        .replace("<dot>", ".")
        .replace(" [dot] ", ".")
        .replace("(dot)", ".")
        .replace("[dot]", ".")
        .replace(" dot:", ".")
        .replace(" dot;", ".")
        .replace("-dot-", ".")
        .replace("_dot_", ".")
        .replace("'dot'", ".")
        .replace(";", ".")
        .replace(",", ".")
        .replace(" ", "")
        .replace(":", ".")
    )
    return email


def is_generic(email: str) -> bool:
    """
    Returns True if the email address is generic, False otherwise.
    A generic email is defined as an email that has a generic local part
    such as 'jobs', 'apply', etc.
    """

    return email.split("@")[0].lower() in GENERIC_KEYWORDS


def has_number(input_string):
    return any(char.isdigit() for char in input_string)


def get_embedding(text):
    text = text.replace("\n", " ")

    embedding = client.embeddings.create(input=[text], model="text-embedding-3-small")

    return embedding.data[0].embedding


def default_alert_name(alert, idx):
    if "technologies" in alert.filter and len(alert.filter) == 1 and alert.filter["technologies"][0]:
        return f"{Technology.objects.get(id=alert.filter['technologies'][0]).name} Alert"
    else:
        return alert.name if alert.name else f"Alert #{idx+1}"
