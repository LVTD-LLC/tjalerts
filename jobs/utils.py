import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import unescape
from itertools import combinations

from allauth.account.models import EmailAddress
from django.conf import settings
from django.db.models import Count, Q
from django.utils.html import strip_tags
from openai import OpenAI

from hn_jobs.posthog_events import ai_span, capture_event, model_from_feature_flag
from hn_jobs.utils import get_tjalerts_logger
from jobs.choices import PostSource
from jobs.constants import GENERIC_KEYWORDS
from jobs.models import Post, Technology, TechnologyMapping, Title

logger = get_tjalerts_logger(__name__)

client = OpenAI()

list_of_expected_keys = [
    "company_name",
    "job_titles",
    "locations",
    "cities",
    "countries",
    "compensation_summary",
    "min_salary",
    "max_salary",
    "currency",
    "is_remote",
    "remote_timezones",
    "is_onsite",
    "capacity",
    "description",
    "job_details",
    "technologies_used",
    "company_homepage_link",
    "emails",
    "company_job_application_link",
    "names_of_the_contact_person",
    "years_of_experience",
    "levels_of_experience",
]


NON_HIRING_COMMENT_OPENING_PATTERNS = [
    r"\bseeking\s+work(?![-/\w])",
    r"\blooking\s+for\s+work(?![-/\w])",
    r"\bavailable\s+for\s+hire\b",
    r"\bopen\s+to\s+work\b",
    r"\bhire\s+me\b",
    (r"\bseeking\s+" r"(?:employment|a\s+(?:job|role|position)|remote\s+work|contract\s+work|freelance\s+work)\b"),
    (
        r"\blooking\s+for\s+"
        r"(?:employment|a\s+(?:job|role|position)|remote\s+work|contract\s+work|"
        r"freelance\s+work|new\s+(?:role|position|opportunity))\b"
    ),
]

NON_HIRING_COMMENT_BODY_PATTERNS = [
    r"\bwho wants to be hired\b",
    r"\bposted (?:this )?(?:in|on) the wrong thread\b",
    r"\bshould (?:be|go) (?:in|on) the (?:who wants to be hired|freelancer|seeking work) thread\b",
    r"\bmy\s+(?:resume|r\u00e9sum\u00e9|cv)\b",
]

SELF_PROMOTION_TITLE_PATTERN = (
    r"(?:(?:junior|mid[- ]level|midlevel|mid|senior|staff|principal|lead|founding|experienced)\s+)?"
    r"(?:full[- ]stack|frontend|front[- ]end|backend|back[- ]end|software|data|mobile|"
    r"devops|machine learning|ml|ai)?\s*"
    r"(?:engineer|developer|designer|scientist)"
)

SELF_PROMOTION_PATTERNS = [
    r"\bi(?:'|\u2019)?m\s+(?:an?\s+)?" + SELF_PROMOTION_TITLE_PATTERN + r"\b",
    r"\bi am\s+(?:an?\s+)?" + SELF_PROMOTION_TITLE_PATTERN + r"\b",
]

CONTACT_MARKER_PATTERNS = [
    r"\bgithub\s*:",
    r"\blinkedin\s*:",
    r"\bportfolio\s*:",
    r"\bemail\s*:",
]

COMPANY_HIRING_ROLE_PATTERN = (
    r"(?:engineers?|developers?|devs?|designers?|scientists?|managers?|leads?|contractors?|"
    r"consultants?|candidates?|persons?|people)"
)

COMPANY_HIRING_SIGNAL_PATTERNS = [
    r"\b(?:we(?:'|\u2019)?re|we are|our team is)\s+hiring\b",
    r"\b(?:my|our)\s+company\s+(?:is|are)\s+hiring\b",
    r"\bwe(?:'|\u2019)?re\s+looking\s+for\b",
    r"\bwe are\s+looking\s+for\b",
    r"\bwe(?:'|\u2019)?re\s+seeking\s+(?:(?:an?|another)\s+)?(?:[\w-]+\s+){0,4}" + COMPANY_HIRING_ROLE_PATTERN + r"\b",
    r"\bwe are\s+seeking\s+(?:(?:an?|another)\s+)?(?:[\w-]+\s+){0,4}" + COMPANY_HIRING_ROLE_PATTERN + r"\b",
    r"\bwe need\s+(?:an?\s+)?(?:[\w-]+\s+){0,4}" + COMPANY_HIRING_ROLE_PATTERN + r"\b",
    r"\bwe need\s+(?:someone|somebody|people|folks|candidates?)\b",
    r"\bopen roles?\b",
    r"\bpositions?\s+(?:available|open)\b",
    r"\bapply\s+(?:at|now|here|online|directly|via|through|below)\b",
    r"\bcareers\s*(?::|/)",
    r"\bcareers\s+(?:at|page|portal|site)\b",
    r"/careers(?:/|\b)",
    r"\bjoin our(?:\s+[\w-]+){0,3}\s+team\b",
    r"\bjoin the(?:\s+[\w-]+){1,3}\s+team\b",
]

OPENING_COMMENT_LINE_COUNT = 4


