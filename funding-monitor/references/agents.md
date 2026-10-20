# Running under any agent

Read this before the first command on an agent other than the Claude apps, when a step needs a capability you are not sure you have, when the email sweep has no email tool, or when the run is unattended. Every step in this skill is a shell command, a web page to read, or an email search, so it runs under Claude Code, Codex, OpenCode and other agents that can run shell commands. What differs between agents is what they are allowed to do and what their tools are called.

## What the work needs

1. **Python 3.11 or newer**, or Python 3.8 to 3.10 with the `tomli` package. Run `python3 --version` first. On an older Python, either run `python3 -m pip install --user tomli` or run the script through uv: `uv run --python 3.11 <skill-dir>/scripts/scan.py ...`. scan.py prints these two remedies itself when it cannot start.
2. **Outbound HTTPS** from the process that runs scan.py, to the funding sites in the profile (Grants.gov, NSF, NIH, SAM.gov, DOE, DARPA, the institution's pages).
3. **Writing files** in the working folder (normally `~/funding-monitor`, holding `out/` and `state.json`), and in `~/.config/funding-monitor/` only when the profile is created or the user asks to change it. See "Paths used in commands" in SKILL.md.
4. **Reading the optional keys** (see "Keys" below and `references/api-keys.md`).
5. **Optional:** Playwright and its Chromium for `browser` channels. Without them, those channels become manual reminders.
6. **An email tool** for the email sweep (see "Connecting email").
7. **Fetching a web page** for triage and manual channels.

## Capabilities by what they do

This skill names capabilities, not tools. Use whatever your agent calls them.

| Capability | Use | If your agent lacks it |
|---|---|---|
| Fetch a web page | the agent's web-fetch tool, or `curl -sL <url>` in the shell | list the channel as not checked in Coverage notes |
| Search and read email | an email MCP (Model Context Protocol) server or app connector | ask the user to connect their email provider (below), and meanwhile list email channels as not checked |
| Memory | a memory tool or memory server | draft keywords from the user's faculty page or papers instead, and treat the profile as the only durable record |
| Ask the user | the agent's prompt or question tool, or plain text | in an unattended run, follow "Unattended runs" |
| Send a file | the agent's attachment or file-sending tool | give the file's full path |
| Drive a browser | Playwright through scan.py, or a browser tool | the page becomes a manual reminder |

## Telling a blocked network from a quiet week

When scan.py reaches no host at all, it says so instead of producing an empty digest that looks like a quiet week:

- `scan` exits with status 2, prints "Every channel that needs the network failed" on standard error, puts the same line at the top of the Markdown output, and sets `"network_down": true` in the JSON summary.
- `check` exits with status 2 and prints the same warning.
- Failed channels are listed in `failed_channels` and are not marked as run in the state file, so the next run retries them.
- After three hosts fail with nothing reached, the rest fail at once, so a blocked run takes seconds.

Never report "nothing new" from such a run. Ask for network access (below) and run it again. One or two failed channels while others work point to a problem with those sources. Report them in Coverage notes.

## Codex

As documented in October 2026 (learn.chatgpt.com, "Agent approvals and security"). Newer versions may name these settings differently, so check the documentation for the version in use.

- **Network.** The default `workspace-write` sandbox has no network and writes only inside the folder Codex was started in and temporary folders such as `/tmp`. For the network, pick one:
  - Approve the command when Codex asks to run it with network access (the interactive default asks).
  - Turn on network access in `~/.codex/config.toml`:

    ```toml
    [sandbox_workspace_write]
    network_access = true
    ```

- **Working folder.** Start Codex in the working folder (`mkdir -p ~/funding-monitor && cd ~/funding-monitor && codex`) and pass `--state ./state.json --out-dir ./out`, so state and output are inside its workspace. A state or output path outside the workspace cannot be written. scan.py then still writes the output but reports `"state_saved": false`, or fails with exit status 1 if the output folder itself is outside. If Codex was started in another folder, ask the user to restart it in the working folder. For a one-off question meanwhile, run without `--state` and with `--out-dir ./funding-out` in the current folder, and say where the files went. Reading the profile from `~/.config/funding-monitor/` needs no write access. Creating or editing it does, so approve that write when the user asks for a profile change, or add the folder as a writable root if your version supports one.
- **Keys.** A third-party guide from 2026 reports that Codex, by default, removes environment variables whose names contain `KEY`, `SECRET` or `TOKEN` from the commands it runs (its `shell_environment_policy`). This has not been checked against Codex's own documentation. If it holds for your version, it removes `SAM_API_KEY`, and `SAM_API_KEY_FILE` as well. The dependable form under Codex is the file `~/.config/funding-monitor/.env` with `chmod 600`, which scan.py reads itself. Confirm with `scan.py credentials`. Codex cloud is covered in `references/api-keys.md`.
- **Unattended runs.** `codex exec` runs a prompt with nobody present to approve anything, so network access must already be on in `config.toml`, and the sandbox must allow writes (Codex recommends `--sandbox workspace-write` for these runs). For example, from cron: `cd ~/funding-monitor && codex exec --sandbox workspace-write "Run my weekly funding scan with the funding-monitor skill. This run is unattended."`. Check `codex exec --help` for the current flags.
- **Where Codex finds skills:** `~/.agents/skills/` as of October 2026. Older versions read `~/.codex/skills/`.

## OpenCode

As documented in October 2026 (opencode.ai/docs/permissions).

- OpenCode has no sandbox and no network restriction by default. Its permission settings decide what asks first. Most actions are allowed by default, but editing or reading outside the working folder (`external_directory`) asks first. Editing `~/.config/funding-monitor/profile.toml` from another folder will ask, which is the right moment for the user to confirm the change.
- To stop prompts for the scan itself, allow the commands in `opencode.json`:

  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "permission": {
      "bash": { "*": "ask", "python3 *": "allow", "uv *": "allow" }
    }
  }
  ```

- OpenCode's read tool refuses `.env` files by default. That does not affect scan.py, which reads `~/.config/funding-monitor/.env` itself. Do not try to open the file to check the key. Run `scan.py credentials` instead.
- **Output inside a project.** Run from the working folder (`cd ~/funding-monitor`), not from a code project, so `out/` and `state.json` do not land in the project.
- **Unattended runs:** `cd ~/funding-monitor && opencode run "Run my weekly funding scan with the funding-monitor skill. This run is unattended."`. Allow the commands first as above, since nobody will answer a prompt. Check `opencode run --help` for the current flags.

## Claude Code

Works as is. Approve its prompts, or allow `python3` and `uv` in its permission settings. For cloud sessions and keys, see `references/api-keys.md`.

## Other agents

Map the list under "What the work needs" onto the agent's own permission system. If the agent cannot run shell commands at all, it can still do Triage, the email sweep and the Join email lists checklist, but not a scan. Say so to the user rather than imitating scan.py by hand.

## Connecting email

Newsletters and provider alerts make up a large share of a typical profile's channels, and some content (Dear Colleague Letters, proposers' days, limited-submission notices) arrives only by email. When the agent has no email tool:

1. **Ask the user to connect their email provider.** Explain in one or two sentences what the sweep reads (senders and labels in the profile, for the scan window) and that it is read-only. Point to the steps below for their provider and agent.
2. Until it is connected, run the rest of the scan, and list every `email` and `alert` channel under Coverage notes as not checked. Never describe an unchecked channel as quiet.
3. After it is connected, check it with one metadata-only search for a known sender, for example `from:govdelivery.com newer_than:30d`, then continue the sweep from `references/email-sweep.md`.

Prefer servers or settings that are read-only. The sweep searches and reads, and drafting is the most it ever needs. Keep client secrets and tokens in environment variables or the agent's secret store, never in a config file that is committed or shared.

### Choosing a server

As of October 2026. These are previews or community projects, so check each one's current documentation before setting it up.

- **Gmail, including Google Workspace university accounts.** Google's own Gmail MCP server, `https://gmailmcp.googleapis.com/mcp/v1`, is a Developer Preview (developers.google.com/workspace/guides/configure-mcp-servers). It needs membership in the Google Workspace Developer Preview Program, a Google Cloud project with the Gmail API and the Gmail MCP API turned on, an OAuth consent screen and an OAuth client. Its tools search, read, label and draft. It cannot send. Google documents setup for its own clients and the Claude apps, and for other clients gives the server name `googleworkspace`, the URL, Streamable HTTP and OAuth 2.0. Community servers that wrap the Gmail API also exist. Prefer one that can run read-only.
- **Microsoft 365 or Outlook.** Microsoft's own mail server (Work IQ Mail, under Agent 365) is a preview that requires a Microsoft 365 Copilot license and an administrator's setup. The widely used community server is Softeria's `@softeria/ms-365-mcp-server` (MIT license, not a Microsoft product). Run it with `npx -y @softeria/ms-365-mcp-server --read-only`, sign in once with `npx @softeria/ms-365-mcp-server --login` (a device code), and add `--org-mode` for a work or school account. A university tenant may require an administrator to approve the app.
- **The Claude apps** have built-in Gmail connectors under Settings, then Connectors. No server setup is needed there.
- **Other providers.** Look for an MCP server for the provider, or a generic IMAP server, that can run read-only, and read its source or documentation before giving it a password.

