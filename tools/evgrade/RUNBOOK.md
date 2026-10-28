# EvGrade Lead Hunter: quality extension

This extends the existing research process. It creates no agent, schedule, crawler,
email sender or Soulvo campaign. CRM snapshots and contacts must stay outside this
public repository. No credentials belong in code or logs.

## Current state, 28 October 2026

- Repository main inspected at 4886a69d6323e7d7ed549b6fb7268eff01504cac.
- Existing workflows validate skills and deploy a website; neither researches leads.
- Existing working Google Sheet located and updated in place. Manual call fields preserved.
- Historical test workbook contains 100 numbered rows plus 8 shifted-schema rows.
  All 100 require fresh evidence/contact provenance; structural audit is not live verification.
- 12 English-market candidates added with official source URLs and individual drafts.
  Company size and call volume remain unconfirmed; none approved for sending.
- Existing production research scheduler has not been identified. Do not create another
  scheduler until its owner, task ID, prompt, cadence and destination are verified.

## Discovery and evidence

Initial markets: UK, Ireland, USA, Canada, Australia, New Zealand, alongside existing
Russian coverage. Rotate dentistry, medical practices, veterinary groups, furniture,
manufacturing, online education and other businesses with telephone-led sales/bookings.
Use search engines and lawfully public official company, careers and contact pages.
Industry/member directories can supply discovery seeds, but verify on company sites.
Do not bypass authentication, CAPTCHAs, robots restrictions or paywalls. Respect provider
terms and rate limits. Do not collect patient/student details, private phones, guessed
email patterns or personal social profiles. A public business contact is not consent.
Do not call, message, subscribe, submit forms or upload call recordings during research.

Store each fact with URL, checked_at, source type, access result and observation.
Keep contact provenance separate from signal provenance. A search snippet is pending
evidence. A live careers page without a date does not establish a newly posted job.
Record dates explicitly; do not use crawl timestamps as publication dates.
Directors' names and roles need their own public source. Shared email is not an LPR email.

## Score and qualification

Use `score()` with verified Boolean evidence only. EN 10; sector 15; confirmed SMB 15;
telephone sales/booking process 20; sales team 15; quality-control/growth signal 15;
published business contact 10. Unknown = 0; competitors/suppressed = 0.
75–100 A, 55–74 B, below 55 C. A phone number alone does not prove a sales process.
An SMB candidate requires size confirmation before becoming qualified. Capture company
headcount and ownership/group information; do not infer SMB from branch size.
Score measures research fit, not permission to send or evidence of buying intent.

## Safe updates and recovery

1. Read current Sheet metadata, headers, IDs, official domains and manual call statuses.
2. Fail closed on schema drift. Quarantine shifted rows without rewriting their cells.
3. Match stable ID, verified legal identity and normalized domain; manually resolve aliases,
   shared domains and parent-group relationships. Do not merge on a fuzzy name alone.
4. Re-read immediately before writing; hold the existing scheduler's single-writer lock.
   `plan_upserts()` preserves manual status, owner, next_contact, comment and suppression.
   The library is not a distributed lock; unknown external writers remain a deployment blocker.
5. Stage a deterministic run key and exact patch in `Ledger`. Apply only explicit ranges.
   Preserve existing S:V manual fields. Avoid blind append on a retry.
6. Read back every changed range and normalize connector numeric/date representations
   before `Ledger.confirm()`. On mismatch leave the run pending and report the error.
7. After interrupted writes, read Sheet IDs first and re-plan only missing/unverified updates.
   Keep historical evidence; never mark a blocked page or network failure as a closed vacancy.
8. Recheck job signals at 7 days and contacts at 30 days; shorten on contradictions.
   Before any approved outreach, check freshness, suppression and jurisdiction/channel rules.

For rate limiting, honor Retry-After; retry transient reads at bounded exponential delays
with jitter, maximum 3 attempts, then report pending work. Do not blindly retry mutations.
Never mark an automation successful when its destination is unavailable.

## Personalization and Soulvo boundary

Approved structure: sourced company observation → possible review burden → EvGrade call
analysis and daily manager summary → one-team pilot → free 40-minute introductory call.
Use sector-appropriate next steps; never claim the target loses sales or handles dozens
of calls without evidence. No fabricated names. Use a generic greeting when role/name
is unknown. `draft()` omits the user-provided 37% case by default because independent
substantiation was not available. Enable only after a usable case source is recorded.
Every draft remains NOT APPROVED. Sending, campaign import and bulk outreach belong to
Soulvo after separate user approval, suppression checks and sender/channel review.

## Existing scheduler deployment checklist

Read its configuration and last successful run; update that same task's prompt to use
the new Sheet rules and this quality layer. Keep its identity and existing destinations.
Target morning Europe/Moscow; quality target up to 20 verified companies per workday,
weekends refresh. The quota must never lower evidence requirements.
Run a dry comparison, then a small batch and readback; verify the next scheduled run.
Until those checks pass, report schedule as NOT DEPLOYED, not operational.

Daily run record: run ID/time, found, source-verified, qualified, inserted, updated,
duplicates skipped, suppressed, archived, unresolved, errors and next checkpoint.
Notify only meaningful changes, completion, failures or user action; do not send status
messages to external recipients. Keep reports in the existing working Sheet/private files.

## Local checks

`python3 -m unittest discover -s tools/evgrade -p 'test_*.py'`

`python3 tools/evgrade/lead_hunter.py PRIVATE_SNAPSHOT.json --output PRIVATE_OUTPUT_DIR`

Snapshot format: connector JSON with `values` array. Audit output contains CRM data;
never commit it. Current audit is structural only. The first 100 rows have no source-date
or contact-provenance columns, so they cannot be promoted automatically to verified.
