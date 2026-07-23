# Tech Jobs Database SEO Sprint — Roadmap

> **Canonical document.** This is the single source of truth for the multi-phase SEO sprint. `docs/seo-roadmap.md` is the earlier technical pass and remains historical context.

## How to use this document

1. Read this file, `.seo/brand.md`, `.seo/config.json`, and `.seo/link-inventory.md`.
2. Pick the lowest-numbered pending phase whose product dependency is ready.
3. Re-query fresh SERP, pricing, feature, and owned-search data when a phase is more than 30 days old or depends on a newly launched interface.
4. Ship one phase per PR. Update this tracker and the link inventory in the same PR.
5. Do not publish API, CLI, or MCP acquisition pages before the corresponding interface is stable and usable.

## Phase Status Tracker

| # | Phase | Pattern | Status | PR |
|---|---|---|---|---|
| 0 | Technical foundations and measurement repair | Setup | pending | – |
| 1 | Retired-alert content and migration cleanup | Content pruning | pending | – |
| 2 | Strengthen Python, Rust, Golang, and Django job hubs | Existing programmatic boost | pending | – |
| 3 | Ship a Hacker News jobs source landing page | Data-led landing | pending | – |
| 4 | Build the highest-paying tech jobs hub | Data-led landing | pending | – |
| 5 | Build a remote developer jobs landing surface | Data-led landing | pending | – |
| 6 | Build an AI jobs landing surface | Data-led landing | pending | – |
| 7 | Publish API landing page and documentation | Developer surface | gated: API contract | – |
| 8 | Publish CLI and MCP landing pages and documentation | Agent surface | gated: CLI/MCP launch | – |
| 9 | Evaluate honest alternatives pages for API/MCP competitors | Alternatives | gated: machine interfaces | – |
| 10 | Audit the internal-link spine | Internal links | pending after phases 2–8 | – |
| 11 | Directory and listicle outreach | Off-page | pending after core pages | – |

Status convention: `pending` → `in_progress` → `completed`. Use `gated: <dependency>` when product readiness, not SEO work, is the blocker.

## Reference Data

### Site facts

- **Domain:** https://jobs.lvtd.dev
- **Legacy domain:** https://gettjalerts.com
- **Product:** Structured developer jobs database for people and AI agents
- **Stack:** Django 5.2, Django templates, Tailwind/Bootstrap, Hotwire/Stimulus
- **Keyword source:** DataForSEO, United States / English
- **Authority baseline:** DataForSEO rank 0; 46 referring domains; 2,484 of 2,561 backlinks are legacy-domain redirects
- **Conservative KD cap:** 30 until non-redirect authority improves
- **GSC:** `sc-domain:lvtd.dev` filtered to `https://jobs.lvtd.dev/`; legacy property `sc-domain:gettjalerts.com`
- **Plausible:** API access works for `gettjalerts.com`; `jobs.lvtd.dev` is not provisioned/accessible as a site ID
- **PostHog:** project `31589`
- **Marketing root:** `templates/`
- **Accent:** `oklch(0.47 0.12 164)`
- **Fonts:** system sans-serif

### Tool evidence snapshot

| Source | Status | Credential/config evidence | API/tool-call evidence | Used for | Config saved | Reason |
|---|---|---|---|---|---|---|
| GSC | connected | `TOOLS.md`; Infisical `/services/google-search-console` | Properties, 90-day query/page rows, and sitemaps queried | Owned search and migration | Two properties | New subdomain is covered by `sc-domain:lvtd.dev` |
| Ahrefs | missing | Deferred tools, env, `TOOLS.md`, and repo checked | No callable connector found | Would provide DR | `null` | DataForSEO supplied market data instead |
| DataForSEO | connected | `dataforseo-toolkit`; Infisical `/services/dataforseo` | Keyword, competitor, backlink, and live SERP calls succeeded | Volume, KD, CPC, SERP, authority | US / English | Primary measured market source |
| Plausible | connected | `PLAUSIBLE_API_KEY`; `TOOLS.md` API host | Legacy site queries succeeded; new site ID failed | Pages, sources, goals | `gettjalerts.com` | Connected with a domain-migration configuration gap |
| PostHog | connected | `POSTHOG_API_KEY`; project list | Project `31589` and 90-day HogQL queries succeeded | Channels, paths, events | `31589` | No custom conversion events currently exist |
| Exa | connected | `EXA_API_KEY` | Three market/competitor discovery searches succeeded | Competitor and source discovery | None | Current market discovery |
| Firecrawl | connected | `FIRECRAWL_API_KEY` | Six official competitor/product pages extracted | Current positioning and feature verification | None | Extraction succeeded; Jina fallback was unnecessary |

