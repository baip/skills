# Email lists worth joining

Read this during Setup (step 2), during an Audit, or when the user asks which mailing lists to join. Many opportunities, especially NSF Dear Colleague Letters, DOE program office calls, and institutional limited-submission notices, reach researchers only by email. The goal is a short, field-appropriate set of subscriptions, each recorded as an `email` channel so the email sweep reads it.

## Procedure

1. **Find what the user already receives.** Start with the enabled `email` and `alert` channels in the profile. If an email connector is available, run one read-only, metadata-only search over the last 90 days for the expected senders and domains in the catalog below, for example `from:(govdelivery.com OR govdelivery.nsf.gov OR mail.nih.gov OR info.science.doe.gov OR grants.gov) newer_than:90d`. Treat a sender seen in the inbox as subscribed even if the profile lacks a channel, and offer to add the channel.
2. **Pick the gaps that matter.** Match catalog rows to the confirmed profile (agencies boosted, field tags, institution) and sort them into two groups, ordered by expected value within each:
   - **Non-redundant lists: always recommend.** A list is non-redundant when it carries content that no structured channel (API, RSS, sitemap, web page) in the profile delivers. Typical examples are Dear Colleague Letters, requests for information (RFIs), notices of intent, solicitation amendments, program previews, proposers' days, industry days, town halls, office hours, and program-officer news. The catalog's "Unique content" column says what each list adds. Recommend every non-redundant list that fits the profile, **even when no sign-up link is verified**. A missing link is a reason to give finding steps (see "When no sign-up link is known" below), never a reason to leave the list out.
   - **Overlapping lists: offer as optional.** A list whose opportunities already arrive through a working structured channel is still worth offering as an early-warning or backup feed. Present these after the non-redundant group, say which channel overlaps, and let the user decide. Do not silently drop them, and never remove a list the user already receives.
3. **Present a checklist.** For each recommended list give: what it carries and why it fits this user, what it adds beyond the structured channels, the sign-up link (or the finding steps when there is none), which topics to tick on the sign-up form, and the sender address to expect. Mark links that were not verified and search for the current page instead of guessing when a link fails.
4. **The user subscribes.** Sign-up forms ask for the user's email address and consent, so the user completes them. Do not submit forms on their behalf. If a browser tool is available and the user explicitly asks you to do it, confirm the exact email address first and stop at any CAPTCHA or confirmation step.
5. **Record the channel.** Add or enable an `email` channel per list (see `references/channels.md`). If the expected sender is known, record it now. Otherwise leave `senders = []` so `scan.py plan` shows "sender not recorded", and on the next scan search the inbox for the confirmation or first issue to fill it in.
6. **Suggest a mail filter.** A filter that labels these senders (and skips the inbox, if the user prefers) keeps the volume manageable. The email sweep finds them either way.

## When no sign-up link is known

Recommend the list anyway and give the user these steps, in this order. Try the first two yourself with web search or fetch before handing them over, and report what you found.

1. **Search the agency site.** Query the agency or office domain for "subscribe", "newsletter", "email updates", "mailing list", or "GovDelivery" (for example `site:onr.navy.mil subscribe`). Many federal offices use GovDelivery, whose account pages follow `https://public.govdelivery.com/accounts/<ACCOUNT>/subscriber/new`. The office's funding or solicitations page often links its list directly.
2. **Check page footers and contact pages.** Sign-up forms often sit in the site footer, on a "news" or "media" page, or behind a "stay connected" link.
3. **Check account notification settings.** Some agencies send announcements only to registered users: NASA through NSPIRES, NIH through eRA Commons and LISTSERV, DOE through the Funding Opportunity Exchange, Simpler.Grants.gov and SAM.gov through saved searches.
4. **Ask a person.** Email the program office or the general contact address and ask to be added to its announcement list, or ask whether one exists. Program officers routinely add researchers who ask. For DARPA office lists, contact DARPA's outreach contractor (see the DARPA row).
5. **Ask the research office.** Research development staff often already subscribe and can forward the route, or forward issues themselves.
6. **Record the channel regardless.** Add the `email` channel with `signup = ""` and a note of the route being tried, so `scan.py plan` keeps it visible until the first issue arrives and the sender can be recorded.

## Catalog

Verification: **V** = page loaded and matched on 2026-10-09 or 2026-10-10. **S** = link from a secondary source. **U** = no verified link, recommend the list anyway and follow "When no sign-up link is known".

"Unique content" marks what a list adds beyond the structured channels in `references/sources.md`: **Unique** means it regularly carries items no structured channel delivers, **Partly** means mostly overlapping but with some list-only items, and **Overlap** means the same items arrive through a structured channel (offer as optional early warning or backup). These ratings come from what each list typically carries, not from a systematic comparison of issues, so revise a rating when the email sweep shows otherwise.

### Cross-agency

