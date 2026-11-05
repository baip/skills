# Private foundations, societies and company programs

Read this during Setup (choosing channels), in an Audit, when the user names a program to watch, and whenever a foundation call reached the user by some other route than the scan ("why didn't the monitor catch this?").

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
   3. Its program page, watched for changes (`page` handler), when the program has no feed and no useful sitemap. Most company programs (Samsung, UL Research Institutes) are like this.
   4. Its email newsletter (`email` channel with a `signup` link).
   5. A browser check-in (`manual` with `check_in_browser = true` and `months`) when the site blocks scripts. See "Sites that block scripts".
3. **An aggregator saved search**, if the institution licenses one: Pivot-RP, GrantForward, SPIN or Candid's Foundation Directory. Each lets the user save keyword searches that are emailed weekly, and those emails become an `alert` channel. Ask the research office which one the institution has. Do not assume a license.
4. **The email sweep's catch-all query**, which already picks up forwards from colleagues and program officers.

## Choosing the foundations

During Setup, after the keywords are confirmed:

1. Propose the catalog rows below whose fields match the profile, and ask which foundations the user has applied to, been funded by, or been nominated for.
2. Ask the foundation-relations office's newsletter or database which foundations it lists for the user's field.
3. For a foundation not in the catalog, find its route with the steps under "Adding a foundation", then add the channels with `enabled = true` and run `check` on each.

Keep the list short and specific: five to ten foundations that fit, not every science funder. Each feed or sitemap channel costs one or two requests a week.

## Sites that block scripts

Some sites put a bot-protection service in front of every page: Cloudflare (Sloan, Beckman, science.org, some Keck news pages), Imperva Incapsula (acs.org, which answers with status 200 and a challenge page) and Akamai (sony.com, 3m.com). A person in a normal browser passes these without noticing, and a script does not.

scan.py identifies itself honestly and does not try to get past them: it does not pretend to be a browser, run a disguised headless browser, or solve challenges. It recognizes the challenge pages, reports the channel as "blocked by bot protection", lists it under "Blocked by bot protection: check these in your own browser" in the scan output, and retries it next run.

The way to "check it like the user would" is to have the user's own browser do it:

1. Make the channel a browser check-in: `means = "manual"`, `check_in_browser = true`, the program page as `url`, and `months` set to when its call usually opens, so the reminder appears only then.
2. In a live session, if the agent has a browser tool that works in the user's own browser (for example Claude in Chrome, or the Claude desktop app's built-in browser), open each due check-in there and read the page, exactly as the user would. If the site shows a challenge or a CAPTCHA, stop and ask the user to complete it themselves. Never solve one.
3. Without a browser tool, or in an unattended run, list the check-ins with their links in Coverage notes so the user can open them.
4. Add the program's newsletter, if it has one, so announcements also arrive by email.

## Adding a foundation

1. Fetch `<site>/robots.txt`. Note any `Sitemap:` lines and whether automated agents are disallowed (then the route is `email` or `manual` unless the user overrides robots rules).
2. Try `<site>/feed/`. If it returns RSS, look at ten recent titles. If calls appear among them, add an `rss` channel with `item_pattern = "funding-calls"` and `min_bucket = "possible"`, and run `check`. The log line reports how many items the filter dropped.
3. Otherwise, or as well, open the sitemap. Find the path shape of program pages (for example `/<program>/` or `/programs/<name>/`), write a `loc_pattern` that excludes dated news paths such as `/2026/10/...`, and set `sitemap_pattern` when the sitemap index also lists image or video sitemaps. Set `title_suffix` to the site name the page titles end with.
4. Look for a newsletter link (often in the footer, "Subscribe" or "Newsletter") and add an `email` channel with that `signup` link and `senders = []`.
5. If neither a feed nor a sitemap shows the program, watch its program page: `means = "page"`, `handler = "page"`. With a state file it reports the page the first time and whenever its text changes, quoting the new lines. Without a state file it reports the page only when it shows a deadline that has not passed.
6. If the site answers scripts with a challenge page (`check` reports "blocked by bot protection"), make it a browser check-in as described above, and add its newsletter.

## Catalog

Checked 2026-11-04 from a script, not a browser. **V** = the route loaded and matched. **403** = the site answered scripts with a Cloudflare challenge page. Program names in the second column are examples and were not re-checked. Templates for the **V** feed and sitemap routes are in `config/profile.template.toml` (tag `foundation`), disabled by default.