### Existing programmatic surface — do not duplicate

| Pattern | Current URL | SEO role | Main risk |
|---|---|---|---|
| Job detail | `/jobs/<uuid>` | Long-tail job/title/company queries | Expiry, UUID readability, duplicate tracking-parameter URLs |
| Company jobs | `/jobs/company/<slug>/` | Company-career queries | Thin/duplicate entities and stale inventory |
| Technology jobs | `/jobs/technology/<slug>/` | Technology-job queries | Thin list pages without unique data summaries |
| Title jobs | `/jobs/title/<slug>/` | Role-job queries | Thin list pages and title normalization quality |
| Highest-paid by technology | `/jobs/<slug>/highest-paid/` | Salary/highest-paying queries | No central hub and incomplete salary coverage |
| Filtered jobs | `/jobs/?...` | User search/filtering | Query parameters canonicalize to `/jobs/`; do not treat them as standalone landing pages |
| Blog | `/blog/<slug>` | HN trends and job-search content | Several posts promote alerts that are being retired |
| API | `/api/` | Machine access | Robots currently disallows `/api/`; no public acquisition/docs page |

### Critical files

| File | What lives there |
|---|---|
| `hn_jobs/sitemaps.py` | Sitemap families, freshness, canonical host |
| `templates/robots.txt` | Crawl rules and sitemap declaration |
| `templates/base.html` | Default metadata, Plausible/PostHog, homepage schema |
| `templates/jobs/all_jobs.html` | Jobs-index metadata, filters, ItemList/JobPosting schema |
| `templates/jobs/technology-jobs.html` | Technology landing page metadata and schema |
| `templates/jobs/title-jobs.html` | Title landing page metadata and schema |
| `templates/jobs/company-jobs.html` | Company landing page metadata and schema |
| `templates/jobs/highest-paid-job.html` | Salary landing page |
| `jobs/views.py` and `jobs/urls.py` | Public job and entity routing |
| `api/urls.py`, `api/views.py`, `api/schemas.py` | Current HTTP API |
| `templates/pages/home.html` | Database-first homepage |
| `frontend/src/styles/index.css` | Visual tokens |

## Keyword Research Appendix

All numbers are US English measurements from 2026-07-23 unless noted. Full cache: `.seo/keyword-research.json`.

### A.0 — Owned search and analytics baseline

- GSC for `jobs.lvtd.dev` returned **15 clicks / 629 impressions / 290 query-page rows** for 2026-04-24 through 2026-07-22.
- The legacy GSC property returned only **15 impressions and 0 clicks**, but its old sitemap remains submitted.
- The new sitemap is **not submitted** in the `lvtd.dev` property.
- PostHog recorded **22,029 pageviews**, **80 Organic Search sessions**, and **159 organic pageviews** over 90 days. It found no custom conversion events.
- Plausible's legacy site ID recorded Google/Bing/DuckDuckGo traffic, but no goals. The API rejects `jobs.lvtd.dev` as a site ID.
- DataForSEO sees only **9 ranking keywords** for the new domain; the best meaningful rows are still outside the top 20.

### A.1 — Alternatives candidates