### Adding the server to the agent

Replace the server name, URL and options with those of the server chosen above.

**Codex** (`~/.codex/config.toml`, or `.codex/config.toml` in a trusted project):

```toml
[mcp_servers.ms365]
command = "npx"
args = ["-y", "@softeria/ms-365-mcp-server", "--read-only"]

[mcp_servers.gmail]
url = "https://gmailmcp.googleapis.com/mcp/v1"
```

For a remote server with OAuth, `codex mcp add gmail --url https://gmailmcp.googleapis.com/mcp/v1 --oauth-client-id <client id> --oauth-client-secret "$GMAIL_MCP_CLIENT_SECRET"` writes the entry, and `codex mcp login gmail` signs in. The OAuth client must allow the redirect address Codex uses for sign-in. Codex's documentation does not state it, so take it from the sign-in error or from Codex's current documentation.

**OpenCode** (`opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ms365": {
      "type": "local",
      "command": ["npx", "-y", "@softeria/ms-365-mcp-server", "--read-only"]
    },
    "gmail": {
      "type": "remote",
      "url": "https://gmailmcp.googleapis.com/mcp/v1",
      "oauth": {
        "clientId": "{env:GMAIL_MCP_CLIENT_ID}",
        "clientSecret": "{env:GMAIL_MCP_CLIENT_SECRET}"
      }
    }
  }
}
```

Then `opencode mcp auth gmail` signs in, and `opencode mcp list` shows the servers.

**Claude Code:** `claude mcp add ms365 -- npx -y @softeria/ms-365-mcp-server --read-only`. For a remote server, `claude mcp add --transport http gmail <url>`, then authenticate it from `/mcp`.

After adding a server, start a new session so the agent loads it.

## Unattended runs

A scheduled or non-interactive run (cron, `codex exec`, `opencode run`, a scheduled task) has nobody to answer questions and often no chat to reply in.

- Treat a run as unattended when a schedule, cron, `codex exec` or `opencode run` started it, when the prompt says it is scheduled or weekly, or when there is no way to ask the user. Then never wait for an answer or an approval.
- Run only Scan. Setup, Add or change a channel and Join email lists need the user's confirmation, so never run them unattended. Steps that say "ask the user" become a line in Coverage notes.
- Run from the working folder with the usual paths: `--state ./state.json --out-dir ./out`.
- Require an existing profile with `is_template = false`. Exit status 3 means the profile is unfinished. Exit status 1 with "No profile found" on standard error means there is none. In both cases write `out/funding-digest-<date>.md` saying that setup is needed, and stop.
- Write the digest to `out/funding-digest-<date>.md` and end by giving its path. A reply alone may never be read. scan.py's own `funding-scan-<date>.md` is its sorted list, not the digest.
- If scan.py exits with status 2, the digest says the network was blocked, and nothing else. Any other failure, including status 1 without "No profile found", is a failed scan: the digest reports the error, quoting scan.py's last lines of standard error, and never calls the week quiet.
- If `out/` itself cannot be written, put the whole digest in your final message instead, and say why.
- If there is no email tool, list the email and alert channels as not checked. Do not try to connect one.
- Do not change the profile, memory, subscriptions or keys. Put suggested changes in the digest for the user to approve.
- Never send email. Leave drafts only if the user asked for them.
