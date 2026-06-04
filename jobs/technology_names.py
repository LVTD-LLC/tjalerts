import html
import re


DEFAULT_TECHNOLOGY_ALIASES = (
    ("python", "Python"),
    ("python3", "Python"),
    ("py", "Python"),
    ("django", "Django"),
    ("drf", "Django REST Framework"),
    ("django rest framework", "Django REST Framework"),
    ("django-rest-framework", "Django REST Framework"),
    ("django rest", "Django REST Framework"),
    ("flask", "Flask"),
    ("fastapi", "FastAPI"),
    ("fast api", "FastAPI"),
    ("javascript", "JavaScript"),
    ("java script", "JavaScript"),
    ("js", "JavaScript"),
    ("typescript", "TypeScript"),
    ("type script", "TypeScript"),
    ("ts", "TypeScript"),
    ("node", "Node.js"),
    ("nodejs", "Node.js"),
    ("node.js", "Node.js"),
    ("react", "React"),
    ("reactjs", "React"),
    ("react.js", "React"),
    ("react native", "React Native"),
    ("next", "Next.js"),
    ("nextjs", "Next.js"),
    ("next.js", "Next.js"),
    ("vue", "Vue.js"),
    ("vuejs", "Vue.js"),
    ("vue.js", "Vue.js"),
    ("nuxt", "Nuxt.js"),
    ("nuxtjs", "Nuxt.js"),
    ("nuxt.js", "Nuxt.js"),
    ("angular", "Angular"),
    ("svelte", "Svelte"),
    ("sveltekit", "SvelteKit"),
    ("svelte kit", "SvelteKit"),
    ("ruby", "Ruby"),
    ("rails", "Ruby on Rails"),
    ("ruby rails", "Ruby on Rails"),
    ("ruby on rails", "Ruby on Rails"),
    ("ror", "Ruby on Rails"),
    ("go", "Go"),
    ("golang", "Go"),
    ("rust", "Rust"),
    ("java", "Java"),
    ("kotlin", "Kotlin"),
    ("swift", "Swift"),
    ("php", "PHP"),
    ("laravel", "Laravel"),
    ("elixir", "Elixir"),
    ("phoenix", "Phoenix"),
    ("phoenix framework", "Phoenix"),
    ("c", "C"),
    ("c++", "C++"),
    ("cpp", "C++"),
    ("c plus plus", "C++"),
    ("c#", "C#"),
    ("c sharp", "C#"),
    (".net", ".NET"),
    ("dotnet", ".NET"),
    ("asp.net", "ASP.NET"),
    ("aspnet", "ASP.NET"),
    ("asp net", "ASP.NET"),
    ("objective c", "Objective-C"),
    ("objective-c", "Objective-C"),
    ("scala", "Scala"),
    ("clojure", "Clojure"),
    ("haskell", "Haskell"),
    ("erlang", "Erlang"),
    ("postgres", "PostgreSQL"),
    ("postgresql", "PostgreSQL"),
    ("postgre sql", "PostgreSQL"),
    ("mysql", "MySQL"),
    ("sqlite", "SQLite"),
    ("mongo", "MongoDB"),
    ("mongodb", "MongoDB"),
    ("redis", "Redis"),
    ("elastic search", "Elasticsearch"),
    ("elasticsearch", "Elasticsearch"),
    ("opensearch", "OpenSearch"),
    ("open search", "OpenSearch"),
    ("dynamodb", "DynamoDB"),
    ("dynamo db", "DynamoDB"),
    ("sql", "SQL"),
    ("graphql", "GraphQL"),
    ("graph ql", "GraphQL"),
    ("aws", "AWS"),
    ("amazon web services", "AWS"),
    ("gcp", "Google Cloud"),
    ("google cloud", "Google Cloud"),
    ("google cloud platform", "Google Cloud"),
    ("azure", "Azure"),
    ("microsoft azure", "Azure"),
    ("docker", "Docker"),
    ("kubernetes", "Kubernetes"),
    ("k8s", "Kubernetes"),
    ("terraform", "Terraform"),
    ("ansible", "Ansible"),
    ("heroku", "Heroku"),
    ("cloudflare", "Cloudflare"),
    ("vercel", "Vercel"),
    ("netlify", "Netlify"),
    ("github actions", "GitHub Actions"),
    ("ci/cd", "CI/CD"),
    ("cicd", "CI/CD"),
    ("kafka", "Kafka"),
    ("apache kafka", "Kafka"),
    ("rabbitmq", "RabbitMQ"),
    ("rabbit mq", "RabbitMQ"),
    ("celery", "Celery"),
    ("spark", "Apache Spark"),
    ("apache spark", "Apache Spark"),
    ("airflow", "Apache Airflow"),
    ("apache airflow", "Apache Airflow"),
    ("dbt", "dbt"),
    ("snowflake", "Snowflake"),
    ("bigquery", "BigQuery"),
    ("big query", "BigQuery"),
    ("redshift", "Redshift"),
    ("datadog", "Datadog"),
    ("sentry", "Sentry"),
    ("opentelemetry", "OpenTelemetry"),
    ("open telemetry", "OpenTelemetry"),
    ("pandas", "Pandas"),
    ("numpy", "NumPy"),
    ("py torch", "PyTorch"),
    ("pytorch", "PyTorch"),
    ("tensorflow", "TensorFlow"),
    ("tensor flow", "TensorFlow"),
    ("scikit learn", "scikit-learn"),
    ("sklearn", "scikit-learn"),
    ("openai", "OpenAI"),
    ("open ai", "OpenAI"),
    ("openai api", "OpenAI API"),
    ("llm", "LLM"),
    ("llms", "LLM"),
)

