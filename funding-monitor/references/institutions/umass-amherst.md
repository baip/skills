# University of Massachusetts Amherst

Channel blocks verified on 2026-10-09, including the two URLs most useful for science and engineering faculty: the ORD weekly funding opportunities page and the filtered FR opportunities database. Offer them during setup to UMass Amherst users and paste the accepted blocks into the profile. Re-run `scan.py check` on each, since campus sites change.

Facts worth telling UMass users:

- The Office of Research Development (ORD) publishes a weekly list of federal opportunities, grouped under dated weekly headings, with links to Grants.gov and SAM.gov. Because it includes SAM.gov broad agency announcements, it partly substitutes for a SAM.gov API key.
- ORD's limited-submission page says that opportunities reported to ORD fewer than eight weeks before the sponsor deadline generally get no internal competition, and slots then go in order of time-stamped contact. When a scan finds a limited-submission program missing from the ORD table, tell the user to contact ORD the same day.
- The limited-submission table itself lives in InfoReady (umass.infoready4.com). It renders publicly with a headless browser (33 rows on 2026-10-09, including past internal deadlines), but its robots.txt disallows all automated agents, so it is a manual channel by default. ORD's emails and the ORD weekly page are the automated routes. A user who chooses to override robots.txt for this one page can replace the manual block with the browser block at the end of this file.
- Foundation Relations (FR) runs a searchable opportunities database and a recurring limited-submissions page, and emails a weekly Foundation Funding Guide. The FR FAQ describes the guide as distributed to all faculty, so faculty should not need to subscribe. If it is missing from a faculty member's inbox, check spam filters before contacting FR. The FR FAQ says Foundation Directory Online is available through the UMass Amherst Libraries.

```toml
[[channel]]
id = "umass-ord-weekly"
name = "UMass ORD weekly funding opportunities page"
covers = "ORD-curated Grants.gov and SAM.gov items, including DoD BAAs"
means = "web"
handler = "web"
url = "https://www.umass.edu/research/weekly-funding-opportunities"
link_pattern = "grants\\.gov/search-results-detail|sam\\.gov/.*opp/"
agency = "UMass ORD list"
frequency = "weekly"
enabled = true

[[channel]]
id = "umass-limited-submissions"
name = "UMass ORD limited submissions (InfoReady)"
covers = "Limited-submission programs and internal deadlines"
means = "manual"
url = "https://umass.infoready4.com/#limitedsubmissions"
frequency = "weekly"
enabled = true

[[channel]]
id = "umass-fr-database"
name = "UMass Foundation Relations opportunities database"
covers = "Private foundation calls, newest first"
means = "web"
handler = "web"
url = "https://umassfoundationrelations.org/opportunities?sort_bef_combine=posted_DESC"
link_pattern = '^https?://(?!(?:[a-z0-9-]+\.)*(?:umassfoundationrelations\.org|uma-foundation\.org|umass\.edu)(?:/|$))'
frequency = "weekly"
enabled = true

[[channel]]
id = "umass-fr-recurring-ls"
name = "UMass FR recurring limited submissions"
covers = "Foundation programs with institutional caps"
means = "manual"
url = "https://umassfoundationrelations.org/recurring-limited-submissions"
frequency = "monthly"
enabled = true

[[channel]]
id = "umass-fr-email"
name = "UMass FR weekly Foundation Funding Guide"
covers = "Curated foundation calls"
means = "email"
senders = ["foundation.relations@email.uma-foundation.org"]
frequency = "weekly"
enabled = true

[[channel]]
id = "umass-vcre-email"
name = "UMass Research and Engagement mailings"
covers = "Campus research announcements and internal calls"
means = "email"
senders = ["vcre@email.umass.edu"]
frequency = "as delivered"
enabled = true
```

The FR database URL above lists all categories. Users can filter it on the site and paste the filtered URL in its place. For science and engineering faculty, this URL (verified 2026-10-09) keeps open opportunities in three categories: physical sciences, engineering and computer science; life sciences and medical research; and environmental and natural sciences, sustainability and agriculture.

