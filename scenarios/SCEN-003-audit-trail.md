---
id: SCEN-003
title: Immutable audit trail for admin actions
source: illustrative
anonymized: true
author: build-team (ILLUSTRATIVE — replace with an external author for the real gate)
expected_key_requirements: every admin action recorded; audit entries are immutable; entries retained and queryable by the compliance team
notes: "Immutable" and retention duration invite the SA to add justified architectural constraints (append-only store, retention policy).
---
As a compliance officer, I want every administrative action in the system to be recorded in an
audit trail so that we can demonstrate who changed what, and when, during an investigation.

Audit entries must not be editable or deletable by anyone, including administrators. The
compliance team needs to search the trail by user, action type, and date range.

This applies to admin actions only (e.g. changing roles, disabling accounts, editing
configuration) — ordinary end-user activity is out of scope for this ticket.
