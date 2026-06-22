---
id: SCEN-101
title: Save a part-completed application and resume later
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: progress saved without submitting; resumable for 30 days then expires; partial data not validated until submit; one in-progress application per user
notes: Storage and auth deliberately unspecified — a good SA should clarify or add justified constraints.
---
**Business value:** Applicants frequently abandon long forms when interrupted; letting them save and
resume reduces drop-off and support contacts.

As an applicant, I want to save my partially-completed application and come back to it later, so that
I don't lose my work if I can't finish in one sitting.

A saved application must be resumable for 30 days, after which it expires. Partial applications must
not trigger the validation or decisioning that a full submission does. A user may have at most one
in-progress application at a time.

**Acceptance criteria:**
- Given an in-progress application, when I return within 30 days, then my entered data is restored.
- Given a saved application older than 30 days, when I return, then it has expired and cannot be resumed.
- Given a partial application, then no validation/decisioning is triggered until I submit.

Out of scope: changes to the final submission flow, and any reminder emails.
