---
id: CAND-03
title: Role-based access control for the admin console
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: roles with distinct permission sets; least-privilege default; role changes take effect without re-login delay; every permission change audited
notes: Number/shape of roles unspecified — SA should propose a model and justify it.
---
As a security administrator, I want to control which admin users can perform which actions, so that
staff only have the access their job requires.

Different admin users need different capabilities — some can only view, some can edit configuration,
some can manage other users. Access should default to the minimum. When an administrator's role
changes, the new permissions should apply promptly. Every change to a user's permissions must be
recorded.

Out of scope: end-user (customer) permissions — this is the internal admin console only.
