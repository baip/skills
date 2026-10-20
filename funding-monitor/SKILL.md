---
name: funding-monitor
description: Set up and run personalized monitoring of research funding opportunity announcements for any US academic researcher or lab. Builds a research-fit profile from the user's memory or web pages (confirmed with the user), guides them through free API keys and provider alerts, shows exactly what is monitored, by what means, and how often, and lets them add channels. Scans Grants.gov, NSF and NIH feeds, optional Simpler.Grants.gov and SAM.gov APIs, agency and institutional web pages, and funding newsletters in the user's email, then produces a ranked digest with deadlines and eligibility flags. Use this skill whenever the user mentions monitoring or finding grants, funding opportunities, solicitations, NOFOs, FOAs, BAAs, RFAs, RFPs, Dear Colleague Letters, limited submissions, or foundation calls, asks "any new funding?", wants a weekly funding scan, asks whether an opportunity fits them, wants to add a source to monitor, or asks why their alerts miss things, even if they do not say "monitor".
compatibility: Any agent that can run shell commands (Claude Code, Codex, OpenCode and others, see references/agents.md). Python 3.11+, or 3.8+ with tomli, and outbound HTTPS. Optional secrets SAM_API_KEY and SIMPLER_API_KEY, declared host-neutrally in config/credentials.toml. Optional Playwright for browser channels. Email channels need an email MCP server or connector.
metadata:
  openclaw:
    primaryEnv: SAM_API_KEY
---

# Funding monitor

Funding notices reach researchers through channels that overlap only partly: assistance-award databases (Grants.gov), procurement notices (SAM.gov, where DoD and DARPA post broad agency announcements), agency feeds, pages and newsletters, and institutional offices (limited submissions, foundation relations). This skill keeps a per-user profile of research keywords and channels, runs a deterministic scanner for everything machine-readable, sweeps email for the rest, and applies judgment about fit.

## Files

| File | Purpose |
|---|---|
| `scripts/scan.py` | Python 3.11+ (or 3.8+ with `tomli`), standard library only, except the optional Playwright package for `browser` channels. Subcommands `init`, `plan`, `check`, `credentials`, `scan`. Its `--help` lists the exit statuses. |
| `config/credentials.toml` | Host-neutral declaration of the optional secrets (name, purpose, where sent, how to obtain, accepted delivery forms). |
| `config/profile.template.toml` | Template with the default channel catalog. Never edit it in place. |
| `references/setup.md` | Setup interview: memory-drafted keywords, channel choice, keys, plan, save. |
| `references/api-keys.md` | Getting and storing keys. Provider saved-search alerts. |
| `references/channels.md` | Adding or changing channels, field reference, testing. |
| `references/email-lists.md` | Which mailing lists to join for a given field, sign-up links, and how to record them. |
| `references/email-sweep.md` | Reading newsletters and alerts through an email tool. |
| `references/agents.md` | Running under any agent: what the work needs, Codex and OpenCode settings, a blocked network, connecting email, unattended runs. |
| `references/sources.md` | Source catalog with verification status. |
| `references/institutions/*.md` | Verified channel blocks for specific institutions. |

The shared skill contains no personal data. scan.py looks for the user's profile in this order, and the first that exists wins: `--profile PATH`, `$FUNDING_MONITOR_PROFILE`, `~/.config/funding-monitor/profile.toml`, `./profile.toml` in the current folder, and `config/profile.toml` in a personal copy of the skill. Pass `--profile` explicitly so a stray draft in the current folder never wins.

## Paths used in commands

