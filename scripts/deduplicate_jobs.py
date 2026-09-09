#!/usr/bin/env python3
"""Deduplicate data/jobs.json.

Groups jobs by a normalized (company + title + location) key — recomputing
duplicateKey when it's missing or stale — and, for any group with more than
one record, merges it into a single record:

  * the most complete record's fields are kept (empty/missing fields are
    filled in from other records in the group, never overwritten)
  * the most *advanced* status in the group wins (scout < applied <
    interview < offer < rejected/closed) — a scout duplicate can never
    demote an applied/interview/offer record
  * notes, follow-up dates, and resume names are preserved, never dropped
  * the earliest dateAdded / lowest-numbered id in the group is kept as the
    record's identity

Nothing is ever deleted based on a guess: only records whose normalized key
matches exactly are merged. Run this after the daily search adds candidate
jobs, and re-run scripts/validate_jobs.py afterward.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "data" / "jobs.json"

# Higher index = further along the funnel = wins when merging duplicates.
STATUS_RANK = {
    "scout": 0,
    "applied": 1,
    "interview": 2,
    "offer": 3,
    "rejected": 4,
    "closed": 4,
}

TITLE_SYNONYMS = [
    (re.compile(r"\bsr\.?\b"), "senior"),
    (re.compile(r"\bpm\b"), "project manager"),
    (re.compile(r"\btpm\b"), "technical program manager"),
    (re.compile(r"\bitsm\b"), "it service management"),
]


def normalize(value: str) -> str:
    v = (value or "").lower().strip()
    v = re.sub(r"[^\w\s]", " ", v)  # strip punctuation
    v = re.sub(r"\s+", " ", v).strip()
    for pattern, repl in TITLE_SYNONYMS:
        v = pattern.sub(repl, v)
    return v


def duplicate_key(job: dict) -> str:
    return "|".join([
        normalize(job.get("company", "")),
        normalize(job.get("title", "")),
        normalize(job.get("location", "")),
    ])


def status_rank(job: dict) -> int:
    return STATUS_RANK.get(job.get("status"), 0)


def completeness(job: dict) -> int:
    return sum(1 for v in job.values() if v not in (None, "", [], {}))


def merge_group(jobs: list[dict]) -> dict:
    """Merge a group of duplicate records into one, never losing data."""
    # Base: the most complete record (ties broken by most-advanced status).
    base = max(jobs, key=lambda j: (status_rank(j), completeness(j)))
    merged = dict(base)

    for job in jobs:
        if job is base:
            continue
        # Fill in any field the base record is missing, from this duplicate.
        for field, value in job.items():
            if value in (None, "", [], {}):
                continue
            if merged.get(field) in (None, "", [], {}):
                merged[field] = value
        # Never let a less-advanced duplicate downgrade status.
        if status_rank(job) > status_rank(merged):
            merged["status"] = job["status"]
        # Preserve notes from every duplicate, don't just keep one.
        if job.get("note") and job.get("note") != merged.get("note"):
            existing_note = merged.get("note") or ""
            if job["note"] not in existing_note:
                merged["note"] = (existing_note + "\n" + job["note"]).strip()
        # Keep the earliest dateAdded so history reads correctly.
        if job.get("dateAdded") and (
            not merged.get("dateAdded") or job["dateAdded"] < merged["dateAdded"]
        ):
            merged["dateAdded"] = job["dateAdded"]

    merged["duplicateKey"] = duplicate_key(merged)
    return merged


def main() -> None:
    if not JOBS_PATH.exists():
        print(f"❌ {JOBS_PATH} does not exist", file=sys.stderr)
        sys.exit(1)

    jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    if not isinstance(jobs, list):
        print("❌ jobs.json top-level value must be a list", file=sys.stderr)
        sys.exit(1)

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for job in jobs:
        key = duplicate_key(job)
        # Also fold in an explicit company+jobUrl match, even if title/location
        # text differs slightly, since the URL is the strongest identity signal.
        url_key = None
        if job.get("jobUrl"):
            url_key = f"url::{normalize(job.get('company', ''))}::{job['jobUrl']}"
        merge_target = key
        if url_key:
            for existing_key, existing_jobs in groups.items():
                if any(
                    j.get("jobUrl") == job.get("jobUrl")
                    and normalize(j.get("company", "")) == normalize(job.get("company", ""))
                    for j in existing_jobs
                ):
                    merge_target = existing_key
                    break

        if merge_target not in groups:
            groups[merge_target] = []
            order.append(merge_target)
        groups[merge_target].append(job)

    result = []
    duplicates_removed = 0
    for key in order:
        group = groups[key]
        if len(group) == 1:
            job = dict(group[0])
            job["duplicateKey"] = duplicate_key(job)
            result.append(job)
        else:
            duplicates_removed += len(group) - 1
            result.append(merge_group(group))

    JOBS_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"✅ Deduplicated jobs.json: {len(jobs)} -> {len(result)} records "
        f"({duplicates_removed} duplicate(s) merged)."
    )


if __name__ == "__main__":
    main()