def normalize_hn_comment_text(text: str) -> str:
    text = re.sub(r"(?i)<\s*(?:p|br)\s*/?>", "\n", text or "")
    text = strip_tags(text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def is_probably_non_hiring_hn_comment(text: str) -> bool:
    normalized_text = normalize_hn_comment_text(text)
    if not normalized_text:
        return True

    lowercase_text = normalized_text.lower()
    compact_text = re.sub(r"\s+", " ", lowercase_text)
    opening_lines = "\n".join(lowercase_text.splitlines()[:OPENING_COMMENT_LINE_COUNT])
    opening_text = re.sub(r"\s+", " ", opening_lines)

    if any(re.search(pattern, opening_text) for pattern in NON_HIRING_COMMENT_OPENING_PATTERNS):
        return True

    if any(re.search(pattern, compact_text) for pattern in NON_HIRING_COMMENT_BODY_PATTERNS):
        return True

    has_self_promotion = any(re.search(pattern, compact_text) for pattern in SELF_PROMOTION_PATTERNS)
    has_contact_marker = any(re.search(pattern, compact_text) for pattern in CONTACT_MARKER_PATTERNS)
    has_company_hiring_signal = any(re.search(pattern, compact_text) for pattern in COMPANY_HIRING_SIGNAL_PATTERNS)

    return has_self_promotion and has_contact_marker and not has_company_hiring_signal


def clean_job_json_object(original_comment: dict, nlp_data: dict) -> dict:
    nlp_data = make_sure_all_keys_exists(nlp_data, list_of_expected_keys)

    for key, value in nlp_data.items():
        nlp_data[key] = if_value_is_unknown_return_empty_string(value)

    nlp_data["years_of_experience"] = check_years_of_experience_value(
        nlp_data["years_of_experience"], original_comment["text"]
    )

    nlp_data["original_text"] = original_comment["text"]

    nlp_data["is_remote"] = check_boolean_value(nlp_data["is_remote"])
    nlp_data["is_onsite"] = check_boolean_value(nlp_data["is_onsite"])

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
    if isinstance(boolean_value, bool):
        return boolean_value

    if boolean_value in ["True", "true", "Yes", "yes"]:
        return True

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
    model = model_from_feature_flag("embedding-model", settings.OPENAI_EMBEDDING_MODEL)

    with ai_span(
        "ai.embedding",
        attributes={
            "ai.workflow": "embedding",
            "gen_ai.request.model": model,
            "input_length": len(text),
        },
    ):
        embedding = client.embeddings.create(input=[text], model=model)

    usage = getattr(embedding, "usage", None)
    capture_event(
        "ai embedding completed",
        properties={
            "model": model,
            "input_length": len(text),
            "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
            "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        },
    )

    return embedding.data[0].embedding


def default_alert_name(alert, idx):
    if "technologies" in alert.filter and len(alert.filter) == 1 and alert.filter["technologies"][0]:
        return f"{Technology.objects.get(id=alert.filter['technologies'][0]).name} Alert"
    else:
        return alert.name if alert.name else f"Alert #{idx + 1}"


def build_intent_alert_suggestions(intent, max_alerts=3):
    normalized_intent = normalize_alert_intent(intent)
    if not normalized_intent:
        return []

    base_filter = {"vector": normalized_intent}
    if re.search(r"\b(remote|distributed|work from anywhere|worldwide)\b", normalized_intent, re.IGNORECASE):
        base_filter["is_remote"] = "True"
    elif re.search(r"\b(on-site|onsite|in office|office-based)\b", normalized_intent, re.IGNORECASE):
        base_filter["is_onsite"] = "True"

    matched_titles = find_named_matches(normalized_intent, Title.objects.exclude(name="").order_by("name"))
    matched_technologies = find_named_matches(normalized_intent, Technology.objects.exclude(name="").order_by("name"))

    specific_suggestions = []
    seen_filters = set()

    def add_specific(name, alert_filter):
        filter_key = canonical_filter_key(alert_filter)
        if filter_key in seen_filters:
            return

        seen_filters.add(filter_key)
        specific_suggestions.append(
            {
                "name": truncate_alert_name(name),
                "filter": alert_filter,
            }
        )

    remote_prefix = "Remote " if base_filter.get("is_remote") == "True" else ""

    for title in matched_titles[:2]:
        for technology in matched_technologies[:2]:
            add_specific(
                f"{remote_prefix}{title.name} with {technology.name}",
                {
                    **base_filter,
                    "titles": [str(title.id)],
                    "technologies": [str(technology.id)],
                },
            )

    for title in matched_titles[:2]:
        add_specific(
            f"{remote_prefix}{title.name} roles",
            {
                **base_filter,
                "titles": [str(title.id)],
            },
        )

    for technology in matched_technologies[:2]:
        add_specific(
            f"{remote_prefix}{technology.name} roles",
            {
                **base_filter,
                "technologies": [str(technology.id)],
            },
        )

    broad_suggestion = {
        "name": "Job brief match",
        "filter": base_filter,
    }

    if max_alerts <= 1:
        return [broad_suggestion]

    return specific_suggestions[: max_alerts - 1] + [broad_suggestion]


def normalize_alert_intent(intent):
    return re.sub(r"\s+", " ", (intent or "").strip())


def find_named_matches(intent, queryset):
    candidates = build_intent_candidate_names(intent)
    if not candidates:
        return []

    query = Q()
    for candidate in candidates:
        query |= Q(name__iexact=candidate)

    matches = [obj for obj in queryset.filter(query) if name_appears_in_intent(intent, obj.name)]
    return sorted(matches, key=lambda match: len(match.name), reverse=True)


def build_intent_candidate_names(intent, max_words=5):
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9#+.:-]*", intent)
    candidates = set()

    for start_index in range(len(tokens)):
        max_end_index = min(len(tokens), start_index + max_words)
        for end_index in range(start_index + 1, max_end_index + 1):
            candidates.add(" ".join(tokens[start_index:end_index]))

    return candidates


def name_appears_in_intent(intent, name):
    name = (name or "").strip()
    if len(name) < 2:
        return False

    pattern = rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])"
    return bool(re.search(pattern, intent, re.IGNORECASE))


def truncate_alert_name(name, max_length=100):
    clean_name = normalize_alert_intent(name)
    if len(clean_name) <= max_length:
        return clean_name

    return f"{clean_name[: max_length - 3].rstrip()}..."


def canonical_filter_key(alert_filter):
    return json.dumps(canonicalize_filter_value(alert_filter), sort_keys=True)


def canonicalize_filter_value(value):
    if isinstance(value, dict):
        return {key: canonicalize_filter_value(nested_value) for key, nested_value in value.items()}

    if isinstance(value, list):
        canonical_items = [canonicalize_filter_value(item) for item in value]
        return sorted(canonical_items, key=lambda item: json.dumps(item, sort_keys=True))

    return value


def is_email_confirmed(user):
    try:
        email_address = EmailAddress.objects.get(user=user, email=user.email)
        return email_address.verified
    except EmailAddress.DoesNotExist:
        return False


def is_positive_salary_floor(value):
    try:
        salary_floor = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return False

    return salary_floor > 0


def parse_positive_day_count(value):
    try:
        day_count = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if day_count <= 0 or day_count != day_count.to_integral_value():
        return None

    return int(day_count)


def day_count_label(day_count):
    return f"{day_count} day{'s' if day_count != 1 else ''}"


def has_meaningful_filter_value(query_params, key):
    values = [value for value in query_params.getlist(key) if value not in ["", "unknown"]]

    if key == "salary_floor":
        return any(is_positive_salary_floor(value) for value in values)

    if key == "added_within_days":
        return any(parse_positive_day_count(value) is not None for value in values)

    return bool(values)