| Candidate | Brand volume | Alternatives volume | KD | Decision |
|---|---:|---:|---:|---|
| Remote OK | 12,100 | 0 / unavailable | – | Do not prioritize |
| We Work Remotely | 33,100 | 10 | – | Do not prioritize |
| Himalayas | 1,900 | unavailable | – | Do not prioritize |
| TheirStack | 720 | unavailable | – | Revisit after API launch |
| JobsPipe | unavailable | unavailable | – | Revisit after API/MCP launch |
| Trackly | 210 | unavailable | – | Revisit after CLI/MCP launch |

There is not enough measured alternatives demand or product readiness to justify early commercial comparison pages.

### A.2 — Existing technology/use-case candidates

| Keyword | Volume | KD | CPC | Existing destination | Priority |
|---|---:|---:|---:|---|---|
| highest paying tech jobs | 2,900 | 0 | $19.54 | Fragmented by technology | High |
| python jobs | 1,900 | 19 | $2.47 | `/jobs/technology/python/` | High |
| rust jobs | 720 | 0 | $6.83 | `/jobs/technology/rust/` | High |
| golang jobs | 590 | 10 | $1.66 | `/jobs/technology/golang/` | High |
| hacker news jobs | 260 | 29 | $0.34 | No dedicated source page | High |
| django jobs | 210 | 11 | $0.64 | `/jobs/technology/django/` | High |
| hn jobs | 40 | 15 | – | No dedicated source page | Supporting |

### A.3 — Audience candidates

| Audience/intent | Volume | KD | Decision |
|---|---:|---:|---|
| remote software engineer jobs | 49,500 | 0 | Defer: giant job boards dominate live SERP |
| remote developer jobs | 22,200 | 4 | Build only with durable inventory and differentiated data summaries |
| remote tech jobs | 4,400 | 4 | Consolidate with the remote developer landing strategy |
| developer job board | 20 | 53 | Not a useful target |
| jobs for AI agents | 10 | 0 | Positioning support only; insufficient demand |

Low backlink-based KD does not override live SERP strength. Remote-developer pages need a data advantage, not generic copy.

### A.4 — API, CLI, and MCP candidates

| Keyword | Volume | KD | CPC | Decision |
|---|---:|---:|---:|---|
| jobs api | 590 | 26 | $12.00 | High commercial value after API stabilization |
| jobs mcp | 140 | 0 | – | Worth a launch page, but SERP intent is ambiguous |
| job search api | 110 | 27 | $7.76 | Support API page |
| job board api | 50 | 3 | $14.48 | Support API page |
| job data api | 50 | 17 | $17.04 | Support API page |
| job listings api | 40 | 9 | $17.26 | Support API page |
| job postings api | 20 | 2 | $4.59 | Support API page |
| job search mcp server | 10 | – | – | Support MCP page |

The `jobs api` SERP mixes Databricks, labor-market data providers, Google Jobs APIs, and public API directories. The page must explicitly disambiguate “job posting data API.”

### A.5 — Comparison candidates

DataForSEO returned no measurable rows for Remote OK vs We Work Remotely, Remote OK vs Himalayas, TheirStack vs JobsPipe, or the reverse variants. No comparison phase is currently justified.

### A.6 — Striking distance

The strict threshold (position 5–20 and ≥20 impressions) returned no rows. Several job-detail/company queries sit between positions 5 and 10 with 5–17 impressions; monitor them but do not create one-off phases from sparse data.

### A.7 — Conversion-weighted opportunities

| Candidate | Conversion signal | SEO signal | Priority effect |
|---|---|---|---|
| Existing jobs database and entity pages | Plausible `/jobs/` is the largest page family; PostHog organic entries land on jobs and company pages | GSC clicks already come from job/company details | Promote data-led improvements |
| API landing/docs | No activation event yet | $12–$17 CPC across API variants | Gate until interface and tracking are real |
| MCP landing/docs | No connection event yet | 140 volume, KD 0, ambiguous SERP | Gate until public launch |
| Alert content | No goals; product is retiring alerts | Existing indexed posts contradict direction | Promote cleanup before new content |

### A.8 — Head terms to avoid for now

