---
id: SCEN-102
title: Bulk-import records from a CSV with a validation report
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: upload CSV up to 50k rows; per-row validation; downloadable error report; valid rows import even if some rows fail
notes: Atomicity (all-or-nothing vs partial) is left open on purpose — a key clarification.
---
**Business value:** Onboarding large customers currently means manual data entry; self-service bulk
import removes a major friction point and reduces operational load.

As an operations user, I want to import a batch of records from a CSV file and get a clear report of
what succeeded and what failed, so I can fix bad rows and re-import them.

The system should accept files up to 50,000 rows, validate each row against the required schema, and
let me download a report listing every rejected row with the reason. Valid rows should still be
imported even when some rows in the file are invalid.

**Acceptance criteria:**
- Given a 50k-row file, when I upload it, then it is accepted and processed without timing out the UI.
- Given a file with some invalid rows, when import completes, then valid rows are saved and a report lists each rejected row with a reason.
- Given a downloaded error report, then it identifies rows unambiguously (e.g. by line number).

Out of scope: a mapping UI for arbitrary column layouts — assume the fixed template.