def generate_job_search_title(query_params, first_item_datetime):
    date = first_item_datetime.strftime("%B %Y")
    meaningful_keys = [
        key
        for key in query_params.keys()
        if key not in {"o", "page"} and has_meaningful_filter_value(query_params, key)
    ]

    if len(meaningful_keys) > 1 or len(meaningful_keys) == 0:
        return f"Available Jobs - {date}"

    query_param = meaningful_keys[0]

    if query_param == "q":
        return f"Jobs matching {query_params['q']} - {date}"

    if query_param == "source":
        return f"{query_params['source']} Jobs - {date}"

    if query_param == "posted_within":
        return f"Jobs from the last {query_params['posted_within']} days - {date}"

    if query_param == "added_within_days":
        day_count = parse_positive_day_count(query_params["added_within_days"])
        if day_count is not None:
            return f"Jobs added in the last {day_count_label(day_count)} - {date}"

    if query_param == "salary_floor" and is_positive_salary_floor(query_params["salary_floor"]):
        return f"Jobs paying at least {query_params['salary_floor']} - {date}"

    if query_param == "work_mode":
        work_mode_titles = {
            "remote": "Remote Jobs",
            "remote_only": "Remote-only Jobs",
            "onsite": "Onsite and Hybrid Jobs",
            "onsite_only": "Onsite Jobs",
            "hybrid": "Hybrid Jobs",
        }
        return f"{work_mode_titles.get(query_params['work_mode'], 'Available Jobs')} - {date}"

    if query_param == "remove_duplicate_employers" and query_params["remove_duplicate_employers"] == "true":
        return f"Unique Employer Jobs - {date}"

    if query_param == "has_compensation":
        compensation_title = (
            "Compensation Info" if query_params["has_compensation"] == "yes" else "No Compensation Info"
        )
        return f"Jobs with {compensation_title} - {date}"

    if query_param == "has_contact":
        return f"Jobs with {'Contact Info' if query_params['has_contact'] == 'yes' else 'No Contact Info'} - {date}"

    if query_param == "technologies":
        technologies_list = query_params.getlist("technologies")
        if len(technologies_list) == 1:
            try:
                tech_name = Technology.objects.get(id=query_params.getlist("technologies")[0]).name
                return f"{tech_name} Jobs - {date}"
            except (Technology.DoesNotExist, ValueError):
                return f"Available Jobs - {date}"

    if query_param == "titles":
        titles_list = query_params.getlist("titles")
        if len(titles_list) == 1:
            try:
                title_name = Title.objects.get(id=query_params.getlist("titles")[0]).name
                return f"{title_name} Jobs - {date}"
            except (Title.DoesNotExist, ValueError):
                return f"Available Jobs - {date}"

    if query_param == "locations":
        return f"Jobs in {query_params['locations']} - {date}"

    if query_param == "compensation_summary__isempty":
        compensation_summary = query_params["compensation_summary__isempty"]
        return f"Jobs with {'no' if compensation_summary == 'false' else ''} Comp Info - {date}"

    if query_param == "emails__isempty":
        emails = query_params["emails__isempty"]
        return f"Jobs with {'no' if emails == 'false' else ''} Contact Info - {date}"

    if query_param == "is_remote":
        is_remote = query_params["is_remote"]
        return f"{'Remote' if is_remote == 'true' else ''} Jobs - {date}"

    if query_param == "is_onsite":
        is_onsite = query_params["is_onsite"]
        return f"{'Onsite' if is_onsite == 'true' else ''} Jobs - {date}"

    return f"Available Jobs - {date}"


def generate_job_search_keywords(query_params):
    keywords = []

    for key in query_params.keys():
        if key == "q":
            keywords.append(query_params["q"])

        if key == "source":
            keywords.append(query_params["source"])

        if key == "posted_within":
            keywords.append(f"Last {query_params['posted_within']} days")

        if key == "added_within_days":
            day_count = parse_positive_day_count(query_params["added_within_days"])
            if day_count is not None:
                keywords.append(f"Added in last {day_count_label(day_count)}")

        if key == "salary_floor" and is_positive_salary_floor(query_params["salary_floor"]):
            keywords.append(f"Salary at least {query_params['salary_floor']}")

        if key == "work_mode":
            work_mode_keywords = {
                "remote": "Remote",
                "remote_only": "Remote only",
                "onsite": "Onsite or hybrid",
                "onsite_only": "Onsite only",
                "hybrid": "Hybrid",
            }
            keywords.append(work_mode_keywords.get(query_params["work_mode"], query_params["work_mode"]))

        if key == "remove_duplicate_employers" and query_params["remove_duplicate_employers"] == "true":
            keywords.append("Unique employers")

        if key == "has_compensation":
            if query_params["has_compensation"] == "yes":
                keywords.append("Compensation Information")
            if query_params["has_compensation"] == "no":
                keywords.append("Missing Compensation Information")

        if key == "has_contact":
            if query_params["has_contact"] == "yes":
                keywords.append("Contact Information")
            if query_params["has_contact"] == "no":
                keywords.append("Missing Contact Information")

        if key == "technologies":
            technologies_list = query_params.getlist("technologies")
            for tech_id in technologies_list:
                try:
                    keywords.append(Technology.objects.get(id=tech_id).name)
                except (Technology.DoesNotExist, ValueError):
                    continue

        if key == "titles":
            titles_list = query_params.getlist("titles")
            for title_id in titles_list:
                try:
                    keywords.append(Title.objects.get(id=title_id).name)
                except (Title.DoesNotExist, ValueError):
                    continue

        if key == "locations":
            keywords.append(query_params["locations"])

        if key == "compensation_summary__isempty":
            if query_params["compensation_summary__isempty"] == "true":
                keywords.append("Compensation Information")
            if query_params["compensation_summary__isempty"] == "false":
                keywords.append("Missing Compensation Information")

        if key == "emails__isempty":
            if query_params["emails__isempty"] == "true":
                keywords.append("Contact Information")
            if query_params["emails__isempty"] == "false":
                keywords.append("Missing Contact Information")

        if key == "is_remote" and query_params["is_remote"] == "true":
            keywords.append("Remote")

        if key == "is_onsite" and query_params["is_onsite"] == "true":
            keywords.append("Onsite")

    return keywords


def count_of_posts_from_source_in_month(source: PostSource, month: int, year: int):
    return Post.objects.filter(
        source=source,
        submitted_datetime__month=month,
        submitted_datetime__year=year,
    ).count()


def calculate_month_over_month_change(
    source: PostSource = None,
    current_month: int = None,
    current_year: int = None,
):
    # Use current month/year if not specified
    if current_month is None or current_year is None:
        now = datetime.now()
        current_month = now.month
        current_year = now.year

    # Calculate previous month and year
    previous_month = current_month - 1
    previous_year = current_year

    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    # Get post counts using the existing function
    current_count = count_of_posts_from_source_in_month(source, current_month, current_year)
    previous_count = count_of_posts_from_source_in_month(source, previous_month, previous_year)

    # Calculate percent change
    if previous_count == 0:
        return float("inf")  # Or return 100.0 to indicate 100% increase

    percent_change = (current_count - previous_count) / previous_count
    # Format the message
    return round(percent_change, 2)


def calculate_year_over_year_change(
    source: PostSource = None,
    current_month: int = None,
    current_year: int = None,
):
    # Use current month/year if not specified
    if current_month is None or current_year is None:
        now = datetime.now()
        current_month = now.month
        current_year = now.year

    # Previous year, same month
    previous_year = current_year - 1

    # Get post counts
    current_count = count_of_posts_from_source_in_month(source, current_month, current_year)
    previous_count = count_of_posts_from_source_in_month(source, current_month, previous_year)

    # Calculate percent change
    if previous_count == 0:
        return "New posts this year (no posts in same month last year)"

    percent_change = (current_count - previous_count) / previous_count

    # Return the rounded percentage change
    return round(percent_change, 2)


