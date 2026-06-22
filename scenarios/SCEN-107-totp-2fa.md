---
id: SCEN-107
title: Optional two-factor authentication (authenticator app)
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: enrol a TOTP authenticator; prompt for code at login when enabled; recovery codes for lost device; user can disable after re-authenticating
notes: Recovery-path security is the crux a good SA must address with justified constraints.
---
**Business value:** Account-takeover incidents are costly and erode trust; offering a second factor
reduces successful credential-stuffing attacks and meets enterprise security expectations.

As a security-conscious user, I want to add a second factor to my login using an authenticator app,
so that my account is protected even if my password is compromised.

I should be able to enrol an authenticator app, after which logging in asks for the current code. I
need a way to get back in if I lose my device. I should be able to turn the second factor off again
after confirming my identity.

**Acceptance criteria:**
- Given I have enrolled, when I log in, then I am prompted for a current authenticator code.
- Given I have lost my device, when I use a recovery code, then I can regain access.
- Given I am logged in, when I disable 2FA, then I must re-authenticate before it is removed.

Out of scope: SMS codes and hardware security keys — authenticator-app (TOTP) only for now.
