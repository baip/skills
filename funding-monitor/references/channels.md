# Adding and editing channels

Read this when the user wants to monitor a new source ("also watch the Dreyfus Foundation page", "add the ACS newsletter", "track this RSS feed") or change how an existing one is monitored.

## Pick the means

Prefer the most structured option the source offers, because structure gives dates, numbers, and reliable dedupe.

1. **api**: only the built-in handlers (`grants_gov`, `simpler`, `sam`). A new API needs code in scan.py. Offer to write the handler if the user wants it, following the pattern of the existing ones.
2. **rss**: look for a feed before scraping. Check the page source for `<link rel="alternate" type="application/rss+xml">` or `application/atom+xml`, and try common paths (`/feed`, `/rss`, `/rss.xml`). Handler `rss` reads RSS 2.0 and Atom. For a news feed that mixes calls with other posts (most foundations and societies), set `item_pattern = "funding-calls"`.
3. **email**: newsletters and listservs. The user subscribes (guide them with `references/email-lists.md`), then you record the sender address. Read during the email sweep.
4. **alert**: a saved search at a provider (Simpler.Grants.gov, SAM.gov, Pivot-RP, GrantForward, Candid) that emails results. Record the sender once the first alert arrives.
5. **sitemap**: when a listing page needs JavaScript, check `/sitemap.xml` (or the `Sitemap:` line in robots.txt). Handler `sitemap` keeps URLs matching `loc_pattern` whose `lastmod` falls in the scan window and fetches each page for its title and deadline.
6. **web**: scrape links from a page that lists opportunities. Handler `web` respects robots.txt, collects links whose URL or text matches `link_pattern`, and uses standalone dates on the page (such as weekly section headings) to drop links older than the scan window.
7. **page**: one program page with no feed, listing or useful sitemap (common for company programs). Handler `page` reports the page the first time and whenever its text changes, quoting the new lines, which needs `--state`. Without state it reports the page only when it shows a deadline that has not passed.
8. **browser**: the page needs JavaScript and has no sitemap or feed. Handler `browser` renders it with headless Chromium through the optional Playwright package (`pip install playwright`, then `python3 -m playwright install chromium`). Use `row_selector` and `columns` to read table rows from the rendered page (most robust, and it captures each row's link), `row_regex` with named groups when the content is not a table, or `link_pattern` to collect rendered links. Without Playwright the channel is listed as a manual check. Prefer options 2 to 6 when they work, because rendering is slower and breaks when the layout changes.
9. **manual**: the page requires a login, the site blocks scripts with a bot-protection challenge, or its robots.txt disallows automated agents and the user has not chosen to override that. It appears in the plan and digest as a reminder to check by hand. Add `check_in_browser = true` when the site blocks scripts, so a live session opens it in the user's own browser (see "Sites that block scripts" in `references/foundations.md`), and `months` to show the reminder only when the call usually opens.

## Test before saving

1. Fetch the URL once with your web-fetch tool or `curl -sL` and look at it.
2. Add the block with `enabled = true`, then run `python3 <skill-dir>/scripts/scan.py --profile <profile> check --channel <id>`.
3. Read the result:
   - `OK (n items)`: look at a few items in a quick scan to confirm the links are real opportunities, not navigation.
   - `REACHABLE, nothing new in the last 30 days`: the source answered but had nothing in the test window. Normal for quiet feeds and for page watches without state.
   - `blocked by bot protection (...)`: the site answers scripts with a challenge page. scan.py does not try to get past it. Make the channel a browser check-in (`means = "manual"`, `check_in_browser = true`, `months`).
   - `page fetched but no matching links`: either adjust `link_pattern`, or the page is JavaScript-rendered (an HTML shell under about 10 KB is a strong sign). Then try a sitemap, then `browser`, then `manual`.
   - `robots.txt disallows`: tell the user and switch to `manual` unless they choose to override it. An override is the user's decision: set `ignore_robots = true` on that channel (or `[fetching] respect_robots = false` for the whole profile), keep the frequency weekly or slower, and mention that the site's terms of use may still restrict automated access.
   - dates on the page are deadlines rather than posting dates: set `use_section_dates = false`, otherwise current items are dropped as "old". Text printed after each matching link (deadline, amount, contact columns) is attached to that item, and scraped deadlines should be confirmed on the item's own page before they go in a digest.
   - many hundreds of links: add `use_section_dates` (default true) if the page has dated sections, or lower `max_links`, or tighten `link_pattern`.
4. Show the user the updated `scan.py plan` row.

## Channel fields

```toml
[[channel]]
id = "short-unique-id"          # required, lowercase, used in logs and state
name = "Human-readable name"     # shown in the plan
covers = "What kinds of opportunities this source carries"
means = "rss"                    # api | rss | sitemap | web | page | browser | email | alert | manual
handler = "rss"                  # grants_gov | simpler | sam | rss | sitemap | web | page | browser
url = "https://..."              # rss, web, manual
frequency = "weekly"             # each scan | daily | weekly | biweekly | monthly
enabled = true
ignore_robots = false            # set true only at the user's request; logged in every digest
agency = "Funder name"           # optional label for items from rss and web channels
agency_code = "NSF"              # optional, used for agency boosts
tags = ["energy"]                # optional, used by setup to suggest channels
min_bucket = "possible"          # optional: items from this channel never fall below this bucket

# rss only
item_pattern = "funding-calls"   # keep only call-like items (apply, call for, new program, launches, LOI, deadline...); or your own regex

# web only
link_pattern = "regex"           # matched against full URL or link text, case-insensitive
min_link_text = 12               # ignore short link texts such as "More"
max_links = 400
use_section_dates = true         # skip links under standalone dates older than the window. Set false when the page's dates are deadlines, not posting dates (then run with --state to get new-only items)

# sitemap only
loc_pattern = '/opportunities/[^/]+$'   # TOML literal string: no doubled backslashes
title_suffix = "| Site Name"     # trimmed from page titles
number_from_slug = true          # use the last URL segment as the opportunity number
max_pages = 25
sitemap_pattern = '/sitemap-\d+\.xml$'   # in a sitemap index, follow only these child sitemaps (skip image and video ones)
newest_sitemaps = 2              # with date-named child sitemaps (sitemap-202610.xml), read only the newest N
page_delay = 0.5                 # seconds between page fetches; raise it to honor a robots.txt Crawl-delay

# page only: one program page watched for changes (needs --state to detect changes)
title_suffix = "| Site Name"

# manual only
check_in_browser = true          # the site blocks scripts: open it in the user's own browser in a live session
months = [7, 8, 9]               # show the reminder only in these months

# browser only (optional Playwright dependency). Prefer row_selector over row_regex.
row_selector = "[role=row]"      # CSS selector for table rows in the rendered page
cell_selector = "td, [role=cell], [role=gridcell]"
columns = ["title", "desc", "due", "category"]   # field name per cell; "" skips a cell
filter = { field = "category", regex = "Limited Submission" }
row_regex = '^(?P<number>\S+)\t(?P<title>[^\t\n]+)$'   # named groups: number title desc due posted agency link
keep = "upcoming"                # drop rows whose due date has passed
wait_for = "table"               # optional CSS selector to wait for
wait_ms = 2000
timeout_ms = 90000

# email and alert only
senders = ["list@example.org"]
signup = "https://..."            # where the user subscribes; shown by plan until a sender is recorded
signup_hint = "email the program office and ask to be added"  # when no link is known; plan shows it instead

# keyed api only
key_env = "SAM_API_KEY"          # environment variable that holds the key
queries = ["..."]                # overrides [queries].api for grants_gov or simpler
organizations = ["..."]          # sam only, one request each
ptypes = ["o", "k", "p", "r", "s"]
max_requests_per_run = 4
```

`frequency` controls skipping only when scans run with `--state`. Without a state file every enabled channel runs each scan.

## Worked examples

A foundation news feed, filtered to calls (more in `references/foundations.md`):

```toml
[[channel]]
id = "foundation-dreyfus-feed"
name = "Camille and Henry Dreyfus Foundation news feed"
covers = "New Dreyfus programs and calls, filtered to call-like posts"
means = "rss"
handler = "rss"
url = "https://www.dreyfus.org/feed/"
item_pattern = "funding-calls"
agency = "Camille and Henry Dreyfus Foundation"
frequency = "weekly"
min_bucket = "possible"
enabled = true
```

A society newsletter:

```toml
[[channel]]
id = "society-funding-news"
name = "Society funding newsletter"
covers = "Society awards and grant calls"
means = "email"
senders = ["<sender address copied from a received issue>"]
frequency = "monthly"
enabled = true
```

Never invent a feed URL or sender address. If the user does not have one yet, add the channel with `enabled = false` and tell them what to fill in.
