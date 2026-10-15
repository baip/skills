# Funding source catalog (United States)

Read this for coverage audits, for explaining why a channel exists, and when judging which sources a user in a given field needs. Verification tags: **V** = checked live on the date shown. **S** = supported by a secondary source, not re-checked at the primary source. **U** = unverified. Re-verify S and U items before stating them as fact.

## 1. Why one feed is never enough

- Grants.gov lists assistance awards (grants and cooperative agreements). Department of Defense (DoD) and Defense Advanced Research Projects Agency (DARPA) broad agency announcements (BAAs), requests for information (RFIs), and special notices are procurement notices on SAM.gov.
- National Science Foundation (NSF) Dear Colleague Letters (DCLs) and many program pages appear on nsf.gov without a Grants.gov record.
- The legacy "Grants.gov Opportunities Update" email digest degraded during the move to Simpler.Grants.gov. A thread on forum.simpler.grants.gov (Aug 2026) reports the all-opportunities digest stopping after migration, and one user's inbox showed the digest arriving about weekly from August to October 2026 with mostly unrelated agencies. **V 2026-10-09**
- Private foundations rarely post to any federal system. Institutional research and foundation-relations offices are the main curated route.
- Limited-submission programs depend on internal institutional deadlines that no federal feed shows.

## 2. Machine-readable sources

| Source | Endpoint | Auth | Status |
|---|---|---|---|
| Grants.gov search2 | `POST https://api.grants.gov/v1/api/search2` | none | **V 2026-10-09** |
| Grants.gov fetchOpportunity | `POST https://api.grants.gov/v1/api/fetchOpportunity` | none | **V 2026-10-09** |
| NSF program announcements RSS | `https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml` | none | **V 2026-10-09**. No per-item dates. Channel date lagged by six weeks on the test date. |
| NSF upcoming due dates RSS | `https://www.nsf.gov/rss/rss_www_funding_upcoming.xml` | none | **V 2026-10-09**. Deadlines in the next 30 days. Contains unescaped ampersands, which scan.py repairs. |
| NIH Guide funding opportunities RSS | `https://grants.nih.gov/grants/guide/newsfeed/fundingopps.xml` | none | **V 2026-10-09** |
| Simpler.Grants.gov API | `POST https://api.simpler.grants.gov/v1/opportunities/search` | `X-API-Key` | 401 without key **V 2026-10-09**. scan.py query path not live-tested. |
| SAM.gov Get Opportunities v2 | `GET https://api.sam.gov/opportunities/v2/search` | `api_key` | Parameters per GSA documentation **V 2026-10-09**. scan.py query path not live-tested. |

Grants.gov quirks observed 2026-10-09:

- `keyword` matching is fuzzy and returns unrelated agencies. scan.py scores on title and synopsis instead of trusting query hits.
- `dateRange` takes a day count and buckets by week. scan.py also filters on `openDate`.
- "OR" inside one keyword string is not a Boolean union. Send one term per query.
- Applicant type codes: 06 public higher education, 20 private higher education, 12 nonprofit 501(c)(3), 25 "others, see text", 99 unrestricted.

## 3. Agency pages and portals

| Page | Scrapable | Notes |
|---|---|---|
| DOE Office of Science funding opportunities, `https://science.osti.gov/Funding-Opportunities` | yes | FOA and lab-announcement PDFs match `/grants/pdf/(foas|lab-announcements)/`. **V 2026-10-09** |
| ONR announcements, `https://www.onr.navy.mil/work-with-us/funding-opportunities/announcements` | yes | Opportunity pages match `/work-with-us/funding-opportunities/[a-z0-9-]{25,}`. **V 2026-10-09** |
| DARPA opportunities, `https://www.darpa.mil/work-with-us/opportunities` | via sitemap or RSS | The listing renders with JavaScript. Two structured routes exist: `https://www.darpa.mil/sitemap.xml` lists every opportunity page with a last-modified date (28 on the test date), and each page states its number and deadline. `https://www.darpa.mil/rss/opportunities.xml` (linked from the DARPAConnect page) carries the latest 10 opportunities with office and summary, but every item links to the general listing and has no number or deadline. `darpa.mil/rss.xml` is a news feed. **V 2026-10-09** |
| DOE Funding Opportunity Exchange, `https://exchange.energy.gov/Default.aspx` | with a headless browser | The old EERE eXCHANGE and ARPA-E eXCHANGE addresses now redirect here ("This eXCHANGE site has moved"). The table loads with JavaScript. Rendered with Playwright it gave 19 rows: NOFOs, lab calls, notices of intent, RFIs, and teaming partner lists, several of which are not on Grants.gov. **V 2026-10-09** |