```
https://umassfoundationrelations.org/opportunities?search_api_fulltext=&sort_bef_combine=posted_DESC&field_opportunity_status%5B286%5D=286&field_opportunity_type%5Benvironmental-natural-sciences-sustainability-agriculture%5D=environmental-natural-sciences-sustainability-agriculture&field_opportunity_type%5Blife-sciences-medical-research%5D=life-sciences-medical-research&field_opportunity_type%5Bphysical-sciences-engineering-computer-science%5D=physical-sciences-engineering-computer-science
```

Behavior observed on 2026-10-09 for both FR pages and the ORD weekly page:

- Items sit under posted-date headings, so scan.py keeps only items posted within the scan window.
- Each FR item is followed by "Funder Deadline", "Amount", and "Focus" text, which scan.py captures as the deadline and as scoring text.
- Only the first page of FR results is fetched. Sorting by newest first makes that sufficient for a weekly cadence, but a longer gap between scans can miss items, so check the site by hand after a long break.
- The FR link pattern excludes the site's own navigation links (umassfoundationrelations.org, uma-foundation.org, umass.edu). It is a TOML literal string in single quotes, so backslashes need no doubling.

## InfoReady limited submissions with a robots.txt override

Use only if the user explicitly chooses to ignore InfoReady's robots.txt. Requires Playwright. Tested 2026-10-09: the page renders without a login. The table mixes limited submissions with internal college awards and fellowships, so `filter` keeps the "Limited Submissions" category. Rows with past internal deadlines are dropped by `keep = "upcoming"`, and each kept row links to its InfoReady detail page.

```toml
[[channel]]
id = "umass-limited-submissions"
name = "UMass ORD limited submissions (InfoReady)"
covers = "Limited-submission programs and internal deadlines"
means = "browser"
handler = "browser"
url = "https://umass.infoready4.com/#limitedsubmissions"
row_selector = "[role=row]"
columns = ["title", "desc", "due", "category"]
filter = { field = "category", regex = "Limited Submission" }
keep = "upcoming"
min_bucket = "possible"         # every limited submission is shown
ignore_robots = true
doc_type = "limited submission (internal deadline)"
frequency = "weekly"
enabled = true
```

## Massachusetts state funders

Verified 2026-10-10. Both pages list current opportunities with deadlines (not posting dates), so `use_section_dates = false` and scans should run with `--state` to report only new items. Most MassTech and MassCEC calls target companies, municipalities, or workforce programs, so expect few research fits. The Collaborative Research and Development Matching Grant and MassCEC's InnovateMass and Climatetech Testing and Demonstration Assets programs are the ones most likely to suit university teams with partners.

```toml
[[channel]]
id = "web-masstech"
name = "MassTech procurements and grant opportunities"
covers = "Massachusetts Technology Collaborative RFPs and grant NOFOs (manufacturing, AI, R&D matching grants)"
means = "web"
handler = "web"
url = "https://innovation.masstech.org/procurements-and-grants"
link_pattern = '^(Request for|Notice of Funding|Grant (Notice|Solicitation)|Collaborative Research)'
use_section_dates = false
agency = "Massachusetts Technology Collaborative"
frequency = "weekly"
enabled = true

[[channel]]
id = "web-masscec"
name = "MassCEC funding opportunities"
covers = "Massachusetts Clean Energy Center grants and programs"
means = "web"
handler = "web"
url = "https://www.masscec.com/funding"
link_pattern = '/program/'
use_section_dates = false
agency = "Massachusetts Clean Energy Center"
frequency = "weekly"
enabled = true
```

Related email sources seen in a UMass inbox: `noreply@masscec.com` (MassCEC newsletter) and `notifications@mail.commbuys.com` (COMMBUYS state procurement bid notices, which require a COMMBUYS vendor subscription). UMass campus lists that carry funding calls: `coe-faculty@groups.umass.edu` (College of Engineering research and graduate affairs updates), department faculty lists, and `eti@email.umass.edu` (Energy Transition Institute).
