---
id: SCEN-108
title: Export the audit log for a date range
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: export audit entries for a chosen date range; tamper-evident/complete export; large ranges don't block the UI; access restricted to compliance role
notes: Format (CSV/JSON) and very-large-range handling left open intentionally.
---
**Business value:** Audits and investigations currently require engineering to pull logs ad hoc;
self-service export for compliance removes a recurring engineering interrupt and speeds responses.

As a compliance officer, I want to export the audit log for a chosen date range, so I can provide
evidence during an investigation or audit.

I select a start and end date and receive a complete export of the audit entries in that period. The
export must be trustworthy — it should be evident that nothing was dropped or altered. Pulling a
large range should not freeze the application. Only users in the compliance role may export.

**Acceptance criteria:**
- Given a date range, when I export, then I receive every audit entry in that range and nothing outside it.
- Given a large date range, when I export, then the application stays responsive while it is prepared.
- Given a non-compliance user, when they attempt an export, then it is denied.

Out of scope: editing or annotating audit entries — they remain immutable.