- `<skill-dir>` is the folder holding this `SKILL.md`. Run the script as `python3 <skill-dir>/scripts/scan.py` from any folder. In prose, `scan.py` means that command. scan.py never writes into the skill folder, so the folder may stay read-only.
- `<profile>` is the user's profile, normally `~/.config/funding-monitor/profile.toml`.
- The working folder, normally `~/funding-monitor` (create it with `mkdir -p` on first use), holds `out/` (scan output and digests) and `state.json` (which items were already shown and when each channel last ran). Use the same two paths for every run that should count as "the scan", interactive or scheduled, so runs agree on what is new. Under a sandboxed agent such as Codex, start the agent in this folder so it may write there. In a sandbox with no lasting files, use any scratch folder and no state.

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

If a scan or plan is requested and no profile exists, or the profile still has `is_template = true`, start Setup and say why. In an unattended run, do not start Setup: write a note saying setup is needed into the working folder's `out/` and stop.

## Before the first command

This skill runs under any agent that can run shell commands. Its steps name capabilities (fetch a web page, search email, ask the user, send a file), not particular tools, so use whatever your agent calls them. Read `references/agents.md` first if any of these holds:

- You are not running in a Claude app, or you are unsure you may use the network, write files or read email.
- `python3 --version` is older than 3.11. scan.py then needs `tomli` or a newer Python through uv, and says so.
- scan.py exits with status 2. Nothing could be reached, so the run says nothing about whether there is new funding.
- The run is unattended: it was started by a schedule, cron, `codex exec` or `opencode run`, the prompt says it is a scheduled or weekly run, or there is no way to ask the user anything. Then run only Scan, follow "Unattended runs" in that file, and write the digest to a file. Never wait for an answer or an approval.

## Setup

Follow `references/setup.md`. In short, draft keywords from memory and confirm them with the user before saving. Then choose channels (including institution and email channels), recommend the mailing lists the user should join with `references/email-lists.md`, walk through optional keys with `references/api-keys.md`, present the plan, and save the profile where the environment allows. Keywords drive everything downstream, so never skip the confirmation.

## Plan

```bash
python3 <skill-dir>/scripts/scan.py --profile <profile> plan
```

Present the table it prints: each channel, what it covers, the means (API query, RSS feed, web page check, email newsletter, provider email alert, or manual reminder), how often it is checked, and its status (ready, disabled, needs KEY, sender not recorded). Add one sentence on scan cadence and what actually triggers it (see Scheduling). Offer the next useful step: a missing key, an unrecorded alert sender, or a channel that tested poorly.

## Add or change a channel

Follow `references/channels.md`: choose the most structured means the source offers (RSS over scraping), test it with `scan.py check --channel <id>`, then show the updated plan row. Edit the user's profile, never the template. Never invent feed URLs or sender addresses.

## Join email lists

