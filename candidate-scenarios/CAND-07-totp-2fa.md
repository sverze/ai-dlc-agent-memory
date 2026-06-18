---
id: CAND-07
title: Optional two-factor authentication (authenticator app)
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: enrol a TOTP authenticator; prompt for code at login when enabled; recovery codes for lost device; user can disable after re-authenticating
notes: Recovery-path security is the crux a good SA must address with justified constraints.
---
As a security-conscious user, I want to add a second factor to my login using an authenticator app,
so that my account is protected even if my password is compromised.

I should be able to enrol an authenticator app, after which logging in asks for the current code. I
need a way to get back in if I lose my device. I should be able to turn the second factor off again
after confirming my identity.

Out of scope: SMS codes and hardware security keys — authenticator-app (TOTP) only for now.
