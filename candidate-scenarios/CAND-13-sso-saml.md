---
id: CAND-13
title: Enterprise single sign-on via SAML
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: customers sign in via their own IdP; per-customer IdP configuration; just-in-time user provisioning; deactivation in the IdP blocks access; fall-back path for admins
notes: JIT provisioning + de-provisioning and the admin lockout edge are the meaty parts.
---
As an enterprise customer's IT admin, I want my users to sign in with our existing identity
provider, so we manage access centrally and our staff don't need separate passwords.

Each enterprise customer should be able to connect their own identity provider. A user signing in
for the first time should be provisioned automatically. When we disable a user in our IdP, their
access to the platform should stop.

Out of scope: SCIM directory sync and social logins — SAML SSO only for this ticket.
