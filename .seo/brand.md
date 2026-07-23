# Tech Jobs Database (TJ Alerts) — Brand Context for SEO

> Read every time. This file is the product and positioning contract for every SEO sprint phase.

## Product

- **Name:** Tech Jobs Database (TJ Alerts)
- **One-liner:** A structured, searchable database of developer jobs for people and AI agents.
- **What we do:** Aggregate developer jobs from Hacker News, Remote OK, and We Work Remotely; normalize role, company, technology, compensation, location, work mode, contact, and application data; expose the same records through a web UI and, as those interfaces ship, API, CLI, and MCP.
- **Pricing structure:** Public browsing is currently free. Pricing for API, CLI, and MCP access is not yet defined.
- **Free tier?** Yes for the public web database. Do not promise a permanent free machine-access tier before product decisions are final.

## Audience

- **Primary persona:** Actively job-seeking developers who need current, filterable job data.
- **Secondary personas:** AI agents searching on a user's behalf; developers building job-search workflows; researchers analyzing developer hiring.
- **Industries:** Software, developer tools, AI, data, infrastructure, and technology-enabled companies.
- **Company size:** Any; inventory quality matters more than employer size.
- **Jobs to be done:**
  1. Find relevant developer openings quickly without scanning several source sites.
  2. Compare roles by stack, company, compensation, location, source, and work mode.
  3. Query dependable normalized job records from software or an AI agent.

## Competitors

The product spans two markets. Human-facing job boards compete for discovery; job-data products compete for programmatic access.

| Brand | Slug | URL | Segment | Notes |
|---|---|---|---|---|
| Remote OK | `remote-ok` | https://remoteok.com/ | Job board | Large remote inventory, category pages, public feeds/API references |
| We Work Remotely | `we-work-remotely` | https://weworkremotely.com/ | Job board | Established remote board with strong role and contract-job pages |
| Himalayas | `himalayas` | https://himalayas.app/jobs | Job board | Rich company, salary, career-guide, and job-description surfaces |
| TheirStack | `theirstack` | https://theirstack.com/en/job-posting-api | Jobs API | Large commercial job-postings dataset with company and technology data |
| JobsPipe | `jobspipe` | https://jobspipe.dev/jobs-api | Jobs API + MCP | Developer-first normalized schema, webhooks, source pages, and MCP |
| Trackly | `trackly` | https://usetrackly.app/cli | CLI + MCP | Job search, application tracking, CLI, local MCP, and remote MCP |

## Brand voice

- **Voice tags:** Clear, useful, technical, quiet, direct, honest.
- **Perspective:** You-focused; use “we” only when explaining product decisions or data methods.
- **Forbidden phrases:** “revolutionary,” “seamless,” “AI-powered” without a concrete mechanism, “all jobs,” “never miss a job,” and any email-digest promise.
- **Tone references:** Good developer documentation and dependable data tools: concise, specific, and transparent about limits.

## Anti-positioning

1. We are not an email digest or alert product; those features are being retired.
2. We are not an ATS, recruiter CRM, or employer-side applicant tracking system.
3. We do not auto-apply to jobs or manage a user's full application pipeline.
4. We do not claim complete coverage of every job on the internet.
5. We are not a general-purpose LinkedIn or Indeed replacement.
6. We do not expose machine interfaces before they are stable and documented.

## Concrete differentiators

1. The same normalized records are intended for UI, API, CLI, and MCP consumption.
2. Every record retains source attribution and an application path.
3. Structured fields and semantic intent search support both precise filters and fuzzy queries.
4. Hacker News “Who is Hiring?” data is normalized alongside remote-job sources.
5. Technology, title, company, compensation, location, and work-mode entities create useful cross-linked discovery surfaces.

## Visual brand

- **Accent:** `oklch(0.47 0.12 164)` with hover `oklch(0.4 0.11 164)`
- **Ink:** `oklch(0.21 0.006 247)`
- **Surface:** `oklch(0.995 0.002 247)`
- **Hero/body font:** System sans-serif stack; no separate display font is configured.
- **Icon set:** No canonical icon set detected.

## Links to existing surfaces

- Homepage: https://jobs.lvtd.dev/
- Job database: https://jobs.lvtd.dev/jobs/
- Companies: https://jobs.lvtd.dev/jobs/companies/
- Technologies: https://jobs.lvtd.dev/jobs/technologies/
- Titles: https://jobs.lvtd.dev/jobs/titles/
- Blog: https://jobs.lvtd.dev/blog/
- API root: https://jobs.lvtd.dev/api/ (machine endpoint; currently disallowed in robots.txt)
- Pricing: Not currently public.