def get_most_in_demand_roles(source: PostSource, month: int, year: int, limit=10):
    posts_query = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)

    post_ids = posts_query.values_list("id", flat=True)

    top_titles = (
        Title.objects.filter(posttitle__post_id__in=post_ids)
        .annotate(post_count=Count("posttitle"))
        .order_by("-post_count")
        .values("name", "post_count")[:limit]
    )

    return list(top_titles)


def get_seniority_distribution(source: PostSource, month: int, year: int):
    """
    Analyzes the distribution of seniority levels in job posts.
    Looks at both levels_of_experience field and job titles.
    Returns percentage breakdown of different seniority levels.
    """

    # Define seniority keywords for classification
    SENIORITY_KEYWORDS = {
        "Junior": ["junior", "jr", "entry", "entry-level", "graduate", "apprentice"],
        "Mid": ["mid", "intermediate", "mid-level", "associate"],
        "Senior": ["senior", "sr", "staff", "principal"],
        "Lead": ["lead", "tech lead", "team lead"],
        "Manager": ["manager", "head", "director", "vp", "chief", "cto", "cio"],
    }

    # Get posts for the specified period
    posts = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)
    total_posts = posts.count()

    if total_posts == 0:
        return {}

    # Initialize counters for each seniority level
    seniority_counts = {level: 0 for level in SENIORITY_KEYWORDS.keys()}

    # Helper function to classify text
    def classify_seniority(text):
        if not text:
            return None
        text = text.lower()
        for level, keywords in SENIORITY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return level
        return None

    # Analyze each post
    for post in posts:
        # Check levels_of_experience field
        seniority_from_level = classify_seniority(post.levels_of_experience)
        if seniority_from_level:
            seniority_counts[seniority_from_level] += 1
            continue

        # Check associated titles if no seniority found in levels_of_experience
        titles = Title.objects.filter(posttitle__post=post).values_list("name", flat=True)
        for title in titles:
            seniority = classify_seniority(title)
            if seniority:
                seniority_counts[seniority] += 1
                break

    # Calculate percentages
    distribution = {
        level: round((count / total_posts) * 100, 1)
        for level, count in seniority_counts.items()
        if count > 0  # Only include levels that have matches
    }

    # Add raw counts
    distribution.update({f"{level}_count": count for level, count in seniority_counts.items() if count > 0})

    # Add total posts analyzed
    distribution["total_posts"] = total_posts

    return distribution


def get_new_job_titles(source: PostSource, month: int, year: int, min_occurrences=2):
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    # Get posts for current month
    current_posts = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)

    # Get posts for previous month
    previous_posts = Post.objects.filter(
        source=source, submitted_datetime__month=previous_month, submitted_datetime__year=previous_year
    )

    # Get titles and their counts from current month
    current_titles = (
        Title.objects.filter(posttitle__post__in=current_posts).annotate(post_count=Count("posttitle"))
        # .filter(post_count__gte=min_occurrences)
        .values("name", "post_count")
    )

    # Get titles from previous month
    previous_titles = (
        Title.objects.filter(posttitle__post__in=previous_posts)
        .annotate(post_count=Count("posttitle"))
        # .filter(post_count__gte=min_occurrences)
        .values_list("name", flat=True)
        .distinct()
    )

    # Find new titles (those in current but not in previous)
    new_titles = [
        {
            "name": title["name"],
            "post_count": title["post_count"],
        }
        for title in current_titles
        if (title["name"] not in previous_titles and title["post_count"] >= min_occurrences)
    ]

    # Add summary stats
    result = {
        "new_titles": new_titles,
        "total_new_titles": len(new_titles),
        "current_month_total_titles": current_titles.count(),
        "previous_month_total_titles": len(previous_titles),
    }

    return result


def get_popular_technologies(source: PostSource, month: int, year: int, limit=20, min_occurrences=2):
    # Get current month's posts
    posts = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)
    post_ids = posts.values_list("id", flat=True)

    # Calculate previous month and year
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    # Get previous month's posts
    previous_month_posts = Post.objects.filter(
        source=source, submitted_datetime__month=previous_month, submitted_datetime__year=previous_year
    )
    previous_month_post_ids = previous_month_posts.values_list("id", flat=True)

    # Get last year same month's posts
    last_year_posts = Post.objects.filter(
        source=source, submitted_datetime__month=month, submitted_datetime__year=year - 1
    )
    last_year_post_ids = last_year_posts.values_list("id", flat=True)

    # Get all technologies and their counts with minimum occurrences
    all_tech_counts = (
        Technology.objects.filter(posttechnology__post_id__in=post_ids)
        .annotate(mention_count=Count("posttechnology"))
        .values("id", "name", "mention_count")
    )

    # Get previous month counts for these technologies
    previous_month_counts = dict(
        Technology.objects.filter(posttechnology__post_id__in=previous_month_post_ids)
        .annotate(mention_count=Count("posttechnology"))
        .values_list("id", "mention_count")
    )

    # Get last year same month counts
    last_year_counts = dict(
        Technology.objects.filter(posttechnology__post_id__in=last_year_post_ids)
        .annotate(mention_count=Count("posttechnology"))
        .values_list("id", "mention_count")
    )

    # Get parent categories and their children
    tech_mappings = TechnologyMapping.objects.select_related("parent", "child").all()

    # Create mappings for technology relationships
    child_to_parent = {}  # Maps child tech ID to parent tech ID
    parent_techs = {}  # Stores parent tech details
    for mapping in tech_mappings:
        child_to_parent[mapping.child_id] = mapping.parent_id
        parent_techs[mapping.parent_id] = mapping.parent.name

    # Initialize aggregated counts
    aggregated_counts = {}
    for tech in all_tech_counts:
        tech_id = tech["id"]
        # If this is a child technology, add its count to the parent
        if tech_id in child_to_parent:
            parent_id = child_to_parent[tech_id]
            if parent_id not in aggregated_counts:
                aggregated_counts[parent_id] = {
                    "name": parent_techs[parent_id],
                    "count": 0,
                    "previous_month_count": 0,
                    "last_year_count": 0,
                }
            aggregated_counts[parent_id]["count"] += tech["mention_count"]
            aggregated_counts[parent_id]["previous_month_count"] += previous_month_counts.get(tech_id, 0)
            aggregated_counts[parent_id]["last_year_count"] += last_year_counts.get(tech_id, 0)
        else:
            # This is either a parent technology or an unmapped technology
            aggregated_counts[tech_id] = {
                "name": tech["name"],
                "count": tech["mention_count"],
                "previous_month_count": previous_month_counts.get(tech_id, 0),
                "last_year_count": last_year_counts.get(tech_id, 0),
            }

    # Process aggregated counts and calculate changes
    processed_techs = []
    for tech_id, data in aggregated_counts.items():
        if data["count"] < min_occurrences:
            continue

        mom_change = None
        if data["previous_month_count"] > 0:
            mom_change = ((data["count"] - data["previous_month_count"]) / data["previous_month_count"]) * 100

        yoy_change = None
        if data["last_year_count"] > 0:
            yoy_change = ((data["count"] - data["last_year_count"]) / data["last_year_count"]) * 100

        tech_data = {
            "name": data["name"],
            "count": data["count"],
            "previous_month_count": data["previous_month_count"],
            "month_over_month_change": round(mom_change, 1) if mom_change is not None else None,
            "last_year_count": data["last_year_count"],
            "year_over_year_change": round(yoy_change, 1) if yoy_change is not None else None,
        }
        processed_techs.append(tech_data)

    # Sort by count in descending order
    processed_techs.sort(key=lambda x: x["count"], reverse=True)

    return {
        "individual_technologies": processed_techs[:limit],
        "total_posts_analyzed": posts.count(),
        "total_technology_mentions": sum(tech["mention_count"] for tech in all_tech_counts),
        "previous_month_total_posts": previous_month_posts.count(),
        "last_year_total_posts": last_year_posts.count(),
    }


