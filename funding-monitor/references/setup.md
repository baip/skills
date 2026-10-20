# Setup

Goal: produce a confirmed `profile.toml` for this user, show them the monitoring plan, and tell them which keys or accounts would add coverage. Work in the order below. Each step ends with the user confirming before you move on, because a wrong keyword list silently hides opportunities for months.

## 0. Look for an existing profile

Check, in order: a `profile.toml` the user uploaded, `$FUNDING_MONITOR_PROFILE`, `~/.config/funding-monitor/profile.toml` (when you have file access to the user's machine), `./profile.toml` in the current folder, `config/profile.toml` inside the installed skill, and the user's memory for a saved funding-monitor summary. If one exists, run `python3 <skill-dir>/scripts/scan.py --profile <path> plan`, show it, and ask whether to keep it, update it, or start over. Paths follow "Paths used in commands" in SKILL.md.

## 1. Draft the research profile from memory

Gather evidence before asking the user to type anything.

1. Memory already in context (user memories, profile summaries, preferences). Read it.
2. Memory tools, if present (for example a memory MCP server or built-in memory search). Search for: research interests, current projects, recent papers, grant proposals, collaborators, department, institution, career stage.
3. Past-conversation search tools, if present. Search for "proposal", "grant", "NSF", "DOE", "NIH", "solicitation", and the user's main research nouns.
4. If memory is empty, thin, or not available (most coding agents have none), ask for one of: a faculty or lab web page URL, a Google Scholar or ORCID profile, or three to five recent paper titles. Fetch the page and extract topics. If the fetch is blocked (a sandbox without network), ask the user to paste the page's text or the paper titles instead, or to allow network access (see `references/agents.md`).

From the evidence, draft:

- **Core terms (tier A):** the group's own methods and systems. Prefer specific multiword terms ("molecular simulation", "ion exchange") over generic ones ("materials").
- **Adjacent terms (tier B):** collaborator-led directions and application areas.
- **Program terms (tier C):** programs and mechanisms worth seeing regardless of topic, adjusted for career stage. For example "CAREER" and "Young Investigator" for pre-tenure faculty, "MURI" and "center" for senior faculty.
- **API queries:** 15 to 30 single terms or short phrases for Grants.gov. One concept per query.
- **Agencies to boost:** from the user's funding history in memory, if any.
- **Exclusions:** mechanisms the user cannot or will not pursue (SBIR-only, K-12, clinical, and so on).
- **Eligibility codes:** from institution type. Public university 06, private university 20. Keep 25 ("see text") and 99 (unrestricted).

Present the draft compactly, grouped by tier, and say where each group came from ("from your memory of the X project", "from your faculty page"). Mark any term you inferred rather than found. Ask the user to add, remove, or move terms. Do not write the file until they confirm. Two short rounds of edits is normal.

Substring matching caveat worth telling the user: short terms match inside longer words. Avoid two-letter terms. Use " ai " with spaces rather than "ai".

## 2. Choose channels

Create the draft profile now, so every later command has a file to read:

```bash
python3 <skill-dir>/scripts/scan.py init --out <draft>
```

`<draft>` is `~/.config/funding-monitor/profile.toml` when the agent may write there, and otherwise `./profile.draft.toml` in the working folder, moved into place in step 5. Write the confirmed keywords from step 1 into it, and pass `--profile <draft>` to every later `plan` and `check`. It keeps `is_template = true` until step 5, so `plan` and `check` work but `scan` refuses (exit status 3).

1. Start from the channel catalog in `config/profile.template.toml`. Propose enabling the field-agnostic defaults (Grants.gov, NSF feeds) plus channels whose tags fit the confirmed profile (energy, defense, biomedical, physical sciences).
2. Institution channels. If `references/institutions/` has a file for the user's institution, offer its channel blocks. Otherwise search the web for "<institution> limited submission", "<institution> research development weekly funding", and "<institution> foundation relations funding opportunities". Fetch each candidate, decide the means (see `references/channels.md`), and run `scan.py --profile <draft> check --channel <id>` after adding it. If the network is blocked, list the institution search as pending in the plan and return to it once network access is allowed.
3. Existing email subscriptions. If an email tool is available (Gmail, Outlook, or Microsoft 365), run one read-only, metadata-only search over the last 90 days, for example `(govdelivery OR grants.gov OR "funding opportunit" OR "foundation relations" OR "limited submission") newer_than:90d -in:sent`. List the distinct senders with counts and ask which to monitor. Also ask whether the user files funding mail under particular labels or folders, record them in `[email_sweep] labels`, and search those labels over the past year for senders the first search missed. Record confirmed senders in `email` channels. If there is no email tool, ask the user to connect their email provider: in a Claude app, through its connectors, and in a coding agent, by adding an email MCP (Model Context Protocol) server as "Connecting email" in `references/agents.md` describes. A newly added server usually loads only in a new session, so do not stop the interview for it. Ask which lists they receive and enable the matching `email` channels, with `senders = []` for any address neither of you knows (never a guessed address, see `references/channels.md`). Then finish setup and save the profile (step 5), and then walk through connecting email. The next session runs this inbox search with the profile already in place. Tell the user that duplicate deliveries to several addresses are harmless.
4. Lists to join. Compare what the user receives against `references/email-lists.md` and recommend the missing lists that fit the confirmed profile, following the procedure there: a checklist with sign-up links, topics to tick, and expected senders. Include every non-redundant list that fits, with finding steps where no link is known, and offer overlapping lists as optional. The user subscribes. Add each list as an `email` channel with its `signup` link, and record the sender once the first issue arrives.

Confirm the enabled set with the user.

## 3. Keys and accounts

Run `scan.py --profile <draft> plan`. For every channel whose status is "needs KEY", and for any alert channel the user wants, walk through the matching section of `references/api-keys.md`. Make keys optional: the skill works without any of them. Store each key with the host agent's own secret mechanism, following the contract under "Storing keys" in that file, and confirm with `scan.py credentials`. Recommend SAM.gov only when the profile has defense-relevant work or the user asks about DoD or DARPA.

## 4. Show the monitoring plan

Run `scan.py --profile <draft> plan` again and present the table to the user, including its "Email lists and alerts still to set up" section, with a two-sentence summary: how many channels are automated (API, RSS, web), how many come through email, and how many are manual reminders. Also state the scan cadence and how it will actually run (see "Scheduling" in SKILL.md), because "weekly" means nothing unless something triggers it.

## 5. Save

1. Set `is_template = false` and fill `[meta]`.
2. Validate with `scan.py --profile <draft> plan`, which parses the file and stops on a syntax error.
3. Deliver according to the environment:
   - With access to the user's machine (a coding agent such as Claude Code, Codex or OpenCode, a desktop app with folder access, or a server): make sure the profile ends up at `~/.config/funding-monitor/profile.toml`, moving the draft there if it was elsewhere. A sandboxed agent may need the user's approval to write there (see `references/agents.md`).
   - In a sandbox with no access to the user's files: give `profile.toml` as a file the user can download (or its full path, if your interface cannot send files), and offer a personal copy of the skill with the profile bundled at `config/profile.toml`, packaged under the same name so it replaces the shared copy when installed. Say that the bundled copy is personal and should not be shared onward, because it can contain email senders and institutional details.
4. If a memory tool is available, save one short entry: that the user set up funding-monitor, the date, the top core terms, and where the profile lives. Do not save API keys, and do not save digests. Tell the user in one line what was saved.
