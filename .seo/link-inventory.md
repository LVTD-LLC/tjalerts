# Tech Jobs Database — Internal Link Inventory

> Every SEO phase selects links from this inventory and updates it when a new destination ships.

## Core pages

| Slug | URL | Anchor-text candidates | Used by |
|---|---|---|---|
| `/` | https://jobs.lvtd.dev/ | tech jobs database; structured developer jobs | All |
| `/jobs/` | https://jobs.lvtd.dev/jobs/ | search developer jobs; browse all jobs | All |
| `/jobs/companies/` | https://jobs.lvtd.dev/jobs/companies/ | companies hiring now; browse hiring companies | Entity and playbook pages |
| `/jobs/technologies/` | https://jobs.lvtd.dev/jobs/technologies/ | technologies in demand; browse jobs by stack | Technology and playbook pages |
| `/jobs/titles/` | https://jobs.lvtd.dev/jobs/titles/ | jobs by role; browse job titles | Role and playbook pages |
| `/blog/` | https://jobs.lvtd.dev/blog/ | developer hiring research; job-search guides | Playbooks |
| `/support` | https://jobs.lvtd.dev/support | support | Occasional |
| `/uses` | https://jobs.lvtd.dev/uses | product stack | Developer pages |

## Existing data-led landing pages

| Slug | URL | Anchor-text candidates | Notes |
|---|---|---|---|
| `/jobs/technology/python/` | https://jobs.lvtd.dev/jobs/technology/python/ | Python jobs; jobs using Python | Target: `python jobs` |
| `/jobs/technology/django/` | https://jobs.lvtd.dev/jobs/technology/django/ | Django jobs; jobs using Django | Target: `django jobs` |
| `/jobs/technology/rust/` | https://jobs.lvtd.dev/jobs/technology/rust/ | Rust jobs; jobs using Rust | Target: `rust jobs` |
| `/jobs/technology/golang/` | https://jobs.lvtd.dev/jobs/technology/golang/ | Golang jobs; Go developer jobs | Target: `golang jobs` |
| `/jobs/technology/artificial-intelligence/` | https://jobs.lvtd.dev/jobs/technology/artificial-intelligence/ | AI jobs; artificial intelligence jobs | Broad term; requires SERP caution |
| `/jobs/title/software-engineer/` | https://jobs.lvtd.dev/jobs/title/software-engineer/ | software engineer jobs; software engineering roles | Strong SERP competition |
| `/jobs/title/full-stack-engineer/` | https://jobs.lvtd.dev/jobs/title/full-stack-engineer/ | full-stack engineer jobs; full-stack roles | Existing role hub |
| `/jobs/python/highest-paid/` | https://jobs.lvtd.dev/jobs/python/highest-paid/ | highest-paid Python jobs; Python salary jobs | Existing salary surface |
| `/jobs/rust/highest-paid/` | https://jobs.lvtd.dev/jobs/rust/highest-paid/ | highest-paid Rust jobs; Rust salary jobs | Existing salary surface |

## Existing blog posts

| URL | Title | Disposition |
|---|---|---|
| `/blog/who-is-hiring-april-2025` | HN “Who is Hiring?” Trends — April 2025 | Keep; update internal links and freshness framing |
| `/blog/who-is-hiring-march-2025` | HN “Who is Hiring?” Trends — March 2025 | Keep; update internal links and freshness framing |
| `/blog/find-dream-tech-job-faster-personalized-alerts` | Find Your Dream Tech Job Faster with Personalized Alerts | Refresh or redirect away from retired alerts |
| `/blog/5-secrets-to-effortless-tech-job-hunting-with-automated-notifications` | 5 Secrets to Effortless Tech Job Hunting with Automated Notifications | Refresh or redirect away from retired alerts |
| `/blog/tech-job-video-intro` | The Hidden Secret to Get the Job of Your Dreams | Refresh stale brand/domain references |

## Planned sprint pages

| Destination | Phase | Inbound-link requirement |
|---|---:|---|
| Hacker News jobs source page | 3 | Homepage/jobs page + both existing HN trend posts |
| Highest-paying tech jobs hub | 4 | Homepage/jobs page + technology index |
| Remote developer jobs landing page | 5 | Homepage/jobs page + relevant title/technology pages |
| AI jobs landing page | 6 | Homepage/jobs page + AI technology page |
| Public API landing/docs | 7 | Homepage/footer + jobs/MCP/CLI pages |
| MCP landing/docs | 8 | Homepage/footer + API/CLI pages |
| CLI landing/docs | 8 | Homepage/footer + API/MCP pages |

## Anchor-text guidance

- Vary descriptive anchors; never use generic “click here.”
- Link to a new landing page from at least two already-indexed pages in the same release.
- Prefer anchors that describe the destination's inventory or interface, not marketing adjectives.
