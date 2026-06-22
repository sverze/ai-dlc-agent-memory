---
id: SCEN-104
title: Let users choose which notifications they receive
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: opt in/out per category; honoured across email and in-app; security/legal notices cannot be opted out of; changes apply immediately
notes: The "mandatory categories" carve-out is the interesting design tension.
---
**Business value:** Notification fatigue drives unsubscribes and lowers engagement with the messages
that matter; granular control improves trust and deliverability.

As a user, I want to control which notifications I get, so that I'm not overwhelmed by messages I
don't care about.

I should be able to turn each category of notification on or off (for example: product updates,
activity summaries, marketing). My choices should apply to both email and in-app notifications.
Certain critical notices — security alerts and legally-required messages — must always be delivered
regardless of my preferences.

**Acceptance criteria:**
- Given I opt out of a category, when an event in that category occurs, then I receive no email or in-app message for it.
- Given a security or legal notice, when it is sent, then I receive it even if I've opted out of everything optional.
- Given I change a preference, then it takes effect for subsequent notifications immediately.

Out of scope: per-message scheduling or digest frequency controls.
