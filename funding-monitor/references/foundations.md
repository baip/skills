# Private foundations

Read this during Setup (choosing channels), in an Audit, and whenever a foundation call reached the user by some other route than the scan ("why didn't the monitor catch this?").

## Why foundation calls slip through

- Foundations post to no federal system, so Grants.gov, SAM.gov and agency feeds never carry them.
- An institution's foundation-relations database is curated by hand and is never complete. On 2026-11-04 the UMass Amherst database listed three Research Corporation for Science Advancement (RCSA) calls posted on 2026-10-26, but not RCSA's Team Science Accelerator (letter of intent due 2026-11-09) or the Dreyfus Foundation's new Program for Transformative Research.
- A new program is usually announced once, as a news post ("Team science focus of new RCSA funding program", 2026-08-10), and then lives on a program page that changes when the call opens. Neither is a listing of opportunities, so a scraper pointed at a "funding" page misses it.
- Many prestigious programs run by invitation or institutional nomination (for example Packard, Sloan, Keck, Beckman and Dreyfus Teacher-Scholar). For those the binding date is the institution's limited-submission deadline, which the institution's limited-submission channel covers.

## The layers

Use all four. They overlap on purpose, because each one misses things the others catch.

1. **The institution's foundation-relations office**: its database or newsletter (an `email`, `web` or `manual` channel, see `references/institutions/`), and the limited-submission list for nominated programs.
2. **The foundations that matter to this user**, watched directly. For each, pick the first route that works:
   1. Its news feed, filtered with `item_pattern = "funding-calls"`, which keeps posts that read like a call or a new program (apply, call for, request for proposals, new program, launches, now accepting, nominations, letter of intent, deadline) and drops award, staff and story posts. Most foundations run WordPress, so try `<site>/feed/` first.
   2. Its sitemap, with `loc_pattern` restricted to program pages (excluding dated news paths) and `min_bucket = "possible"`, which reports program pages added or updated in the window. This catches a call that opens on an existing page with no news post. The sitemap handler reads deadlines from the page, including calendar layouts such as "NOVEMBER 9, 2026 LOI Due".
   3. Its email newsletter (`email` channel with a `signup` link).
   4. A `manual` reminder when the site refuses automated requests (several large foundations answer scripts with a Cloudflare challenge).
3. **An aggregator saved search**, if the institution licenses one: Pivot-RP, GrantForward, SPIN or Candid's Foundation Directory. Each lets the user save keyword searches that are emailed weekly, and those emails become an `alert` channel. Ask the research office which one the institution has. Do not assume a license.
4. **The email sweep's catch-all query**, which already picks up forwards from colleagues and program officers.

## Choosing the foundations

During Setup, after the keywords are confirmed:

1. Propose the catalog rows below whose fields match the profile, and ask which foundations the user has applied to, been funded by, or been nominated for.
2. Ask the foundation-relations office's newsletter or database which foundations it lists for the user's field.
3. For a foundation not in the catalog, find its route with the steps under "Adding a foundation", then add the channels with `enabled = true` and run `check` on each.

Keep the list short and specific: five to ten foundations that fit, not every science funder. Each feed or sitemap channel costs one or two requests a week.

## Adding a foundation

1. Fetch `<site>/robots.txt`. Note any `Sitemap:` lines and whether automated agents are disallowed (then the route is `email` or `manual` unless the user overrides robots rules).
2. Try `<site>/feed/`. If it returns RSS, look at ten recent titles. If calls appear among them, add an `rss` channel with `item_pattern = "funding-calls"` and `min_bucket = "possible"`, and run `check`. The log line reports how many items the filter dropped.
3. Otherwise, or as well, open the sitemap. Find the path shape of program pages (for example `/<program>/` or `/programs/<name>/`), write a `loc_pattern` that excludes dated news paths such as `/2026/10/...`, and set `sitemap_pattern` when the sitemap index also lists image or video sitemaps. Set `title_suffix` to the site name the page titles end with.
4. Look for a newsletter link (often in the footer, "Subscribe" or "Newsletter") and add an `email` channel with that `signup` link and `senders = []`.
5. If the site answers scripts with 403 or a challenge page, use the newsletter and a `manual` reminder for its program page.