| List | Fits | Unique content | Sign-up | Topics to choose | Expected sender |
|---|---|---|---|---|---|
| Simpler.Grants.gov saved-search alerts | everyone | Partly: forecasts and modifications to saved items, sometimes before the keyword scan matches them | account at https://simpler.grants.gov (see `api-keys.md`) | saved searches including forecasted items | `notifications@simpler.grants.gov` (seen in a subscriber's inbox **V**). Lists each opportunity. |
| Grants.gov subscriptions (legacy) | backstop only | Overlap with the Grants.gov API channel | https://www.grants.gov/connect/manage-subscriptions **V** | saved searches or opportunity numbers | `do_not_reply@grants.gov` **V** |
| SAM.gov saved-search alerts | defense-relevant research | Unique when the SAM.gov API key is not set up: Broad Agency Announcements and special notices that never reach Grants.gov | SAM.gov account (see `api-keys.md`) | office codes 97AE, N00014, FA9550, FA8650, W911NF plus keywords | `donotreply@sam.gov` (seen in a subscriber's inbox **V**). Carries a sign-in link only. |
| Simpler.Grants.gov newsletter | people who want platform changes | Unique but not opportunities: platform and process news | https://simpler.grants.gov/newsletter **V** | n/a | record after first issue |

### Agencies

| List | Fits | Unique content | Sign-up | Topics to choose | Expected sender |
|---|---|---|---|---|---|
| NSF Update (GovDelivery) | anyone seeking NSF funding | Unique: Dear Colleague Letters, webinars, policy changes that the NSF feeds carry late or not at all | https://service.govdelivery.com/accounts/USNSF/subscriber/new?qsp=823 **V** (linked from nsf.gov) | funding opportunities, plus the user's directorates and divisions | `nsf-update@govdelivery.nsf.gov` **V** |
| NSF division newsletters | NSF applicants in that division | Unique: division news, program officer changes, virtual office hours | same NSF GovDelivery account, division topics. The Chemistry division documents a monthly newsletter there **V** | the user's divisions | `nsf-update@govdelivery.nsf.gov` or a division sender |
| NIH Guide weekly table of contents | biomedical or NIH-adjacent | Overlap with the NIH Guide RSS channel, but useful as a weekly digest | https://grants.nih.gov/funding/nih-guide-for-grants-and-contracts/subscribe **V** | weekly TOC LISTSERV | `GuideTOC@mail.nih.gov` **V** |
| DOE Office of Science (GovDelivery) | physical sciences, energy, computing, biology funded by DOE | Partly: program office news, workshops, and early-career program reminders alongside the calls on the funding page | https://public.govdelivery.com/accounts/USDOEOS/subscriber/new **V** | funding opportunities, plus program offices (Basic Energy Sciences, Advanced Scientific Computing Research, Biological and Environmental Research, Fusion Energy Sciences, High Energy Physics, Nuclear Physics) | `updates@info.science.doe.gov` (seen in a subscriber's inbox, link between the two **S**) |
| DOE Office of Critical Minerals and Energy Innovation, formerly EERE (GovDelivery) | applied energy, materials, manufacturing, critical minerals | Unique: notices of intent, RFIs, prizes, and lab calls that precede or bypass Grants.gov | https://public.govdelivery.com/accounts/USEERE/subscriber/new **V** (page titled with the new office name) | funding opportunities and the relevant technology offices | per-topic `@service.govdelivery.com` senders |
| DOE Hydrocarbons and Geothermal Energy Office (HGEO) | geothermal, subsurface, hydrocarbon resources | Unique: office notices of intent, RFIs, and prizes | https://public.govdelivery.com/accounts/USDOEOFE/subscriber/new **V** (linked from the office's solicitations page as "HGEO's email distribution list") | funding opportunities | `HGEO@public.govdelivery.com` (seen in a subscriber's inbox **V**) |
| DOE department-wide (GovDelivery) | anyone tracking DOE broadly | Partly: department announcements and new programs | https://public.govdelivery.com/accounts/USDOE/subscriber/new **V** | funding and the user's program areas | record after first issue |
| ARPA-E newsletter | energy technology | Unique: program previews, workshops, RFIs, and the annual Summit, which precede the Funding Opportunity Exchange posting | **U**. No sign-up link found on arpa-e.energy.gov on 2026-10-10. Check the site footer and "News" pages, or email the ARPA-E contact address and ask to be added | n/a | Mailchimp sender, for example `arpaecommunications@11114499.mailchimpapp.com` (seen in a subscriber's inbox **V**) |
| NIST (GovDelivery) | measurement science, materials, manufacturing | Unique: NIST funding notices and Manufacturing USA calls that are easy to miss in keyword searches | https://public.govdelivery.com/accounts/USNIST/subscriber/new **V** | grants and funding topics | record after first issue |
| USDA NIFA (GovDelivery) | agriculture, food, bioproducts | Partly: program updates and webinars alongside Grants.gov calls | https://public.govdelivery.com/accounts/USDANIFA/subscriber/new **V** | funding opportunities | record after first issue |
| ARPA-H Vitals | health technology | Unique: proposers' days, solicitation previews, and program launches | https://engage.arpa-h.gov/arpa-h-vitals-newsletter-sign-up **S** | n/a | record after first issue |
| NASA research newsletters | space, earth science, astrobiology, materials in space, small business | Unique: division funding roundups, flight opportunities, prize competitions, and solicitation amendments | https://www.nasa.gov/nasa-newsletters/ **V** (linked from NASA's grant-solicitations page). Relevant entries on 2026-10-10 include the Earth Science Division, Astrobiology Program, Flight Opportunities, SBIR/STTR, and the prizes and challenges digest | the divisions that match the profile | record after first issue |
| NASA Science Mission Directorate (SMD) list and NSPIRES notifications | anyone proposing to NASA science | Unique: ROSES amendments, new program elements, and due-date changes | NSPIRES account notification settings at https://nspires.nasaprs.com/ **V**. NASA also publishes how to subscribe to the ROSES due-date calendars, linked from the grant-solicitations page | SMD announcements and the user's divisions | `smd@listsrv2.nasaprs.com` (seen in a subscriber's inbox **V**) |
| DARPAConnect | anyone exploring DARPA funding, especially newcomers | Unique: opportunity roundups, Mission Connect events, office hours, training | https://www.darpaconnect.us/ **V** (site loads, no direct sign-up link found) or email darpaconnect@darpa.mil (per DARPA's DARPAConnect page **S**) | n/a. Run by the Applied Research Institute (ARI) | `ecosystem@theari.us`, `ERIS@theari.us` (seen in a subscriber's inbox **V**) |
| DARPA office lists (for example the Defense Sciences Office) | defense-relevant research | Unique: proposers' days, special notices, and office news ahead of the SAM.gov posting | **U**. Sent by Strategic Analysis, Inc., DARPA's outreach contractor. A university page describes joining DARPA's weekly university email alerts by contacting that contractor's outreach coordinator. Ask the user's research office or DARPA outreach for the current route | the relevant technical offices | `dsonews@sainc.com` for the Defense Sciences Office (seen in a subscriber's inbox **V**) |
| Office of Naval Research (ONR) | naval science and technology | Partly: Broad Agency Announcement updates and special program announcements, most of which also appear on SAM.gov | **U**. No sign-up link found on onr.navy.mil on 2026-10-10. Follow "When no sign-up link is known", including asking the relevant program officer | the user's codes or divisions | record after first issue |
| Air Force Office of Scientific Research (AFOSR) | basic research for the Air Force and Space Force | Partly: Broad Agency Announcement amendments, Young Investigator Program reminders, program officer news | **U**. The AFOSR site refused automated access on 2026-10-10. Follow "When no sign-up link is known" | the user's portfolios | record after first issue |
| Army Research Office (ARO) and DEVCOM Army Research Laboratory (ARL) | basic and applied Army research | Partly: Broad Agency Announcement amendments, program officer news | **U**. No sign-up link found. Follow "When no sign-up link is known" | the user's program areas | record after first issue |

For defense agencies, SAM.gov saved-search alerts remain the dependable route for the solicitations themselves. The office lists above add the events and previews around them.

### State and other agencies

| List | Fits | Unique content | Sign-up | Topics to choose | Expected sender |
|---|---|---|---|---|---|
| State clean-energy and technology agencies (for example MassCEC, MassTech in Massachusetts) | energy, manufacturing, applied research with industry partners | Partly: events and program launches beyond the funding page, which is better watched as a `web` channel | the agency's newsletter page | funding announcements | for MassCEC, `noreply@masscec.com` (seen **V**) |
| State procurement portal (for example COMMBUYS in Massachusetts) | applied work for state agencies | Unique: state bids posted only on the portal | vendor registration and commodity-code subscription on the portal | research and consulting commodity codes | for COMMBUYS, `notifications@mail.commbuys.com` (seen **V**) |
| Research consortia and centers the user belongs to (for example the Genesis Mission Consortium, a DOE Energy Frontier Research Center) | members | Unique: member-only calls and teaming requests | membership | n/a | record after first issue |

### Institutional

Ask whether the user receives these, and help find them on the institution's website if not:

- The research development office's funding newsletter or weekly opportunities list.
- Limited-submission announcements, which often go to a separate list or an InfoReady-type portal with its own notification settings.
- The foundation or corporate relations office's funding guide.
- The college or department research administrator's list, which often forwards targeted calls.

Check `references/institutions/` for verified details about the user's institution.

### Foundations and societies

- Candid RFP Bulletin, a weekly newsletter of foundation and corporate RFPs **S**.
- Newsletters from the foundations that matter in the user's field. Identify them from the profile and the foundation-relations office, and find each sign-up page at run time.
- Professional societies in the user's field often send funding, award, and fellowship announcements to members. Ask which societies the user belongs to and check their communication preferences.
