import logging
import re
from datetime import datetime

from .constants import GENERIC_KEYWORDS

logger = logging.getLogger(__file__)

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

    check_boolean_value(nlp_data["is_remote"])
    check_boolean_value(nlp_data["is_onsite"])

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
