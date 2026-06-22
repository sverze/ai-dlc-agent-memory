---
id: SCEN-106
title: Soft-delete and restore for records
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: delete hides not destroys; restore within 30 days; deleted records excluded from normal views/search; permanent purge after retention
notes: Cascade behaviour for related records is unspecified — a likely clarification.
---
**Business value:** Accidental deletions currently mean data-recovery tickets and lost work;
reversible deletion cuts support load and user frustration.

As a user, I want deleting a record to be reversible for a while, so that an accidental deletion
doesn't lose data permanently.

A deleted record should disappear from normal views and search but be restorable for 30 days. After
that window it should be permanently removed. Restoring a record should bring it back exactly as it was.

**Acceptance criteria:**
- Given I delete a record, when I view lists or search, then it no longer appears.
- Given a record deleted fewer than 30 days ago, when I restore it, then it returns with its data intact.
- Given a record deleted more than 30 days ago, then it has been permanently purged and cannot be restored.

Out of scope: a full version history / undo for edits — this is about deletion only.