| Keyword | Volume | KD | Why not now |
|---|---:|---:|---|
| jobs database | 6,600 | 100 | Unwinnable at current authority; use as positioning language |
| software engineer jobs | 40,500 | 9 | Live SERP strength is much higher than KD implies |
| AI jobs | 22,200 | 25 | Broad term; requires deep current inventory and a strong template |
| remote software engineer jobs | 49,500 | 0 | Dominated by LinkedIn, Indeed, Glassdoor, and ZipRecruiter |

### A.9 — Intentionally out of scope

- Email alert/digest acquisition or retention.
- Employer ATS/recruiting pages.
- Auto-apply and application-tracking claims.
- Public API/CLI/MCP SEO pages before those interfaces are stable.
- Location/role/technology combinatorial pages without recurring inventory thresholds.

## Phases

### Phase 0 — Technical foundations and measurement repair

**Why:** crawl/indexing signals and conversion measurement must be trustworthy before new landing pages ship.

**Scope:**

1. Replace template-interpolated JobPosting/ItemList JSON-LD with deterministic JSON serialization. The current `/jobs/` schema is invalid when descriptions contain raw newline control characters.
2. Give unfiltered `/jobs/` evergreen metadata. Current output is `Available Jobs - July 2026` and `Jobs that match these keywords: . From July 2026.`
3. Add `SoftwareApplication` or `Product` schema alongside the existing homepage `WebSite` schema, describing only shipped capabilities.
4. Cache or split the 9,485-URL sitemap. It is valid and deduplicated, but the measured response took ~17 seconds and exceeded the sprint audit script's 10-second timeout.
5. Submit `https://jobs.lvtd.dev/sitemap.xml` in the `sc-domain:lvtd.dev` GSC property and retain the legacy submission for migration monitoring.
6. Provision/rename the Plausible site so `jobs.lvtd.dev` is accepted, preserving legacy history where possible. The script already sends `data-domain="jobs.lvtd.dev"`.
7. Add or verify business events in PostHog: `job_search_performed`, `job_filter_applied`, `job_application_clicked`, and later `api_first_success`, `cli_first_query`, and `mcp_first_connection`.
8. Keep digest-removal code out of this phase to avoid colliding with the founder's in-progress removal work.

**Likely files:** `templates/jobs/all_jobs.html`, a JSON-LD helper/serializer and tests, `templates/base.html`, `hn_jobs/sitemaps.py`, analytics event call sites, `.seo/config.json`.

**Verification:**

- [ ] `/jobs/` JSON-LD parses with `json.loads` and validates as ItemList/JobPosting.
- [ ] Unfiltered and filtered jobs pages have intentional unique metadata and one canonical each.
- [ ] Homepage schema validates with no unsupported claims.
- [ ] Sitemap returns valid XML consistently under the agreed latency threshold.
- [ ] New sitemap appears in GSC with no submission errors.
- [ ] Plausible accepts `jobs.lvtd.dev` and records pageviews.
- [ ] PostHog receives at least the search/filter/application events.

### Phase 1 — Retired-alert content and migration cleanup

**Why:** indexed alert-led content and the legacy redirect contradict the database-first product and split trust.

**Scope:**

1. Refresh or redirect the two alert-led posts listed in `.seo/link-inventory.md`; preserve any useful search equity rather than deleting blindly.
2. Refresh `/blog/tech-job-video-intro` to remove stale domain/product references.
3. Add prominent database/entity links to both HN trend posts.
4. Change `gettjalerts.com/*` from a temporary redirect to a path-preserving single-hop `301` or `308` to `https://jobs.lvtd.dev/*` in the actual production routing layer.
5. Verify old/new canonicals and redirects with a representative URL set.

**Dependency:** Infrastructure access for the legacy-domain redirect.

### Phase 2 — Strengthen Python, Rust, Golang, and Django job hubs

**Why:** these pages already exist, match measured demand, and can gain value without creating index bloat.

**Scope per page:**

