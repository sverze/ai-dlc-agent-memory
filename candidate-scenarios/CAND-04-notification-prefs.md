---
id: CAND-04
title: Let users choose which notifications they receive
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: opt in/out per notification category; preferences honoured across email and in-app; security/legal notices cannot be opted out of; changes apply immediately
notes: The "mandatory categories" carve-out is the interesting design tension.
---
As a user, I want to control which notifications I get, so that I'm not overwhelmed by messages I
don't care about.

I should be able to turn each category of notification on or off (for example: product updates,
activity summaries, marketing). My choices should apply to both email and in-app notifications.
Certain critical notices — security alerts and legally-required messages — must always be delivered
regardless of my preferences.

Out of scope: per-message scheduling or digest frequency controls.
