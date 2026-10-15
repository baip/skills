---
name: funding-monitor
description: Set up and run personalized monitoring of research funding opportunity announcements for any US academic researcher or lab. Builds a research-fit profile from the user's memory (confirmed with the user), guides them through free API keys and provider alerts, shows exactly what is monitored, by what means, and how often, and lets them add channels. Scans Grants.gov, NSF and NIH feeds, optional Simpler.Grants.gov and SAM.gov APIs, agency and institutional web pages, and funding newsletters in the user's email, then produces a ranked digest with deadlines and eligibility flags. Use this skill whenever the user mentions monitoring or finding grants, funding opportunities, solicitations, NOFOs, FOAs, BAAs, RFAs, RFPs, Dear Colleague Letters, limited submissions, or foundation calls, asks "any new funding?", wants a weekly funding scan, asks whether an opportunity fits them, wants to add a source to monitor, or asks why their alerts miss things, even if they do not say "monitor".
compatibility: Python 3.11+ and outbound HTTPS. Optional secrets SAM_API_KEY and SIMPLER_API_KEY, declared host-neutrally in config/credentials.toml. Optional Playwright for browser channels. Email channels need an email connector.
metadata:
  openclaw:
    primaryEnv: SAM_API_KEY
---

# Funding monitor

Funding notices reach researchers through channels that overlap only partly: assistance-award databases (Grants.gov), procurement notices (SAM.gov, where DoD and DARPA post broad agency announcements), agency feeds, pages and newsletters, and institutional offices (limited submissions, foundation relations). This skill keeps a per-user profile of research keywords and channels, runs a deterministic scanner for everything machine-readable, sweeps email for the rest, and applies judgment about fit.

## Files

| File | Purpose |
|---|---|
| `scripts/scan.py` | Python 3.11+, standard library only, except the optional Playwright package for `browser` channels. Subcommands `init`, `plan`, `check`, `credentials`, `scan`. |
| `config/credentials.toml` | Host-neutral declaration of the optional secrets (name, purpose, where sent, how to obtain, accepted delivery forms). |
| `config/profile.template.toml` | Template with the default channel catalog. Never edit it in place. |
| `references/setup.md` | Setup interview: memory-drafted keywords, channel choice, keys, plan, save. |
| `references/api-keys.md` | Getting and storing keys. Provider saved-search alerts. |
| `references/channels.md` | Adding or changing channels, field reference, testing. |
| `references/email-lists.md` | Which mailing lists to join for a given field, sign-up links, and how to record them. |
| `references/email-sweep.md` | Reading newsletters and alerts through an email connector. |
| `references/sources.md` | Source catalog with verification status. |
| `references/institutions/*.md` | Verified channel blocks for specific institutions. |

The shared skill contains no personal data. A user's profile lives at `~/.config/funding-monitor/profile.toml`, in a file they upload, or bundled as `config/profile.toml` in a personal copy of the skill. scan.py finds it in that order (see its `--help`).

## Pick the mode

| The user says something like | Mode |
|---|---|
| first use, no profile found, "set this up", "update my keywords" | Setup |
| "what are you monitoring?", "show my plan" | Plan |
| "also watch X", "add this feed/newsletter/page", "stop monitoring Y" | Add or change a channel |
| "which mailing lists should I join?", "what am I not subscribed to?" | Join email lists |
| "any new funding?", "run the scan", "what came out this week" | Scan |
| a link, NOFO number, or "does this fit us?" | Triage |
| "why do I keep missing calls?", "is my coverage complete?" | Audit |

If a scan or plan is requested and no profile exists, or the profile still has `is_template = true`, start Setup and say why.

The skill folder may be read-only. Copy it to a writable directory before running anything, for example `cp -r <skill-dir> /tmp/funding-monitor`.

## Setup

Follow `references/setup.md`. In short, draft keywords from memory and confirm them with the user before saving. Then choose channels (including institution and email channels), recommend the mailing lists the user should join with `references/email-lists.md`, walk through optional keys with `references/api-keys.md`, present the plan, and save the profile where the environment allows. Keywords drive everything downstream, so never skip the confirmation.

## Plan

```bash
python3 scripts/scan.py --profile <profile> plan
```

Present the table it prints: each channel, what it covers, the means (API query, RSS feed, web page check, email newsletter, provider email alert, or manual reminder), how often it is checked, and its status (ready, disabled, needs KEY, sender not recorded). Add one sentence on scan cadence and what actually triggers it (see Scheduling). Offer the next useful step: a missing key, an unrecorded alert sender, or a channel that tested poorly.

## Add or change a channel

Follow `references/channels.md`: choose the most structured means the source offers (RSS over scraping), test it with `scan.py check --channel <id>`, then show the updated plan row. Edit the user's profile, never the template. Never invent feed URLs or sender addresses.

## Join email lists