DESCRIPTOR_PATTERNS = (
    r"\bbackend\b",
    r"\bback end\b",
    r"\bfront[\s-]?end\b",
    r"\bfull[\s-]?stack\b",
    r"\bengineers?\b",
    r"\bdevelopers?\b",
    r"\bapis?\b",
    r"\bprogrammers?\b",
    r"\bprogramming\b",
    r"\bdevelopment\b",
    r"\broles?\b",
    r"\bjobs?\b",
    r"\bstack\b",
    r"\bplatform\b",
    r"\blanguages?\b",
    r"\blibraries?\b",
    r"\btools?\b",
    r"\bservices?\b",
    r"\bapps?\b",
    r"\bapplications?\b",
    r"\bsystems?\b",
    r"\bpipelines?\b",
)

GENERIC_TECHNOLOGY_KEYS = {
    "",
    "api",
    "apis",
    "backend",
    "back end",
    "frontend",
    "front end",
    "fullstack",
    "full stack",
    "web",
    "mobile",
    "cloud",
    "database",
    "databases",
    "framework",
    "frameworks",
    "language",
    "languages",
    "library",
    "libraries",
    "tool",
    "tools",
    "platform",
    "platforms",
    "rest",
    "restful",
    "stack",
    "stacks",
}

VERSIONABLE_TECHNOLOGY_KEYS = {
    "angular",
    "django",
    "dotnet",
    "java",
    "node",
    "nodejs",
    "php",
    "python",
    "rails",
    "react",
    "ruby",
    "vue",
}

SPECIAL_KEY_REPLACEMENTS = (
    ("c++", "cplusplus"),
    ("c#", "csharp"),
    ("asp.net", "aspnet"),
    (".net", "dotnet"),
    ("node.js", "nodejs"),
    ("react.js", "reactjs"),
    ("next.js", "nextjs"),
    ("vue.js", "vuejs"),
    ("nuxt.js", "nuxtjs"),
)


def normalize_technology_key(value):
    text = html.unescape(str(value or "")).casefold()
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    text = text.replace("&", " and ")

    for old, new in SPECIAL_KEY_REPLACEMENTS:
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9+#./-]+", " ", text)
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return strip_version_suffix(text)