def get_common_technology_combinations(source: PostSource, month: int, year: int, limit=20, min_occurrences=2):
    # Get current month's posts
    posts = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)

    # Calculate previous month and year
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    # Get previous month's posts for comparison
    previous_month_posts = Post.objects.filter(
        source=source, submitted_datetime__month=previous_month, submitted_datetime__year=previous_year
    )

    # Build technology mapping cache
    tech_mapping_cache = {}
    tech_mappings = TechnologyMapping.objects.select_related("parent", "child").all()
    for mapping in tech_mappings:
        tech_mapping_cache[mapping.child.name] = mapping.parent.name

    def normalize_tech_name(tech_name):
        return tech_mapping_cache.get(tech_name, tech_name)

    # Get all posts with their technologies
    current_post_techs = {}
    for post in posts:
        techs = list(Technology.objects.filter(posttechnology__post=post).values_list("name", flat=True))
        if len(techs) > 1:
            # Normalize technology names using the mapping
            normalized_techs = [normalize_tech_name(tech) for tech in techs]
            # Remove duplicates that might occur after normalization
            normalized_techs = list(dict.fromkeys(normalized_techs))
            if len(normalized_techs) > 1:
                current_post_techs[post.id] = normalized_techs

    # Get previous month's post technologies
    previous_post_techs = {}
    for post in previous_month_posts:
        techs = list(Technology.objects.filter(posttechnology__post=post).values_list("name", flat=True))
        if len(techs) > 1:
            normalized_techs = [normalize_tech_name(tech) for tech in techs]
            normalized_techs = list(dict.fromkeys(normalized_techs))
            if len(normalized_techs) > 1:
                previous_post_techs[post.id] = normalized_techs

    # Count current month combinations
    current_combinations = {}
    for techs in current_post_techs.values():
        # Look at pairs of technologies
        for combo in combinations(sorted(techs), 2):
            current_combinations[combo] = current_combinations.get(combo, 0) + 1

    # Count previous month combinations
    previous_combinations = {}
    for techs in previous_post_techs.values():
        for combo in combinations(sorted(techs), 2):
            previous_combinations[combo] = previous_combinations.get(combo, 0) + 1

    # Filter and sort combinations
    filtered_combinations = []
    for combo, count in current_combinations.items():
        if count >= min_occurrences:
            prev_count = previous_combinations.get(combo, 0)

            # Calculate month-over-month change
            mom_change = None
            if prev_count > 0:
                mom_change = ((count - prev_count) / prev_count) * 100

            filtered_combinations.append(
                {
                    "combination": " + ".join(combo),
                    "count": count,
                    "previous_month_count": prev_count,
                    "month_over_month_change": round(mom_change, 1) if mom_change is not None else None,
                }
            )

    # Sort by count (descending)
    filtered_combinations.sort(key=lambda x: x["count"], reverse=True)

    return {
        "technology_combinations": filtered_combinations[:limit],
        "total_posts_analyzed": len(current_post_techs),
        "total_combinations_found": len(current_combinations),
        "previous_month_total_posts": len(previous_post_techs),
        "previous_month_total_combinations": len(previous_combinations),
    }


