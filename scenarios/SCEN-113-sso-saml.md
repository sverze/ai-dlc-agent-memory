---
id: SCEN-113
title: Enterprise single sign-on via SAML
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: customers sign in via their own IdP; per-customer IdP configuration; just-in-time user provisioning; deactivation in the IdP blocks access; fall-back path for admins
notes: JIT provisioning + de-provisioning and the admin lockout edge are the meaty parts.
---
**Business value:** SSO is a hard procurement requirement for enterprise deals; without it, larger
contracts stall in security review.

As an enterprise customer's IT admin, I want my users to sign in with our existing identity provider,
so we manage access centrally and our staff don't need separate passwords.

Each enterprise customer should be able to connect their own identity provider. A user signing in for
the first time should be provisioned automatically. When we disable a user in our IdP, their access
to the platform should stop.

**Acceptance criteria:**
- Given a configured IdP, when a user authenticates through it, then they reach the platform signed in.
- Given a first-time SSO user, when they sign in, then an account is provisioned automatically.
- Given a user disabled in the customer's IdP, when they attempt access, then they are blocked.

Out of scope: SCIM directory sync and social logins — SAML SSO only for this ticket.
