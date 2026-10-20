# API keys and alert accounts

Read this when a channel's status in `scan.py plan` says "needs KEY", or when the user asks how to get a key or set up provider alerts. Walk the user through one service at a time and wait for them to finish each step. Verification dates are when the steps were checked against official or secondary sources. Website menus change, so if a step does not match what the user sees, search for the current instructions rather than guessing.

## Which channels need what

| Channel | Needs | Cost | Why bother |
|---|---|---|---|
| Grants.gov API | nothing | free | Core federal grant coverage. Works out of the box. |
| NSF and NIH RSS feeds | nothing | free | Works out of the box. |
| Simpler.Grants.gov API | free API key | free | Optional. Same data as Grants.gov with cleaner date filters. Skip it unless the Grants.gov API misbehaves. |
| SAM.gov API | free API key | free | DoD and DARPA broad agency announcements (BAAs), RFIs, and special notices, which never appear on Grants.gov. Worth it for anyone with defense-relevant research. |
| Simpler.Grants.gov saved searches | free Login.gov account | free | Provider-side email alerts, including forecasts. No key. |
| SAM.gov saved searches | free SAM.gov account | free | Provider-side daily email alerts. The no-code alternative to the SAM.gov API. |
| Institutional databases (Pivot-RP, GrantForward, InfoReady) | institutional login | paid by the institution | Curated federal plus private funders. Ask the research office whether there is a license. |

## Simpler.Grants.gov

Verified 2026-10-09 from the developer page and the project wiki.

1. Go to https://simpler.grants.gov/developer and read the developer page.
2. Sign in. Simpler.Grants.gov uses Login.gov accounts. Create one at https://login.gov if needed.
3. Choose "Manage API Keys", create a key, and give it a descriptive name such as "funding-monitor".
4. Copy the key and store it as `SIMPLER_API_KEY` (see "Storing keys" below).

Limits stated on the developer page: 60 requests per minute and 10,000 per day per key. Keys that go unused for 30 days are disabled automatically, so a monthly scan cadence can lose the key. Create a new one if requests start returning 401.

## SAM.gov

Verified 2026-10-09 against the GSA Get Opportunities API documentation (open.gsa.gov/api/get-opportunities-public-api).

1. Create a SAM.gov user account at https://sam.gov with Login.gov. Third-party developer guides report that an individual user account is enough and that entity registration (UEI) is not needed for a public key. This is not stated on the GSA page.
2. Sign in and open "Account Details" from the profile menu.
3. Enter your account password when prompted. The API key section only appears after that.
4. Request or generate the Public API Key. The documentation says the key is visible until you leave the page, so copy it immediately.
5. Store it as `SAM_API_KEY`.

Quota: the official page says daily request limits depend on whether the account is federal, non-federal, or general, without giving numbers. Third-party developer guides report about 10 requests per day for some non-federal personal keys and about 1,000 for system accounts. Treat the exact figure as unverified. scan.py therefore sends one request per organization listed in the channel and stops at `max_requests_per_run` (default 4). A 429 response means the quota is spent for the day. On 2026-10-09 an invalid key returned HTTP 404 with an empty body, the same code the documentation uses for "no data found", so a 404 on every organization usually means the key is wrong.

Organizations: SAM.gov identifies issuers by contracting office code, and research agencies often post through a contracting office whose name does not mention them. Codes confirmed in the SAM.gov saved-search filter or on posted notices (2026-10-09):

| Agency | Code in SAM.gov | Shown as |
|---|---|---|
| DARPA | `97AE` | DEFENSE ADVANCED RESEARCH PROJECTS AGENCY (DARPA) |
| Office of Naval Research | `N00014` | OFFICE OF NAVAL RESEARCH |
| AFRL Air Force Office of Scientific Research (AFOSR) | `FA9550` | FA9550 AFRL AFOSR |
| AFRL directorates at Wright-Patterson, including Materials and Manufacturing (RX) | `FA8650` | FA8650 USAF AFMC AFRL PZL AFRL/PZL |
| Army Research Office and DEVCOM Army Research Laboratory | `W911NF` | W6QK ACC-APG DURHAM (Army Contracting Command, Research Triangle Park Division) |

