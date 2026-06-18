---
id: CAND-01
title: Save a part-completed application and resume later
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: progress saved without submitting; resumable for 30 days then expires; partial data not validated until submit; one in-progress application per user
notes: Storage tech and auth deliberately unspecified — a good SA should clarify or add justified constraints.
---
As an applicant, I want to save my partially-completed application and come back to it later, so
that I don't lose my work if I can't finish in one sitting.

A saved application must be resumable for 30 days, after which it expires. Partial applications must
not trigger the validation or decisioning that a full submission does. A user may have at most one
in-progress application at a time.

Out of scope: changes to the final submission flow, and any reminder emails.