def get_salary_data(source: PostSource, month: int, year: int):
    """
    Analyzes the percentage of job posts that include salary information and how this rate
    has changed over time. Also calculates salary statistics.

    A post is considered to have salary information if either min_salary or max_salary is greater than 0.

    Returns a dictionary with three main sections:
    - transparency_rate: Current and historical transparency rates with changes
    - min_salary: Minimum salary statistics and their changes over time
    - max_salary: Maximum salary statistics and their changes over time
    """
    # Get current month's posts and stats
    current_posts = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)
    total_current_posts = current_posts.count()

    if total_current_posts == 0:
        return {
            "transparency_rate": {
                "current": 0,
                "previous_month": None,
                "previous_year": None,
                "mom_change": None,
                "yoy_change": None,
                "total_posts": 0,
                "posts_with_salary": 0,
            },
            "min_salary": {
                "current_avg": None,
                "previous_month_avg": None,
                "previous_year_avg": None,
                "mom_avg_change": None,
                "yoy_avg_change": None,
                "current_median": None,
                "previous_month_median": None,
                "previous_year_median": None,
                "mom_median_change": None,
                "yoy_median_change": None,
            },
            "max_salary": {
                "current_avg": None,
                "previous_month_avg": None,
                "previous_year_avg": None,
                "mom_avg_change": None,
                "yoy_avg_change": None,
                "current_median": None,
                "previous_month_median": None,
                "previous_year_median": None,
                "mom_median_change": None,
                "yoy_median_change": None,
            },
        }

    # A post has salary info if either min or max salary is greater than 0
    posts_with_salary = current_posts.filter(Q(min_salary__gt=0) | Q(max_salary__gt=0)).count()

    current_rate = (posts_with_salary / total_current_posts) * 100

    # Get current month salary stats for posts with salary info
    current_salary_posts = current_posts.filter(Q(min_salary__gt=0) | Q(max_salary__gt=0)).order_by(
        "min_salary", "max_salary"
    )

    current_salary_stats = calculate_salary_stats(current_salary_posts)

    # Calculate previous month and year
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    # Get previous month's stats
    previous_month_posts = Post.objects.filter(
        source=source, submitted_datetime__month=previous_month, submitted_datetime__year=previous_year
    )
    total_previous_posts = previous_month_posts.count()

    previous_month_rate = None
    previous_month_salary_stats = None
    if total_previous_posts > 0:
        previous_with_salary = previous_month_posts.filter(Q(min_salary__gt=0) | Q(max_salary__gt=0)).count()
        previous_month_rate = (previous_with_salary / total_previous_posts) * 100

        previous_month_salary_posts = previous_month_posts.filter(Q(min_salary__gt=0) | Q(max_salary__gt=0)).order_by(
            "min_salary", "max_salary"
        )
        previous_month_salary_stats = calculate_salary_stats(previous_month_salary_posts)

    # Get last year's same month stats
    last_year_posts = Post.objects.filter(
        source=source, submitted_datetime__month=month, submitted_datetime__year=year - 1
    )
    total_last_year_posts = last_year_posts.count()

    last_year_rate = None
    previous_year_salary_stats = None
    if total_last_year_posts > 0:
        last_year_with_salary = last_year_posts.filter(Q(min_salary__gt=0) | Q(max_salary__gt=0)).count()
        last_year_rate = (last_year_with_salary / total_last_year_posts) * 100

        last_year_salary_posts = last_year_posts.filter(Q(min_salary__gt=0) | Q(max_salary__gt=0)).order_by(
            "min_salary", "max_salary"
        )
        previous_year_salary_stats = calculate_salary_stats(last_year_salary_posts)

    # Calculate changes
    month_over_month_change = None
    if previous_month_rate is not None:
        month_over_month_change = current_rate - previous_month_rate

    year_over_year_change = None
    if last_year_rate is not None:
        year_over_year_change = current_rate - last_year_rate

    # Calculate salary changes
    min_salary_mom_avg_change = None
    min_salary_yoy_avg_change = None
    min_salary_mom_median_change = None
    min_salary_yoy_median_change = None
    max_salary_mom_avg_change = None
    max_salary_yoy_avg_change = None
    max_salary_mom_median_change = None
    max_salary_yoy_median_change = None

    if current_salary_stats and previous_month_salary_stats:
        if "min_salary_avg" in current_salary_stats and "min_salary_avg" in previous_month_salary_stats:
            if previous_month_salary_stats["min_salary_avg"] > 0:
                min_salary_mom_avg_change = (
                    (current_salary_stats["min_salary_avg"] - previous_month_salary_stats["min_salary_avg"])
                    / previous_month_salary_stats["min_salary_avg"]
                ) * 100
        if "min_salary_median" in current_salary_stats and "min_salary_median" in previous_month_salary_stats:
            if previous_month_salary_stats["min_salary_median"] > 0:
                min_salary_mom_median_change = (
                    (current_salary_stats["min_salary_median"] - previous_month_salary_stats["min_salary_median"])
                    / previous_month_salary_stats["min_salary_median"]
                ) * 100
        if "max_salary_avg" in current_salary_stats and "max_salary_avg" in previous_month_salary_stats:
            if previous_month_salary_stats["max_salary_avg"] > 0:
                max_salary_mom_avg_change = (
                    (current_salary_stats["max_salary_avg"] - previous_month_salary_stats["max_salary_avg"])
                    / previous_month_salary_stats["max_salary_avg"]
                ) * 100
        if "max_salary_median" in current_salary_stats and "max_salary_median" in previous_month_salary_stats:
            if previous_month_salary_stats["max_salary_median"] > 0:
                max_salary_mom_median_change = (
                    (current_salary_stats["max_salary_median"] - previous_month_salary_stats["max_salary_median"])
                    / previous_month_salary_stats["max_salary_median"]
                ) * 100

    if current_salary_stats and previous_year_salary_stats:
        if "min_salary_avg" in current_salary_stats and "min_salary_avg" in previous_year_salary_stats:
            if previous_year_salary_stats["min_salary_avg"] > 0:
                min_salary_yoy_avg_change = (
                    (current_salary_stats["min_salary_avg"] - previous_year_salary_stats["min_salary_avg"])
                    / previous_year_salary_stats["min_salary_avg"]
                ) * 100
        if "min_salary_median" in current_salary_stats and "min_salary_median" in previous_year_salary_stats:
            if previous_year_salary_stats["min_salary_median"] > 0:
                min_salary_yoy_median_change = (
                    (current_salary_stats["min_salary_median"] - previous_year_salary_stats["min_salary_median"])
                    / previous_year_salary_stats["min_salary_median"]
                ) * 100
        if "max_salary_avg" in current_salary_stats and "max_salary_avg" in previous_year_salary_stats:
            if previous_year_salary_stats["max_salary_avg"] > 0:
                max_salary_yoy_avg_change = (
                    (current_salary_stats["max_salary_avg"] - previous_year_salary_stats["max_salary_avg"])
                    / previous_year_salary_stats["max_salary_avg"]
                ) * 100
        if "max_salary_median" in current_salary_stats and "max_salary_median" in previous_year_salary_stats:
            if previous_year_salary_stats["max_salary_median"] > 0:
                max_salary_yoy_median_change = (
                    (current_salary_stats["max_salary_median"] - previous_year_salary_stats["max_salary_median"])
                    / previous_year_salary_stats["max_salary_median"]
                ) * 100

    return {
        "transparency_rate": {
            "current": round(current_rate, 1),
            "previous_month": round(previous_month_rate, 1) if previous_month_rate is not None else None,
            "previous_year": round(last_year_rate, 1) if last_year_rate is not None else None,
            "mom_change": round(month_over_month_change, 1) if month_over_month_change is not None else None,
            "yoy_change": round(year_over_year_change, 1) if year_over_year_change is not None else None,
            "total_posts": total_current_posts,
            "posts_with_salary": posts_with_salary,
        },
        "min_salary": {
            "current_avg": current_salary_stats.get("min_salary_avg") if current_salary_stats else None,
            "previous_month_avg": previous_month_salary_stats.get("min_salary_avg")
            if previous_month_salary_stats
            else None,
            "previous_year_avg": previous_year_salary_stats.get("min_salary_avg")
            if previous_year_salary_stats
            else None,
            "mom_avg_change": round(min_salary_mom_avg_change, 1) if min_salary_mom_avg_change is not None else None,
            "yoy_avg_change": round(min_salary_yoy_avg_change, 1) if min_salary_yoy_avg_change is not None else None,
            "current_median": current_salary_stats.get("min_salary_median") if current_salary_stats else None,
            "previous_month_median": previous_month_salary_stats.get("min_salary_median")
            if previous_month_salary_stats
            else None,
            "previous_year_median": previous_year_salary_stats.get("min_salary_median")
            if previous_year_salary_stats
            else None,
            "mom_median_change": round(min_salary_mom_median_change, 1)
            if min_salary_mom_median_change is not None
            else None,
            "yoy_median_change": round(min_salary_yoy_median_change, 1)
            if min_salary_yoy_median_change is not None
            else None,
        },
        "max_salary": {
            "current_avg": current_salary_stats.get("max_salary_avg") if current_salary_stats else None,
            "previous_month_avg": previous_month_salary_stats.get("max_salary_avg")
            if previous_month_salary_stats
            else None,
            "previous_year_avg": previous_year_salary_stats.get("max_salary_avg")
            if previous_year_salary_stats
            else None,
            "mom_avg_change": round(max_salary_mom_avg_change, 1) if max_salary_mom_avg_change is not None else None,
            "yoy_avg_change": round(max_salary_yoy_avg_change, 1) if max_salary_yoy_avg_change is not None else None,
            "current_median": current_salary_stats.get("max_salary_median") if current_salary_stats else None,
            "previous_month_median": previous_month_salary_stats.get("max_salary_median")
            if previous_month_salary_stats
            else None,
            "previous_year_median": previous_year_salary_stats.get("max_salary_median")
            if previous_year_salary_stats
            else None,
            "mom_median_change": round(max_salary_mom_median_change, 1)
            if max_salary_mom_median_change is not None
            else None,
            "yoy_median_change": round(max_salary_yoy_median_change, 1)
            if max_salary_yoy_median_change is not None
            else None,
        },
    }


