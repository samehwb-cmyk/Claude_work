# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Automated daily job discovery for Sameh Iskander's IT/PM/Program Management
job search. A scheduled GitHub Action runs a Claude Code agent that searches
job boards, scores and deduplicates results, and appends new opportunities to
`data/jobs.json`. A separate Claude Artifact (the "Sameh Iskander — Job
Pipeline" board, not part of this repo) fetches `data/jobs.json` and
`data/profile.json` as raw files and is where the human tracks/advances jobs
through the funnel.

## Commands

```bash
python3 scripts/validate_jobs.py      # validate data/jobs.json schema/privacy; exits non-zero on failure
python3 scripts/deduplicate_jobs.py   # merge duplicate records in-place, in-order
```

Always run `validate_jobs.py` before and after `deduplicate_jobs.py` when
touching `data/jobs.json` by hand. There is no test suite, linter, or build
step — these two scripts are the only checks in this repo, and both operate
directly on `data/jobs.json` (path resolved relative to the script, not cwd).

## Architecture

```
.github/workflows/daily-job-search.yml   # cron (11:00 UTC daily) + manual dispatch
        → anthropics/claude-code-action@v1, driven by prompts/daily-job-search.md
        → reads data/profile.json + data/jobs.json
        → searches LinkedIn/Indeed/Dice/Built In/ZipRecruiter/company sites via WebSearch/WebFetch
        → scores + dedupes candidates, appends "scout" records to data/jobs.json
        → scripts/validate_jobs.py, scripts/deduplicate_jobs.py
        → commits data/jobs.json only if it changed (no commit on a zero-new-jobs day)
```

`prompts/daily-job-search.md` is the actual operating contract for the daily
agent — not just a prompt but the source of truth for scoring rules,
negative filters, dedup logic, record shape, and hard limits. The workflow's
inline `prompt:` is a thin pointer to it. When changing search behavior,
scoring, or output schema, edit `prompts/daily-job-search.md` and/or
`data/profile.json` — not the workflow YAML.

**Two files never change together automatically:** the daily agent is
scoped to touch only `data/jobs.json` (enforced by the workflow prompt and
by `--allowedTools`), and it never edits an existing record's `status` —
only a human moving jobs through the pipeline in the Artifact does that. Any
change that has the agent editing other files or existing statuses is a
scope violation of the design, not a bug to silently "fix" in the script.

**`data/profile.json` vs `prompts/daily-job-search.md`:** `profile.json` is
structured data (target roles, locations, compensation, the weighted
`matchScoreModel`, priority bands) that the agent reads at runtime; the
prompt file is the procedural instructions that reference it. If they ever
conflict, `profile.json` wins (stated explicitly in the prompt file).

**Duplicate detection** has two independent implementations that must stay
in sync: the agent's own reasoning in `prompts/daily-job-search.md` step 4
(normalized `company+title+location`, or `company+jobUrl`), and the
programmatic pass in `scripts/deduplicate_jobs.py` (`normalize()` /
`duplicate_key()`). `deduplicate_jobs.py` additionally ranks by
`STATUS_RANK` so a `scout` duplicate can never demote an
`applied`/`interview`/`offer` record, and merges rather than drops fields
across a duplicate group (see the module docstring for the merge rules).

**`data/jobs.json` is a public artifact** — it's fetched by raw GitHub URL
from the Claude Artifact, so it must never contain recruiter emails/phones
or other private data. `scripts/validate_jobs.py` enforces this (and schema
shape, valid `status`/`priority` enums, date formats, id/duplicate
uniqueness) and is meant to fail CI loudly rather than let bad data commit.

**`linkedin_scraper.py`** (repo root) is a standalone, manual Playwright
scraper — it is *not* wired into the daily workflow, which instead relies on
the Claude agent's own WebSearch/WebFetch. Its output
(`raw_extracted_jobs.json`) is git-ignored. Treat it as a separate, optional
tool, not part of the automated pipeline described above.

## Data schema (`data/jobs.json`)

Each record:

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

Status lifecycle: `scout → applied → interview → offer` (also `rejected`,
`closed`). Only a human advances status; the automation only ever appends
new `scout` records.

## Required secret

`ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN` as an alternative — swap
the corresponding line in `daily-job-search.yml`) must be set under repo
Settings → Secrets and variables → Actions for the daily workflow to run.