Other AFRL directorates use other offices (for example Rome, Kirtland, and Eglin), so add those only if the user's field needs them. W911NF also posts for other Army research units, so keep keyword filters on. In the `sam-gov` channel, list these as `requests = [{ organizationCode = "..." }, ...]` (one API request each) rather than `organizations` names. The `organizationCode` parameter is in the GSA parameter list but was not live-tested with a key. After adding a key, run `scan.py check --channel sam-gov`, and if a code returns nothing, fall back to `organizationName` with the department or sub-tier name shown on a known notice.

Many basic-research BAAs from ONR, AFOSR, and ARO are also posted on Grants.gov, which the Grants.gov channel already covers. SAM.gov adds the contract-type BAAs, calls under them, RFIs, and special notices.

## Saved-search alerts

No key needed. These arrive by email, so after the first alert arrives, record the sender address in the matching `alert-*` channel so the email sweep picks it up.

Simpler.Grants.gov (source: Nova Southeastern University guide, CASRAI summary of release notes):
1. Sign in at https://simpler.grants.gov with Login.gov.
2. Search with your keywords and filters. Include forecasted opportunities, because forecasts give months of lead time.
3. Click "Save". Saving a blank search sends an alert whenever any federal opportunity is posted, which is usually too broad. Several focused saved searches work better.

SAM.gov (sources: NIH Extramural Nexus, July 2026, and SAM.gov user guides. Steps adjusted after a user test on 2026-10-09):
1. Sign in at https://sam.gov and open Search. Set the domain to **Contract Opportunities** before anything else. In a test on 2026-10-09, a search run outside that domain showed no Notice Type filter, and its saved-search menu offered only Edit Name, Duplicate, and Delete. Guides describe both features for Contract Opportunities searches only, so the domain is the likely cause when either is missing.
2. Under "Federal Organizations", enter the office codes from the table in the SAM.gov section above (DARPA `97AE`, ONR `N00014`, AFOSR `FA9550`, AFRL Wright-Patterson `FA8650`, Army Research Office `W911NF`), then add keywords. Searching by agency name often fails because notices carry the contracting office's name.
3. Under "Notice Type" (present only in the Contract Opportunities domain), select Solicitation, Combined Synopsis/Solicitation, Presolicitation, Sources Sought, and Special Notice, because RFIs often precede a program by months.
4. Save the search, then open Workspace, Saved Searches, and choose "Notify" from the search's Actions menu. Some guides describe an email toggle with daily or weekly frequency instead, so take whichever control the page shows. Digests arrive on days with new matches.
5. A search saved in the wrong domain cannot be switched. Re-create it in Contract Opportunities and delete the old one.

Agency newsletters (NSF Update, NIH Guide, DOE offices): subscription pages move often. Search for the current "subscribe" page on the agency site and give the user the link. Do not guess URLs.

## Storing keys

### The contract (applies on every host)

`config/credentials.toml` declares each secret this skill can use: its variable name, that it is a secret, that it is optional, what it is for, which hosts it is sent to, and how to obtain it. Any agent host, including ones not named below, should treat that file as the specification and do three things:

1. **Store** the value with the host's own secret mechanism (a credential store, vault, keychain, or secrets settings). If the host has none, use a file outside the skill folder, readable only by the user (`chmod 600`).
2. **Deliver** it to the process that runs `scripts/scan.py`, in whichever context that process runs (host process, sandbox, container, or remote VM). scan.py accepts any of these forms, in this order: the environment variable `NAME`; a file whose path is in `NAME_FILE`; `$CREDENTIALS_DIRECTORY/NAME` (systemd credentials); `/run/secrets/name` in lowercase (Docker or Kubernetes mounted secrets); a `NAME=value` line in `~/.config/funding-monitor/.env`. A file-based form keeps the value out of process listings and container metadata, so prefer it when the host supports mounted secrets.
3. **Verify** with `python3 <skill-dir>/scripts/scan.py --profile <profile> credentials`, which reports for each secret whether it resolved and through which form, never the value. Then run `scan.py check --channel sam-gov`.

