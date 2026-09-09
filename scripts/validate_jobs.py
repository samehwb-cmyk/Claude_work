#!/usr/bin/env python3
"""Validate data/jobs.json against the pipeline's job schema.

Exits non-zero (and prints every problem found) if the file is invalid.
Intended to run in CI (daily-job-search workflow) and locally before a commit.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "data" / "jobs.json"

REQUIRED_FIELDS = [
    "id", "source", "status", "flag",
    "title", "company", "location",
    "matchScore", "priority",
    "duplicateKey", "dateAdded",
]

VALID_STATUSES = {"scout", "applied", "interview", "offer", "rejected", "closed"}
VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")


def fail(errors: list[str]) -> None:
    print(f"❌ jobs.json failed validation with {len(errors)} problem(s):\n")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)


def main() -> None:
    errors: list[str] = []

    if not JOBS_PATH.exists():
        fail([f"{JOBS_PATH} does not exist"])

    raw = JOBS_PATH.read_text(encoding="utf-8")
    try:
        jobs = json.loads(raw)
    except json.JSONDecodeError as e:
        fail([f"invalid JSON: {e}"])
        return

    if not isinstance(jobs, list):
        fail(["top-level jobs.json value must be a JSON array"])
        return

    seen_ids: dict[str, int] = {}
    seen_dupe_url: dict[tuple[str, str], int] = {}

    for i, job in enumerate(jobs):
        where = f"job[{i}] (id={job.get('id', '?') if isinstance(job, dict) else '?'})"

        if not isinstance(job, dict):
            errors.append(f"{where}: is not a JSON object")
            continue

        for field in REQUIRED_FIELDS:
            if field not in job:
                errors.append(f"{where}: missing required field '{field}'")

        job_id = job.get("id")
        if isinstance(job_id, str) and job_id:
            if job_id in seen_ids:
                errors.append(
                    f"{where}: duplicate id '{job_id}' (also job[{seen_ids[job_id]}])"
                )
            else:
                seen_ids[job_id] = i

        status = job.get("status")
        if status is not None and status not in VALID_STATUSES:
            errors.append(f"{where}: invalid status '{status}' (expected one of {sorted(VALID_STATUSES)})")

        priority = job.get("priority")
        if priority is not None and priority not in VALID_PRIORITIES:
            errors.append(f"{where}: invalid priority '{priority}' (expected one of {sorted(VALID_PRIORITIES)})")

        score = job.get("matchScore")
        if score is not None:
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not (0 <= score <= 100):
                errors.append(f"{where}: matchScore must be a number 0-100, got {score!r}")

        for date_field in ("dateAdded", "date", "postingDate"):
            val = job.get(date_field)
            if val and not DATE_RE.match(str(val)):
                errors.append(f"{where}: {date_field} '{val}' is not YYYY-MM-DD")

        job_url = job.get("jobUrl")
        if job_url and not URL_RE.match(str(job_url)):
            errors.append(f"{where}: jobUrl '{job_url}' does not look like a valid http(s) URL")

        # Privacy: no recruiter emails or phone numbers anywhere in the public feed.
        for field, val in job.items():
            if not isinstance(val, str):
                continue
            if EMAIL_RE.search(val):
                errors.append(f"{where}: field '{field}' appears to contain an email address — not allowed in public feed")
            if PHONE_RE.search(val):
                errors.append(f"{where}: field '{field}' appears to contain a phone number — not allowed in public feed")

        # Duplicate detection: same duplicateKey AND same jobUrl is a hard duplicate.
        dupe_key = job.get("duplicateKey")
        if dupe_key and job_url:
            key = (dupe_key, job_url)
            if key in seen_dupe_url:
                errors.append(
                    f"{where}: looks like a duplicate of job[{seen_dupe_url[key]}] "
                    f"(same duplicateKey and jobUrl)"
                )
            else:
                seen_dupe_url[key] = i

    if errors:
        fail(errors)

    print(f"✅ jobs.json is valid — {len(jobs)} job(s) checked, no problems found.")


if __name__ == "__main__":
    main()
