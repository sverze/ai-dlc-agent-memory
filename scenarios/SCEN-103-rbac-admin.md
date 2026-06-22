---
id: SCEN-103
title: Role-based access control for the admin console
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: roles with distinct permission sets; least-privilege default; role changes take effect promptly; every permission change audited
notes: Number/shape of roles unspecified — SA should propose a model and justify it.
---
**Business value:** Over-broad admin access is an audit finding and a breach risk; scoping access to
role reduces both and unblocks the next compliance review.

As a security administrator, I want to control which admin users can perform which actions, so that
staff only have the access their job requires.

Different admin users need different capabilities — some can only view, some can edit configuration,
some can manage other users. Access should default to the minimum. When an administrator's role
changes, the new permissions should apply promptly. Every change to a user's permissions must be recorded.

**Acceptance criteria:**
- Given a user with a view-only role, when they attempt a restricted action, then it is denied.
- Given an admin whose role is changed, when they next act, then the new permissions apply without a long delay.
- Given any permission change, then an audit entry records who changed what, for whom, and when.

Out of scope: end-user (customer) permissions — this is the internal admin console only.