## Catalog

Checked 2026-11-04 from a script, not a browser. **V** = the route loaded and matched. **403** = the site answered scripts with a Cloudflare challenge page. Program names in the second column are examples and were not re-checked. Templates for the **V** feed and sitemap routes are in `config/profile.template.toml` (tag `foundation`), disabled by default.

| Foundation | Programs (examples) | Feed | Sitemap | Newsletter | Notes |
|---|---|---|---|---|---|
| Research Corporation for Science Advancement (RCSA) | Cottrell Scholar, SEED, STAR, IMPACT awards; Scialog; Team Science Accelerator | `https://rescorp.org/feed/` **V** | `https://rescorp.org/sitemap.xml` **V**, program pages at the top level | `https://rescorp.org/rcsa/email-list/` **V** | Feed caught the Team Science Accelerator announcement, sitemap caught its program page with both deadlines |
| Camille and Henry Dreyfus Foundation | Teacher-Scholar (nominated), Program for Transformative Research (announced 2026-10-15) | `https://www.dreyfus.org/feed/` **V** | `https://www.dreyfus.org/sitemap_index.xml` (from robots.txt) | none found on the home page | Feed posts are mostly awards, so the filter matters |
| Schmidt Sciences | AI for science, AI2050, Polymaths, climate, astrophysics | `https://www.schmidtsciences.org/feed/` **V** | `https://www.schmidtsciences.org/sitemap_index.xml` (from robots.txt) | sign-up form on the home page | Mostly press releases |
| Simons Foundation | Collaborations, Investigators, fellows programs | `https://www.simonsfoundation.org/feed/` **V** | `https://www.simonsfoundation.org/sitemap.xml` **V** | `https://www.simonsfoundation.org/newsletter/` | Feed is dominated by Flatiron Institute science news |
| Heising-Simons Foundation | 51 Pegasi b and Astronova fellowships, science events calls | `https://www.hsfoundation.org/feed/` **V** | `https://www.hsfoundation.org/sitemap_index.xml` (from robots.txt) | none found on the home page | Posts calls as "Now Accepting Applications" |
| David and Lucile Packard Foundation | Packard Fellowships for Science and Engineering (nominated) | `https://www.packard.org/feed/` **V**, rarely about calls | `https://www.packard.org/sitemap_index.xml` (from robots.txt) | the feed carries its newsletter issues | Institutional nomination, so the limited-submission channel is the route |
| Gordon and Betty Moore Foundation | Experimental Physics Investigators, Emergent Phenomena in Quantum Systems | none (`/feed/` returns a web page) | `https://www.moore.org/sitemap/sitemap-index.xml` (from robots.txt) | form on the home page | Program-page pattern not yet worked out |
| W. M. Keck Foundation | Research program (limited submission) | none | `https://www.wmkeck.org/sitemap.xml` **V** | not checked | Home page answered with a Cloudflare challenge. Limited-submission channel is the route |
| Alfred P. Sloan Foundation | Sloan Research Fellowships (nominated), program grants | **403** | **403** | not checked | Use its newsletter, if the user wants one, and the limited-submission channel |
| Arnold and Mabel Beckman Foundation | Beckman Young Investigators (limited submission) | **403** | **403** | not checked | Limited-submission channel |
| Kavli Foundation | Institutes and initiatives, rarely open calls | none | `https://www.kavlifoundation.org/sitemap.xml` **V** | not checked | Low value for open calls |

Fields other than the physical sciences have their own foundations (for example Howard Hughes Medical Institute, Burroughs Wellcome Fund and Chan Zuckerberg Initiative in biomedicine). Find their routes at run time with "Adding a foundation" and record them here once checked.
