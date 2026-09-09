# Sameh Iskander — Job Pipeline Automation

Automated daily job discovery for Sameh Iskander's IT/PM/Program Management
job search, feeding the **Sameh Iskander — Job Pipeline** Claude Artifact.

## Architecture

```
                 ┌─────────────────────┐
                 │   Daily Scheduler   │  .github/workflows/daily-job-search.yml
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │   Claude Job Agent  │  anthropics/claude-code-action
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │   Job Search/Web    │  LinkedIn, Indeed, Dice, ZipRecruiter, etc.
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Deduplicate + Score │  scripts/deduplicate_jobs.py + prompt scoring model
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │     jobs.json       │  data/jobs.json (committed to this repo)
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │  Claude Artifact    │  Job Pipeline (fetches the raw JSON feed)
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Review → Apply →    │  user-controlled status changes only
                 │ Interview → Offer   │
                 └─────────────────────┘
```

## Repository structure

```
data/
  jobs.json        # the live job feed — always starts new jobs as "scout"
  profile.json      # candidate profile, target roles/locations, scoring weights
prompts/
  daily-job-search.md  # full operating instructions for the daily search agent
scripts/
  validate_jobs.py     # schema/consistency/privacy validation, exits non-zero on failure
  deduplicate_jobs.py  # merges duplicate records without losing status/history
.github/workflows/
  daily-job-search.yml # scheduled + manually-triggerable Claude Code Action
```

## How the daily automation works

1. `daily-job-search.yml` runs once a day (and on-demand via
   **Actions → Daily Job Search → Run workflow**).
2. It checks out the repo and runs `anthropics/claude-code-action@v1` with
   the instructions in `prompts/daily-job-search.md`.
3. The agent reads `data/profile.json` and the existing `data/jobs.json`,
   searches public job boards for new, relevant postings, scores and
   deduplicates them, and appends only genuinely new records with
   `"status": "scout"`.
4. It runs `scripts/validate_jobs.py` and `scripts/deduplicate_jobs.py`
   before finishing.
5. It commits and pushes `data/jobs.json` **only if new jobs were found**.
   No commit is made on a day with nothing new.

The automation **never** changes the status of an existing job (scout →
applied → interview → offer are always user-controlled), never deletes a
record, and never touches any file other than `data/jobs.json`.

## Required GitHub secret

| Secret | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Authenticates `anthropics/claude-code-action` to run the daily search. Add it under **Settings → Secrets and variables → Actions**. |

(`CLAUDE_CODE_OAUTH_TOKEN` is a supported alternative to `ANTHROPIC_API_KEY`
if you prefer a Claude Pro/Max plan token instead of a metered API key — swap
the `anthropic_api_key:` line in the workflow for `claude_code_oauth_token:`
if you use this instead.)

No other secrets are required. Nothing is hard-coded; the workflow reads the
key from `${{ secrets.ANTHROPIC_API_KEY }}` only.

## Running a manual search

Go to the repo's **Actions** tab → **Daily Job Search** → **Run workflow**.
This runs the exact same procedure as the daily schedule, on demand.

## Modifying search criteria

You should never need to edit the workflow YAML or the scripts to change
what the agent looks for. Instead:

- **Target roles, locations, compensation, scoring weights** → edit
  `data/profile.json`.
- **Search strategy, negative filters, schema rules, report format** → edit
  `prompts/daily-job-search.md`.

## Data schema

Each record in `data/jobs.json`:

```json
{
  "id": "LI-YYYYMMDD-001",
  "source": "LinkedIn",
  "status": "scout",
  "flag": false,
  "title": "", "company": "", "location": "", "workType": "",
  "rate": "", "salary": "",
  "date": "", "postingDate": "",
  "jobUrl": "",
  "matchScore": 0, "priority": "P1", "targetRole": "",
  "whyItMatches": "",
  "nextAction": "Review and decide whether to apply",
  "followUp": "", "resume": "", "note": "",
  "duplicateKey": "", "dateAdded": ""
}
```

`matchScore` (0–100) and `priority` (P1 85–100 / P2 75–84 / P3 65–74 / P4
below 65, not normally added) come from the weighted model in
`profile.json` → `matchScoreModel`.

## Status lifecycle

```
SCOUT → APPLIED → INTERVIEW → OFFER      (also: REJECTED, CLOSED)
```

New jobs always enter as `scout`. Only a person (via the Job Pipeline
artifact) moves a job forward in the funnel — the automation never does.

## Duplicate handling

`duplicateKey` is a normalized `company + title + location` (lowercase,
punctuation stripped, common title variants like "Sr." / "Senior"
normalized). A match on `duplicateKey`, or on `company + jobUrl`, is treated
as a duplicate. `scripts/deduplicate_jobs.py`:

- keeps the most complete record in a duplicate group,
- never lets a `scout` duplicate downgrade an `applied`/`interview`/`offer`
  record,
- preserves notes from every duplicate instead of dropping any,
- never silently deletes a record it isn't sure is a true duplicate — two
  different postings at the same company are never collapsed.

## Data privacy

`data/jobs.json` is meant to be publicly fetchable (the Artifact reads it
via a raw GitHub URL), so it must never contain recruiter personal emails,
phone numbers, or any other private/sensitive information —
`scripts/validate_jobs.py` scans every field for email/phone patterns and
fails the build if it finds one.

## Connecting the Job Pipeline Artifact

Point the artifact's remote sync at this repo's raw files on `main`:

```js
const JOB_FEED_URL = "https://raw.githubusercontent.com/samehwb-cmyk/claude_work/main/data/jobs.json";
const PROFILE_URL  = "https://raw.githubusercontent.com/samehwb-cmyk/claude_work/main/data/profile.json";
```

On sync, the artifact should treat every remote record's `status` as a
starting point only — it must never downgrade a local job's status,
overwrite local recruiter notes/follow-up dates/application history, and
new remote jobs not already present locally should be added as `scout`.

## Troubleshooting

- **Workflow fails with an authentication error** — check that
  `ANTHROPIC_API_KEY` is set under **Settings → Secrets and variables →
  Actions** and hasn't expired.
- **No commit was made after a run** — check the run's log for the daily
  report; if it says 0 new jobs were found, that's expected — no commit
  means no changes.
- **`validate_jobs.py` fails in CI** — read the printed list of problems;
  it names the exact record and field. Fix `data/jobs.json` by hand or
  re-run `scripts/deduplicate_jobs.py` if the issue is a duplicate.
- **Artifact isn't showing new jobs** — confirm `JOB_FEED_URL` points at
  `main` (not a feature branch), and that the workflow actually committed
  (check the repo's commit history for `jobs: add N new opportunities …`).