Rules that hold everywhere: never put keys in `profile.toml`, because profiles are shared and bundled. Never ask for a key in chat when the host offers a secure entry path. Never write keys into presented files, memory, logs, or digests. If a key is exposed, tell the user to regenerate it. Both keys are optional, and scan.py skips and logs a channel whose key does not resolve.

If you run on a host not covered below, look up that host's documented secret mechanism (its docs, or ask the user) rather than inventing one, and map it onto steps 1 to 3. The notes below are worked examples of the contract, verified against each host's documentation on the dates shown.

### Host notes

**OpenClaw** (docs.openclaw.ai, 2026-10-09). The frontmatter declares `metadata.openclaw.primaryEnv: SAM_API_KEY`, so store it as `skills.entries."funding-monitor".apiKey` in `~/.openclaw/openclaw.json`, preferably as a SecretRef `{ source: "env", provider: "default", id: "SAM_API_KEY" }` resolved from the gateway's environment, or through the macOS app's Skills settings. Put `SIMPLER_API_KEY` under that entry's `env` map if used. These apply to host runs only. For a Docker sandbox, deliver the secret separately: OpenClaw offers `agents.defaults.sandbox.docker.env`, but warns that Docker daemon users can read those values, so a mounted secret file read through `SAM_API_KEY_FILE` or `/run/secrets/sam_api_key` is the safer form. The skill deliberately does not declare `requires.env`, which would hide it until a key exists.

**Hermes Agent** (hermes-agent.nousresearch.com, 2026-10-09). Hermes stores secrets in `~/.hermes/.env`, hidden from the model, and its native declaration is a top-level `required_environment_variables` frontmatter block, which also passes the variables into its terminal and code sandboxes. Claude's validator rejects that top-level key, so add it to the installed Hermes copy only:

```yaml
required_environment_variables:
  - name: SAM_API_KEY
    prompt: SAM.gov public API key (optional)
    help: "sam.gov Account Details, then Public API Key. See references/api-keys.md."
    required_for: SAM.gov API channel. Scans run without it.
  - name: SIMPLER_API_KEY
    prompt: Simpler.Grants.gov API key (optional)
    help: "https://simpler.grants.gov/developer"
    required_for: Simpler.Grants.gov API channel. Grants.gov needs no key.
```

Without the patch, put the key in `~/.hermes/.env` and list it under `terminal.env_passthrough` in `~/.hermes/config.yaml`.

**Claude Code, Codex or OpenCode on a machine you control, cron, or a server.** Under Codex, use the `.env` file below, because Codex removes variables whose names contain `KEY` from the commands it runs (see `references/agents.md`). Otherwise use a secrets manager that sets the variable at run time (for example the macOS Keychain), a systemd unit with `LoadCredential=SAM_API_KEY:/path/to/file`, or `~/.config/funding-monitor/.env` with `chmod 600`.

**Claude Code cloud sessions.** Local files are invisible there. On Pro and Max, an environment's API credentials let Anthropic's proxy attach a key to requests without exposing it, but as a request header, and SAM.gov documents its key as an `api_key` query parameter, so this works only if SAM.gov also accepts an `X-Api-Key` header (unverified). Otherwise use an environment variable on a personal cloud environment, never an organization-shared one, and allow the funding domains under Custom network access.

**Codex cloud.** Values stored as Codex secrets are removed before the agent phase, so scan.py would not see them. Use an environment variable and enable agent internet access for the funding domains.

**Claude chat sandbox.** Nothing persists and chat history keeps whatever is pasted. Prefer running keyed channels elsewhere. For a one-off scan, set the variable only on the command line, never in a presented file or memory, and suggest regenerating the key afterward.
