---
id: CAND-06
title: Soft-delete and restore for records
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: delete hides not destroys; restore within 30 days; deleted records excluded from normal views/search; permanent purge after retention
notes: Cascade behaviour for related records is unspecified — a likely clarification.
---
As a user, I want deleting a record to be reversible for a while, so that an accidental deletion
doesn't lose data permanently.

A deleted record should disappear from normal views and search but be restorable for 30 days. After
that window it should be permanently removed. Restoring a record should bring it back exactly as it
was.

Out of scope: a full version history / undo for edits — this is about deletion only.
