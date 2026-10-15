# Adding and editing channels

Read this when the user wants to monitor a new source ("also watch the Sloan Foundation page", "add the ACS newsletter", "track this RSS feed") or change how an existing one is monitored.

## Pick the means

Prefer the most structured option the source offers, because structure gives dates, numbers, and reliable dedupe.

1. **api**: only the built-in handlers (`grants_gov`, `simpler`, `sam`). A new API needs code in scan.py. Offer to write the handler if the user wants it, following the pattern of the existing ones.
2. **rss**: look for a feed before scraping. Check the page source for `<link rel="alternate" type="application/rss+xml">` or `application/atom+xml`, and try common paths (`/feed`, `/rss`, `/rss.xml`). Handler `rss` reads RSS 2.0 and Atom.
3. **email**: newsletters and listservs. The user subscribes (guide them with `references/email-lists.md`), then you record the sender address. Read during the email sweep.
4. **alert**: a saved search at a provider (Simpler.Grants.gov, SAM.gov, Pivot-RP, GrantForward, Candid) that emails results. Record the sender once the first alert arrives.
5. **sitemap**: when a listing page needs JavaScript, check `/sitemap.xml` (or the `Sitemap:` line in robots.txt). Handler `sitemap` keeps URLs matching `loc_pattern` whose `lastmod` falls in the scan window and fetches each page for its title and deadline.
6. **web**: scrape links from a page that lists opportunities. Handler `web` respects robots.txt, collects links whose URL or text matches `link_pattern`, and uses standalone dates on the page (such as weekly section headings) to drop links older than the scan window.
7. **browser**: the page needs JavaScript and has no sitemap or feed. Handler `browser` renders it with headless Chromium through the optional Playwright package (`pip install playwright`, then `python3 -m playwright install chromium`). Use `row_selector` and `columns` to read table rows from the rendered page (most robust, and it captures each row's link), `row_regex` with named groups when the content is not a table, or `link_pattern` to collect rendered links. Without Playwright the channel is listed as a manual check. Prefer options 2 to 6 when they work, because rendering is slower and breaks when the layout changes.
8. **manual**: the page requires a login, or its robots.txt disallows automated agents and the user has not chosen to override that. It appears in the plan and digest as a reminder to check by hand.

## Test before saving

1. Fetch the URL once with web_fetch or curl and look at it.
2. Add the block with `enabled = true`, then run `python3 scripts/scan.py --profile <profile> check --channel <id>`.
3. Read the result:
   - `OK (n items)`: look at a few items in a quick scan to confirm the links are real opportunities, not navigation.
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
means = "rss"                    # api | rss | sitemap | web | browser | email | alert | manual
handler = "rss"                  # grants_gov | simpler | sam | rss | sitemap | web | browser
url = "https://..."              # rss, web, manual
frequency = "weekly"             # each scan | daily | weekly | biweekly | monthly
enabled = true
ignore_robots = false            # set true only at the user's request; logged in every digest
agency = "Funder name"           # optional label for items from rss and web channels
agency_code = "NSF"              # optional, used for agency boosts
tags = ["energy"]                # optional, used by setup to suggest channels
min_bucket = "possible"          # optional: items from this channel never fall below this bucket

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

A foundation news page with an RSS feed:

```toml
[[channel]]
id = "sloan-news"
name = "Sloan Foundation news feed"
covers = "Program announcements and calls"
means = "rss"
handler = "rss"
url = "<feed URL found on the page>"
agency = "Alfred P. Sloan Foundation"
frequency = "weekly"
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
