---
id: CAND-02
title: Bulk-import records from a CSV with a validation report
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: upload CSV up to 50k rows; per-row validation; downloadable error report; valid rows import even if some rows fail
notes: Atomicity (all-or-nothing vs partial) is left open on purpose — a key clarification.
---
As an operations user, I want to import a batch of records from a CSV file and get a clear report of
what succeeded and what failed, so I can fix bad rows and re-import them.

The system should accept files up to 50,000 rows, validate each row against the required schema, and
let me download a report listing every rejected row with the reason. Valid rows should still be
imported even when some rows in the file are invalid.

Out of scope: a mapping UI for arbitrary column layouts — assume the fixed template.