Follow `references/email-lists.md`: find what the user already receives (profile channels plus a metadata-only inbox search when an email tool exists), recommend the missing lists that fit their profile as a checklist with sign-up links, topics to tick, and expected senders, and let the user subscribe. Always recommend every non-redundant list that fits (one that carries Dear Colleague Letters, requests for information, previews, amendments, proposers' days, or other content no structured channel delivers), even when no sign-up link is verified: give the finding steps from that file instead of leaving it out. Offer overlapping lists as optional rather than dropping them. Then add each list as an `email` channel and record its sender once the first issue arrives. Repeat this check after any profile change that adds agencies or fields. Also offer it at the end of a scan when the email sweep shows a list has gone silent or the digest relied on a source the user is not subscribed to.

## Scan

1. Run the scanner:

   ```bash
   mkdir -p ~/funding-monitor && cd ~/funding-monitor
   python3 <skill-dir>/scripts/scan.py --profile <profile> scan --details --state ./state.json --out-dir ./out
   ```

   The window defaults to `[schedule].window_days`. The state file hides items an earlier run already showed, honors per-channel frequencies, and widens a channel's window back to its last run so nothing falls between runs. When the user asks about a period ("anything this week?") rather than "what's new since last time", leave out `--state`, so the question neither hides items an earlier run showed nor changes what the next scheduled scan considers new. In a sandbox with no lasting files, leave out `--state` and compare against earlier digests in the conversation instead. Keys are read from the environment or `~/.config/funding-monitor/.env`.

   Check the exit status before reading anything:
   - **0:** finished. If the summary has `"state_saved": false`, the state path could not be written, so say in Coverage notes that items may repeat.
   - **2:** no channel could be reached, usually because the agent's sandbox blocks the network. Do not write "nothing new". Ask for network access as `references/agents.md` describes and run it again. Unattended, write a digest that says only this.
   - **3:** the profile is unfinished (`is_template = true`). Start Setup, or unattended, write the note described above.
   - **1 or anything else:** the scan failed. Report the error. Never present a failed run as a quiet week.

   Channels listed in `failed_channels` go in Coverage notes.

2. Read what the scan wrote. scan.py prints a summary (counts, `failed_channels`, `network_down`, `state_saved`, and the run log) and writes two files to `--out-dir`: `funding-scan-<date>.json`, every item with its score and bucket, and `funding-scan-<date>.md`, the same items sorted for a person. Neither is the digest, which you write in step 5. Read the JSON file. Review every "strong" and "possible" item and skim "low" and "filtered" titles for misses. The scorer is a recall-oriented pre-sort, and Grants.gov keyword search is fuzzy, so final relevance is your call. When fit depends on the solicitation text, fetch it.

3. Sweep email for every enabled `email` and `alert` channel, following `references/email-sweep.md`. If you have no email tool, ask the user to connect their email provider, pointing to "Connecting email" in `references/agents.md`, and list those channels as not checked until they do.

4. List the `manual` channels, and any `browser` channel the run log says fell back to manual, as reminders with their links in Coverage notes. In a live session, read one yourself with your web-fetch tool or `curl -sL` where robots rules allow, or offer a browser tool working in the user's own signed-in session if your agent has one. Unattended, only list them. Say clearly when a page could not be read.

5. Merge (by Grants.gov id, SAM.gov notice id, opportunity number, or title) and write the digest below. In a live session, give it in your reply unless the user asks for a file. In an unattended run, write it to `out/funding-digest-<date>.md` in the working folder and give that path.

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
  0 7 * * 1  cd ~/funding-monitor && python3 <skill-dir>/scripts/scan.py --profile <profile> \
    scan --details --state ./state.json --out-dir ./out
  ```

- A scheduled task in an agent app that supports them, or a non-interactive agent run from cron (`codex exec`, `opencode run`), pointed at this skill. Follow "Unattended runs" in `references/agents.md`.
- By hand: ask your agent to "run my funding scan" on the cadence in the profile.

The script gathers and pre-sorts. The email sweep and judgment steps need an agent session (Claude, Codex, OpenCode or another), because they read email and decide fit.

## Rules

- Separate documented facts from inference. When a source could not be accessed, say so and do not imply nothing is new there.
- Copy deadlines exactly. When sources disagree, show both and name them.
- Award announcements, job postings, and news are not opportunities.
- Spell out each acronym at its first use in a digest.
- Never send email or create calendar invites with guests without explicit approval. Drafts stay unsent.
- Secrets follow the contract in `config/credentials.toml` and "Storing keys" in `references/api-keys.md`: store them with the host's own secret mechanism, deliver them to whatever process runs scan.py (host, sandbox, or container) in one of the accepted forms, and verify with `scan.py credentials`. This applies on any host, including ones the reference does not name. Never put keys in profiles, presented files, memory, or chat when the host offers a secure entry path.
- scan.py honors robots.txt unless the user's profile overrides it. Only the user makes that choice. Do not suggest overrides unprompted, and report overrides in Coverage notes.
- Memory: if your agent has a memory tool, save only durable facts (profile location, confirmed core keywords, a decision to pursue or skip a named opportunity, a subscription change). Do not save digests. Tell the user in one line what was saved. Without a memory tool, the profile is the durable record, so propose profile edits instead.
- When the user's interests change, propose the exact profile edit and apply it after they agree.