| Foundation | Programs (examples) | Feed | Sitemap | Newsletter | Notes |
|---|---|---|---|---|---|
| Research Corporation for Science Advancement (RCSA) | Cottrell Scholar, SEED, STAR, IMPACT awards; Scialog; Team Science Accelerator | `https://rescorp.org/feed/` **V** | `https://rescorp.org/sitemap.xml` **V**, program pages at the top level | `https://rescorp.org/rcsa/email-list/` **V** | Feed caught the Team Science Accelerator announcement, sitemap caught its program page with both deadlines |
| Camille and Henry Dreyfus Foundation | Teacher-Scholar (nominated), Program for Transformative Research (announced 2026-10-15) | `https://www.dreyfus.org/feed/` **V** | `https://www.dreyfus.org/sitemap_index.xml` (from robots.txt) | none found on the home page | Feed posts are mostly awards, so the filter matters |
| Schmidt Sciences | AI for science, AI2050, Polymaths, climate, astrophysics | `https://www.schmidtsciences.org/feed/` **V** | `https://www.schmidtsciences.org/sitemap_index.xml` (from robots.txt) | sign-up form on the home page | Mostly press releases |
| Simons Foundation | Collaborations, Investigators, fellows programs | `https://www.simonsfoundation.org/feed/` **V** | `https://www.simonsfoundation.org/sitemap.xml` **V** | `https://www.simonsfoundation.org/newsletter/` | Feed is dominated by Flatiron Institute science news |
| Heising-Simons Foundation | 51 Pegasi b and Astronova fellowships, science events calls | `https://www.hsfoundation.org/feed/` **V** | `https://www.hsfoundation.org/sitemap_index.xml` (from robots.txt) | none found on the home page | Posts calls as "Now Accepting Applications" |
| David and Lucile Packard Foundation | Packard Fellowships for Science and Engineering | `https://www.packard.org/feed/` **V**, rarely about calls | `https://www.packard.org/sitemap_index.xml` **V** | `https://www.packard.org/stay-connected/` **V** | See "Named programs" |
| Gordon and Betty Moore Foundation | Experimental Physics Investigators, Emergent Phenomena in Quantum Systems | none (`/feed/` returns a web page) | `https://www.moore.org/sitemap/sitemap-index.xml` **V**, no lastmod dates and program pages use query strings | form on the home page | Moore Inventor Fellows ended: "In Spring 2025, we selected our tenth and final cohort" |
| W. M. Keck Foundation | Research program (limited submission) | `/feed/` **V** but empty | `https://www.wmkeck.org/sitemap_index.xml` **V** | none found | See "Named programs" |
| Alfred P. Sloan Foundation | Sloan Research Fellowships, program grants | **403** | **403** | not checked | Browser check-in, see "Named programs" |
| Arnold and Mabel Beckman Foundation | Beckman Young Investigators | **403** | **403** | page mentions updates by email, no link found | Browser check-in, see "Named programs" |
| Kavli Foundation | Institutes and initiatives, rarely open calls | none | `https://www.kavlifoundation.org/sitemap.xml` **V** | not checked | Low value for open calls |

Fields other than the physical sciences have their own foundations (for example Howard Hughes Medical Institute, Burroughs Wellcome Fund and Chan Zuckerberg Initiative in biomedicine). Find their routes at run time with "Adding a foundation" and record them here once checked.

## Named programs

Checked 2026-11-04 by fetching each page, except where marked **S** (secondary source) or **U** (not verified). Every row has a channel in the template (`program-*` ids, disabled by default) unless the route says "none". Dates are the ones the pages stated on that day: confirm before acting on them, and confirm the institution's internal deadline for nominated programs.

