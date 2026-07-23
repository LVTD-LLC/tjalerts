# SEO Roadmap: Jobs Database

Last updated: 2026-07-23

## Product thesis

`jobs.lvtd.dev` is a structured jobs database for people and AI agents. The same normalized job records should be discoverable through the web UI and reusable through the API, CLI, and MCP. Email digests are being retired and should not anchor acquisition, page copy, or new SEO work.

The durable organic advantage is the underlying data: current jobs organized by role, technology, company, compensation, location, work mode, and source.

## Baseline audit

The live site already has useful SEO primitives:

- Public job, company, technology, title, and editorial pages.
- Crawlable internal links from index pages to detail pages.
- Canonical tags, XML sitemap, robots.txt, and `JobPosting`/`ItemList` structured data.
- Recent-job filtering that keeps many directory pages useful rather than permanently stale.

The 2026-07-23 live audit found two urgent migration issues:

- `jobs.lvtd.dev` served canonical tags, robots.txt, and sitemap URLs for `gettjalerts.com`.
- The sitemap contained 9,619 entries but only 9,235 unique URLs: 384 duplicate entries across 193 paths. Duplicate slugs affected company, technology, title, and highest-paid page families.
- `gettjalerts.com` used a temporary redirect to `http://jobs.lvtd.dev/` instead of a permanent, single-hop HTTPS redirect that preserves the requested path.

This sprint fixes the in-repo sitemap duplication, default canonical host, analytics attribution, and database-first metadata. Production configuration and the legacy-domain redirect still need deployment-level verification.

## Prioritized roadmap

### Now: protect the domain migration

**Outcome:** consolidate existing authority on `jobs.lvtd.dev` and stop sending conflicting canonical signals.

- Set production `SITE_URL=https://jobs.lvtd.dev`.
- Update the Django Site record for `SITE_ID=1` to `jobs.lvtd.dev`.
- Redirect every `gettjalerts.com/*` URL to the equivalent `https://jobs.lvtd.dev/*` URL with one `301` or `308` hop.
- Keep both domains verified in Google Search Console, submit `https://jobs.lvtd.dev/sitemap.xml`, and use Change of Address if the property supports it.
- Confirm canonicals, Open Graph URLs, robots sitemap reference, sitemap locations, and structured-data URLs all use the new HTTPS host after deploy.
- Retain redirects for at least one year and monitor legacy-domain crawl activity before considering removal.

**Owner:** engineering / infrastructure  
**Effort:** small  
**Impact:** very high  
**Confidence:** high  
**Leading indicators:** new-domain indexed pages, falling old-domain impressions, no alternate-canonical errors  
**Business outcome:** preserves discoverability and prior link equity during the move

### Now: make database pages the acquisition surface

**Outcome:** match search intent with useful, current inventory rather than alert-oriented copy.

- Lead the homepage with database search, filters, sources, and normalized fields.
- Remove digest promotion as the feature is retired; avoid replacing it with unsupported promises.
- Keep category hubs for jobs, companies, technologies, and titles prominent in global navigation.
- Improve page titles and descriptions for each template using the primary entity and actual inventory.
- Keep filtered query-string pages canonicalized to the stable jobs index unless a filter combination becomes a curated landing page.

**Owner:** product + engineering + content  
**Effort:** small to medium  
**Impact:** high  
**Confidence:** high  
**Leading indicators:** organic entrances to database pages, search-to-job-detail rate, application-link clicks  
**Business outcome:** more qualified job discovery and repeat database usage

### Next: improve the existing programmatic page families

**Outcome:** turn entity directories into defensible landing pages rather than thin result lists.

- Consolidate duplicate company, technology, and title records so each slug maps to one entity.
- Add useful summary blocks based on live data: open-job count, latest-post date, common roles/stacks, remote share, salary coverage, and source mix.
- Index only pages with enough current inventory and unique value; return a useful empty state without keeping expired thin pages indexed indefinitely.
- Use deterministic, escaped JSON-LD serialization and validate representative pages with Google Rich Results Test.
- Add breadcrumbs and contextual cross-links: job → company/role/technology; entity page → related entities; hub → priority entities.
- Replace UUID-only job URLs with stable descriptive slugs only if redirects and collision handling can be guaranteed. UUID URLs are acceptable until then.

**Owner:** engineering + data + content  
**Effort:** medium  
**Impact:** high  
**Confidence:** medium-high  
**Leading indicators:** valid indexed entity pages, non-brand impressions, entity-page engagement  
**Business outcome:** scalable acquisition from long-tail job searches

### Next: create public access landing pages

**Outcome:** capture developer and agent demand while making each interface easy to adopt.

- Ship `/api/`, `/cli/`, and `/mcp/` documentation pages when each interface is publicly usable.
- Give each page a distinct job-to-be-done, examples, authentication model, limits, freshness expectations, and link to a working quickstart.
- Link these pages from the homepage, footer, developer docs, and each other in the same release that makes the interface available.
- Add machine-readable API documentation and an `llms.txt` only when they accurately represent the production surface.

**Owner:** engineering + developer documentation  
**Effort:** medium  
**Impact:** medium-high  
**Confidence:** medium  
**Leading indicators:** docs entrances, successful first request/tool call, API-key creation, CLI installs, MCP connections  
**Business outcome:** adoption by developers and AI agents

### Later: launch evidence-backed landing-page expansions

**Outcome:** expand only where inventory and search demand justify a durable page.

Candidate dimensions:

- Technology + role.
- Role + remote/work mode.
- Technology + location.
- Salary-transparent jobs.
- Source-specific collections such as Hacker News jobs.

Before shipping a page family:

1. Confirm recurring inventory and minimum quality thresholds.
2. Measure keyword demand and inspect current search results.
3. Define unique content/data beyond a filtered list.
4. Ship the destination and at least two relevant internal links atomically.
5. Add the page family to the sitemap only after indexability and canonical tests pass.

**Owner:** product + data + SEO + engineering  
**Effort:** large  
**Impact:** potentially high  
**Confidence:** low until validated  
**Leading indicators:** qualifying inventory, indexed-page quality, impressions per page family  
**Business outcome:** efficient long-tail acquisition without index bloat

## Measurement

Track the funnel by landing-page family and access method:

1. Search visibility: indexed pages, impressions, clicks, and canonical/indexation errors.
2. Database engagement: searches, filters used, job-detail views, and return visits.
3. Job outcome proxy: outbound application clicks.
4. Developer/agent activation: first successful API request, CLI query, or MCP connection.
5. Retention: repeat human searches and repeat authenticated machine usage.

Avoid treating raw indexed-page count or ranking count as the goal. The useful outcome is qualified job discovery and repeated consumption of the database.