def calculate_salary_stats(queryset):
    """
    Calculate salary statistics (average and median) for a queryset of posts.
    Only considers posts where either min_salary or max_salary is greater than 0.
    """
    if not queryset.exists():
        return None

    # Convert queryset to list for easier manipulation
    posts = list(queryset.values("min_salary", "max_salary"))

    # Calculate min salary stats
    min_salaries = [p["min_salary"] for p in posts if p["min_salary"] > 0]
    max_salaries = [p["max_salary"] for p in posts if p["max_salary"] > 0]

    if not min_salaries and not max_salaries:
        return None

    stats = {}

    if min_salaries:
        min_salaries.sort()
        stats["min_salary_avg"] = round(sum(min_salaries) / len(min_salaries))
        stats["min_salary_median"] = min_salaries[len(min_salaries) // 2]

    if max_salaries:
        max_salaries.sort()
        stats["max_salary_avg"] = round(sum(max_salaries) / len(max_salaries))
        stats["max_salary_median"] = max_salaries[len(max_salaries) // 2]

    return stats


def get_work_arrangement_stats(source: PostSource, month: int, year: int):
    # Get current month's posts
    current_posts = Post.objects.filter(source=source, submitted_datetime__month=month, submitted_datetime__year=year)
    total_current_posts = current_posts.count()

    if total_current_posts == 0:
        return {
            "remote": {
                "current_percentage": 0,
                "previous_month_percentage": None,
                "previous_year_percentage": None,
                "mom_change": None,
                "yoy_change": None,
            },
            "onsite": {
                "current_percentage": 0,
                "previous_month_percentage": None,
                "previous_year_percentage": None,
                "mom_change": None,
                "yoy_change": None,
            },
            "hybrid": {
                "current_percentage": 0,
                "previous_month_percentage": None,
                "previous_year_percentage": None,
                "mom_change": None,
                "yoy_change": None,
            },
            "unknown": {
                "current_percentage": 0,
                "previous_month_percentage": None,
                "previous_year_percentage": None,
                "mom_change": None,
                "yoy_change": None,
            },
            "total_posts": 0,
        }

    # First identify hybrid posts (is_remote AND is_onsite, or hybrid keywords)
    hybrid_posts = (
        current_posts.filter(
            (Q(is_remote=True) & Q(is_onsite=True))
            | Q(description__iregex=r"hybrid|flexible|partially\s+remote|part\s+remote|remote\s+optional")
        )
        .distinct()
        .count()
    )

    # Then identify non-hybrid remote and onsite posts
    hybrid_post_ids = current_posts.filter(
        (Q(is_remote=True) & Q(is_onsite=True))
        | Q(description__iregex=r"hybrid|flexible|partially\s+remote|part\s+remote|remote\s+optional")
    ).values_list("id", flat=True)

    remote_posts = current_posts.filter(is_remote=True).exclude(id__in=hybrid_post_ids).count()
    onsite_posts = current_posts.filter(is_onsite=True).exclude(id__in=hybrid_post_ids).count()

    # Unknown posts are those not in any of the above categories
    unknown_posts = total_current_posts - (hybrid_posts + remote_posts + onsite_posts)

    # Calculate percentages
    current_remote_percentage = (remote_posts / total_current_posts) * 100
    current_onsite_percentage = (onsite_posts / total_current_posts) * 100
    current_hybrid_percentage = (hybrid_posts / total_current_posts) * 100
    current_unknown_percentage = (unknown_posts / total_current_posts) * 100

    # Get previous month's stats
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    previous_posts = Post.objects.filter(
        source=source, submitted_datetime__month=previous_month, submitted_datetime__year=previous_year
    )
    total_previous_posts = previous_posts.count()

    # Get previous year's stats
    last_year_posts = Post.objects.filter(
        source=source, submitted_datetime__month=month, submitted_datetime__year=year - 1
    )
    total_last_year_posts = last_year_posts.count()

    previous_remote_percentage = None
    previous_onsite_percentage = None
    previous_hybrid_percentage = None
    previous_unknown_percentage = None
    last_year_remote_percentage = None
    last_year_onsite_percentage = None
    last_year_hybrid_percentage = None
    last_year_unknown_percentage = None
    mom_remote_change = None
    mom_onsite_change = None
    mom_hybrid_change = None
    mom_unknown_change = None
    yoy_remote_change = None
    yoy_onsite_change = None
    yoy_hybrid_change = None
    yoy_unknown_change = None

    if total_previous_posts > 0:
        # Calculate previous month stats
        previous_hybrid_post_ids = previous_posts.filter(
            (Q(is_remote=True) & Q(is_onsite=True))
            | Q(description__iregex=r"hybrid|flexible|partially\s+remote|part\s+remote|remote\s+optional")
        ).values_list("id", flat=True)

        previous_hybrid = previous_posts.filter(id__in=previous_hybrid_post_ids).count()
        previous_remote = previous_posts.filter(is_remote=True).exclude(id__in=previous_hybrid_post_ids).count()
        previous_onsite = previous_posts.filter(is_onsite=True).exclude(id__in=previous_hybrid_post_ids).count()
        previous_unknown = total_previous_posts - (previous_hybrid + previous_remote + previous_onsite)

        previous_remote_percentage = (previous_remote / total_previous_posts) * 100
        previous_onsite_percentage = (previous_onsite / total_previous_posts) * 100
        previous_hybrid_percentage = (previous_hybrid / total_previous_posts) * 100
        previous_unknown_percentage = (previous_unknown / total_previous_posts) * 100

        # Calculate month-over-month changes
        mom_remote_change = current_remote_percentage - previous_remote_percentage
        mom_onsite_change = current_onsite_percentage - previous_onsite_percentage
        mom_hybrid_change = current_hybrid_percentage - previous_hybrid_percentage
        mom_unknown_change = current_unknown_percentage - previous_unknown_percentage

    if total_last_year_posts > 0:
        # Calculate last year stats
        last_year_hybrid_post_ids = last_year_posts.filter(
            (Q(is_remote=True) & Q(is_onsite=True))
            | Q(description__iregex=r"hybrid|flexible|partially\s+remote|part\s+remote|remote\s+optional")
        ).values_list("id", flat=True)

        last_year_hybrid = last_year_posts.filter(id__in=last_year_hybrid_post_ids).count()
        last_year_remote = last_year_posts.filter(is_remote=True).exclude(id__in=last_year_hybrid_post_ids).count()
        last_year_onsite = last_year_posts.filter(is_onsite=True).exclude(id__in=last_year_hybrid_post_ids).count()
        last_year_unknown = total_last_year_posts - (last_year_hybrid + last_year_remote + last_year_onsite)

        last_year_remote_percentage = (last_year_remote / total_last_year_posts) * 100
        last_year_onsite_percentage = (last_year_onsite / total_last_year_posts) * 100
        last_year_hybrid_percentage = (last_year_hybrid / total_last_year_posts) * 100
        last_year_unknown_percentage = (last_year_unknown / total_last_year_posts) * 100

        # Calculate year-over-year changes
        yoy_remote_change = current_remote_percentage - last_year_remote_percentage
        yoy_onsite_change = current_onsite_percentage - last_year_onsite_percentage
        yoy_hybrid_change = current_hybrid_percentage - last_year_hybrid_percentage
        yoy_unknown_change = current_unknown_percentage - last_year_unknown_percentage

    return {
        "remote": {
            "current_percentage": round(current_remote_percentage, 1),
            "previous_month_percentage": round(previous_remote_percentage, 1)
            if previous_remote_percentage is not None
            else None,
            "previous_year_percentage": round(last_year_remote_percentage, 1)
            if last_year_remote_percentage is not None
            else None,
            "mom_change": round(mom_remote_change, 1) if mom_remote_change is not None else None,
            "yoy_change": round(yoy_remote_change, 1) if yoy_remote_change is not None else None,
        },
        "onsite": {
            "current_percentage": round(current_onsite_percentage, 1),
            "previous_month_percentage": round(previous_onsite_percentage, 1)
            if previous_onsite_percentage is not None
            else None,
            "previous_year_percentage": round(last_year_onsite_percentage, 1)
            if last_year_onsite_percentage is not None
            else None,
            "mom_change": round(mom_onsite_change, 1) if mom_onsite_change is not None else None,
            "yoy_change": round(yoy_onsite_change, 1) if yoy_onsite_change is not None else None,
        },
        "hybrid": {
            "current_percentage": round(current_hybrid_percentage, 1),
            "previous_month_percentage": round(previous_hybrid_percentage, 1)
            if previous_hybrid_percentage is not None
            else None,
            "previous_year_percentage": round(last_year_hybrid_percentage, 1)
            if last_year_hybrid_percentage is not None
            else None,
            "mom_change": round(mom_hybrid_change, 1) if mom_hybrid_change is not None else None,
            "yoy_change": round(yoy_hybrid_change, 1) if yoy_hybrid_change is not None else None,
        },
        "unknown": {
            "current_percentage": round(current_unknown_percentage, 1),
            "previous_month_percentage": round(previous_unknown_percentage, 1)
            if previous_unknown_percentage is not None
            else None,
            "previous_year_percentage": round(last_year_unknown_percentage, 1)
            if last_year_unknown_percentage is not None
            else None,
            "mom_change": round(mom_unknown_change, 1) if mom_unknown_change is not None else None,
            "yoy_change": round(yoy_unknown_change, 1) if yoy_unknown_change is not None else None,
        },
        "total_posts": total_current_posts,
    }


def get_top_onsite_locations(source: PostSource, month: int, year: int, limit=20):
    """
    Analyzes the most frequently mentioned countries and cities in non-remote job posts.
    Returns the top locations with their counts and percentage changes compared to previous periods.

    Args:
        source: The source of the job posts (e.g., HACKER_NEWS)
        month: The month to analyze
        year: The year to analyze
        limit: Maximum number of locations to return (default 10)

    Returns:
        Dictionary containing:
        - Top countries with their counts and changes
        - Top cities with their counts and changes
        - Total number of posts analyzed
    """
    # Get current month's onsite posts
    current_posts = Post.objects.filter(
        source=source, submitted_datetime__month=month, submitted_datetime__year=year, is_onsite=True
    )
    total_current_posts = current_posts.count()

    if total_current_posts == 0:
        return {"countries": [], "cities": [], "total_posts": 0}

    # Calculate previous month and year
    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    # Get previous month's posts
    previous_posts = Post.objects.filter(
        source=source, submitted_datetime__month=previous_month, submitted_datetime__year=previous_year, is_onsite=True
    )

    # Get last year's posts
    last_year_posts = Post.objects.filter(
        source=source, submitted_datetime__month=month, submitted_datetime__year=year - 1, is_onsite=True
    )

    # Process current month's locations
    current_countries = {}
    current_cities = {}

    # Helper function to process locations
    def process_locations(posts, location_dict, field_name):
        for post in posts:
            locations = getattr(post, field_name, "").strip()
            if locations:
                for location in locations.split(","):
                    location = location.strip()
                    if location:
                        location_dict[location] = location_dict.get(location, 0) + 1

    # Process current month locations
    process_locations(current_posts, current_countries, "countries")
    process_locations(current_posts, current_cities, "cities")

    # Process previous month locations
    previous_countries = {}
    previous_cities = {}
    process_locations(previous_posts, previous_countries, "countries")
    process_locations(previous_posts, previous_cities, "cities")

    # Process last year locations
    last_year_countries = {}
    last_year_cities = {}
    process_locations(last_year_posts, last_year_countries, "countries")
    process_locations(last_year_posts, last_year_cities, "cities")

    # Helper function to calculate changes
    def calculate_changes(current_count, previous_count, last_year_count):
        mom_change = None
        yoy_change = None

        if previous_count > 0:
            mom_change = ((current_count - previous_count) / previous_count) * 100
        if last_year_count > 0:
            yoy_change = ((current_count - last_year_count) / last_year_count) * 100

        return mom_change, yoy_change

    # Prepare results
    def prepare_location_data(current_data, previous_data, last_year_data, total_posts):
        result = []
        for location, count in sorted(current_data.items(), key=lambda x: x[1], reverse=True)[:limit]:
            previous_count = previous_data.get(location, 0)
            last_year_count = last_year_data.get(location, 0)
            mom_change, yoy_change = calculate_changes(count, previous_count, last_year_count)

            result.append(
                {
                    "name": location,
                    "count": count,
                    "percentage": round((count / total_posts) * 100, 1),
                    "previous_month_count": previous_count,
                    "previous_year_count": last_year_count,
                    "mom_change": round(mom_change, 1) if mom_change is not None else None,
                    "yoy_change": round(yoy_change, 1) if yoy_change is not None else None,
                }
            )
        return result

    return {
        "countries": prepare_location_data(
            current_countries, previous_countries, last_year_countries, total_current_posts
        ),
        "cities": prepare_location_data(current_cities, previous_cities, last_year_cities, total_current_posts),
        "total_posts": total_current_posts,
    }
