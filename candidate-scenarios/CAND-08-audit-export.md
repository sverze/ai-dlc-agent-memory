---
id: CAND-08
title: Export the audit log for a date range
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: export audit entries for a chosen date range; tamper-evident/complete export; large ranges don't block the UI; access restricted to compliance role
notes: Format (CSV/JSON) and very-large-range handling left open intentionally.
---
As a compliance officer, I want to export the audit log for a chosen date range, so I can provide
evidence during an investigation or audit.

I select a start and end date and receive a complete export of the audit entries in that period. The
export must be trustworthy — it should be evident that nothing was dropped or altered. Pulling a
large range should not freeze the application. Only users in the compliance role may export.

Out of scope: editing or annotating audit entries — they remain immutable.
