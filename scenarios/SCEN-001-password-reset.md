---
id: SCEN-001
title: Self-service password reset via email
source: illustrative
anonymized: true
author: build-team (ILLUSTRATIVE — replace with an external author for the real gate)
expected_key_requirements: reset initiated via email; reset link expires after 30 minutes; all reset attempts logged for security
notes: Deliberately leaves auth-store and rate-limiting unspecified, so the SA must either clarify or add justified constraints.
---
As a registered user, I want to reset my password via a link sent to my email address so
that I can regain access to my account if I forget my password.

The reset link must expire after 30 minutes. Every password reset attempt — successful or
not — must be recorded so the security team can review them.

Out of scope for this ticket: changing the email provider and any UI redesign of the login page.
