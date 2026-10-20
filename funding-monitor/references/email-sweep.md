# Email sweep

Covers every channel with `means = "email"` or `means = "alert"`. These are often the only route to Dear Colleague Letters, agency newsletters, research-office digests, foundation guides, and provider saved-search alerts.

## Tools

Use whichever email tool is available: an app connector or an email MCP (Model Context Protocol) server for Gmail, Outlook or Microsoft 365. If your agent loads tools on demand, search its tool list first. If none is available, ask the user to connect their email provider: in a Claude app, through its connectors, and in a coding agent, by adding an email MCP server as "Connecting email" in `references/agents.md` describes. Until then, list the email and alert channels under Coverage notes as not checked. Do not ask the user to paste newsletters unless they offer.

The sweep is read-only. Never reply, forward, label, archive, mark read, or delete. Drafts (for example to a program officer or the research office) are allowed only when the user asks, and they stay unsent.

## Queries

Build the sender list from the enabled email and alert channels. A sender entry can be a full address or a bare domain (for example `nsf.gov`), and both work inside Gmail's `from:(...)` operator.

If the profile has `[email_sweep] labels`, also search each label for the scan window (`label:<name>`). Use the label's name with `/` and spaces replaced by `-`, in lowercase, for example `label:umass-funding` for "UMass/Funding". In testing on 2026-10-10, queries using label IDs such as `label:Label_330` returned nothing, while label names worked. Labels catch mail from senders nobody has listed yet. When a label search turns up a new sender with funding content, suggest adding it as a channel.

Build the sender list from the enabled email and alert channels in the profile (`scan.py plan` lists them). Use the scan window, normally `newer_than:8d`.

1. Subscribed senders, Gmail syntax (adapt operators for other providers):

```
from:(<sender1> OR <sender2> OR ...) newer_than:8d
```

Split into several queries if the list is long. Read subjects and snippets first.

2. Catch-all for forwards from colleagues, the department, or program officers:

```
("funding opportunity" OR "notice of funding" OR NOFO OR "broad agency announcement" OR "request for proposals" OR "request for applications" OR "limited submission" OR "dear colleague letter" OR "call for proposals" OR "white paper") newer_than:8d -in:sent
```

Exclude the subscribed senders from this query to avoid double reading.

3. Open full text (plain-text format) only for messages whose subject or snippet suggests an opportunity, deadline, RFI, or limited submission. Digest-style newsletters list many items in one message, so open those every time.

## Extraction rules

- An opportunity has an applicant action: apply, letter of intent, white paper, preproposal, or nomination. Award announcements, selections, job postings, and general news are not opportunities. A recurring program's award announcement goes under "Forecasts and signals" when it fits the profile.
- Record title, funder, number if given, deadlines exactly as written, link, sender, and email date. Tag the item **[email]**.
- Merge with scan results when a number, Grants.gov link, or SAM.gov link matches.
- If an item has no number and no link, say so instead of guessing.
- Many lists deliver the same issue to several of the user's addresses. Dedupe by subject.

## Provider saved-search alerts

Formats observed in a real inbox, October 2026:

- **Simpler.Grants.gov** (`notifications@simpler.grants.gov`, subject like "11 New Grants Published on 10/9/2026"). The body lists every matching opportunity with title, link, status (posted or forecasted), submission period, award range, expected awards, and cost sharing. Read the full message and treat each listing as an item tagged **[email]**. The HTML part wraps links in a click-tracking redirect, so take the plain `simpler.grants.gov/opportunity/...` links from the plain-text part. Score listings against the profile like any other item. If most listings are off-topic week after week, the saved queries are too broad, so suggest narrowing them.
- **SAM.gov** (`donotreply@sam.gov`, subject "SAM.gov | Saved Search Notification - <search name>"). The body holds only the search name and two links: records updated since `last_notified_date`, and the whole saved search. Both require signing in to SAM.gov, so a fetch from the agent's side lands on the terms-of-use sign-in page (tested 2026-10-10). "Updates" can be amendments to existing notices, not only new ones. To get the notices themselves, in order of preference: (1) the `sam-gov` API channel with the user's key, which runs the same office codes; (2) the user's own signed-in browser through a browser tool, if one is available and the user agrees; (3) list the alert in the digest as "SAM.gov reports updates in saved search <name> since <date>" with the link, and say its contents were not read. Never describe an unread SAM.gov alert as containing nothing relevant.

## Keeping the sender list current

When the user subscribes to something new, add the sender to an email channel (see `references/channels.md`). When a sender appears repeatedly in the catch-all query, suggest adding it as a channel.