Follow `references/email-lists.md`: find what the user already receives (profile channels plus a metadata-only inbox search when an email connector exists), recommend the missing lists that fit their profile as a checklist with sign-up links, topics to tick, and expected senders, and let the user subscribe. Always recommend every non-redundant list that fits (one that carries Dear Colleague Letters, requests for information, previews, amendments, proposers' days, or other content no structured channel delivers), even when no sign-up link is verified: give the finding steps from that file instead of leaving it out. Offer overlapping lists as optional rather than dropping them. Then add each list as an `email` channel and record its sender once the first issue arrives. Repeat this check after any profile change that adds agencies or fields. Also offer it at the end of a scan when the email sweep shows a list has gone silent or the digest relied on a source the user is not subscribed to.

## Scan

1. Run the scanner:

   ```bash
   python3 scripts/scan.py --profile <profile> scan --details --out-dir <dir>
   ```

   The window defaults to `[schedule].window_days`. Add `--state <file>` where state can persist (the user's machine or server) so only unseen items appear and per-channel frequencies are honored. In a chat sandbox there is no persistent state, so compare against earlier digests in the conversation instead. Keys are read from the environment or `~/.config/funding-monitor/.env`.

2. Read the JSON output. Review every "strong" and "possible" item and skim "low" and "filtered" titles for misses. The scorer is a recall-oriented pre-sort, and Grants.gov keyword search is fuzzy, so final relevance is your call. When fit depends on the solicitation text, fetch it.

3. Sweep email for every enabled `email` and `alert` channel, following `references/email-sweep.md`.

4. Check `manual` channels when they are due by their frequency, and any `browser` channel the run log says fell back to manual. Use web_fetch where robots rules allow, and otherwise ask the user to look or offer a browser agent working in their own session. Say clearly when a page could not be read.

5. Merge (by Grants.gov id, SAM.gov notice id, opportunity number, or title) and write the digest below. Keep it in chat unless the user asks for a file.

### Digest format

Lead with what needs action. Omit empty sections except Coverage notes.

```
## Act now
Deadlines (LOI, preproposal, white paper, full) within 6 weeks, and every limited-submission program.
## New and relevant
## Forecasts and signals
## Possible, collaborator-led
## Coverage notes
Channels checked, channels that failed or were skipped and why, keys not set, unverified claims.
```

Each item:

```
**Title** (Funder, number) [evidence tag]
Deadlines: exact text from the source, with time zone if given. Posted date.
Mechanism and size: instrument, ceiling, number of awards, cost share, if stated.
Eligibility: what the source says. Flag lead-applicant limits, institutional caps, citizenship limits.
Fit: one or two sentences tying it to the profile, marked as your assessment.
Link
```

Evidence tags: **[API]**, **[feed]**, **[page]**, **[email]**, **[inferred]**. Notices of intent, teaming partner lists, and RFIs from the DOE Exchange or SAM.gov go under "Forecasts and signals".

## Triage a single opportunity

Fetch the solicitation, then report each point with a section citation:

1. Mechanism (grant, cooperative agreement, contract, other transaction) and any white-paper stage.
2. Eligibility from the text. Never rely on applicant codes alone, since code 25 means "see text".
3. Institutional caps, and whether the user's research office already lists the program.
4. Every deadline in order. Remind the user that institutions require internal routing before the sponsor deadline, and tell them to confirm the lead time with their office rather than inventing one.
5. Budget, duration, and cost share.
6. Fit and needed partners, marked as your assessment.
7. Questions for the program officer.

Offer to draft that email and leave it unsent.

## Audit coverage

Run `plan`, then compare against `references/sources.md` and the user's field. Typical gaps: SAM.gov for defense-relevant work, saved-search alerts that include forecasts, NSF division newsletters and other agency lists from `references/email-lists.md`, the institution's limited-submission list, and a foundation channel. Give each gap a one-time action and point to the matching section of `references/api-keys.md` or `references/channels.md`.

## Scheduling

scan.py runs only when something runs it. Options, in order of automation:

- A server or always-on machine with cron:

  ```bash
  0 7 * * 1  cd ~/funding-monitor && python3 scripts/scan.py scan --details \
    --state ~/.config/funding-monitor/state.json --out-dir ~/funding-monitor/out
  ```

- A scheduled task in an agent app that supports them, pointed at this skill.
- By hand: ask Claude "run my funding scan" on the cadence in the profile.

The script gathers and pre-sorts. The email sweep and judgment steps need a Claude session.

## Rules

- Separate documented facts from inference. When a source could not be accessed, say so and do not imply nothing is new there.
- Copy deadlines exactly. When sources disagree, show both and name them.
- Award announcements, job postings, and news are not opportunities.
- Spell out each acronym at its first use in a digest.
- Never send email or create calendar invites with guests without explicit approval. Drafts stay unsent.
- Secrets follow the contract in `config/credentials.toml` and "Storing keys" in `references/api-keys.md`: store them with the host's own secret mechanism, deliver them to whatever process runs scan.py (host, sandbox, or container) in one of the accepted forms, and verify with `scan.py credentials`. This applies on any host, including ones the reference does not name. Never put keys in profiles, presented files, memory, or chat when the host offers a secure entry path.
- scan.py honors robots.txt unless the user's profile overrides it. Only the user makes that choice. Do not suggest overrides unprompted, and report overrides in Coverage notes.
- Memory: save only durable facts (profile location, confirmed core keywords, a decision to pursue or skip a named opportunity, a subscription change). Do not save digests. Tell the user in one line what was saved.
- When the user's interests change, propose the exact profile edit and apply it after they agree.