def strip_version_suffix(normalized_key):
    parts = normalized_key.split()
    if len(parts) < 2:
        return normalized_key

    first = parts[0]
    if first not in VERSIONABLE_TECHNOLOGY_KEYS:
        return normalized_key

    suffix = " ".join(parts[1:])
    if re.fullmatch(r"(?:v?\d+(?:[.\s]\d+)*|x|lts)(?:\s+(?:v?\d+(?:[.\s]\d+)*|x|lts))*", suffix):
        return first

    return normalized_key


DEFAULT_TECHNOLOGY_ALIAS_MAP = {}
for alias, canonical_name in DEFAULT_TECHNOLOGY_ALIASES:
    DEFAULT_TECHNOLOGY_ALIAS_MAP.setdefault(normalize_technology_key(alias), canonical_name)


def split_context_technology_values(value):
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = re.split(r"[,;\n]+", str(value or ""))

    return [html.unescape(str(raw_value)).strip() for raw_value in raw_values if str(raw_value).strip()]


def extract_technology_names(value):
    names = []
    seen = set()

    for raw_value in split_context_technology_values(value):
        for name in expand_technology_value(raw_value):
            key = normalize_technology_key(name)
            if key and key not in seen:
                names.append(name)
                seen.add(key)

    return names


def expand_technology_value(value):
    value = clean_technology_display_value(value)
    if not value:
        return []

    exact_alias = DEFAULT_TECHNOLOGY_ALIAS_MAP.get(normalize_technology_key(value))
    if exact_alias:
        return [exact_alias]

    inner_values = []
    base_value = value
    for inner_value in re.findall(r"\(([^)]+)\)", value):
        inner_values.extend(expand_technology_value(inner_value))

    base_value = re.sub(r"\([^)]*\)", " ", base_value)
    base_value = clean_technology_display_value(base_value)
    if not base_value:
        return deduplicate_technology_names(inner_values)

    descriptor_cleaned_value = remove_descriptors(base_value)
    if descriptor_cleaned_value != base_value:
        return deduplicate_technology_names([*expand_technology_value(descriptor_cleaned_value), *inner_values])

    if should_split_composite_value(base_value):
        values = []
        parts = re.split(r"\s*/\s*|\s+\+\s+|\s+and\s+|\s+with\s+|\s+&\s+", base_value, flags=re.IGNORECASE)
        for part in parts:
            values.extend(expand_technology_value(part))
        return deduplicate_technology_names([*values, *inner_values])

    canonical_name = DEFAULT_TECHNOLOGY_ALIAS_MAP.get(normalize_technology_key(base_value))
    values = []
    if canonical_name:
        values.append(canonical_name)
    elif not is_generic_technology_value(base_value):
        values.append(base_value)

    return deduplicate_technology_names([*values, *inner_values])


def clean_technology_display_value(value):
    value = html.unescape(str(value or "")).strip()
    value = value.strip(" \t\r\n'\"`[]{}")
    value = value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def remove_descriptors(value):
    normalized_value = value
    for pattern in DESCRIPTOR_PATTERNS:
        normalized_value = re.sub(pattern, " ", normalized_value, flags=re.IGNORECASE)
    normalized_value = re.sub(r"\s+", " ", normalized_value).strip(" -/")
    return normalized_value


def should_split_composite_value(value):
    if DEFAULT_TECHNOLOGY_ALIAS_MAP.get(normalize_technology_key(value)):
        return False

    return bool(re.search(r"\s*/\s*|\s+\+\s+|\s+and\s+|\s+with\s+|\s+&\s+", value, flags=re.IGNORECASE))


def is_generic_technology_value(value):
    return normalize_technology_key(value) in GENERIC_TECHNOLOGY_KEYS


def deduplicate_technology_names(values):
    names = []
    seen = set()

    for value in values:
        key = normalize_technology_key(value)
        if key and key not in seen:
            names.append(value)
            seen.add(key)

    return names