A Congressional Research Service brief reports that DOE reorganized EERE functions into an Office of Critical Minerals and Energy Innovation (CMEI) on November 20, 2025. **S**

## 4. Email channels

| Channel | Sender | Notes |
|---|---|---|
| NSF Update | `nsf-update@govdelivery.nsf.gov` | daily digest option, topic selection. Sender **V** from a real inbox. |
| NSF division newsletters | GovDelivery | Chemistry has a monthly newsletter **V**. Others not checked. |
| NIH Guide weekly TOC | `GuideTOC@mail.nih.gov` | Fridays **V**. A university research-office page reports that from fiscal year 2026 NIH publishes NOFOs only on Grants.gov **S**. |
| DOE Office of Science | `updates@info.science.doe.gov` | Mixes FOAs, awards, jobs, town halls **V** |
| DOE applied offices | various `@service.govdelivery.com` and `@public.govdelivery.com` lists | subscribe per office |
| Provider saved searches | Simpler.Grants.gov, SAM.gov, Pivot-RP, GrantForward, Candid | see `api-keys.md` |

## 5. Foundations and aggregators

| Tool | Use | Status |
|---|---|---|
| Institutional foundation-relations office | curated foundation calls, help identifying aligned funders | varies by institution |
| Foundation Directory Online (Candid) | prospecting funders without open calls, RFP alerts | often licensed through university libraries |
| Pivot-RP (Clarivate) | saved searches, weekly email, profile-based recommendations | institutional license |
| GrantForward | saved searches, sponsor alerts, pre-solicitation alerts | institutional license or trial |
| Candid RFP Bulletin | weekly newsletter | public **S** |

Many prestigious foundation programs (for example Keck, Beckman, Dreyfus, Research Corporation, Packard) run through institutional nomination, so the binding date is internal.

## 6. Signals that precede solicitations

Report these under "Forecasts and signals", not as opportunities: forecasted Grants.gov items, SAM.gov RFIs, sources-sought and special notices, agency town halls and summits, advisory committee meetings, NSF office hours, DCLs announcing future competitions, and award announcements for annual programs.

## 7. Pages that need JavaScript

Options in order of preference, all tested 2026-10-09 except where noted:

1. A structured source behind the page: sitemap.xml with lastmod (DARPA), an RSS or Atom feed that is not linked from the listing page itself (DARPA's is linked only from its DARPAConnect page), an export view, or the data requests visible in browser developer tools. Data endpoints that need session cookies or signed parameters (InfoReady's) are brittle and not used.
2. The same content through another channel: Exchange NOFOs on Grants.gov, DARPA BAAs on SAM.gov, limited submissions in research-office email.
3. Headless rendering with the `browser` handler (Playwright and Chromium, optional). Heavier and sensitive to layout changes, so each browser channel logs a "check manually" line when its pattern stops matching.
4. A self-hosted page-change monitor such as changedetection.io, which can render JavaScript and send notifications. Not tested here.
5. A browser agent working in the user's own browser session, for pages behind a login. Semi-manual.

Robots rules apply by default. `umass.infoready4.com/robots.txt` disallows all automated agents (`Disallow: /`), so the UMass limited-submission table is a manual channel unless the user overrides robots.txt for it, in which case the `browser` handler reads it (see `institutions/umass-amherst.md`).