| Program | Sponsor (type) | Selection and eligibility | Next date stated | Channel |
|---|---|---|---|---|
| ACS Petroleum Research Fund (Doctoral New Investigator, New Directions) | American Chemical Society (society) | Open. DNI: first three years as assistant professor **S** | last cycle due March 6, 2026 **S** | Browser check-in, December to March (acs.org serves an Incapsula challenge) |
| Packard Fellowships for Science and Engineering | David and Lucile Packard Foundation | Nomination by the 50 invited institutions, two each, first three years on faculty. UMass Amherst is not invited | timeline gives March 15 for nominations and April 20 for applications, without a year | Sitemap of the guidelines and timeline pages |
| Sloan Research Fellowships | Alfred P. Sloan Foundation | Department nomination, untenured tenure-track faculty in chemistry, computer science, Earth system science, economics, mathematics, neuroscience, physics or related fields | "Applications for 2028 Sloan Research Fellowships will open on July 15, 2027" | Browser check-in, July to September (Cloudflare) |
| Beckman Young Investigators | Arnold and Mabel Beckman Foundation | Letter of intent with institutional endorsement, first four years of a tenure-track appointment | portal usually open June to August **U** | Browser check-in, May to August (Cloudflare) |
| Welch Foundation research grants | The Welch Foundation | Texas institutions only | January 31 each year | Page watch (useful only in Texas) |
| W. M. Keck Foundation research program | W. M. Keck Foundation | Limited submission, up to 3 per institution through the campus liaison | December 7, 2026 and June 7, 2027 (4:30 p.m. Pacific) | Sitemap of research pages and research news. Some news pages answer scripts with a Cloudflare challenge |
| Moore Inventor Fellows | Gordon and Betty Moore Foundation | Ended after the 2025 cohort | none | none |
| Blavatnik National Awards for Young Scientists | Blavatnik Family Foundation, run by the New York Academy of Sciences | Institutional nomination, one per category (Physical Sciences & Engineering, Chemical Sciences, Life Sciences), born in or after 1985. UMass Amherst is on the eligible list | nominations close December 2, 2026, 11:59 p.m. Pacific. Letters of support due December 16, 2026 | Sitemap of dates, guidelines and institutions pages |
| Searle Scholars Program | Kinship Foundation | Participating institutions only ("University of Massachusetts" is listed, campus not stated), biomedical and related chemistry, first tenure-track appointment on or after May 1, 2025 for the last cycle | next cycle starts June 1, 2027 | Sitemap of cycle-dates and eligibility pages, monthly, with a 5-second delay (the site rate-limits) |
| 3M Non-Tenured Faculty Award | 3M (company) | Invitation: nominated by 3M researchers **S** | none | none. Only through a 3M research contact. 3m.com answers scripts with an Akamai denial |
| AI for the Global Goals | Google.org (company philanthropy) | Open call in 2022 and 2023, now archived | none | Google.org news feed, filtered for open calls and impact challenges |
| Amazon Research Awards | Amazon (company) | Open, one proposal per PI per call period, full-time faculty | Fall 2026 calls close November 11, 2026 (all on AI, security or Trainium) | Sitemap: the two newest monthly sitemaps, call-for-proposals pages, 10-second delay (robots.txt crawl delay). The program's RSS feed is stale |
| Sony Focused Research Award | Sony Group (company) | Open to universities in the US, Canada, India and listed European countries; Sony-chosen themes | 2026 cycle closed (September 15, 2026 **S**) | Browser check-in, July to September (Akamai) |
| Climate Change AI Innovation Grants | Climate Change AI (nonprofit) | 2024 call: OECD-country universities; 2025 by invitation | "does not currently have any future calls of this program planned" | Page watch of the calls page, monthly. Newsletter at `https://www.climatechange.ai/newsletter` |
| Samsung Global Collaboration grants = Global Research Outreach (GRO) | Samsung Advanced Institute of Technology (company) | Open to university researchers worldwide. 2026 topics included electronic materials for memory and thermal-management materials | 2026 closed August 23, 2026. Next call expected around June 2027 **U** | Page watch of the program page |
| ECS Toyota Young Investigator Fellowship | The Electrochemical Society with Toyota Research Institute of North America | Open, under 45, working in North America or Europe, ECS member, green-energy electrochemistry | 2026 closed May 22, 2026. The 2025–2026 call opened November 22, 2024 | Tag feed for the fellowship |
| Synthesis Advanced Research Challenge | Toyota Research Institute (company) | Open request for proposals, 2024, two phases. Phase Two went to one team (October 27, 2026 news) | none | Toyota Research Institute feed, filtered for challenges and university programs |
| Cooperative AI Research Grants | Cooperative AI Foundation (UK charity), recent call with Schmidt Sciences, Google DeepMind and others | Open worldwide, multi-agent AI safety | August 8, 2026 call closed | Sitemap of grant and call pages (each round gets a new page) |
| Global Science Summit Programme | Novo Nordisk Foundation | Open, international teams of 2 or 3 groups. The 2026 topic was digital and AI tools for cardiometabolic disease | 2026 closed September 1, 2026 | The foundation's feed of all grant calls |
| Chen Institute and Science Prize for AI Accelerated Research | Tianqiao and Chrissy Chen Institute, run by Science (AAAS) | Essay prize for early-career scientists in AI-related fields, degree within the last 10 years | entry period ends December 13, 2026, 11:59 p.m. Eastern | Page watch of the contest rules. Newsletter: `https://cheninstitute.us17.list-manage.com/subscribe?u=52012dde9962674edda12541c&id=d582baebcb`. science.org pages use Cloudflare |
| UL Research Institutes Discoveries Grant = Discoveries in Safety Grants | UL Research Institutes (nonprofit) | Open, letter of intent first, global, current grantees excluded. 2026 topics included recovering critical minerals from energy storage | 2026 closed. The previous call opened December 3, 2025 with letters due January 27, 2026 | Page watch of the grants page, where all calls are posted |