- Current open-job count and latest-post date.
- Common titles, companies, work modes, compensation coverage, and adjacent technologies from live data.
- At least two inbound links from the technology index, jobs page, homepage, blog, or sibling hubs.
- Valid ItemList/Breadcrumb schema and unique metadata.
- Honest empty/low-inventory behavior with `noindex` rules when thresholds are not met.

**Targets:** Python 1,900/KD 19; Rust 720/KD 0; Golang 590/KD 10; Django 210/KD 11.

### Phase 3 — Hacker News jobs source landing page

**Why:** the database has a defensible source-specific advantage and measured demand (`hacker news jobs`, 260/KD 29).

**Scope:**

- A stable source route with current HN jobs, month/source context, field coverage, and source attribution.
- Links from `/jobs/`, homepage, and both HN trend posts.
- Links out to relevant company, title, and technology hubs.
- FAQ and ItemList schema.
- No email-alert framing.

### Phase 4 — Highest-paying tech jobs hub

**Why:** `highest paying tech jobs` measures 2,900 volume, KD 0, and $19.54 CPC, while salary pages already exist by technology.

**Scope:**

- Central hub linking only to technology pages with sufficient current salary data.
- Explain salary coverage, currency normalization, recency, and missing-data limits.
- Aggregate live medians/ranges only where methodology is defensible.
- Add inbound links from homepage, jobs page, and technology index.

### Phase 5 — Remote developer jobs landing surface

**Why:** demand is large, but the live SERP is strong and a generic filter page will not compete.

**Gate:** Recurring inventory and a template that adds role, stack, location eligibility, salary coverage, source mix, and freshness summaries beyond a list.

**Targets:** `remote developer jobs` 22,200/KD 4; `remote tech jobs` 4,400/KD 4.

### Phase 6 — AI jobs landing surface

**Why:** `ai jobs` measures 22,200 volume/KD 25, but is broad.

**Gate:** Define the inclusion taxonomy and confirm enough current AI/ML roles. Avoid classifying jobs from incidental “AI” text alone.

### Phase 7 — API landing page and documentation

**Why:** measured commercial-intent terms are modest but valuable.

**Gate:** Public API contract, authentication, limits, freshness, error behavior, and quickstart must be stable.

**Scope:** A crawlable human docs/landing route, OpenAPI where accurate, first-request example, pricing/access truth, and activation event. Do not simply index the current machine `/api/` root while robots disallows it.

### Phase 8 — CLI and MCP landing pages and documentation

**Why:** machine access is central to product direction and `jobs mcp` already measures 140 volume/KD 0.

**Gate:** Installable CLI and connectable MCP server.

**Scope:** Installation, authentication, examples, tool/command reference, transport, limits, freshness, and first-success tracking. Cross-link API, CLI, and MCP pages.

### Phase 9 — Evaluate honest alternatives pages

Only after phases 7–8 ship, re-query alternatives demand and compare actual capabilities against TheirStack, JobsPipe, and Trackly. Every page must include at least three areas where the competitor is the better choice. Skip the phase if measured demand and switching intent remain absent.

### Phase 10 — Internal-link spine audit

Verify every priority landing page is reachable from at least two indexed pages, entity pages link across company/title/technology relationships, and no new page is orphaned. Update `.seo/link-inventory.md` with shipped destinations and anchor variations.

### Phase 11 — Directory and listicle outreach

Use `.seo/backlink-targets.json`. First update existing profiles/backlinks to the new domain. Then pursue developer-job, remote-work, public-API, and MCP directories only when the corresponding surface is public. No paid-link networks or generic mass submissions.

## Off-page checklist

- [ ] Update existing SaaSHub listing to `jobs.lvtd.dev`
- [ ] Update Built with Django profile and description
- [ ] Verify Django showcase/backlinks use the new canonical domain
- [ ] Submit to relevant remote-work resources after core landing pages ship
- [ ] Submit public API to API directories only after Phase 7
- [ ] Submit MCP server to MCP directories only after Phase 8
- [ ] Monitor referring domains separately from legacy redirect backlinks
